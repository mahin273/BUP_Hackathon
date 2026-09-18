"""Independent replay validator and physics recheck engine for GridWise."""

from __future__ import annotations

import logging
from typing import Optional
from app.optimizer import (
    build_directive_constraints,
    compute_effective_solar,
    greedy_energy_scheduler,
)
from app.schemas import (
    BatteryInput,
    DirectiveInterpretation,
    HourInput,
    HourPlan,
)

logger = logging.getLogger(__name__)


def round_and_balance_plan(plan: list[HourPlan], hours: list[HourInput]) -> list[HourPlan]:
    """Rounds hourly plan figures to 2 decimal places and performs micro-adjustments
    on grid import so energy balance holds precisely after rounding."""
    adjusted_plans: list[HourPlan] = []

    for h in range(24):
        p = plan[h]
        inp = hours[h]

        grid = round(float(p.grid_kwh), 2)
        solar = round(float(p.solar_used_kwh), 2)
        act = p.battery_action
        bat_kwh = round(float(p.battery_kwh), 2)
        if act == "idle" or bat_kwh < 1e-4:
            act = "idle"
            bat_kwh = 0.0

        energy_after = round(float(p.battery_energy_after_kwh), 2)

        # Re-check energy balance with rounded numbers
        # grid + solar + discharge = demand + charge
        ch = bat_kwh if act == "charge" else 0.0
        dis = bat_kwh if act == "discharge" else 0.0
        generation_and_discharge = grid + solar + dis
        demand_and_charge = inp.demand_kwh + ch
        diff = round(generation_and_discharge - demand_and_charge, 2)

        # Micro-adjust grid if rounding shifted it by ±0.01 or ±0.02
        if abs(diff) > 0.001 and abs(diff) <= 0.05:
            grid = max(0.0, round(grid - diff, 2))

        adjusted_plans.append(
            HourPlan(
                hour=h,
                grid_kwh=grid,
                solar_used_kwh=solar,
                battery_action=act,
                battery_kwh=bat_kwh,
                battery_energy_after_kwh=energy_after,
            )
        )

    return adjusted_plans


def validate_schedule(
    plan: list[HourPlan],
    hours: list[HourInput],
    battery: BatteryInput,
    directives: list[DirectiveInterpretation],
) -> tuple[bool, list[str]]:
    """Performs an independent audit against physical laws, battery constraints, and directives."""
    errors: list[str] = []

    if len(plan) != 24:
        errors.append(f"Plan must contain exactly 24 hourly entries; found {len(plan)}")
        return False, errors

    effective_solar = compute_effective_solar(hours, directives)
    min_reserves, no_charge_hours, no_discharge_hours, grid_caps = build_directive_constraints(
        battery=battery, directives=directives
    )

    prev_energy = battery.initial_energy_kwh

    for h in range(24):
        p = plan[h]
        inp = hours[h]

        if p.hour != h:
            errors.append(f"Hour mismatch at index {h}: plan hour is {p.hour}")

        # Check non-negative
        if p.grid_kwh < -0.01:
            errors.append(f"Hour {h}: negative grid_kwh ({p.grid_kwh})")
        if p.solar_used_kwh < -0.01:
            errors.append(f"Hour {h}: negative solar_used_kwh ({p.solar_used_kwh})")
        if p.battery_kwh < -0.01:
            errors.append(f"Hour {h}: negative battery_kwh ({p.battery_kwh})")

        # Solar limitation
        if p.solar_used_kwh > effective_solar[h] + 0.02:
            errors.append(
                f"Hour {h}: solar_used_kwh ({p.solar_used_kwh}) exceeds effective solar ({effective_solar[h]:.2f})"
            )

        # Battery action rules
        ch = p.battery_kwh if p.battery_action == "charge" else 0.0
        dis = p.battery_kwh if p.battery_action == "discharge" else 0.0

        if p.battery_action == "idle" and p.battery_kwh > 0.01:
            errors.append(f"Hour {h}: battery_action is idle but battery_kwh is {p.battery_kwh}")

        # Rate limits
        if ch > battery.max_charge_kwh_per_hour + 0.02:
            errors.append(f"Hour {h}: charge ({ch}) exceeds max charge limit ({battery.max_charge_kwh_per_hour})")
        if dis > battery.max_discharge_kwh_per_hour + 0.02:
            errors.append(f"Hour {h}: discharge ({dis}) exceeds max discharge limit ({battery.max_discharge_kwh_per_hour})")

        # Directives compliance
        if h in no_charge_hours and ch > 0.01:
            errors.append(f"Hour {h}: charge ({ch}) in no_charge_window")
        if h in no_discharge_hours and dis > 0.01:
            errors.append(f"Hour {h}: discharge ({dis}) in no_discharge_window")
        if h in grid_caps and p.grid_kwh > grid_caps[h] + 0.02:
            errors.append(f"Hour {h}: grid_kwh ({p.grid_kwh}) exceeds grid cap ({grid_caps[h]})")

        # Hourly Energy Balance: grid + solar + discharge == demand + charge
        left = p.grid_kwh + p.solar_used_kwh + dis
        right = inp.demand_kwh + ch
        if abs(left - right) > 0.05:
            errors.append(f"Hour {h}: Energy balance violated. Generation ({left:.2f}) != Demand ({right:.2f})")

        # State of charge bounds
        if p.battery_energy_after_kwh < min_reserves[h] - 0.05:
            errors.append(
                f"Hour {h}: battery energy ({p.battery_energy_after_kwh}) below reserve minimum ({min_reserves[h]})"
            )
        if p.battery_energy_after_kwh > battery.capacity_kwh + 0.05:
            errors.append(
                f"Hour {h}: battery energy ({p.battery_energy_after_kwh}) exceeds capacity ({battery.capacity_kwh})"
            )

        prev_energy = p.battery_energy_after_kwh

    # End-of-day battery neutrality
    final_energy = plan[23].battery_energy_after_kwh
    if abs(final_energy - battery.initial_energy_kwh) > 0.05:
        errors.append(
            f"End-of-day battery neutrality violated: final ({final_energy}) != initial ({battery.initial_energy_kwh})"
        )

    is_valid = len(errors) == 0
    return is_valid, errors


def recalculate_totals(plan: list[HourPlan], hours: list[HourInput]) -> tuple[float, float, float]:
    """Recalculates aggregate metrics strictly from the final rounded hourly plan entries."""
    total_grid = sum(p.grid_kwh for p in plan)
    total_cost = sum(p.grid_kwh * h.tariff_bdt_per_kwh for p, h in zip(plan, hours))
    peak_grid = max(p.grid_kwh for p in plan) if plan else 0.0

    return (
        round(total_grid, 2),
        round(total_cost, 2),
        round(peak_grid, 2),
    )


def validate_and_recompute_plan(
    plan: list[HourPlan],
    hours: list[HourInput],
    battery: BatteryInput,
    directives: list[DirectiveInterpretation],
) -> tuple[list[HourPlan], float, float, float]:
    """Validates, balances, rounds, and computes totals for the final response.
    
    If the provided plan fails replay checks, falls back to the deterministic
    greedy scheduler to guarantee that a valid plan is always returned.
    """
    balanced_plan = round_and_balance_plan(plan, hours)
    is_valid, errors = validate_schedule(balanced_plan, hours, battery, directives)

    if not is_valid:
        logger.warning("Primary plan failed validation (%d errors). Triggering fallback. Errors: %s", len(errors), errors[:3])
        effective_solar = compute_effective_solar(hours, directives)
        min_reserves, no_charge_hours, no_discharge_hours, grid_caps = build_directive_constraints(
            battery=battery, directives=directives
        )
        fallback = greedy_energy_scheduler(
            hours=hours,
            battery=battery,
            effective_solar=effective_solar,
            min_reserves=min_reserves,
            no_charge_hours=no_charge_hours,
            no_discharge_hours=no_discharge_hours,
            grid_caps=grid_caps,
        )
        balanced_plan = round_and_balance_plan(fallback, hours)

    total_grid, total_cost, peak_grid = recalculate_totals(balanced_plan, hours)
    return balanced_plan, total_grid, total_cost, peak_grid
