"""Unit tests for the SciPy HiGHS LP optimizer and greedy fallback."""

import pytest
from app.optimizer import (
    build_directive_constraints,
    compute_effective_solar,
    greedy_energy_scheduler,
    solve_energy_optimization,
)
from app.schemas import BatteryInput, DirectiveInterpretation, HourInput, HourPlan


@pytest.fixture
def standard_battery() -> BatteryInput:
    return BatteryInput(
        capacity_kwh=500.0,
        initial_energy_kwh=200.0,
        minimum_energy_kwh=50.0,
        max_charge_kwh_per_hour=100.0,
        max_discharge_kwh_per_hour=100.0,
    )


@pytest.fixture
def standard_24h_scenario() -> list[HourInput]:
    hours = []
    for h in range(24):
        # Day hours 8-17 have solar
        solar = 120.0 if 8 <= h <= 16 else 0.0
        # Peak tariff 17-21 (15 BDT), Off-peak 0-6 (6 BDT), Regular (9 BDT)
        if 17 <= h <= 21:
            tariff = 15.0
        elif 0 <= h <= 6:
            tariff = 6.0
        else:
            tariff = 9.0
        demand = 150.0 + (30.0 if 10 <= h <= 18 else 0.0)
        hours.append(HourInput(hour=h, demand_kwh=demand, solar_kwh=solar, tariff_bdt_per_kwh=tariff))
    return hours


def test_base_optimization_satisfies_all_laws(standard_24h_scenario, standard_battery):
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    assert len(plan) == 24

    for h, p in enumerate(plan):
        hour_in = standard_24h_scenario[h]
        # Energy balance
        ch = p.battery_kwh if p.battery_action == "charge" else 0.0
        dis = p.battery_kwh if p.battery_action == "discharge" else 0.0
        balance = (p.grid_kwh + p.solar_used_kwh + dis) - (hour_in.demand_kwh + ch)
        assert abs(balance) < 0.05, f"Hour {h} balance error: {balance}"

        # Solar constraint
        assert p.solar_used_kwh <= hour_in.solar_kwh + 0.01

        # Battery bounds
        assert p.battery_energy_after_kwh >= standard_battery.minimum_energy_kwh - 0.01
        assert p.battery_energy_after_kwh <= standard_battery.capacity_kwh + 0.01

        # Battery idle rule
        if p.battery_action == "idle":
            assert p.battery_kwh == 0.0

    # End-of-day battery neutrality
    assert abs(plan[23].battery_energy_after_kwh - standard_battery.initial_energy_kwh) < 0.05


def test_solar_reduction_directive(standard_24h_scenario, standard_battery):
    directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="solar_reduction",
        structured_adjustment={"hours": [12, 13], "factor": 0.2},
    )
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[directive])
    for h in [12, 13]:
        max_allowed_solar = standard_24h_scenario[h].solar_kwh * 0.2
        assert plan[h].solar_used_kwh <= max_allowed_solar + 0.01


def test_no_charge_window_directive(standard_24h_scenario, standard_battery):
    directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="no_charge_window",
        structured_adjustment={"hours": [2, 3, 4]},
    )
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[directive])
    for h in [2, 3, 4]:
        assert plan[h].battery_action != "charge"


def test_no_discharge_window_directive(standard_24h_scenario, standard_battery):
    directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="no_discharge_window",
        structured_adjustment={"hours": [18, 19]},
    )
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[directive])
    for h in [18, 19]:
        assert plan[h].battery_action != "discharge"


def test_minimum_battery_reserve_directive(standard_24h_scenario, standard_battery):
    directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="minimum_battery_reserve",
        structured_adjustment={"hours": [17, 18, 19], "minimum_energy_kwh": 250.0},
    )
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[directive])
    for h in [17, 18, 19]:
        assert plan[h].battery_energy_after_kwh >= 250.0 - 0.05


def test_max_grid_window_directive(standard_24h_scenario, standard_battery):
    directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="max_grid_window",
        structured_adjustment={"hours": [10, 11], "max_grid_kwh": 60.0},
    )
    plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[directive])
    for h in [10, 11]:
        assert plan[h].grid_kwh <= 60.0 + 0.01


def test_greedy_fallback_scheduler(standard_24h_scenario, standard_battery):
    eff_solar = compute_effective_solar(standard_24h_scenario, [])
    min_res, no_ch, no_dis, grid_caps = build_directive_constraints(standard_battery, [])
    fallback_plan = greedy_energy_scheduler(
        standard_24h_scenario, standard_battery, eff_solar, min_res, no_ch, no_dis, grid_caps
    )
    assert len(fallback_plan) == 24
    assert fallback_plan[23].battery_energy_after_kwh == standard_battery.initial_energy_kwh
    for h, p in enumerate(fallback_plan):
        assert p.grid_kwh >= 0.0
        assert p.solar_used_kwh <= standard_24h_scenario[h].solar_kwh
