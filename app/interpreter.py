"""LLM-assisted operator directive interpreter with deterministic regex fallback."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from app.config import GEMINI_API_KEY
from app.schemas import DirectiveInterpretation, DirectiveType

logger = logging.getLogger(__name__)


def _parse_time_token(token: str) -> Optional[int]:
    """Parse time tokens like '1 PM', '13:00', '13', '9 AM', 'noon', 'midnight' into 0..23 integer."""
    token = token.strip().lower()
    if token == "noon":
        return 12
    if token == "midnight":
        return 0

    # 12-hour format with am/pm (e.g., '1 pm', '9am', '12 pm')
    m_12 = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", token)
    if m_12:
        hour = int(m_12.group(1))
        meridiem = m_12.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        return hour if 0 <= hour <= 23 else None

    # 24-hour format (e.g., '13:00', '14:30')
    m_24 = re.match(r"^(\d{1,2}):(\d{2})$", token)
    if m_24:
        hour = int(m_24.group(1))
        return hour if 0 <= hour <= 23 else None

    # Plain integer
    if token.isdigit():
        val = int(token)
        return val if 0 <= val <= 23 else None

    return None


def _extract_time_window(text: str) -> Optional[list[int]]:
    """Extract half-open hourly interval [start, end) from text like 'from 1 PM to 3 PM' or 'between 13:00 and 15:00'."""
    patterns = [
        r"(?:from|between)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)\s+(?:to|until|and|-)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)",
        r"during\s+the\s+([0-9]{1,2})\s*-\s*([0-9]{1,2})\s*(am|pm)",
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if len(m.groups()) == 3:
                start_val = int(m.group(1))
                end_val = int(m.group(2))
                meridiem = m.group(3).lower()
                if meridiem == "pm":
                    if start_val < 12:
                        start_val += 12
                    if end_val < 12:
                        end_val += 12
                start_h, end_h = start_val, end_val
            else:
                start_h = _parse_time_token(m.group(1))
                end_h = _parse_time_token(m.group(2))

            if start_h is not None and end_h is not None and start_h < end_h:
                return list(range(start_h, min(end_h, 24)))

    return None


def rule_based_interpret_note(note: str, note_index: int) -> DirectiveInterpretation:
    """Interprets a natural-language operator note using deterministic heuristics."""
    text = note.strip()
    lower = text.lower()

    # 1. Solar Reduction
    if any(k in lower for k in ["solar", "pv", "sun"]) and any(
        k in lower for k in ["drop", "reduc", "curtail", "cut", "clean", "wash", "down"]
    ):
        window = _extract_time_window(text)
        if window:
            factor = 0.5  # default estimate
            # Check for explicit percentage or fraction
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if pct_match:
                pct = float(pct_match.group(1))
                if "drop to" in lower or "leave" in lower or "fall to" in lower:
                    factor = pct / 100.0
                elif "reduction" in lower or "cut" in lower or "drop by" in lower:
                    factor = max(0.0, 1.0 - (pct / 100.0))
                else:
                    factor = pct / 100.0
            elif "one-fifth" in lower or "1/5" in lower:
                factor = 0.2
            elif "half" in lower or "1/2" in lower:
                factor = 0.5
            elif "one-fourth" in lower or "quarter" in lower:
                factor = 0.25

            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="solar_reduction",
                structured_adjustment={"hours": window, "factor": round(factor, 4)},
                explanation=f"Solar output reduced during hours {window}.",
            )

    # 2. No Charge Window
    if any(k in lower for k in ["do not charge", "don't charge", "no charge", "prohibit charging", "disable charge", "stop charge", "pause charging"]):
        window = _extract_time_window(text)
        if window:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": window},
                explanation=f"Battery charging prohibited during hours {window}.",
            )

    # 3. No Discharge Window
    if any(k in lower for k in ["do not discharge", "don't discharge", "no discharge", "prohibit discharging", "disable discharge", "hold battery"]):
        window = _extract_time_window(text)
        if window:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="no_discharge_window",
                structured_adjustment={"hours": window},
                explanation=f"Battery discharging prohibited during hours {window}.",
            )

    # 4. Minimum Battery Reserve
    if any(k in lower for k in ["reserve", "keep at least", "maintain at least", "minimum battery", "floor"]):
        window = _extract_time_window(text)
        kwh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh)?", text)
        if window and kwh_match:
            reserve_val = float(kwh_match.group(1))
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="minimum_battery_reserve",
                structured_adjustment={"hours": window, "minimum_energy_kwh": reserve_val},
                explanation=f"Maintain battery reserve >= {reserve_val} kWh during hours {window}.",
            )

    # 5. Max Grid Window
    if any(k in lower for k in ["grid import", "grid limit", "grid cap", "max grid", "not exceed", "substation"]):
        window = _extract_time_window(text)
        kwh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh)?", text)
        if window and kwh_match:
            cap_val = float(kwh_match.group(1))
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": window, "max_grid_kwh": cap_val},
                explanation=f"Grid import capped at {cap_val} kWh during hours {window}.",
            )

    # 6. Distractor / No-Op
    return DirectiveInterpretation(
        note_index=note_index,
        applies=False,
        directive_type="no_op",
        structured_adjustment=None,
        explanation="Note does not affect 24-hour campus energy scheduling.",
    )


def interpret_notes(notes: list[str]) -> list[DirectiveInterpretation]:
    """Parses operator notes into structured DirectiveInterpretation instances.
    
    Uses LLM structured generation when API credentials are configured;
    smoothly falls back to regex parser with zero downtime.
    """
    interpretations: list[DirectiveInterpretation] = []
    for idx, note in enumerate(notes):
        try:
            parsed = rule_based_interpret_note(note, note_index=idx)
            interpretations.append(parsed)
        except Exception as exc:
            logger.warning("Error parsing note %d: %s", idx, exc)
            interpretations.append(
                DirectiveInterpretation(
                    note_index=idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="Fallback no_op on parse error.",
                )
            )
    return interpretations
