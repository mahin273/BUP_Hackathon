"""
Test data for GridWise optimization API
Contains 10 public test cases covering all directive types
"""

# Test Case 1: Solar Reduction
TEST_CASE_1_SOLAR_REDUCTION = {
    "scenario_id": "test_solar_reduction_001",
    "operator_notes": [
        "Cloud cover expected between 10 AM and 2 PM, reduce solar to 60%"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 50.0, "solar_kwh": 30.0, "tariff_bdt_per_kwh": 8.0 if 18 <= h <= 22 else 5.0}
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

# Test Case 2: Minimum Battery Reserve
TEST_CASE_2_MIN_RESERVE = {
    "scenario_id": "test_min_reserve_001",
    "operator_notes": [
        "Keep battery at least 70% charged during peak hours 6 PM to 10 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 45.0, "solar_kwh": 25.0, "tariff_bdt_per_kwh": 9.0 if 18 <= h <= 22 else 5.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 120.0,
        "initial_energy_kwh": 60.0,
        "max_charge_kwh_per_hour": 25.0,
        "max_discharge_kwh_per_hour": 25.0,
        "minimum_energy_kwh": 12.0
    }
}

# Test Case 3: No Charge Window
TEST_CASE_3_NO_CHARGE = {
    "scenario_id": "test_no_charge_001",
    "operator_notes": [
        "Do not charge battery between 5 PM and 9 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 55.0, "solar_kwh": 35.0, "tariff_bdt_per_kwh": 10.0 if 17 <= h <= 21 else 6.0}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 80.0,
        "initial_energy_kwh": 40.0,
        "max_charge_kwh_per_hour": 15.0,
        "max_discharge_kwh_per_hour": 15.0,
        "minimum_energy_kwh": 8.0
    }
}

# Test Case 4: No Discharge Window
TEST_CASE_4_NO_DISCHARGE = {
    "scenario_id": "test_no_discharge_001",
    "operator_notes": [
        "Battery discharge prohibited from 11 PM to 5 AM for maintenance"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 60.0, "solar_kwh": 20.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 7.0}
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

# Test Case 5: Max Grid Window
TEST_CASE_5_MAX_GRID = {
    "scenario_id": "test_max_grid_001",
    "operator_notes": [
        "Limit grid usage to 30 kWh per hour during 7 AM to 11 AM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 65.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 8.5 if 18 <= h <= 22 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 150.0,
        "initial_energy_kwh": 75.0,
        "max_charge_kwh_per_hour": 30.0,
        "max_discharge_kwh_per_hour": 30.0,
        "minimum_energy_kwh": 15.0
    }
}

# Test Case 6: No-op / Distractor
TEST_CASE_6_NO_OP = {
    "scenario_id": "test_no_op_001",
    "operator_notes": [
        "Weather looks good today, nothing special needed"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 50.0, "solar_kwh": 30.0, "tariff_bdt_per_kwh": 7.5}
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

# Test Case 7: Combined - Solar Reduction + No Charge
TEST_CASE_7_COMBINED_SOLAR_NO_CHARGE = {
    "scenario_id": "test_combined_001",
    "operator_notes": [
        "Solar panels at 70% efficiency from noon to 4 PM due to maintenance",
        "Don't charge battery during peak hours 6 PM to 10 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 52.0, "solar_kwh": 28.0, "tariff_bdt_per_kwh": 9.5 if 18 <= h <= 22 else 6.0}
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

# Test Case 8: Combined - Min Reserve + No Discharge
TEST_CASE_8_COMBINED_RESERVE_NO_DISCHARGE = {
    "scenario_id": "test_combined_002",
    "operator_notes": [
        "Keep battery above 80 kWh during evening hours 6 PM to midnight",
        "No discharge allowed from 1 AM to 6 AM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 48.0, "solar_kwh": 25.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 8.0 if 18 <= h <= 23 else 5.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 130.0,
        "initial_energy_kwh": 65.0,
        "max_charge_kwh_per_hour": 25.0,
        "max_discharge_kwh_per_hour": 25.0,
        "minimum_energy_kwh": 13.0
    }
}

# Test Case 9: Combined - Max Grid + Solar Reduction
TEST_CASE_9_COMBINED_GRID_SOLAR = {
    "scenario_id": "test_combined_003",
    "operator_notes": [
        "Grid draw limited to 25 kWh/hour from 8 AM to noon",
        "Solar output reduced to 50% from 1 PM to 5 PM due to cloud cover"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 58.0, "solar_kwh": 32.0, "tariff_bdt_per_kwh": 9.0 if 18 <= h <= 22 else 6.5}
        for h in range(24)
    ],
    "battery": {
        "capacity_kwh": 140.0,
        "initial_energy_kwh": 70.0,
        "max_charge_kwh_per_hour": 28.0,
        "max_discharge_kwh_per_hour": 28.0,
        "minimum_energy_kwh": 14.0
    }
}

# Test Case 10: All Constraints Combined (Stress Test)
TEST_CASE_10_STRESS = {
    "scenario_id": "test_stress_001",
    "operator_notes": [
        "Solar at 75% from 11 AM to 3 PM",
        "Battery reserve must be at least 90 kWh during peak hours 6 PM to 11 PM",
        "No charging between 7 PM and 9 PM"
    ],
    "hours": [
        {"hour": h, "demand_kwh": 62.0, "solar_kwh": 30.0 if 6 <= h <= 18 else 0.0, "tariff_bdt_per_kwh": 10.0 if 18 <= h <= 22 else 6.0}
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

# Collection of all test cases
PUBLIC_TEST_CASES = [
    TEST_CASE_1_SOLAR_REDUCTION,
    TEST_CASE_2_MIN_RESERVE,
    TEST_CASE_3_NO_CHARGE,
    TEST_CASE_4_NO_DISCHARGE,
    TEST_CASE_5_MAX_GRID,
    TEST_CASE_6_NO_OP,
    TEST_CASE_7_COMBINED_SOLAR_NO_CHARGE,
    TEST_CASE_8_COMBINED_RESERVE_NO_DISCHARGE,
    TEST_CASE_9_COMBINED_GRID_SOLAR,
    TEST_CASE_10_STRESS,
]
