"""End-to-end API tests for GridWise endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_energy_end_to_end():
    scenario_payload = {
        "scenario_id": "GRID-TEST-101",
        "operator_notes": [
            "Solar output will drop to about 20% from 1 PM to 3 PM.",
            "Do not charge the battery between 2 PM and 4 PM.",
            "The cafeteria menu changes tomorrow.",
        ],
        "hours": [
            {
                "hour": h,
                "demand_kwh": 180.0 if 8 <= h <= 18 else 100.0,
                "solar_kwh": 80.0 if 9 <= h <= 16 else 0.0,
                "tariff_bdt_per_kwh": 14.0 if 17 <= h <= 21 else (6.0 if 0 <= h <= 6 else 9.0),
            }
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 500.0,
            "initial_energy_kwh": 200.0,
            "minimum_energy_kwh": 50.0,
            "max_charge_kwh_per_hour": 100.0,
            "max_discharge_kwh_per_hour": 100.0,
        },
    }

    response = client.post("/optimize-energy", json=scenario_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["scenario_id"] == "GRID-TEST-101"
    assert len(data["directive_interpretation"]) == 3
    assert len(data["hourly_plan"]) == 24
    assert data["total_grid_kwh"] > 0
    assert data["total_cost_bdt"] > 0
    assert data["peak_grid_kwh"] > 0
    assert isinstance(data["plan_summary"], str)

    # Note 0: solar_reduction
    d0 = data["directive_interpretation"][0]
    assert d0["note_index"] == 0
    assert d0["applies"] is True
    assert d0["directive_type"] == "solar_reduction"
    assert d0["structured_adjustment"]["hours"] == [13, 14]
    assert d0["structured_adjustment"]["factor"] == 0.2

    # Note 1: no_charge_window
    d1 = data["directive_interpretation"][1]
    assert d1["note_index"] == 1
    assert d1["applies"] is True
    assert d1["directive_type"] == "no_charge_window"
    assert d1["structured_adjustment"]["hours"] == [14, 15]

    # Note 2: no_op
    d2 = data["directive_interpretation"][2]
    assert d2["note_index"] == 2
    assert d2["applies"] is False
    assert d2["directive_type"] == "no_op"
    assert d2["structured_adjustment"] is None

    # End-of-day battery neutrality
    assert abs(data["hourly_plan"][23]["battery_energy_after_kwh"] - 200.0) <= 0.05


def test_malformed_request_returns_400():
    # Only 23 hours instead of 24
    bad_payload = {
        "scenario_id": "BAD-REQ-01",
        "operator_notes": ["Note 1"],
        "hours": [
            {"hour": h, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 8}
            for h in range(23)
        ],
        "battery": {
            "capacity_kwh": 500,
            "initial_energy_kwh": 200,
            "minimum_energy_kwh": 50,
            "max_charge_kwh_per_hour": 100,
            "max_discharge_kwh_per_hour": 100,
        },
    }
    response = client.post("/optimize-energy", json=bad_payload)
    assert response.status_code == 400
    assert response.json()["error"] == "Bad Request"


def test_empty_notes_returns_400():
    bad_payload = {
        "scenario_id": "BAD-REQ-02",
        "operator_notes": [],
        "hours": [
            {"hour": h, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 8}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 500,
            "initial_energy_kwh": 200,
            "minimum_energy_kwh": 50,
            "max_charge_kwh_per_hour": 100,
            "max_discharge_kwh_per_hour": 100,
        },
    }
    response = client.post("/optimize-energy", json=bad_payload)
    assert response.status_code == 400


def test_battery_initial_exceeding_capacity_returns_400():
    bad_payload = {
        "scenario_id": "BAD-BAT-01",
        "operator_notes": ["Note 1"],
        "hours": [
            {"hour": h, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 8}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 500,
            "initial_energy_kwh": 600,  # exceeds capacity
            "minimum_energy_kwh": 50,
            "max_charge_kwh_per_hour": 100,
            "max_discharge_kwh_per_hour": 100,
        },
    }
    response = client.post("/optimize-energy", json=bad_payload)
    assert response.status_code == 400
