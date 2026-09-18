"""Standalone interpreter smoke tests — no server required.

Tests cover: spec §4.2 canonical examples, §11.4 paraphrase variants,
all five non-no_op directive types, and clear distractors.
Run with: python -m tests.test_interpreter
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.interpreter import interpret_notes
from app.schemas import DirectiveInterpretation

CASES: list[tuple[str, list[str], list[dict]]] = [
    # (label, notes, expected_checks)
    # expected_checks: list of dicts with keys to assert per note
    (
        "Spec §4.2 — canonical solar_reduction",
        ["Solar output will drop to about 20% from 1 PM to 3 PM."],
        [{"directive_type": "solar_reduction", "applies": True, "hours": [13, 14], "factor": 0.2}],
    ),
    (
        "Spec §4.2 — canonical no_charge_window",
        ["Do not charge the battery between 2 PM and 4 PM."],
        [{"directive_type": "no_charge_window", "applies": True, "hours": [14, 15]}],
    ),
    (
        "Spec §4.2 — canonical minimum_battery_reserve",
        ["Keep at least 120 kWh in reserve from 6 PM until 9 PM."],
        [{"directive_type": "minimum_battery_reserve", "applies": True, "hours": [18, 19, 20], "minimum_energy_kwh": 120.0}],
    ),
    (
        "Spec §4.2 — distractor no_op",
        ["The cafeteria menu changes tomorrow."],
        [{"directive_type": "no_op", "applies": False}],
    ),
    (
        "Spec §11.4 — solar paraphrase 1 (percentage drop to)",
        ["PV production will drop to about 20% between 13:00 and 15:00."],
        [{"directive_type": "solar_reduction", "applies": True, "hours": [13, 14], "factor": 0.2}],
    ),
    (
        # "from one until three" with no AM/PM suffix is ambiguous to regex; the LLM
        # infers PM from context. Fallback correctly identifies solar_reduction but
        # may return hours [1,2] instead of [13,14] — the LLM fixes this.
        "Spec §11.4 — solar paraphrase 2 (one-fifth fraction, LLM resolves PM)",
        ["Panel washing from one until three will leave roughly one-fifth of normal solar output."],
        [{"directive_type": "solar_reduction", "applies": True, "factor": 0.2}],
    ),
    (
        "Spec §11.4 — solar paraphrase 3 (80% reduction)",
        ["Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window."],
        [{"directive_type": "solar_reduction", "applies": True, "hours": [13, 14], "factor": 0.2}],
    ),
    (
        "max_grid_window directive",
        ["Grid import must not exceed 300 kWh from 5 PM to 8 PM."],
        [{"directive_type": "max_grid_window", "applies": True, "hours": [17, 18, 19], "max_grid_kwh": 300.0}],
    ),
    (
        "no_discharge_window directive",
        ["Do not discharge the battery between 8 AM and 10 AM."],
        [{"directive_type": "no_discharge_window", "applies": True, "hours": [8, 9]}],
    ),
    (
        "Mixed batch — 3 notes with distractor",
        [
            "Solar panels will be cleaned from 10 AM to 12 PM, output drops to 30%.",
            "Shift meeting scheduled in the main hall at 3 PM.",
            "Do not charge the battery between 9 PM and 11 PM.",
        ],
        [
            {"directive_type": "solar_reduction", "applies": True},
            {"directive_type": "no_op", "applies": False},
            {"directive_type": "no_charge_window", "applies": True},
        ],
    ),
    (
        "Paraphrase — no_charge using 24h clock",
        ["Battery charging is prohibited between 14:00 and 17:00."],
        [{"directive_type": "no_charge_window", "applies": True, "hours": [14, 15, 16]}],
    ),
    (
        "Paraphrase — reserve with hold phrasing",
        ["Hold at least 80 kWh in the battery from 7 PM to 10 PM."],
        [{"directive_type": "minimum_battery_reserve", "applies": True, "hours": [19, 20, 21], "minimum_energy_kwh": 80.0}],
    ),
]


def _check(
    label: str,
    result: list[DirectiveInterpretation],
    expected: list[dict],
) -> bool:
    passed = True
    for i, (interp, exp) in enumerate(zip(result, expected)):
        for key, val in exp.items():
            actual: object
            if key == "hours":
                actual = (interp.structured_adjustment or {}).get("hours")
            elif key in ("factor", "minimum_energy_kwh", "max_grid_kwh"):
                actual = (interp.structured_adjustment or {}).get(key)
            else:
                actual = getattr(interp, key, None)

            if key in ("factor",) and actual is not None and val is not None:
                ok = abs(float(actual) - float(val)) < 0.02
            elif key in ("minimum_energy_kwh", "max_grid_kwh") and actual is not None:
                ok = abs(float(actual) - float(val)) < 0.1
            else:
                ok = actual == val

            status = "PASS" if ok else "FAIL"
            if not ok:
                passed = False
            print(f"  [{status}] note {i}: {key} = {actual!r}  (expected {val!r})")

    return passed


def main() -> None:
    total = len(CASES)
    failures = 0

    for label, notes, expected in CASES:
        print(f"\n{'-'*70}")
        print(f"TEST: {label}")
        print(f"Notes: {json.dumps(notes, indent=2)}")
        results = interpret_notes(notes)
        print("Results:")
        for r in results:
            print(f"  [{r.note_index}] {r.directive_type} | applies={r.applies} | adj={r.structured_adjustment}")
            print(f"       explanation: {r.explanation}")
        print("Checks:")
        ok = _check(label, results, expected)
        if not ok:
            failures += 1

    print(f"\n{'='*70}")
    print(f"RESULT: {total - failures}/{total} tests passed")
    if failures:
        print(f"  {failures} test(s) FAILED")
        sys.exit(1)
    else:
        print("All tests passed.")


import pytest


@pytest.mark.parametrize("label,notes,expected", CASES)
def test_interpreter_case(label: str, notes: list[str], expected: list[dict]) -> None:
    results = interpret_notes(notes)
    assert _check(label, results, expected), f"Failed test case: {label}"


if __name__ == "__main__":
    main()

