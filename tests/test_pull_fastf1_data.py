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
VALIDATION_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "validation"

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


# --- Story 1.8: advisory validation + source_load logging ----------------


def test_main_logs_a_curated_null_violation_and_still_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture):
    db_path = tmp_path / "test.duckdb"
    # null_violation/drivers.csv carries a driver row with a NULL driver_id
    # (unreachable by the fastf1 fixture's VER/HAM/ALO codes, so it never
    # participates in id-mapping) -- exercises the drivers.driver_id
    # null-rate check without disturbing a normal race landing.
    drivers = pd.read_csv(VALIDATION_FIXTURE_DIR / "null_violation" / "drivers.csv")
    constructors = pd.read_csv(VALIDATION_FIXTURE_DIR / "null_violation" / "constructors.csv")
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "drivers", drivers)
        write_dataframe(conn, "constructors", constructors)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    targets = (("Normal", "Test Grand Prix"),)
    fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})

    exit_code = pull_fastf1_data_main(
        targets=targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        findings = conn.execute(
            "SELECT * FROM validation_results WHERE table_name = 'drivers' AND column_name = 'driver_id'"
        ).fetch_df()
        laps_count = conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps").fetchone()[0]

    assert len(findings) == 1
    assert not findings["passed"].iloc[0]
    assert findings["null_count"].iloc[0] == 1
    assert laps_count == 6  # the race itself still landed normally

    captured = capsys.readouterr()
    assert "validation" in captured.out
    assert "FAILED" in captured.out


def test_main_logs_an_orphan_in_raw_fastf1_laps_reached_through_the_real_mapping_pipeline(
    tmp_path: Path,
):
    """A raw_fastf1_laps orphan can only arise across two runs: within a
    single run, `map_driver_ids` always resolves against the exact same
    `drivers` snapshot validation later reads, so nothing can be orphaned
    yet. Here, run 1 lands a real race (via the actual FastF1
    fetch->id-map->write pipeline, not a synthetic frame) that includes
    Alonso; the curated `drivers` roster is then rebuilt without Alonso
    (as Story 1.5's build script legitimately might); run 2 lands a
    different, Alonso-free race whose smaller frame trips the
    write-regression guard, so `raw_fastf1_laps` keeps run 1's rows --
    including Alonso's, now an orphan against the new `drivers` table.
    This proves `pull_fastf1_data.py`'s VALIDATION_TABLES/`checks.py`
    registry wiring actually fires for `raw_fastf1_laps`, not just
    `run_validations()` in isolation.
    """
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    first_targets = (("Normal", "Test Grand Prix"),)
    first_fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})
    first_exit_code = pull_fastf1_data_main(
        targets=first_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=first_fetch
    )
    assert first_exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        alonso_laps_before = conn.execute(
            "SELECT COUNT(*) FROM raw_fastf1_laps WHERE driver_id = 'alonso'"
        ).fetchone()[0]
    assert alonso_laps_before == 1

    # A curated-roster rebuild (Story 1.5) that drops Alonso -- real FastF1
    # rows landed under his driver_id in run 1 are now orphaned.
    drivers_without_alonso = pd.read_csv(KAGGLE_FIXTURE_DIR / "f1_drivers.csv")
    drivers_without_alonso = drivers_without_alonso[drivers_without_alonso["driver_id"] != "alonso"]
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "drivers", drivers_without_alonso)

    # A second, Alonso-free race lands cleanly this run (its VER code still
    # maps fine) -- but its 2-lap frame is smaller than the 6 rows already
    # landed, so write_table_unless_regressed refuses the write and
    # raw_fastf1_laps keeps run 1's rows, orphan included.
    second_targets = (("VerOnly", "Solo Grand Prix"),)
    second_fetch = _fake_fetch({"VerOnly"}, {"VerOnly": "ver_only_race"})
    second_exit_code = pull_fastf1_data_main(
        targets=second_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=second_fetch
    )

    assert second_exit_code == 0  # VerOnly landed this run
    with connect_duckdb(db_path, read_only=True) as conn:
        laps_count = conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps").fetchone()[0]
        finding = conn.execute(
            "SELECT * FROM validation_results "
            "WHERE table_name = 'raw_fastf1_laps' AND column_name = 'driver_id' "
            "AND check_type = 'referential_integrity' "
            "ORDER BY checked_at"
        ).fetch_df()

    assert laps_count == 6  # the refused write kept run 1's table intact
    assert len(finding) == 2  # one logged row per run
    assert finding["passed"].iloc[0]  # run 1: alonso was still a valid driver
    assert not finding["passed"].iloc[-1]  # run 2: alonso is now orphaned
    assert finding["orphan_count"].iloc[-1] == 1


def test_main_logs_source_load_only_for_tables_this_runs_writes_touched(tmp_path: Path):
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
        load_log = conn.execute("SELECT * FROM source_load_log").fetch_df()

    assert set(load_log["table_name"]) == {"raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather"}
    assert (load_log["source_name"] == "fastf1").all()
    laps_row = load_log[load_log["table_name"] == "raw_fastf1_laps"].iloc[0]
    assert laps_row["row_count"] == 6


def test_a_run_where_every_race_fails_after_a_prior_success_logs_no_stale_source_load_row(
    tmp_path: Path,
):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fastf1_raw_dir = tmp_path / "fastf1_raw"

    good_targets = (("Normal", "Test Grand Prix"),)
    good_fetch = _fake_fetch({"Normal"}, {"Normal": "normal_race"})
    first_exit_code = pull_fastf1_data_main(
        targets=good_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=good_fetch
    )
    assert first_exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        first_load_log_count = conn.execute(
            "SELECT COUNT(*) FROM source_load_log WHERE table_name = 'raw_fastf1_laps'"
        ).fetchone()[0]
    assert first_load_log_count == 1

    # Every race fails this run -- laps_frames stays empty, so the write
    # (and thus the source_load row) must never happen, even though
    # raw_fastf1_laps still exists from the prior successful run.
    failing_fetch = _fake_fetch(set(), {})
    second_exit_code = pull_fastf1_data_main(
        targets=good_targets, season=2026, fastf1_raw_dir=fastf1_raw_dir, db_path=db_path, fetch=failing_fetch
    )
    assert second_exit_code == 1

    with connect_duckdb(db_path, read_only=True) as conn:
        load_log = conn.execute("SELECT * FROM source_load_log WHERE table_name = 'raw_fastf1_laps'").fetch_df()
        laps_count = conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps").fetchone()[0]

    # Still just the one row from the first run -- no stale/duplicate
    # source_load row was logged for a write that never happened.
    assert len(load_log) == 1
    assert laps_count == 6  # the prior run's table is untouched
