"""Deterministic guardrails and sanitization for LLM directive interpretations."""

from __future__ import annotations

import math
from typing import Any, Optional
from app.schemas import (
    ALLOWED_DIRECTIVES,
    DirectiveInterpretation,
    DirectiveType,
)


def _sanitize_hours(raw_hours: Any) -> list[int]:
    """Extract, validate, deduplicate, and sort hourly indices in [0, 23]."""
    if not isinstance(raw_hours, (list, tuple, set)):
        return []
    valid_hours: set[int] = set()
    for h in raw_hours:
        try:
            h_int = int(h)
            if 0 <= h_int <= 23:
                valid_hours.add(h_int)
        except (ValueError, TypeError):
            continue
    return sorted(valid_hours)


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to finite float; return None if invalid or non-finite."""
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except (ValueError, TypeError):
        return None


def sanitize_single_directive(
    item: DirectiveInterpretation | dict[str, Any],
    fallback_index: int,
    battery_capacity: Optional[float] = None,
) -> DirectiveInterpretation:
    """Sanitizes a single directive interpretation entry, guaranteeing compliance.
    
    If the entry violates physical or structural schemas, it is safely repaired
    or demoted to 'no_op' with an explanation. NEVER raises an exception.
    """
    try:
        # Normalize input to dictionary/attributes
        if isinstance(item, DirectiveInterpretation):
            note_idx = item.note_index
            dir_type = item.directive_type
            adj = item.structured_adjustment or {}
            explanation = item.explanation or ""
        elif isinstance(item, dict):
            note_idx = item.get("note_index", fallback_index)
            dir_type = item.get("directive_type", "no_op")
            adj = item.get("structured_adjustment") or {}
            explanation = item.get("explanation", "")
        else:
            return DirectiveInterpretation(
                note_index=fallback_index,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation="Demoted to no_op: unsupported input structure.",
            )

        # Ensure note_idx is non-negative int
        try:
            note_idx = int(note_idx)
            if note_idx < 0:
                note_idx = fallback_index
        except (ValueError, TypeError):
            note_idx = fallback_index

        # Verify allowed directive type
        if dir_type not in ALLOWED_DIRECTIVES or dir_type == "no_op":
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=explanation or "No operational adjustment required.",
            )

        # Validate structured adjustment dictionary
        if not isinstance(adj, dict):
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation="Demoted to no_op: structured adjustment was not a valid dictionary.",
            )

        sanitized_hours = _sanitize_hours(adj.get("hours"))
        if not sanitized_hours:
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=f"Demoted to no_op: {dir_type} requires non-empty hours in range 0-23.",
            )

        # Type-specific validation and clamping
        if dir_type == "solar_reduction":
            raw_factor = _safe_float(adj.get("factor"))
            if raw_factor is None:
                return DirectiveInterpretation(
                    note_index=note_idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="Demoted to no_op: solar_reduction factor was missing or non-numeric.",
                )
            # If given as percentage > 1.0 (e.g. 20 for 20%), normalize if <= 100, else clamp
            factor = raw_factor
            if factor > 1.0 and factor <= 100.0:
                factor = factor / 100.0
            factor = max(0.0, min(1.0, factor))
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=True,
                directive_type="solar_reduction",
                structured_adjustment={"hours": sanitized_hours, "factor": round(factor, 4)},
                explanation=explanation or "Applied solar reduction adjustment.",
            )

        elif dir_type == "minimum_battery_reserve":
            raw_reserve = _safe_float(adj.get("minimum_energy_kwh"))
            if raw_reserve is None or raw_reserve < 0.0:
                return DirectiveInterpretation(
                    note_index=note_idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="Demoted to no_op: minimum_battery_reserve must be non-negative.",
                )
            reserve = raw_reserve
            if battery_capacity is not None and reserve > battery_capacity:
                reserve = battery_capacity
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=True,
                directive_type="minimum_battery_reserve",
                structured_adjustment={"hours": sanitized_hours, "minimum_energy_kwh": round(reserve, 4)},
                explanation=explanation or "Applied minimum battery reserve constraint.",
            )

        elif dir_type == "no_charge_window":
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": sanitized_hours},
                explanation=explanation or "Battery charging prohibited during specified window.",
            )

        elif dir_type == "no_discharge_window":
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=True,
                directive_type="no_discharge_window",
                structured_adjustment={"hours": sanitized_hours},
                explanation=explanation or "Battery discharging prohibited during specified window.",
            )

        elif dir_type == "max_grid_window":
            raw_max_grid = _safe_float(adj.get("max_grid_kwh"))
            if raw_max_grid is None or raw_max_grid < 0.0:
                return DirectiveInterpretation(
                    note_index=note_idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="Demoted to no_op: max_grid_kwh must be non-negative.",
                )
            return DirectiveInterpretation(
                note_index=note_idx,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": sanitized_hours, "max_grid_kwh": round(raw_max_grid, 4)},
                explanation=explanation or "Applied grid import limit during specified window.",
            )

        # Catch-all fallback
        return DirectiveInterpretation(
            note_index=note_idx,
            applies=False,
            directive_type="no_op",
            structured_adjustment=None,
            explanation=explanation or "Neutralized by guardrails.",
        )

    except Exception as exc:
        return DirectiveInterpretation(
            note_index=fallback_index,
            applies=False,
            directive_type="no_op",
            structured_adjustment=None,
            explanation=f"Demoted to no_op: unexpected error during sanitization ({type(exc).__name__}).",
        )


def sanitize_directives(
    raw_directives: list[DirectiveInterpretation] | list[dict[str, Any]],
    num_notes: Optional[int] = None,
    battery_capacity: Optional[float] = None,
) -> list[DirectiveInterpretation]:
    """Sanitizes an entire list of directive interpretations.
    
    Guarantees:
    1. Output contains exactly one DirectiveInterpretation per note index 0..N-1.
    2. Strictly ascending note_index order: 0, 1, ..., N-1.
    3. No duplicates or omissions.
    4. All directives adhere to Section 08 schema rules.
    5. Never raises an exception.
    """
    if not isinstance(raw_directives, (list, tuple)):
        raw_directives = []

    # Determine expected count
    n_expected = num_notes if num_notes is not None else len(raw_directives)
    if n_expected <= 0:
        n_expected = max(len(raw_directives), 1)

    # Sanitize each item
    sanitized_pool: list[DirectiveInterpretation] = []
    for idx, item in enumerate(raw_directives):
        sanitized = sanitize_single_directive(item, fallback_index=idx, battery_capacity=battery_capacity)
        sanitized_pool.append(sanitized)

    # Map by note_index, deduplicating
    indexed_map: dict[int, DirectiveInterpretation] = {}
    overflow_items: list[DirectiveInterpretation] = []

    for item in sanitized_pool:
        if 0 <= item.note_index < n_expected and item.note_index not in indexed_map:
            indexed_map[item.note_index] = item
        else:
            overflow_items.append(item)

    # Re-assign any overflow items to missing slots if available
    for missing_idx in range(n_expected):
        if missing_idx not in indexed_map and overflow_items:
            candidate = overflow_items.pop(0)
            candidate.note_index = missing_idx
            indexed_map[missing_idx] = candidate

    # Backfill remaining empty slots with no_op
    final_list: list[DirectiveInterpretation] = []
    for idx in range(n_expected):
        if idx in indexed_map:
            final_list.append(indexed_map[idx])
        else:
            final_list.append(
                DirectiveInterpretation(
                    note_index=idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="No directive provided for this note index.",
                )
            )

    # Sort strictly by note_index
    final_list.sort(key=lambda d: d.note_index)
    return final_list
