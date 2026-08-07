"""Offline integration tests for the read -> build -> write pipeline (AC 1, 4).

Drives the same flow scripts/build_f1_dataset.py wires (orchestration-shell
role: no business logic of its own), against the Task-2 fixtures and a
tmp_path DuckDB file — never the real dataset, never the network.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from f1_analytics.config import PROJECT_ROOT
from f1_analytics.data_sources.kaggle_csv import RAW_FILES
from f1_analytics.database.duckdb_io import connect_duckdb


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kaggle_csv"

_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_f1_dataset.py"
_spec = importlib.util.spec_from_file_location("build_f1_dataset", _SCRIPT_PATH)
_build_f1_dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build_f1_dataset)
build_f1_dataset_main = _build_f1_dataset.main


def _build_and_list_tables(raw_dir: Path, db_path: Path) -> list[str]:
    build_f1_dataset_main(raw_dir=raw_dir, db_path=db_path)

    with connect_duckdb(db_path, read_only=True) as conn:
        return [row[0] for row in conn.execute("SHOW TABLES").fetchall()]


def test_full_pipeline_lands_all_19_raw_and_curated_tables(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    tables = _build_and_list_tables(FIXTURE_DIR, db_path)

    expected_raw_tables = {f"raw_{name}" for name in RAW_FILES}
    expected_curated_tables = {
        "races",
        "results",
        "drivers",
        "constructors",
        "circuits",
        "qualifying",
        "race_results_enriched",
        "driver_standings_by_round",
        "constructor_standings_by_round",
        "final_driver_standings",
        "final_constructor_standings",
    }

    assert set(tables) == expected_raw_tables | expected_curated_tables
    assert len(tables) == 19


def test_pipeline_fails_fast_with_a_named_error_when_a_csv_is_missing(tmp_path: Path):
    incomplete_raw_dir = tmp_path / "incomplete_raw"
    incomplete_raw_dir.mkdir()
    for filename in RAW_FILES.values():
        shutil.copy(FIXTURE_DIR / filename, incomplete_raw_dir / filename)
    (incomplete_raw_dir / "f1_qualifying.csv").unlink()

    db_path = tmp_path / "test.duckdb"

    with pytest.raises(FileNotFoundError) as excinfo:
        _build_and_list_tables(incomplete_raw_dir, db_path)

    assert "f1_qualifying.csv" in str(excinfo.value)
