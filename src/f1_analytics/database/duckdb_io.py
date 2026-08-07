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


def write_dataframe(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    frame: pd.DataFrame,
) -> None:
    conn.register("source_df", frame)
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM source_df")
    conn.unregister("source_df")
