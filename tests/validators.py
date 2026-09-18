"""
Core validation functions for GridWise API responses
Validates energy balance, battery constraints, and totals recomputation
"""

from typing import List, Dict, Any, Tuple
import math


class ValidationError(Exception):
    """Custom exception for validation failures"""
    pass


def validate_energy_balance(hourly_plan: List[Dict], hours_data: List[Dict], tolerance: float = 0.01) -> Tuple[bool, List[str]]:
    """
    Validate energy balance for every hour: grid + solar + discharge = demand + charge
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        hours_data: List of hour input data with demand values
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Create demand lookup
    demand_map = {h["hour"]: h["demand_kwh"] for h in hours_data}
    
    for hour_plan in hourly_plan:
        hour = hour_plan["hour"]
        grid = hour_plan["grid_kwh"]
        solar = hour_plan["solar_used_kwh"]
        discharge = hour_plan["battery_kwh"] if hour_plan["battery_action"] == "discharge" else 0.0
        charge = hour_plan["battery_kwh"] if hour_plan["battery_action"] == "charge" else 0.0
        
        demand = demand_map.get(hour, 0.0)
        
        # Balance equation: grid + solar + discharge = demand + charge
        supply = grid + solar + discharge
        consumption = demand + charge
        
        if abs(supply - consumption) > tolerance:
            errors.append(
                f"Hour {hour}: Energy balance violated. "
                f"Supply ({supply:.2f}) != Consumption ({consumption:.2f}). "
                f"Difference: {abs(supply - consumption):.4f} kWh"
            )
    
    return len(errors) == 0, errors


def validate_battery_bounds(
    hourly_plan: List[Dict], 
    battery_config: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Validate battery energy stays within [min_energy_kwh, capacity_kwh] at all times
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        battery_config: Battery configuration with capacity and min_energy
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    capacity = battery_config["capacity_kwh"]
    min_energy = battery_config["min_energy_kwh"]
    
    for hour_plan in hourly_plan:
        hour = hour_plan["hour"]
        energy_after = hour_plan["battery_energy_after_kwh"]
        
        # Check minimum bound
        if energy_after < min_energy - tolerance:
            errors.append(
                f"Hour {hour}: Battery energy ({energy_after:.2f} kWh) below minimum ({min_energy:.2f} kWh). "
                f"Violation: {min_energy - energy_after:.4f} kWh"
            )
        
        # Check maximum bound (capacity)
        if energy_after > capacity + tolerance:
            errors.append(
                f"Hour {hour}: Battery energy ({energy_after:.2f} kWh) exceeds capacity ({capacity:.2f} kWh). "
                f"Violation: {energy_after - capacity:.4f} kWh"
            )
    
    return len(errors) == 0, errors


def validate_battery_rate_limits(
    hourly_plan: List[Dict], 
    battery_config: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Validate charge/discharge rates don't exceed per-hour limits
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        battery_config: Battery configuration with rate limits
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    max_charge = battery_config["max_charge_per_hour"]
    max_discharge = battery_config["max_discharge_per_hour"]
    
    for hour_plan in hourly_plan:
        hour = hour_plan["hour"]
        action = hour_plan["battery_action"]
        battery_kwh = hour_plan["battery_kwh"]
        
        if action == "charge":
            if battery_kwh > max_charge + tolerance:
                errors.append(
                    f"Hour {hour}: Charge rate ({battery_kwh:.2f} kWh) exceeds max ({max_charge:.2f} kWh). "
                    f"Violation: {battery_kwh - max_charge:.4f} kWh"
                )
        elif action == "discharge":
            if battery_kwh > max_discharge + tolerance:
                errors.append(
                    f"Hour {hour}: Discharge rate ({battery_kwh:.2f} kWh) exceeds max ({max_discharge:.2f} kWh). "
                    f"Violation: {battery_kwh - max_discharge:.4f} kWh"
                )
        elif action == "idle":
            # Idle should have battery_kwh = 0 (with tolerance for floating point)
            if abs(battery_kwh) > tolerance:
                errors.append(
                    f"Hour {hour}: Battery action is 'idle' but battery_kwh is {battery_kwh:.4f} (should be 0)"
                )
    
    return len(errors) == 0, errors


def validate_end_of_day_neutrality(
    hourly_plan: List[Dict], 
    battery_config: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Validate that battery energy at end of day (hour 23) equals initial energy
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        battery_config: Battery configuration with initial_energy_kwh
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    initial_energy = battery_config["initial_energy_kwh"]
    
    # Find hour 23 (last hour)
    hour_23 = next((h for h in hourly_plan if h["hour"] == 23), None)
    
    if hour_23 is None:
        errors.append("Hour 23 not found in hourly_plan")
        return False, errors
    
    final_energy = hour_23["battery_energy_after_kwh"]
    
    if abs(final_energy - initial_energy) > tolerance:
        errors.append(
            f"End-of-day neutrality violated: "
            f"Final energy ({final_energy:.2f} kWh) != Initial energy ({initial_energy:.2f} kWh). "
            f"Difference: {abs(final_energy - initial_energy):.4f} kWh"
        )
    
    return len(errors) == 0, errors


def validate_battery_energy_continuity(
    hourly_plan: List[Dict],
    battery_config: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Validate that battery energy transitions are continuous and correct
    energy_after[h] = energy_after[h-1] + charge[h] - discharge[h]
    
    Args:
        hourly_plan: List of HourPlan dicts from API response (must be sorted by hour)
        battery_config: Battery configuration with initial_energy_kwh
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Sort by hour to ensure correct order
    sorted_plan = sorted(hourly_plan, key=lambda x: x["hour"])
    
    initial_energy = battery_config["initial_energy_kwh"]
    
    for i, hour_plan in enumerate(sorted_plan):
        hour = hour_plan["hour"]
        action = hour_plan["battery_action"]
        battery_kwh = hour_plan["battery_kwh"]
        energy_after = hour_plan["battery_energy_after_kwh"]
        
        # Determine energy before this hour
        if i == 0:
            energy_before = initial_energy
        else:
            energy_before = sorted_plan[i-1]["battery_energy_after_kwh"]
        
        # Calculate expected energy after based on action
        if action == "charge":
            expected_energy_after = energy_before + battery_kwh
        elif action == "discharge":
            expected_energy_after = energy_before - battery_kwh
        else:  # idle
            expected_energy_after = energy_before
        
        if abs(energy_after - expected_energy_after) > tolerance:
            errors.append(
                f"Hour {hour}: Battery energy continuity violated. "
                f"Expected {expected_energy_after:.2f} kWh, got {energy_after:.2f} kWh. "
                f"Difference: {abs(energy_after - expected_energy_after):.4f} kWh"
            )
    
    return len(errors) == 0, errors


def recompute_and_validate_totals(
    hourly_plan: List[Dict],
    hours_data: List[Dict],
    response_totals: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Recompute total_grid_kwh, total_cost_bdt, and peak_grid_kwh from hourly_plan
    and compare with values in the response
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        hours_data: List of hour input data with tariff values
        response_totals: Dict with total_grid_kwh, total_cost_bdt, peak_grid_kwh
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Create tariff lookup
    tariff_map = {h["hour"]: h["tariff_bdt_per_kwh"] for h in hours_data}
    
    # Recompute totals
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0
    
    for hour_plan in hourly_plan:
        hour = hour_plan["hour"]
        grid_kwh = hour_plan["grid_kwh"]
        tariff = tariff_map.get(hour, 0.0)
        
        total_grid += grid_kwh
        total_cost += grid_kwh * tariff
        peak_grid = max(peak_grid, grid_kwh)
    
    # Round to 2 decimal places like the API should
    total_grid = round(total_grid, 2)
    total_cost = round(total_cost, 2)
    peak_grid = round(peak_grid, 2)
    
    # Compare with response values
    response_total_grid = response_totals.get("total_grid_kwh", 0.0)
    response_total_cost = response_totals.get("total_cost_bdt", 0.0)
    response_peak_grid = response_totals.get("peak_grid_kwh", 0.0)
    
    if abs(total_grid - response_total_grid) > tolerance:
        errors.append(
            f"total_grid_kwh mismatch: "
            f"Recomputed {total_grid:.2f} kWh != Response {response_total_grid:.2f} kWh. "
            f"Difference: {abs(total_grid - response_total_grid):.4f} kWh"
        )
    
    if abs(total_cost - response_total_cost) > tolerance:
        errors.append(
            f"total_cost_bdt mismatch: "
            f"Recomputed {total_cost:.2f} BDT != Response {response_total_cost:.2f} BDT. "
            f"Difference: {abs(total_cost - response_total_cost):.4f} BDT"
        )
    
    if abs(peak_grid - response_peak_grid) > tolerance:
        errors.append(
            f"peak_grid_kwh mismatch: "
            f"Recomputed {peak_grid:.2f} kWh != Response {response_peak_grid:.2f} kWh. "
            f"Difference: {abs(peak_grid - response_peak_grid):.4f} kWh"
        )
    
    return len(errors) == 0, errors


def validate_hourly_plan_completeness(hourly_plan: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Validate that hourly_plan contains exactly 24 hours (0-23) with no gaps or duplicates
    
    Args:
        hourly_plan: List of HourPlan dicts from API response
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check count
    if len(hourly_plan) != 24:
        errors.append(f"Expected 24 hours in plan, got {len(hourly_plan)}")
    
    # Extract hours
    hours = [h["hour"] for h in hourly_plan]
    
    # Check for duplicates
    if len(hours) != len(set(hours)):
        duplicates = [h for h in hours if hours.count(h) > 1]
        errors.append(f"Duplicate hours found: {set(duplicates)}")
    
    # Check for gaps
    expected_hours = set(range(24))
    actual_hours = set(hours)
    missing = expected_hours - actual_hours
    extra = actual_hours - expected_hours
    
    if missing:
        errors.append(f"Missing hours: {sorted(missing)}")
    
    if extra:
        errors.append(f"Extra/invalid hours: {sorted(extra)}")
    
    # Check ascending order
    if hours != sorted(hours):
        errors.append("Hours are not in ascending order")
    
    return len(errors) == 0, errors


def validate_all_constraints(
    response: Dict,
    test_case: Dict,
    tolerance: float = 0.01
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run all validation checks on a response
    
    Args:
        response: Complete API response
        test_case: Test case input data
        tolerance: Floating point comparison tolerance
        
    Returns:
        (all_valid, detailed_results_dict)
    """
    results = {
        "valid": True,
        "checks": {}
    }
    
    hourly_plan = response.get("hourly_plan", [])
    hours_data = test_case["hours"]
    battery_config = test_case["battery"]
    
    # 1. Check hourly plan completeness
    valid, errors = validate_hourly_plan_completeness(hourly_plan)
    results["checks"]["hourly_plan_completeness"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 2. Check energy balance per hour
    valid, errors = validate_energy_balance(hourly_plan, hours_data, tolerance)
    results["checks"]["energy_balance"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 3. Check battery bounds
    valid, errors = validate_battery_bounds(hourly_plan, battery_config, tolerance)
    results["checks"]["battery_bounds"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 4. Check battery rate limits
    valid, errors = validate_battery_rate_limits(hourly_plan, battery_config, tolerance)
    results["checks"]["battery_rate_limits"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 5. Check battery energy continuity
    valid, errors = validate_battery_energy_continuity(hourly_plan, battery_config, tolerance)
    results["checks"]["battery_continuity"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 6. Check end-of-day neutrality
    valid, errors = validate_end_of_day_neutrality(hourly_plan, battery_config, tolerance)
    results["checks"]["end_of_day_neutrality"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 7. Recompute and validate totals
    response_totals = {
        "total_grid_kwh": response.get("total_grid_kwh"),
        "total_cost_bdt": response.get("total_cost_bdt"),
        "peak_grid_kwh": response.get("peak_grid_kwh")
    }
    valid, errors = recompute_and_validate_totals(hourly_plan, hours_data, response_totals, tolerance)
    results["checks"]["totals_recomputation"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    return results["valid"], results
