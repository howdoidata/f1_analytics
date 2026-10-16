"""Offline unit tests for `validation/store.py`'s append-only writers (Story 1.8).

`log_validation_results`/`log_source_load` are AD-4 class-3: `CREATE TABLE
IF NOT EXISTS` + `INSERT`, distinct from `database.duckdb_io.write_dataframe`'s
replace-sync pattern. Rows must accumulate across calls, never overwrite.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.database.duckdb_io import connect_duckdb
from f1_analytics.validation.checks import run_validations
from f1_analytics.validation.store import SOURCE_METADATA, log_source_load, log_validation_results


def _sample_validation_frame() -> pd.DataFrame:
    return run_validations({"drivers": pd.DataFrame({"driver_id": ["verstappen", None]})})


def test_log_validation_results_creates_the_table_and_inserts_rows(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    frame = _sample_validation_frame()

    with connect_duckdb(db_path) as conn:
        log_validation_results(conn, frame)
        row_count = conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0]
        landed = conn.execute("SELECT * FROM validation_results").fetch_df()

    assert row_count == len(frame)
    assert landed["table_name"].tolist() == ["drivers"]
    assert not landed["passed"].iloc[0]  # one NULL driver_id
    assert landed["null_count"].iloc[0] == 1


def test_log_validation_results_accumulates_across_two_calls_never_overwrites(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    first = _sample_validation_frame()
    second = _sample_validation_frame()

    with connect_duckdb(db_path) as conn:
        log_validation_results(conn, first)
        log_validation_results(conn, second)
        row_count = conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0]

    assert row_count == len(first) + len(second)


def test_log_validation_results_handles_an_empty_frame_without_error(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    empty = run_validations({})

    with connect_duckdb(db_path) as conn:
        log_validation_results(conn, empty)
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        row_count = conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0]

    # The table is still created (so later runs can append to it) even
    # though this run logged zero findings.
    assert "validation_results" in tables
    assert row_count == 0


def test_log_source_load_creates_both_tables_and_inserts_matching_rows(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect_duckdb(db_path) as conn:
        log_source_load(conn, "fastf1", "raw_fastf1_laps", 42)
        registry = conn.execute("SELECT * FROM source_registry").fetch_df()
        load_log = conn.execute("SELECT * FROM source_load_log").fetch_df()

    assert registry["source_name"].tolist() == ["fastf1"]
    assert registry["role"].iloc[0] == SOURCE_METADATA["fastf1"]["role"]
    assert registry["access_model"].iloc[0] == SOURCE_METADATA["fastf1"]["access_model"]
    assert registry["recorded_at"].notna().all()

    assert load_log["source_name"].tolist() == ["fastf1"]
    assert load_log["table_name"].tolist() == ["raw_fastf1_laps"]
    assert load_log["row_count"].tolist() == [42]
    assert load_log["loaded_at"].notna().all()


def test_log_source_load_accumulates_across_calls_never_overwrites(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect_duckdb(db_path) as conn:
        log_source_load(conn, "jolpica", "results", 10)
        log_source_load(conn, "fastf1", "raw_fastf1_laps", 3)
        registry_count = conn.execute("SELECT COUNT(*) FROM source_registry").fetchone()[0]
        load_log = conn.execute("SELECT * FROM source_load_log ORDER BY source_name").fetch_df()

    assert registry_count == 2
    assert load_log["source_name"].tolist() == ["fastf1", "jolpica"]
    assert load_log["row_count"].tolist() == [3, 10]


def test_registered_sources_are_jolpica_and_fastf1_only():
    assert set(SOURCE_METADATA) == {"jolpica", "fastf1"}


def test_log_source_load_raises_value_error_for_an_unregistered_source(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect_duckdb(db_path) as conn:
        with pytest.raises(ValueError, match="not_a_real_source"):
            log_source_load(conn, "not_a_real_source", "some_table", 1)

        # The failed call must not have created either table -- an
        # unregistered source is a programming error, not a partial write.
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert "source_registry" not in tables
    assert "source_load_log" not in tables
