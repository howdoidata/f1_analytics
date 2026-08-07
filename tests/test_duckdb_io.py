"""Tests for the storage edge's replace-sync writer (AD-4 class 1)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1_analytics.database.duckdb_io import connect_duckdb, write_dataframe


def test_write_dataframe_replaces_rather_than_appends(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    first = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    second = pd.DataFrame({"a": [10, 20]})

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "some_table", first)
        write_dataframe(conn, "some_table", second)

        result = conn.execute("SELECT * FROM some_table ORDER BY a").fetch_df()

    assert list(result.columns) == ["a"]
    assert result["a"].tolist() == [10, 20]


def test_write_dataframe_is_idempotent_on_repeated_identical_writes(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    frame = pd.DataFrame({"a": [1, 2, 3]})

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "some_table", frame)
        write_dataframe(conn, "some_table", frame)

        row_count = conn.execute("SELECT COUNT(*) FROM some_table").fetchone()[0]

    assert row_count == 3
