"""LLM-assisted operator directive interpreter with deterministic rule-based fallback.

Processing path (per spec §02, §08):
  1. Call Gemini (primary) or Groq (secondary) with a structured JSON-mode prompt.
  2. Parse and lightly validate the raw LLM response.
  3. Return DirectiveInterpretation list — downstream guardrails (guardrails.py) do
     the full deterministic sanitization before anything touches the optimizer.
  4. On any LLM failure (timeout, bad JSON, provider outage) degrade to the
     deterministic regex parser so the request never returns a 500.
"""

from __future__ import annotations

import json
import logging
import re
import signal
import threading
from typing import Any, Optional

from app.config import GEMINI_API_KEY, GROQ_API_KEY, TIMEOUT_SECONDS
from app.schemas import DirectiveInterpretation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an energy management assistant for a smart campus.
Your only job is to convert natural-language operator notes into structured energy directives.

SUPPORTED DIRECTIVE TYPES (use exactly these strings):
  solar_reduction         – usable solar drops to a fraction during specific hours
  minimum_battery_reserve – battery must stay at or above a kWh level during specific hours
  no_charge_window        – battery charging is forbidden during specific hours
  no_discharge_window     – battery discharging is forbidden during specific hours
  max_grid_window         – grid import is capped at a kWh value during specific hours
  no_op                   – the note has no effect on today's 24-hour energy schedule

RULES:
- Return ONLY a JSON array, one object per note, in the same order as the input list.
- Every object must have: note_index (int), applies (bool), directive_type (string),
  structured_adjustment (object or null), explanation (string ≤ 80 chars).
- applies is false ONLY for no_op; it is true for every other directive type.
- structured_adjustment shapes:
    solar_reduction:          {"hours": [int,...], "factor": float}   -- factor is the REMAINING fraction (0.2 = 80% reduced)
    minimum_battery_reserve:  {"hours": [int,...], "minimum_energy_kwh": float}
    no_charge_window:         {"hours": [int,...]}
    no_discharge_window:      {"hours": [int,...]}
    max_grid_window:          {"hours": [int,...], "max_grid_kwh": float}
    no_op:                    null
- hours arrays: unique integers 0–23 in ascending order, half-open interval
  (e.g. "1 PM to 3 PM" → hours [13, 14], NOT [13, 14, 15]).
- Do NOT invent demand, tariff, battery capacity, or unsupported directive types.
- If a note is ambiguous or irrelevant (cafeteria menu, meetings, weather updates,
  staffing) → no_op.
- If a note maps to two directives in one sentence, pick the more specific/quantified one.

WORKED EXAMPLES (Section 4.2 of the spec):
  Input:  "Solar output will drop to about 20% from 1 PM to 3 PM."
  Output: {"note_index":0,"applies":true,"directive_type":"solar_reduction",
           "structured_adjustment":{"hours":[13,14],"factor":0.2},
           "explanation":"Solar reduced to 20% of normal during panel maintenance."}

  Input:  "Do not charge the battery between 2 PM and 4 PM."
  Output: {"note_index":0,"applies":true,"directive_type":"no_charge_window",
           "structured_adjustment":{"hours":[14,15]},
           "explanation":"Battery charging prohibited 14:00–16:00."}

  Input:  "Keep at least 120 kWh in reserve from 6 PM until 9 PM."
  Output: {"note_index":0,"applies":true,"directive_type":"minimum_battery_reserve",
           "structured_adjustment":{"hours":[18,19,20],"minimum_energy_kwh":120.0},
           "explanation":"Battery reserve floor raised to 120 kWh from 18:00–21:00."}

  Input:  "The cafeteria menu changes tomorrow."
  Output: {"note_index":0,"applies":false,"directive_type":"no_op",
           "structured_adjustment":null,
           "explanation":"Irrelevant to the 24-hour energy schedule."}

PARAPHRASE ROBUSTNESS (Section 11.4 of the spec — these all mean solar_reduction hours=[13,14] factor=0.2):
  "PV production will drop to about 20% between 13:00 and 15:00."
  "Panel washing from one until three will leave roughly one-fifth of normal solar output."
  "Expect an 80% reduction in rooftop solar during the 1-3 PM maintenance window."

Return ONLY the JSON array. No markdown fences, no prose, no extra keys."""


def _build_user_prompt(notes: list[str]) -> str:
    numbered = "\n".join(f"{i}. {note}" for i, note in enumerate(notes))
    return (
        f"Interpret the following {len(notes)} operator note(s) and return a JSON array "
        f"with exactly {len(notes)} object(s) in order:\n\n{numbered}"
    )


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------

def _call_gemini(notes: list[str]) -> list[dict[str, Any]]:
    """Call Google Gemini via google-genai SDK with JSON-mode output."""
    import google.genai as genai  # type: ignore[import-untyped]
    from google.genai import types as genai_types  # type: ignore[import-untyped]

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=_build_user_prompt(notes),
        config=genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )
    raw = response.text.strip()
    return json.loads(raw)


def _call_groq(notes: list[str]) -> list[dict[str, Any]]:
    """Call Groq with llama-3.3-70b-versatile using JSON-mode output."""
    from groq import Groq  # type: ignore[import-untyped]

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(notes)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = completion.choices[0].message.content.strip()
    parsed = json.loads(raw)
    # Groq json_object mode wraps arrays under a key; unwrap if needed.
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
        raise ValueError("Groq response is a dict with no array value")
    return parsed


def _call_llm_with_timeout(notes: list[str]) -> list[dict[str, Any]]:
    """Try Gemini then Groq, each within TIMEOUT_SECONDS, using a thread-based timeout."""
    providers = []
    if GEMINI_API_KEY:
        providers.append(("Gemini", _call_gemini))
    if GROQ_API_KEY:
        providers.append(("Groq", _call_groq))

    if not providers:
        raise RuntimeError("No LLM API key configured")

    for name, fn in providers:
        result: list[dict[str, Any]] = []
        exc_holder: list[Exception] = []

        def _worker() -> None:
            try:
                result.extend(fn(notes))
            except Exception as e:
                exc_holder.append(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=TIMEOUT_SECONDS)

        if thread.is_alive():
            logger.warning("%s call exceeded %.1fs timeout", name, TIMEOUT_SECONDS)
            continue
        if exc_holder:
            logger.warning("%s call failed: %s", name, exc_holder[0])
            continue
        return result

    raise RuntimeError("All LLM providers failed or timed out")


# ---------------------------------------------------------------------------
# LLM response → DirectiveInterpretation
# ---------------------------------------------------------------------------

def _coerce_entry(entry: dict[str, Any], note_index: int) -> DirectiveInterpretation:
    """Best-effort coercion of a single raw LLM dict into DirectiveInterpretation.

    Normalises common LLM quirks (wrong note_index, missing keys) without
    rejecting the whole batch — downstream guardrails do the strict enforcement.
    """
    dtype = str(entry.get("directive_type", "no_op")).strip()
    adjustment = entry.get("structured_adjustment")
    explanation = str(entry.get("explanation", "LLM interpretation."))[:200]

    return DirectiveInterpretation(
        note_index=note_index,
        applies=(dtype != "no_op"),
        directive_type=dtype if dtype in {  # type: ignore[arg-type]
            "solar_reduction", "minimum_battery_reserve",
            "no_charge_window", "no_discharge_window",
            "max_grid_window", "no_op",
        } else "no_op",
        structured_adjustment=adjustment if dtype != "no_op" else None,
        explanation=explanation,
    )


def _parse_llm_response(
    raw: list[dict[str, Any]], num_notes: int
) -> list[DirectiveInterpretation]:
    """Map raw LLM output list to exactly num_notes DirectiveInterpretation objects."""
    by_index: dict[int, dict[str, Any]] = {}
    for entry in raw:
        if isinstance(entry, dict):
            idx = entry.get("note_index")
            if isinstance(idx, int) and 0 <= idx < num_notes and idx not in by_index:
                by_index[idx] = entry

    results: list[DirectiveInterpretation] = []
    for i in range(num_notes):
        if i in by_index:
            results.append(_coerce_entry(by_index[i], i))
        else:
            logger.warning("LLM response missing entry for note_index=%d; defaulting to no_op", i)
            results.append(_no_op(i, "LLM response did not include this note index."))
    return results


def _no_op(note_index: int, reason: str) -> DirectiveInterpretation:
    return DirectiveInterpretation(
        note_index=note_index,
        applies=False,
        directive_type="no_op",
        structured_adjustment=None,
        explanation=reason,
    )


# ---------------------------------------------------------------------------
# Deterministic rule-based fallback
# ---------------------------------------------------------------------------

def _parse_time_token(token: str) -> Optional[int]:
    """Parse time tokens like '1 PM', '13:00', '9am', 'noon', 'midnight', 'one' -> 0..23."""
    _WORD_HOURS: dict[str, int] = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    }
    t = token.strip().lower()
    if t == "noon":
        return 12
    if t == "midnight":
        return 0
    if t in _WORD_HOURS:
        return _WORD_HOURS[t]

    m12 = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", t)
    if m12:
        h = int(m12.group(1))
        meridiem = m12.group(3)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return h if 0 <= h <= 23 else None

    m24 = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if m24:
        h = int(m24.group(1))
        return h if 0 <= h <= 23 else None

    if t.isdigit():
        h = int(t)
        return h if 0 <= h <= 23 else None

    return None


def _extract_time_window(text: str) -> Optional[list[int]]:
    """Return a sorted list of half-open hour integers from a time range in text."""
    _WORD = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    _TIME = rf"(?:\d{{1,2}}(?::\d{{2}})?(?:\s*(?:am|pm))?|{_WORD}(?:\s*(?:am|pm))?)"
    patterns = [
        rf"(?:from|between)\s+({_TIME})\s+(?:to|until|and|-)\s+({_TIME})",
        r"during\s+the\s+(\d{1,2})\s*-\s*(\d{1,2})\s*(am|pm)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 3:
            s, e, meridiem = int(groups[0]), int(groups[1]), groups[2].lower()
            if meridiem == "pm":
                s = s + 12 if s < 12 else s
                e = e + 12 if e < 12 else e
            start_h, end_h = s, e
        else:
            start_h = _parse_time_token(groups[0])
            end_h = _parse_time_token(groups[1])
        if start_h is not None and end_h is not None and start_h < end_h:
            return list(range(start_h, min(end_h, 24)))
    return None


def _rule_based_interpret(note: str, note_index: int) -> DirectiveInterpretation:
    """Interpret a single operator note using keyword heuristics and regex."""
    lower = note.lower()

    # solar_reduction
    solar_kw = any(k in lower for k in ("solar", "pv", "rooftop", "photovoltaic", "panel"))
    reduce_kw = any(k in lower for k in ("drop", "reduc", "curtail", "cut", "wash", "clean", "down", "loss", "maintenance", "one-fifth", "1/5", "leave", "output"))
    if solar_kw and reduce_kw:
        window = _extract_time_window(note)
        if window:
            factor = 0.5
            pct = re.search(r"(\d+(?:\.\d+)?)\s*%", note)
            if pct:
                pct_val = float(pct.group(1))
                if any(k in lower for k in ("drop to", "fall to", "leave", "remain", "only")):
                    factor = pct_val / 100.0
                else:
                    factor = max(0.0, 1.0 - pct_val / 100.0)
            elif "one-fifth" in lower or "1/5" in lower:
                factor = 0.2
            elif "one-quarter" in lower or "quarter" in lower or "1/4" in lower:
                factor = 0.25
            elif "half" in lower or "1/2" in lower:
                factor = 0.5
            elif "one-third" in lower or "1/3" in lower:
                factor = round(1 / 3, 4)
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="solar_reduction",
                structured_adjustment={"hours": window, "factor": round(factor, 4)},
                explanation=f"Fallback: solar reduced to factor {round(factor, 4)} during hours {window}.",
            )

    # no_charge_window
    no_charge_kw = any(k in lower for k in ("do not charge", "don't charge", "no charge", "prohibit charg", "disable charg", "stop charg", "pause charg", "cannot charge", "charging is prohibited", "charging is forbidden", "charging is not allowed", "charging unavailable"))
    if no_charge_kw:
        window = _extract_time_window(note)
        if window:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": window},
                explanation=f"Fallback: battery charging prohibited during hours {window}.",
            )

    # no_discharge_window
    no_discharge_kw = any(k in lower for k in ("do not discharge", "don't discharge", "no discharge", "prohibit discharg", "disable discharg", "hold battery", "cannot discharge", "discharging is prohibited", "discharging is forbidden", "discharging is not allowed", "discharging unavailable"))
    if no_discharge_kw:
        window = _extract_time_window(note)
        if window:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="no_discharge_window",
                structured_adjustment={"hours": window},
                explanation=f"Fallback: battery discharging prohibited during hours {window}.",
            )

    # minimum_battery_reserve
    reserve_kw = any(k in lower for k in ("reserve", "keep at least", "maintain at least", "minimum battery", "floor", "hold at least", "no lower than", "at least"))
    if reserve_kw:
        window = _extract_time_window(note)
        kwh_m = re.search(r"(\d+(?:\.\d+)?)\s*kwh", lower)
        if window and kwh_m:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="minimum_battery_reserve",
                structured_adjustment={"hours": window, "minimum_energy_kwh": float(kwh_m.group(1))},
                explanation=f"Fallback: battery reserve >= {kwh_m.group(1)} kWh during hours {window}.",
            )

    # max_grid_window
    grid_cap_kw = any(k in lower for k in ("grid import", "grid limit", "grid cap", "max grid", "not exceed", "substation", "grid draw", "import cap"))
    if grid_cap_kw:
        window = _extract_time_window(note)
        kwh_m = re.search(r"(\d+(?:\.\d+)?)\s*kwh", lower)
        if window and kwh_m:
            return DirectiveInterpretation(
                note_index=note_index,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": window, "max_grid_kwh": float(kwh_m.group(1))},
                explanation=f"Fallback: grid import capped at {kwh_m.group(1)} kWh during hours {window}.",
            )

    return _no_op(note_index, "Fallback: note does not match any supported energy directive.")


def _rule_based_interpret_all(notes: list[str]) -> list[DirectiveInterpretation]:
    results: list[DirectiveInterpretation] = []
    for idx, note in enumerate(notes):
        try:
            results.append(_rule_based_interpret(note, idx))
        except Exception as exc:
            logger.warning("Rule-based fallback failed for note %d: %s", idx, exc)
            results.append(_no_op(idx, "Fallback parse error."))
    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def interpret_notes(notes: list[str]) -> list[DirectiveInterpretation]:
    """Interpret operator notes into structured directives via LLM with rule-based fallback.

    The LLM (Gemini primary, Groq secondary) is the canonical interpretation path per
    spec §02 and §08. The rule-based fallback is engaged only when all providers fail
    or time out, ensuring the request never returns a 500.
    """
    if not notes:
        return []

    try:
        raw = _call_llm_with_timeout(notes)
        if not isinstance(raw, list):
            raise ValueError(f"LLM returned non-list top-level type: {type(raw)}")
        directives = _parse_llm_response(raw, len(notes))
        logger.info("LLM interpretation succeeded for %d notes", len(notes))
        return directives
    except Exception as exc:
        logger.warning(
            "LLM interpretation failed (%s); engaging rule-based fallback for %d notes",
            exc,
            len(notes),
        )
        return _rule_based_interpret_all(notes)
