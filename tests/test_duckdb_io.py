"""Tests for the storage edge's replace-sync writer (AD-4 class 1)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.database.duckdb_io import (
    WriteRegressionError,
    connect_duckdb,
    write_dataframe,
)


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


def test_write_dataframe_refuses_a_shrinking_write_when_guarded(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    first = pd.DataFrame({"a": [1, 2, 3]})
    second = pd.DataFrame({"a": [10, 20]})

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "some_table", first, refuse_regression=True)

        with pytest.raises(WriteRegressionError, match="some_table.*2.*fewer.*3"):
            write_dataframe(conn, "some_table", second, refuse_regression=True)

        result = conn.execute("SELECT * FROM some_table ORDER BY a").fetch_df()

    assert result["a"].tolist() == [1, 2, 3]


def test_write_dataframe_guard_allows_the_first_write_even_when_empty(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    empty = pd.DataFrame({"a": pd.Series([], dtype="int64")})

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "some_table", empty, refuse_regression=True)
        row_count = conn.execute("SELECT COUNT(*) FROM some_table").fetchone()[0]

    assert row_count == 0


def test_write_dataframe_guard_allows_growth_and_equal_counts(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    first = pd.DataFrame({"a": [1, 2, 3]})
    grown = pd.DataFrame({"a": [1, 2, 3, 4]})

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "some_table", first, refuse_regression=True)
        write_dataframe(conn, "some_table", first, refuse_regression=True)
        write_dataframe(conn, "some_table", grown, refuse_regression=True)

        row_count = conn.execute("SELECT COUNT(*) FROM some_table").fetchone()[0]

    assert row_count == 4
