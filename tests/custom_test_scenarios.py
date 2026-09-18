"""
Custom test scenarios for GridWise API
Testing paraphrased notes and complex multi-directive combinations
These scenarios prepare for hidden test cases with varied wording
"""

# Custom Scenario 1: Paraphrased Solar Reduction
CUSTOM_SOLAR_PARAPHRASE = {
    "scenario_id": "custom_solar_paraphrase_001",
    "operator_notes": [
        "Expect 40% cloud coverage reducing solar panel output during midday hours 11 to 3"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 55.0, "solar_kwh": 35.0, "tariff_bdt_per_kwh": 8.5 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 120.0,
        "initial_energy_kwh": 60.0,
        "max_charge_kwh_per_hour": 24.0,
        "max_discharge_kwh_per_hour": 24.0,
        "minimum_energy_kwh": 12.0
    }
}

# Custom Scenario 2: Paraphrased Battery Reserve
CUSTOM_RESERVE_PARAPHRASE = {
    "scenario_id": "custom_reserve_paraphrase_001",
    "operator_notes": [
        "Maintain battery storage at minimum 85 kWh throughout evening peak from 7 PM until midnight"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 60.0, "solar_kwh": 28.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 10.0 if 19 <= h <= 23 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 150.0,
        "initial_energy_kwh": 75.0,
        "max_charge_kwh_per_hour": 28.0,
        "max_discharge_kwh_per_hour": 28.0,
        "minimum_energy_kwh": 15.0
    }
}

# Custom Scenario 3: Triple Directive - Solar + No Charge + Max Grid
CUSTOM_TRIPLE_COMBO = {
    "scenario_id": "custom_triple_combo_001",
    "operator_notes": [
        "Solar panel efficiency drops to 65% between 2 PM and 5 PM due to partial shading",
        "Battery charging must be disabled during peak tariff hours 6 PM to 10 PM",
        "Grid consumption capped at 35 kWh per hour during morning rush 7 AM to 10 AM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 58.0, "solar_kwh": 30.0, "tariff_bdt_per_kwh": 9.5 if 18 <= h <= 22 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 140.0,
        "initial_energy_kwh": 70.0,
        "max_charge_kwh_per_hour": 26.0,
        "max_discharge_kwh_per_hour": 26.0,
        "minimum_energy_kwh": 14.0
    }
}

# Custom Scenario 4: Reserve + No Discharge + Solar (Complex Overlap)
CUSTOM_COMPLEX_OVERLAP = {
    "scenario_id": "custom_complex_overlap_001",
    "operator_notes": [
        "Keep battery level above 100 kWh from 5 PM to 11 PM for backup",
        "Prevent battery discharge between midnight and 6 AM during off-peak",
        "Solar generation expected at only 55% capacity from 10 AM to 2 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 52.0, "solar_kwh": 32.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 9.0 if 17 <= h <= 23 else 5.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 160.0,
        "initial_energy_kwh": 80.0,
        "max_charge_kwh_per_hour": 30.0,
        "max_discharge_kwh_per_hour": 30.0,
        "minimum_energy_kwh": 16.0
    }
}

# Custom Scenario 5: Paraphrased No Charge Window
CUSTOM_NO_CHARGE_PARAPHRASE = {
    "scenario_id": "custom_no_charge_paraphrase_001",
    "operator_notes": [
        "Avoid charging the battery storage system during high demand period from 4 PM to 9 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 50.0, "solar_kwh": 25.0 if 7 <= h <= 17 else 0.0, "tariff_bdt_per_kwh": 8.0 if 16 <= h <= 21 else 5.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 100.0,
        "initial_energy_kwh": 50.0,
        "max_charge_kwh_per_hour": 20.0,
        "max_discharge_kwh_per_hour": 20.0,
        "minimum_energy_kwh": 10.0
    }
}

# Custom Scenario 6: Extreme Multi-Constraint (Stress Test)
CUSTOM_EXTREME_STRESS = {
    "scenario_id": "custom_extreme_stress_001",
    "operator_notes": [
        "Solar panels operating at 70% due to dust accumulation from noon to 4 PM",
        "Battery must maintain 90 kWh minimum reserve during evening hours 6 PM to midnight",
        "No battery charging permitted between 7 PM and 10 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 65.0, "solar_kwh": 33.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 10.5 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 150.0,
        "initial_energy_kwh": 75.0,
        "max_charge_kwh_per_hour": 28.0,
        "max_discharge_kwh_per_hour": 28.0,
        "minimum_energy_kwh": 15.0
    }
}

# Custom Scenario 7: Ambiguous Wording Test
CUSTOM_AMBIGUOUS_WORDING = {
    "scenario_id": "custom_ambiguous_wording_001",
    "operator_notes": [
        "Weather forecast indicates reduced sunlight availability, expecting around 80% normal output 1 PM through 5 PM",
        "Keep the battery well-charged during peak evening, at least 70 kWh from 6 PM onwards"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 48.0, "solar_kwh": 26.0, "tariff_bdt_per_kwh": 8.5 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 110.0,
        "initial_energy_kwh": 55.0,
        "max_charge_kwh_per_hour": 22.0,
        "max_discharge_kwh_per_hour": 22.0,
        "minimum_energy_kwh": 11.0
    }
}

# Custom Scenario 8: Natural Language Variants
CUSTOM_NATURAL_LANGUAGE = {
    "scenario_id": "custom_natural_language_001",
    "operator_notes": [
        "We need to cap how much we pull from the grid at 28 kWh per hour between 9 AM and 1 PM",
        "Don't let the battery discharge from 2 AM to 7 AM while we do maintenance"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 54.0, "solar_kwh": 29.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 8.0 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 125.0,
        "initial_energy_kwh": 62.5,
        "max_charge_kwh_per_hour": 25.0,
        "max_discharge_kwh_per_hour": 25.0,
        "minimum_energy_kwh": 12.5
    }
}

# Custom Scenario 9: Edge Case - Adjacent Time Windows
CUSTOM_ADJACENT_WINDOWS = {
    "scenario_id": "custom_adjacent_windows_001",
    "operator_notes": [
        "No charging allowed from 5 PM to 8 PM",
        "No discharging allowed from 8 PM to 11 PM",
        "Maintain 80 kWh battery minimum from 11 PM to 2 AM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 56.0, "solar_kwh": 27.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 9.0 if 17 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 130.0,
        "initial_energy_kwh": 65.0,
        "max_charge_kwh_per_hour": 26.0,
        "max_discharge_kwh_per_hour": 26.0,
        "minimum_energy_kwh": 13.0
    }
}

# Custom Scenario 10: Percentage-Based Reserve
CUSTOM_PERCENTAGE_RESERVE = {
    "scenario_id": "custom_percentage_reserve_001",
    "operator_notes": [
        "Battery should stay above 75% capacity during high demand evening 6 PM to 10 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 53.0, "solar_kwh": 28.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 9.5 if 18 <= h <= 22 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 120.0,  # 75% = 90 kWh
        "initial_energy_kwh": 60.0,
        "max_charge_kwh_per_hour": 24.0,
        "max_discharge_kwh_per_hour": 24.0,
        "minimum_energy_kwh": 12.0
    }
}

# Custom Scenario 11: Conflicting Constraints Test (Should be feasible but tight)
CUSTOM_TIGHT_CONSTRAINTS = {
    "scenario_id": "custom_tight_constraints_001",
    "operator_notes": [
        "Solar reduced to 50% from 11 AM to 3 PM",
        "Maximum 40 kWh grid draw per hour from 6 PM to 9 PM",
        "Battery reserve must be at least 65 kWh during those same hours 6 PM to 9 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 62.0, "solar_kwh": 31.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 10.0 if 18 <= h <= 21 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 135.0,
        "initial_energy_kwh": 67.5,
        "max_charge_kwh_per_hour": 27.0,
        "max_discharge_kwh_per_hour": 27.0,
        "minimum_energy_kwh": 13.5
    }
}

# Custom Scenario 12: Varied Time Format Test
CUSTOM_TIME_FORMAT_VARIANTS = {
    "scenario_id": "custom_time_format_001",
    "operator_notes": [
        "Solar at 85% efficiency during afternoon period 1300 to 1700 hours",
        "Grid usage limited to 32 kWh/hr in the morning between 8-11"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 51.0, "solar_kwh": 28.0, "tariff_bdt_per_kwh": 8.0 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 115.0,
        "initial_energy_kwh": 57.5,
        "max_charge_kwh_per_hour": 23.0,
        "max_discharge_kwh_per_hour": 23.0,
        "minimum_energy_kwh": 11.5
    }
}

# Custom Scenario 13: Multiple Distractors + One Real Directive
CUSTOM_DISTRACTOR_HEAVY = {
    "scenario_id": "custom_distractor_heavy_001",
    "operator_notes": [
        "Weather looks stable today with no major issues expected",
        "Keep battery above 70 kWh from 7 PM to 11 PM",
        "All systems operational and functioning normally"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 49.0, "solar_kwh": 26.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 8.5 if 18 <= h <= 22 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 110.0,
        "initial_energy_kwh": 55.0,
        "max_charge_kwh_per_hour": 22.0,
        "max_discharge_kwh_per_hour": 22.0,
        "minimum_energy_kwh": 11.0
    }
}

# Custom Scenario 14: Overnight Constraints
CUSTOM_OVERNIGHT_FOCUS = {
    "scenario_id": "custom_overnight_focus_001",
    "operator_notes": [
        "No battery discharge during overnight hours 10 PM to 5 AM for equipment preservation",
        "Maintain minimum 60 kWh reserve from midnight to 4 AM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 45.0 if h < 6 or h >= 22 else 58.0, "solar_kwh": 28.0 if 7 <= h <= 17 else 0.0, "tariff_bdt_per_kwh": 5.0 if h < 6 or h >= 22 else 7.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 105.0,
        "initial_energy_kwh": 52.5,
        "max_charge_kwh_per_hour": 21.0,
        "max_discharge_kwh_per_hour": 21.0,
        "minimum_energy_kwh": 10.5
    }
}

# Custom Scenario 15: Very Short Time Windows
CUSTOM_SHORT_WINDOWS = {
    "scenario_id": "custom_short_windows_001",
    "operator_notes": [
        "Solar output reduced to 60% just during hour 2 PM to 3 PM due to temporary obstruction",
        "No charging for one hour from 8 PM to 9 PM",
        "Grid limited to 25 kWh during peak hour 7 PM to 8 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 54.0, "solar_kwh": 29.0, "tariff_bdt_per_kwh": 9.0 if h == 19 or h == 20 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 125.0,
        "initial_energy_kwh": 62.5,
        "max_charge_kwh_per_hour": 25.0,
        "max_discharge_kwh_per_hour": 25.0,
        "minimum_energy_kwh": 12.5
    }
}


# Collection of all custom test scenarios
CUSTOM_TEST_SCENARIOS = [
    CUSTOM_SOLAR_PARAPHRASE,
    CUSTOM_RESERVE_PARAPHRASE,
    CUSTOM_TRIPLE_COMBO,
    CUSTOM_COMPLEX_OVERLAP,
    CUSTOM_NO_CHARGE_PARAPHRASE,
    CUSTOM_EXTREME_STRESS,
    CUSTOM_AMBIGUOUS_WORDING,
    CUSTOM_NATURAL_LANGUAGE,
    CUSTOM_ADJACENT_WINDOWS,
    CUSTOM_PERCENTAGE_RESERVE,
    CUSTOM_TIGHT_CONSTRAINTS,
    CUSTOM_TIME_FORMAT_VARIANTS,
    CUSTOM_DISTRACTOR_HEAVY,
    CUSTOM_OVERNIGHT_FOCUS,
    CUSTOM_SHORT_WINDOWS,
]
