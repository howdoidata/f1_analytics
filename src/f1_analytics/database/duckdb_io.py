"""The storage edge's replace-sync writer (AD-4 class 1: ingestion tables)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH


def connect_duckdb(
    db_path: Path = DUCKDB_PATH,
    *,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


class WriteRegressionError(Exception):
    """A replace-sync write would shrink `table_name` below its already-landed row count."""


def _existing_row_count(conn: duckdb.DuckDBPyConnection, table_name: str) -> int | None:
    # Scoped to `main` BASE TABLEs deliberately. Unqualified, the probe matches
    # a same-named object in ANY schema (and matches VIEWs as well as tables),
    # while the COUNT(*) below resolves only against the search path -- so a
    # table existing solely as `other.combined_results` made the probe truthy
    # and the very next line raise CatalogException, and a same-named view
    # could have supplied the row count the regression guard compares against.
    exists = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = ? AND table_schema = 'main' AND table_type = 'BASE TABLE'",
        [table_name],
    ).fetchone()
    if exists is None:
        return None
    return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def write_dataframe(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    frame: pd.DataFrame,
    *,
    refuse_regression: bool = False,
) -> None:
    """Replace-sync `table_name` from `frame` (AD-4 class 1).

    `refuse_regression=True` guards live-fetched ingestion tables against a
    degraded/partial source run silently shrinking already-landed data: if
    the table already exists and `frame` has fewer rows, the write is
    refused (raising `WriteRegressionError`) and the existing table is left
    untouched. A table that doesn't exist yet always accepts the write,
    including an empty `frame` -- there is nothing to regress from.
    """
    if refuse_regression:
        existing_count = _existing_row_count(conn, table_name)
        if existing_count is not None and len(frame) < existing_count:
            raise WriteRegressionError(
                f"{table_name}: this write has {len(frame)} row(s), fewer than the "
                f"{existing_count} row(s) already landed -- refusing to replace"
            )
    conn.register("source_df", frame)
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM source_df")
    conn.unregister("source_df")
