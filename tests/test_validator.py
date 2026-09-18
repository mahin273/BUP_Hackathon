"""Unit tests for the independent replay validator and physics recheck engine."""

import pytest
from app.optimizer import solve_energy_optimization
from app.schemas import BatteryInput, DirectiveInterpretation, HourInput, HourPlan
from app.validator import (
    recalculate_totals,
    round_and_balance_plan,
    validate_and_recompute_plan,
    validate_schedule,
)


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
        solar = 100.0 if 9 <= h <= 15 else 0.0
        tariff = 12.0 if 17 <= h <= 21 else 7.0
        demand = 160.0
        hours.append(HourInput(hour=h, demand_kwh=demand, solar_kwh=solar, tariff_bdt_per_kwh=tariff))
    return hours


def test_valid_plan_passes_replay(standard_24h_scenario, standard_battery):
    raw_plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    balanced = round_and_balance_plan(raw_plan, standard_24h_scenario)
    is_valid, errors = validate_schedule(balanced, standard_24h_scenario, standard_battery, directives=[])
    assert is_valid is True, f"Validation errors: {errors}"
    assert len(errors) == 0


def test_detect_energy_balance_violation(standard_24h_scenario, standard_battery):
    raw_plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    # Corrupt hour 4 grid
    corrupted = [p.model_copy() for p in raw_plan]
    corrupted[4].grid_kwh += 50.0  # Creates balance mismatch

    is_valid, errors = validate_schedule(corrupted, standard_24h_scenario, standard_battery, directives=[])
    assert is_valid is False
    assert any("Energy balance violated" in err for err in errors)


def test_detect_battery_neutrality_violation(standard_24h_scenario, standard_battery):
    raw_plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    corrupted = [p.model_copy() for p in raw_plan]
    corrupted[23].battery_energy_after_kwh = standard_battery.initial_energy_kwh + 100.0

    is_valid, errors = validate_schedule(corrupted, standard_24h_scenario, standard_battery, directives=[])
    assert is_valid is False
    assert any("neutrality violated" in err for err in errors)


def test_detect_solar_excess(standard_24h_scenario, standard_battery):
    raw_plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    corrupted = [p.model_copy() for p in raw_plan]
    corrupted[10].solar_used_kwh = standard_24h_scenario[10].solar_kwh + 50.0

    is_valid, errors = validate_schedule(corrupted, standard_24h_scenario, standard_battery, directives=[])
    assert is_valid is False
    assert any("exceeds effective solar" in err for err in errors)


def test_recalculate_totals_exactness(standard_24h_scenario):
    plan = [
        HourPlan(
            hour=h,
            grid_kwh=10.0,
            solar_used_kwh=0.0,
            battery_action="idle",
            battery_kwh=0.0,
            battery_energy_after_kwh=200.0,
        )
        for h in range(24)
    ]
    total_grid, total_cost, peak_grid = recalculate_totals(plan, standard_24h_scenario)
    assert total_grid == 240.0
    assert peak_grid == 10.0
    expected_cost = sum(10.0 * h.tariff_bdt_per_kwh for h in standard_24h_scenario)
    assert total_cost == round(expected_cost, 2)


def test_validate_and_recompute_auto_recovery(standard_24h_scenario, standard_battery):
    raw_plan = solve_energy_optimization(standard_24h_scenario, standard_battery, directives=[])
    corrupted = [p.model_copy() for p in raw_plan]
    corrupted[0].grid_kwh += 200.0  # Breaking balance

    final_plan, total_grid, total_cost, peak_grid = validate_and_recompute_plan(
        corrupted, standard_24h_scenario, standard_battery, directives=[]
    )
    # Replay on the recovered final plan should be valid
    is_valid, errors = validate_schedule(final_plan, standard_24h_scenario, standard_battery, directives=[])
    assert is_valid is True
    assert total_grid > 0.0
    assert total_cost > 0.0
