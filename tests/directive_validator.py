"""
Directive interpretation validation
Validates that directive_interpretation has correct type/hours/values per note
"""

from typing import List, Dict, Any, Tuple, Set

VALID_DIRECTIVE_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}

VALID_BATTERY_ACTIONS = {"charge", "discharge", "idle"}


def validate_directive_types(directives: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Validate that all directive_type values are valid
    
    Args:
        directives: List of DirectiveInterpretation dicts
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    for i, directive in enumerate(directives):
        directive_type = directive.get("directive_type")
        
        if directive_type not in VALID_DIRECTIVE_TYPES:
            errors.append(
                f"Directive {i} (note_index={directive.get('note_index')}): "
                f"Invalid directive_type '{directive_type}'. "
                f"Must be one of {VALID_DIRECTIVE_TYPES}"
            )
    
    return len(errors) == 0, errors


def validate_note_coverage(directives: List[Dict], num_notes: int) -> Tuple[bool, List[str]]:
    """
    Validate that every note is covered exactly once with no gaps or duplicates
    
    Args:
        directives: List of DirectiveInterpretation dicts
        num_notes: Number of operator notes in the input
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    note_indices = [d.get("note_index") for d in directives]
    
    # Check for duplicates
    if len(note_indices) != len(set(note_indices)):
        duplicates = [idx for idx in note_indices if note_indices.count(idx) > 1]
        errors.append(f"Duplicate note_index values: {set(duplicates)}")
    
    # Check for gaps and extra indices
    expected_indices = set(range(num_notes))
    actual_indices = set(note_indices)
    
    missing = expected_indices - actual_indices
    extra = actual_indices - expected_indices
    
    if missing:
        errors.append(f"Missing note_index values: {sorted(missing)}")
    
    if extra:
        errors.append(f"Extra/invalid note_index values: {sorted(extra)}")
    
    return len(errors) == 0, errors


def validate_applies_field(directives: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Validate applies field logic:
    - applies=false only allowed with no_op
    - all other directive_types must have applies=true
    
    Args:
        directives: List of DirectiveInterpretation dicts
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    for i, directive in enumerate(directives):
        directive_type = directive.get("directive_type")
        applies = directive.get("applies")
        note_index = directive.get("note_index")
        
        if directive_type == "no_op":
            # no_op can have applies=true or false
            pass
        else:
            # All other types must have applies=true
            if applies is not True:
                errors.append(
                    f"Directive {i} (note_index={note_index}, type={directive_type}): "
                    f"Non-no_op directive must have applies=true, got {applies}"
                )
    
    return len(errors) == 0, errors


def validate_hours_array(hours: List[int], directive_type: str, note_index: int) -> Tuple[bool, List[str]]:
    """
    Validate hours array: unique, in range 0-23, ascending
    
    Args:
        hours: List of hour integers
        directive_type: Type of directive
        note_index: Note index for error messages
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    if not hours:
        # Empty hours array might be valid for no_op
        if directive_type != "no_op":
            errors.append(f"Note {note_index} ({directive_type}): Hours array is empty")
        return len(errors) == 0, errors
    
    # Check for duplicates
    if len(hours) != len(set(hours)):
        duplicates = [h for h in hours if hours.count(h) > 1]
        errors.append(f"Note {note_index} ({directive_type}): Duplicate hours: {set(duplicates)}")
    
    # Check range
    for h in hours:
        if not isinstance(h, int) or h < 0 or h > 23:
            errors.append(f"Note {note_index} ({directive_type}): Invalid hour value: {h} (must be 0-23)")
    
    # Check ascending order
    if hours != sorted(hours):
        errors.append(f"Note {note_index} ({directive_type}): Hours not in ascending order: {hours}")
    
    return len(errors) == 0, errors


def validate_solar_reduction(directive: Dict) -> Tuple[bool, List[str]]:
    """
    Validate solar_reduction structured_adjustment
    Must have: factor (0 to 1), hours array
    
    Args:
        directive: DirectiveInterpretation dict
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    adjustment = directive.get("structured_adjustment", {})
    
    if not adjustment:
        errors.append(f"Note {note_index} (solar_reduction): Missing structured_adjustment")
        return False, errors
    
    # Check factor
    factor = adjustment.get("factor")
    if factor is None:
        errors.append(f"Note {note_index} (solar_reduction): Missing 'factor' in structured_adjustment")
    elif not isinstance(factor, (int, float)) or factor < 0 or factor > 1:
        errors.append(
            f"Note {note_index} (solar_reduction): "
            f"factor must be between 0 and 1, got {factor}"
        )
    
    # Check hours
    hours = adjustment.get("hours", [])
    valid, hour_errors = validate_hours_array(hours, "solar_reduction", note_index)
    errors.extend(hour_errors)
    
    return len(errors) == 0, errors


def validate_minimum_battery_reserve(directive: Dict, battery_capacity: float) -> Tuple[bool, List[str]]:
    """
    Validate minimum_battery_reserve structured_adjustment
    Must have: reserve_kwh (0 to capacity), hours array
    
    Args:
        directive: DirectiveInterpretation dict
        battery_capacity: Battery capacity from test case
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    adjustment = directive.get("structured_adjustment", {})
    
    if not adjustment:
        errors.append(f"Note {note_index} (minimum_battery_reserve): Missing structured_adjustment")
        return False, errors
    
    # Check minimum_energy_kwh (or legacy reserve_kwh)
    reserve = adjustment.get("minimum_energy_kwh", adjustment.get("reserve_kwh"))
    if reserve is None:
        errors.append(f"Note {note_index} (minimum_battery_reserve): Missing 'minimum_energy_kwh'")
    elif not isinstance(reserve, (int, float)) or reserve < 0:
        errors.append(f"Note {note_index} (minimum_battery_reserve): minimum_energy_kwh must be >= 0, got {reserve}")
    elif reserve > battery_capacity:
        errors.append(
            f"Note {note_index} (minimum_battery_reserve): "
            f"minimum_energy_kwh ({reserve}) exceeds battery capacity ({battery_capacity})"
        )
    
    # Check hours
    hours = adjustment.get("hours", [])
    valid, hour_errors = validate_hours_array(hours, "minimum_battery_reserve", note_index)
    errors.extend(hour_errors)
    
    return len(errors) == 0, errors


def validate_no_charge_window(directive: Dict) -> Tuple[bool, List[str]]:
    """
    Validate no_charge_window structured_adjustment
    Must have: hours array
    
    Args:
        directive: DirectiveInterpretation dict
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    adjustment = directive.get("structured_adjustment", {})
    
    if not adjustment:
        errors.append(f"Note {note_index} (no_charge_window): Missing structured_adjustment")
        return False, errors
    
    # Check hours
    hours = adjustment.get("hours", [])
    valid, hour_errors = validate_hours_array(hours, "no_charge_window", note_index)
    errors.extend(hour_errors)
    
    return len(errors) == 0, errors


def validate_no_discharge_window(directive: Dict) -> Tuple[bool, List[str]]:
    """
    Validate no_discharge_window structured_adjustment
    Must have: hours array
    
    Args:
        directive: DirectiveInterpretation dict
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    adjustment = directive.get("structured_adjustment", {})
    
    if not adjustment:
        errors.append(f"Note {note_index} (no_discharge_window): Missing structured_adjustment")
        return False, errors
    
    # Check hours
    hours = adjustment.get("hours", [])
    valid, hour_errors = validate_hours_array(hours, "no_discharge_window", note_index)
    errors.extend(hour_errors)
    
    return len(errors) == 0, errors


def validate_max_grid_window(directive: Dict) -> Tuple[bool, List[str]]:
    """
    Validate max_grid_window structured_adjustment
    Must have: max_grid_kwh (>= 0), hours array
    
    Args:
        directive: DirectiveInterpretation dict
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    adjustment = directive.get("structured_adjustment", {})
    
    if not adjustment:
        errors.append(f"Note {note_index} (max_grid_window): Missing structured_adjustment")
        return False, errors
    
    # Check max_grid_kwh
    max_grid = adjustment.get("max_grid_kwh")
    if max_grid is None:
        errors.append(f"Note {note_index} (max_grid_window): Missing 'max_grid_kwh'")
    elif not isinstance(max_grid, (int, float)) or max_grid < 0:
        errors.append(f"Note {note_index} (max_grid_window): max_grid_kwh must be >= 0, got {max_grid}")
    
    # Check hours
    hours = adjustment.get("hours", [])
    valid, hour_errors = validate_hours_array(hours, "max_grid_window", note_index)
    errors.extend(hour_errors)
    
    return len(errors) == 0, errors


def validate_no_op(directive: Dict) -> Tuple[bool, List[str]]:
    """
    Validate no_op directive
    Should typically have applies=false and minimal/no structured_adjustment
    
    Args:
        directive: DirectiveInterpretation dict
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    note_index = directive.get("note_index")
    
    # no_op doesn't require specific validation, but we can check consistency
    applies = directive.get("applies")
    adjustment = directive.get("structured_adjustment")
    
    # If no_op has structured_adjustment with actual data, that's suspicious
    if adjustment and any(adjustment.values()):
        errors.append(
            f"Note {note_index} (no_op): "
            f"Has non-null structured_adjustment {adjustment} but marked as no_op"
        )
    
    return len(errors) == 0, errors


def validate_directive_structured_adjustments(
    directives: List[Dict],
    battery_capacity: float
) -> Tuple[bool, List[str]]:
    """
    Validate structured_adjustment for each directive based on its type
    
    Args:
        directives: List of DirectiveInterpretation dicts
        battery_capacity: Battery capacity from test case
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    for directive in directives:
        directive_type = directive.get("directive_type")
        
        if directive_type == "solar_reduction":
            valid, directive_errors = validate_solar_reduction(directive)
        elif directive_type == "minimum_battery_reserve":
            valid, directive_errors = validate_minimum_battery_reserve(directive, battery_capacity)
        elif directive_type == "no_charge_window":
            valid, directive_errors = validate_no_charge_window(directive)
        elif directive_type == "no_discharge_window":
            valid, directive_errors = validate_no_discharge_window(directive)
        elif directive_type == "max_grid_window":
            valid, directive_errors = validate_max_grid_window(directive)
        elif directive_type == "no_op":
            valid, directive_errors = validate_no_op(directive)
        else:
            # Unknown directive type (should be caught by validate_directive_types)
            continue
        
        errors.extend(directive_errors)
    
    return len(errors) == 0, errors


def validate_directive_enforcement(
    directives: List[Dict],
    hourly_plan: List[Dict],
    hours_data: List[Dict],
    tolerance: float = 0.01
) -> Tuple[bool, List[str]]:
    """
    Validate that directives are actually enforced in the hourly_plan
    
    Args:
        directives: List of DirectiveInterpretation dicts
        hourly_plan: List of HourPlan dicts from API response
        hours_data: List of hour input data
        tolerance: Floating point comparison tolerance
        
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Create hour plan lookup
    hour_plan_map = {h["hour"]: h for h in hourly_plan}
    solar_map = {h["hour"]: h.get("solar_kwh", h.get("solar_available_kwh", 0.0)) for h in hours_data}
    
    for directive in directives:
        directive_type = directive.get("directive_type")
        applies = directive.get("applies")
        adjustment = directive.get("structured_adjustment", {})
        note_index = directive.get("note_index")
        
        if not applies or directive_type == "no_op":
            continue
        
        hours = adjustment.get("hours", [])
        
        # Check each hour in the directive
        for hour in hours:
            if hour not in hour_plan_map:
                errors.append(f"Note {note_index}: Hour {hour} not found in hourly_plan")
                continue
            
            hour_plan = hour_plan_map[hour]
            
            if directive_type == "solar_reduction":
                # Check that solar_used is reduced by the factor
                factor = adjustment.get("factor", 1.0)
                expected_max_solar = solar_map.get(hour, 0) * factor
                actual_solar = hour_plan["solar_used_kwh"]
                
                # Solar used should not exceed reduced amount
                if actual_solar > expected_max_solar + tolerance:
                    errors.append(
                        f"Note {note_index} (solar_reduction): Hour {hour}: "
                        f"Solar used ({actual_solar:.2f}) exceeds reduced cap ({expected_max_solar:.2f})"
                    )
            
            elif directive_type == "no_charge_window":
                # Check that battery is not charging
                if hour_plan["battery_action"] == "charge" and hour_plan["battery_kwh"] > tolerance:
                    errors.append(
                        f"Note {note_index} (no_charge_window): Hour {hour}: "
                        f"Battery is charging ({hour_plan['battery_kwh']:.2f} kWh) but shouldn't"
                    )
            
            elif directive_type == "no_discharge_window":
                # Check that battery is not discharging
                if hour_plan["battery_action"] == "discharge" and hour_plan["battery_kwh"] > tolerance:
                    errors.append(
                        f"Note {note_index} (no_discharge_window): Hour {hour}: "
                        f"Battery is discharging ({hour_plan['battery_kwh']:.2f} kWh) but shouldn't"
                    )
            
            elif directive_type == "max_grid_window":
                # Check that grid usage doesn't exceed limit
                max_grid = adjustment.get("max_grid_kwh", float('inf'))
                actual_grid = hour_plan["grid_kwh"]
                
                if actual_grid > max_grid + tolerance:
                    errors.append(
                        f"Note {note_index} (max_grid_window): Hour {hour}: "
                        f"Grid usage ({actual_grid:.2f}) exceeds limit ({max_grid:.2f})"
                    )
            
            elif directive_type == "minimum_battery_reserve":
                # Check that battery energy stays above reserve
                reserve = adjustment.get("minimum_energy_kwh", adjustment.get("reserve_kwh", 0))
                actual_energy = hour_plan["battery_energy_after_kwh"]
                
                if actual_energy < reserve - tolerance:
                    errors.append(
                        f"Note {note_index} (minimum_battery_reserve): Hour {hour}: "
                        f"Battery energy ({actual_energy:.2f}) below reserve ({reserve:.2f})"
                    )
    
    return len(errors) == 0, errors


def validate_all_directives(
    directives: List[Dict],
    test_case: Dict,
    hourly_plan: List[Dict],
    tolerance: float = 0.01
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run all directive validation checks
    
    Args:
        directives: List of DirectiveInterpretation dicts from response
        test_case: Test case input data
        hourly_plan: List of HourPlan dicts from response
        tolerance: Floating point comparison tolerance
        
    Returns:
        (all_valid, detailed_results_dict)
    """
    results = {
        "valid": True,
        "checks": {}
    }
    
    num_notes = len(test_case["operator_notes"])
    battery_capacity = test_case["battery"]["capacity_kwh"]
    hours_data = test_case["hours"]
    
    # 1. Validate directive types
    valid, errors = validate_directive_types(directives)
    results["checks"]["directive_types"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 2. Validate note coverage
    valid, errors = validate_note_coverage(directives, num_notes)
    results["checks"]["note_coverage"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 3. Validate applies field
    valid, errors = validate_applies_field(directives)
    results["checks"]["applies_field"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 4. Validate structured adjustments
    valid, errors = validate_directive_structured_adjustments(directives, battery_capacity)
    results["checks"]["structured_adjustments"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    # 5. Validate directive enforcement in hourly_plan
    valid, errors = validate_directive_enforcement(directives, hourly_plan, hours_data, tolerance)
    results["checks"]["directive_enforcement"] = {"valid": valid, "errors": errors}
    if not valid:
        results["valid"] = False
    
    return results["valid"], results
