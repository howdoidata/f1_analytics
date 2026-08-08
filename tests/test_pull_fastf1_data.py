"""Offline test for the FastF1 pull orchestration entry point (Story 1.6).

Drives scripts/pull_fastf1_data.py's per-race loop against fixture CSVs
with the isolated-subprocess call monkeypatched out at its seam (AD-11):
one race's simulated failure -- at the fetch stage or the mapping stage --
must never stop the remaining races from landing.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.config import PROJECT_ROOT
from f1_analytics.database.duckdb_io import connect_duckdb, write_dataframe


FASTF1_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fastf1_csv"
KAGGLE_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kaggle_csv"

_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "pull_fastf1_data.py"
_spec = importlib.util.spec_from_file_location("pull_fastf1_data", _SCRIPT_PATH)
_pull_fastf1_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pull_fastf1_data)
pull_fastf1_data_main = _pull_fastf1_data.main


def _seed_curated_tables(db_path: Path) -> None:
    drivers = pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_drivers.csv")
    constructors = pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_constructors.csv")
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "drivers", drivers)
        write_dataframe(conn, "constructors", constructors)


def _fake_fetch(succeeding_labels: set[str], fixture_by_label: dict[str, str]):
    """Build a fetch seam matching run_fetch_subprocess's (label, event,
    output_dir) -> dict contract: copies a fixture race dump for races that
    should "succeed", and reports a simulated failure for the rest --
    without ever shelling out to `uv run --isolated`.
    """

    def fetch(label: str, event: str, output_dir: Path) -> dict:
        if label not in succeeding_labels:
            return {"race_label": label, "status": "failed", "exception": "SimulatedFetchFailure: boom"}
        output_dir.mkdir(parents=True, exist_ok=True)
        source_dir = FASTF1_FIXTURE_DIR / fixture_by_label[label]
        for filename in ("laps.csv", "weather.csv", "counts.json"):
            shutil.copy(source_dir / filename, output_dir / filename)
        return {"race_label": label, "status": "pass"}

    return fetch


def test_one_race_fetch_failure_does_not_stop_the_others(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    targets = (("Normal", "Test Grand Prix"), ("Barcelona", "Spanish Grand Prix"))
    fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})

    exit_code = pull_fastf1_data_main(
        targets=targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        laps_labels = [row[0] for row in conn.execute("SELECT DISTINCT race_label FROM raw_fastf1_laps").fetchall()]
        stints_labels = [
            row[0] for row in conn.execute("SELECT DISTINCT race_label FROM raw_fastf1_stints").fetchall()
        ]
        weather_labels = [
            row[0] for row in conn.execute("SELECT DISTINCT race_label FROM raw_fastf1_weather").fetchall()
        ]

    assert laps_labels == ["Normal"]
    assert stints_labels == ["Normal"]
    assert weather_labels == ["Normal"]


def test_one_race_mapping_failure_does_not_stop_the_others(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    targets = (("Normal", "Test Grand Prix"), ("UnmappedDriver", "Bad Grand Prix"))
    fetch = _fake_fetch(
        {"Normal", "UnmappedDriver"},
        {"Normal": "normal_race", "UnmappedDriver": "unmapped_driver"},
    )

    exit_code = pull_fastf1_data_main(
        targets=targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        laps_labels = [row[0] for row in conn.execute("SELECT DISTINCT race_label FROM raw_fastf1_laps").fetchall()]

    assert laps_labels == ["Normal"]


def test_all_races_landed_carries_every_row_id_mapped(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    targets = (("Normal", "Test Grand Prix"),)
    fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})

    exit_code = pull_fastf1_data_main(
        targets=targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        laps = conn.execute("SELECT * FROM raw_fastf1_laps").fetch_df()

    assert len(laps) == 6
    assert laps["driver_id"].notna().all()
    assert laps["constructor_id"].notna().all()
    assert (laps["round"] == 1).all()  # from the normal_race fixture's counts.json


def test_all_races_failing_returns_nonzero_exit_and_writes_no_tables(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    targets = (("OnlyFailing", "Nonexistent Grand Prix"),)
    fetch = _fake_fetch(set(), {})

    exit_code = pull_fastf1_data_main(
        targets=targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=fetch
    )

    assert exit_code == 1
    with connect_duckdb(db_path, read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}

    assert "raw_fastf1_laps" not in tables


def test_pull_race_reports_a_clean_message_for_an_empty_fetch_status(tmp_path: Path):
    drivers = pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_drivers.csv")
    constructors = pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_constructors.csv")

    def fetch(label: str, event: str, output_dir: Path) -> dict:
        # Mirrors run_fetch_subprocess's contract for a still-future/
        # cancelled session: status "empty", no "exception" key at all.
        return {"race_label": label, "status": "empty", "lap_count": 0}

    outcome = _pull_fastf1_data.pull_race(
        "Barcelona", "Spanish Grand Prix", tmp_path / "Barcelona", 2026, fetch, drivers, constructors
    )

    assert outcome["status"] == "failed"
    assert outcome["stage"] == "fetch"
    assert "still-future or cancelled session" in outcome["detail"]
    assert "0 laps" in outcome["detail"]
    # Must be the clean message, not a dump of the raw fetch_result dict.
    assert "{" not in outcome["detail"]


def test_main_raises_named_error_when_curated_tables_are_missing(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    # Deliberately do NOT seed drivers/constructors -- as if Story 1.5's
    # build script (scripts/build_f1_dataset.py) never ran. Create the
    # empty db file itself so the failure comes from the named
    # require_curated_tables() check, not a bare "file does not exist".
    with connect_duckdb(db_path):
        pass

    targets = (("Normal", "Test Grand Prix"),)
    fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})

    with pytest.raises(RuntimeError) as excinfo:
        pull_fastf1_data_main(
            targets=targets, season=2026, fastf1_raw_dir=tmp_path / "fastf1_raw", db_path=db_path, fetch=fetch
        )

    assert "drivers" in str(excinfo.value)
    assert "constructors" in str(excinfo.value)
    assert "Story 1.5" in str(excinfo.value)


def test_a_later_run_landing_fewer_races_does_not_shrink_the_table(tmp_path: Path, capsys: pytest.CaptureFixture):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    good_targets = (("RaceA", "Race A Grand Prix"), ("RaceB", "Race B Grand Prix"))
    good_fetch = _fake_fetch({"RaceA", "RaceB"}, {"RaceA": "normal_race", "RaceB": "normal_race"})
    first_exit_code = pull_fastf1_data_main(
        targets=good_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=good_fetch
    )
    assert first_exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        landed_after_first_run = conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps").fetchone()[0]
    assert landed_after_first_run == 12  # two races x 6 laps (normal_race fixture)

    # A later run where RaceB transiently fails must never shrink the table
    # a prior, more-complete run already landed.
    degraded_fetch = _fake_fetch({"RaceA"}, {"RaceA": "normal_race"})
    second_exit_code = pull_fastf1_data_main(
        targets=good_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=degraded_fetch
    )

    assert second_exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        landed_after_second_run = conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps").fetchone()[0]
    assert landed_after_second_run == 12  # unchanged -- the shrinking write was refused

    captured = capsys.readouterr()
    assert "raw_fastf1_laps" in captured.out
    assert "keeping the previously-landed table" in captured.out
