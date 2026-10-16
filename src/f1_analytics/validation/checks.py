"""Null-rate and referential-integrity checks for curated and raw FastF1 tables.

Pure functions only -- no DB access here. Each check returns a
finding-row dict with a `check_id`/`checked_at` envelope; `store.py` (a
separate module) is the only thing that persists them. Covers the curated
tables and `raw_fastf1_laps`/`raw_fastf1_stints`/`raw_fastf1_weather`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd


# Curated tables plus raw_fastf1_laps/raw_fastf1_stints/raw_fastf1_weather.
# raw_fastf1_weather is track-level (no driver_id) -- only
# season/round are checked there.
NULL_RATE_CHECKS: list[tuple[str, list[str]]] = [
    ("results", ["season", "round", "driver_id", "position", "points"]),
    ("drivers", ["driver_id"]),
    ("constructors", ["constructor_id"]),
    ("final_driver_standings", ["constructor_id"]),
    ("raw_fastf1_laps", ["season", "round", "driver_id"]),
    ("raw_fastf1_stints", ["season", "round", "driver_id"]),
    ("raw_fastf1_weather", ["season", "round"]),
]

REFERENTIAL_CHECKS: list[tuple[str, str, str, str]] = [
    ("results", "driver_id", "drivers", "driver_id"),
    ("results", "constructor_id", "constructors", "constructor_id"),
    ("races", "circuit_id", "circuits", "circuit_id"),
    ("raw_fastf1_laps", "driver_id", "drivers", "driver_id"),
    ("raw_fastf1_laps", "constructor_id", "constructors", "constructor_id"),
    ("raw_fastf1_stints", "driver_id", "drivers", "driver_id"),
    ("raw_fastf1_stints", "constructor_id", "constructors", "constructor_id"),
]


def check_null_rate(frame: pd.DataFrame, table_name: str, column: str) -> dict[str, object]:
    row_count = len(frame)
    null_count = int(frame[column].isna().sum()) if column in frame.columns else row_count
    null_rate = (null_count / row_count) if row_count else 0.0
    return {
        "check_type": "null_rate",
        "table_name": table_name,
        "column_name": column,
        "ref_table_name": None,
        "row_count": row_count,
        "null_count": null_count,
        "null_rate": null_rate,
        "orphan_count": None,
        "passed": null_count == 0,
    }


def check_referential_integrity(
    child_frame: pd.DataFrame,
    child_table: str,
    child_column: str,
    parent_frame: pd.DataFrame,
    parent_table: str,
    parent_column: str,
) -> dict[str, object]:
    """Every non-null `child_column` value must exist in `parent_column`.

    A missing `child_column`/`parent_column` is guarded exactly like
    `check_null_rate` guards a missing column: rather than raising a
    `KeyError` (which would violate this story's "never halt a build"
    boundary), every row is counted as an orphan -- there is nothing to
    verify it against.
    """
    row_count = len(child_frame)
    if child_column not in child_frame.columns or parent_column not in parent_frame.columns:
        orphan_count = row_count
    else:
        child_values = child_frame[child_column].dropna()
        parent_values = set(parent_frame[parent_column].dropna())
        orphan_count = int((~child_values.isin(parent_values)).sum())
    return {
        "check_type": "referential_integrity",
        "table_name": child_table,
        "column_name": child_column,
        "ref_table_name": f"{parent_table}.{parent_column}",
        "row_count": row_count,
        "null_count": None,
        "null_rate": None,
        "orphan_count": orphan_count,
        "passed": orphan_count == 0,
    }


def run_validations(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run every registry check whose table(s) are present in `tables`.

    A registry entry naming a table absent from `tables` is skipped, never
    a `KeyError` -- `uv run build` only passes whatever tables actually exist
    (via `runner.load_present_tables`).
    """
    rows: list[dict[str, object]] = []

    for table_name, columns in NULL_RATE_CHECKS:
        frame = tables.get(table_name)
        if frame is None:
            continue
        for column in columns:
            rows.append(check_null_rate(frame, table_name, column))

    for child_table, child_column, parent_table, parent_column in REFERENTIAL_CHECKS:
        child_frame = tables.get(child_table)
        parent_frame = tables.get(parent_table)
        if child_frame is None or parent_frame is None:
            continue
        rows.append(
            check_referential_integrity(
                child_frame, child_table, child_column, parent_frame, parent_table, parent_column
            )
        )

    result = pd.DataFrame(rows)
    result.insert(0, "check_id", [str(uuid4()) for _ in range(len(result))])
    result["checked_at"] = datetime.now(timezone.utc)
    return result
