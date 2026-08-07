"""Null-rate and referential-integrity checks for curated Kaggle tables."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd


NULL_RATE_CHECKS: list[tuple[str, list[str]]] = [
    ("results", ["season", "round", "driver_id", "position", "points"]),
    ("drivers", ["driver_id"]),
    ("constructors", ["constructor_id"]),
    ("final_driver_standings", ["constructor_id"]),
]

REFERENTIAL_CHECKS: list[tuple[str, str, str, str]] = [
    ("results", "driver_id", "drivers", "driver_id"),
    ("results", "constructor_id", "constructors", "constructor_id"),
    ("races", "circuit_id", "circuits", "circuit_id"),
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
    child_values = child_frame[child_column].dropna()
    parent_values = set(parent_frame[parent_column].dropna())
    orphan_count = int((~child_values.isin(parent_values)).sum())
    return {
        "check_type": "referential_integrity",
        "table_name": child_table,
        "column_name": child_column,
        "ref_table_name": f"{parent_table}.{parent_column}",
        "row_count": len(child_frame),
        "null_count": None,
        "null_rate": None,
        "orphan_count": orphan_count,
        "passed": orphan_count == 0,
    }


def run_kaggle_validations(curated: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for table_name, columns in NULL_RATE_CHECKS:
        frame = curated.get(table_name)
        if frame is None:
            continue
        for column in columns:
            rows.append(check_null_rate(frame, table_name, column))

    for child_table, child_column, parent_table, parent_column in REFERENTIAL_CHECKS:
        child_frame = curated.get(child_table)
        parent_frame = curated.get(parent_table)
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
