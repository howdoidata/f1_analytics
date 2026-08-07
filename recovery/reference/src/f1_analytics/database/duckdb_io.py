"""Small DuckDB IO helpers used by scripts and reusable modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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


def ensure_source_metadata_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_registry (
            source_name TEXT PRIMARY KEY,
            source_type TEXT,
            description TEXT,
            landing_tables TEXT,
            credential_required BOOLEAN,
            status TEXT,
            updated_at TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_load_log (
            load_id TEXT,
            source_name TEXT,
            table_name TEXT,
            source_path TEXT,
            row_count INTEGER,
            loaded_at TIMESTAMP
        )
        """
    )


def ensure_validation_log_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_results (
            check_id TEXT,
            check_type TEXT,
            table_name TEXT,
            column_name TEXT,
            ref_table_name TEXT,
            row_count INTEGER,
            null_count INTEGER,
            null_rate DOUBLE,
            orphan_count INTEGER,
            passed BOOLEAN,
            checked_at TIMESTAMP
        )
        """
    )


def log_validation_results(
    conn: duckdb.DuckDBPyConnection,
    results: pd.DataFrame,
) -> None:
    ensure_validation_log_table(conn)
    conn.register("validation_df", results)
    conn.execute("INSERT INTO validation_results SELECT * FROM validation_df")
    conn.unregister("validation_df")


def register_source(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_name: str,
    source_type: str,
    description: str,
    landing_tables: list[str],
    credential_required: bool,
    status: str,
) -> None:
    ensure_source_metadata_tables(conn)
    conn.execute("DELETE FROM source_registry WHERE source_name = ?", [source_name])
    conn.execute(
        """
        INSERT INTO source_registry (
            source_name,
            source_type,
            description,
            landing_tables,
            credential_required,
            status,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            source_name,
            source_type,
            description,
            ", ".join(landing_tables),
            credential_required,
            status,
            datetime.now(timezone.utc),
        ],
    )


def log_source_load(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_name: str,
    table_name: str,
    source_path: Path | str,
    row_count: int,
) -> None:
    ensure_source_metadata_tables(conn)
    conn.execute(
        """
        INSERT INTO source_load_log (
            load_id,
            source_name,
            table_name,
            source_path,
            row_count,
            loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid4()),
            source_name,
            table_name,
            str(source_path),
            int(row_count),
            datetime.now(timezone.utc),
        ],
    )

