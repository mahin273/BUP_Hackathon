"""Unit tests for the guardrails validator and directive sanitizer."""

import pytest
from app.guardrails import sanitize_directives, sanitize_single_directive
from app.schemas import DirectiveInterpretation


def test_sanitize_valid_directives():
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [14, 13], "factor": 0.2},
            "explanation": "Panel cleaning",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [15, 14]},
            "explanation": "No charging",
        },
        {
            "note_index": 2,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "Cafeteria lunch menu",
        },
    ]

    sanitized = sanitize_directives(raw, num_notes=3)
    assert len(sanitized) == 3

    # Note 0: hours sorted [13, 14]
    assert sanitized[0].note_index == 0
    assert sanitized[0].applies is True
    assert sanitized[0].directive_type == "solar_reduction"
    assert sanitized[0].structured_adjustment == {"hours": [13, 14], "factor": 0.2}

    # Note 1: hours sorted [14, 15]
    assert sanitized[1].note_index == 1
    assert sanitized[1].applies is True
    assert sanitized[1].directive_type == "no_charge_window"
    assert sanitized[1].structured_adjustment == {"hours": [14, 15]}

    # Note 2: no_op
    assert sanitized[2].note_index == 2
    assert sanitized[2].applies is False
    assert sanitized[2].directive_type == "no_op"
    assert sanitized[2].structured_adjustment is None


def test_sanitize_unknown_directive_type():
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "hallucinated_directive_power_boost",
            "structured_adjustment": {"hours": [10, 11]},
            "explanation": "Fake boost",
        }
    ]
    sanitized = sanitize_directives(raw, num_notes=1)
    assert len(sanitized) == 1
    assert sanitized[0].directive_type == "no_op"
    assert sanitized[0].applies is False
    assert sanitized[0].structured_adjustment is None


def test_sanitize_hours_out_of_bounds_and_duplicates():
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": [-5, 18, 19, 18, 24, 30]},
            "explanation": "Evening hold",
        }
    ]
    sanitized = sanitize_directives(raw, num_notes=1)
    assert sanitized[0].structured_adjustment == {"hours": [18, 19]}


def test_empty_hours_downgrades_to_no_op():
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [50, 60], "factor": 0.5},
            "explanation": "Bad hours",
        }
    ]
    sanitized = sanitize_directives(raw, num_notes=1)
    assert sanitized[0].directive_type == "no_op"
    assert sanitized[0].applies is False
    assert sanitized[0].structured_adjustment is None


def test_factor_clamping_and_normalization():
    # Percentage 80 -> 0.8
    entry1 = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {"hours": [10, 11], "factor": 80.0},
    }
    s1 = sanitize_single_directive(entry1, fallback_index=0)
    assert s1.structured_adjustment["factor"] == 0.8

    # Factor > 100 clamped to 1.0
    entry2 = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {"hours": [10, 11], "factor": 150.0},
    }
    s2 = sanitize_single_directive(entry2, fallback_index=0)
    assert s2.structured_adjustment["factor"] == 1.0

    # Negative factor clamped to 0.0
    entry3 = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "structured_adjustment": {"hours": [10, 11], "factor": -0.5},
    }
    s3 = sanitize_single_directive(entry3, fallback_index=0)
    assert s3.structured_adjustment["factor"] == 0.0


def test_battery_reserve_clamped_to_capacity():
    entry = {
        "note_index": 0,
        "applies": True,
        "directive_type": "minimum_battery_reserve",
        "structured_adjustment": {"hours": [18, 19], "minimum_energy_kwh": 600.0},
    }
    sanitized = sanitize_single_directive(entry, fallback_index=0, battery_capacity=500.0)
    assert sanitized.structured_adjustment["minimum_energy_kwh"] == 500.0


def test_missing_note_indices_backfilled():
    # Only note_index 1 is provided for 3 notes
    raw = [
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {"hours": [12, 13], "max_grid_kwh": 100.0},
        }
    ]
    sanitized = sanitize_directives(raw, num_notes=3)
    assert len(sanitized) == 3
    assert [d.note_index for d in sanitized] == [0, 1, 2]
    assert sanitized[0].directive_type == "no_op"
    assert sanitized[1].directive_type == "max_grid_window"
    assert sanitized[2].directive_type == "no_op"


def test_duplicate_indices_handled():
    raw = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [1, 2]},
        },
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": [3, 4]},
        },
    ]
    sanitized = sanitize_directives(raw, num_notes=2)
    assert len(sanitized) == 2
    assert sanitized[0].note_index == 0
    assert sanitized[1].note_index == 1
    assert sanitized[0].directive_type == "no_charge_window"
    assert sanitized[1].directive_type == "no_discharge_window"


def test_corrupted_input_never_crashes():
    garbage = ["not a dict", None, 12345]
    sanitized = sanitize_directives(garbage, num_notes=3)
    assert len(sanitized) == 3
    for s in sanitized:
        assert s.directive_type == "no_op"
        assert s.applies is False
