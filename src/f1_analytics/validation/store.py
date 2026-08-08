"""Append-only writers for validation/source-tracking tables (AD-4 class 3).

Distinct from `database.duckdb_io.write_dataframe` (AD-4 class 1's
replace-sync pattern, for ingestion tables only): every table here is
`CREATE TABLE IF NOT EXISTS` + `INSERT`, so every build's rows accumulate
rather than replace what a prior build already logged.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd


# role/access_model per source, keyed by the `source` name callers pass to
# `log_source_load`. An unregistered source name is a programming error
# (a new loader forgot to register itself here), never silently logged.
SOURCE_METADATA: dict[str, dict[str, str]] = {
    "kaggle": {"role": "curated_baseline", "access_model": "local_csv"},
    "jolpica": {"role": "gap_fill", "access_model": "rest_api"},
    "fastf1": {"role": "telemetry_facts", "access_model": "isolated_python_client"},
}

VALIDATION_RESULTS_COLUMNS = [
    "check_id",
    "check_type",
    "table_name",
    "column_name",
    "ref_table_name",
    "row_count",
    "null_count",
    "null_rate",
    "orphan_count",
    "passed",
    "checked_at",
]


def _clean(value: object) -> object:
    """Normalize a pandas/numpy scalar into something DuckDB's parameterized INSERT accepts."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # value isn't a type pd.isna() can evaluate (e.g. a plain str) -- not null.
    if hasattr(value, "item"):
        return value.item()  # numpy scalar (int64, bool_, float64, ...) -> native Python type.
    return value


def log_validation_results(conn, frame: pd.DataFrame) -> None:
    """Append `frame`'s rows to `validation_results` (creating it on first use)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_results (
            check_id VARCHAR,
            check_type VARCHAR,
            table_name VARCHAR,
            column_name VARCHAR,
            ref_table_name VARCHAR,
            row_count BIGINT,
            null_count BIGINT,
            null_rate DOUBLE,
            orphan_count BIGINT,
            passed BOOLEAN,
            checked_at TIMESTAMP
        )
        """
    )
    if frame.empty:
        return

    rows = [tuple(_clean(row[column]) for column in VALIDATION_RESULTS_COLUMNS) for _, row in frame.iterrows()]
    placeholders = ", ".join(["?"] * len(VALIDATION_RESULTS_COLUMNS))
    conn.executemany(
        f"INSERT INTO validation_results ({', '.join(VALIDATION_RESULTS_COLUMNS)}) VALUES ({placeholders})",
        rows,
    )


def log_source_load(conn, source: str, table_name: str, row_count: int) -> None:
    """Append one `source_registry` row and one `source_load_log` row for this build.

    Asserts "this build loaded `table_name` from `source`" -- callers must
    only invoke this for a table this run's own writes actually touched,
    never a table's mere presence from an earlier run. Raises `ValueError`
    for a `source` not in `SOURCE_METADATA`.
    """
    if source not in SOURCE_METADATA:
        raise ValueError(f"Unregistered source {source!r}; known sources: {sorted(SOURCE_METADATA)}")
    metadata = SOURCE_METADATA[source]
    now = datetime.now(timezone.utc)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_registry (
            source_name VARCHAR,
            role VARCHAR,
            access_model VARCHAR,
            recorded_at TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO source_registry (source_name, role, access_model, recorded_at) VALUES (?, ?, ?, ?)",
        [source, metadata["role"], metadata["access_model"], now],
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_load_log (
            source_name VARCHAR,
            table_name VARCHAR,
            row_count BIGINT,
            loaded_at TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO source_load_log (source_name, table_name, row_count, loaded_at) VALUES (?, ?, ?, ?)",
        [source, table_name, int(row_count), now],
    )
