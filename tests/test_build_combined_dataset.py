"""Offline tests for the coverage view and scripts/build_combined_dataset.py (Story 1.7).

Covers `kaggle_jolpica_coverage`'s AD-2 tagging directly against fixtures
(all five statuses: match/kaggle_only/jolpica_only/row_count_diverges/
no_data), `combined_results`/combined standings construction from those
tags, the missing-prerequisite fail-fast case, and graceful degradation
when a live Jolpica fetch/load fails mid-run. The isolated-subprocess
Jolpica fetch is monkeypatched out at its seam (AD-11), mirroring
`test_pull_fastf1_data.py`.

Fixture season (tests/fixtures/combined/): round 1 = match (2 Kaggle rows,
2 Jolpica rows, equal counts); round 2 = kaggle_only (2 Kaggle rows, no
Jolpica); round 3 = jolpica_only (no Kaggle rows, 2 Jolpica rows); round 4
= row_count_diverges (2 Kaggle rows, 3 Jolpica rows); round 5 = no_data (on
the `races` calendar, zero rows in either source).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from f1_analytics.config import PROJECT_ROOT
from f1_analytics.data_sources.jolpica_loader import load_and_map_season_results
from f1_analytics.database.duckdb_io import connect_duckdb, write_dataframe


COMBINED_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "combined"
KAGGLE_FIXTURE_DIR = COMBINED_FIXTURE_DIR / "kaggle"
JOLPICA_DUMP_DIR = COMBINED_FIXTURE_DIR / "jolpica_dump"

COVERAGE_VIEW_SQL_PATH = PROJECT_ROOT / "sql" / "kaggle_jolpica_coverage.sql"
VALIDATION_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "validation"

_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_combined_dataset.py"
_spec = importlib.util.spec_from_file_location("build_combined_dataset", _SCRIPT_PATH)
_build_combined_dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build_combined_dataset)
build_combined_dataset_main = _build_combined_dataset.main

EXPECTED_STATUS_BY_ROUND = {
    1: "match",
    2: "kaggle_only",
    3: "jolpica_only",
    4: "row_count_diverges",
    5: "no_data",
}


def _kaggle_results() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "results.csv")


def _races() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "races.csv")


def _drivers() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "drivers.csv")


def _constructors() -> pd.DataFrame:
    return pd.read_csv(KAGGLE_FIXTURE_DIR / "constructors.csv")


def _seed_curated_tables(db_path: Path) -> None:
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "results", _kaggle_results())
        write_dataframe(conn, "races", _races())
        write_dataframe(conn, "drivers", _drivers())
        write_dataframe(conn, "constructors", _constructors())


def _fake_fetch(status: str, fixture_name: str | None):
    """Build a fetch seam matching build_combined_dataset's (season, output_dir)
    -> dict contract: copies a fixture Jolpica dump for a "pass" status, and
    reports a simulated failure otherwise -- without ever shelling out to
    `uv run --isolated`.
    """

    def fetch(season: int, output_dir: Path) -> dict:
        if status != "pass":
            return {"season": season, "status": status, "exception": "SimulatedFetchFailure: boom"}
        output_dir.mkdir(parents=True, exist_ok=True)
        source_dir = JOLPICA_DUMP_DIR / fixture_name
        for filename in ("race_results.csv", "counts.json"):
            shutil.copy(source_dir / filename, output_dir / filename)
        return {"season": season, "status": "pass"}

    return fetch


# --- kaggle_jolpica_coverage.sql: the AD-2 arbiter, tested directly against
# fixtures rather than only through the full build (isolates a future view
# regression from a future orchestration regression).


def test_coverage_view_tags_all_five_ad2_statuses_directly(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    jolpica_results = load_and_map_season_results(
        JOLPICA_DUMP_DIR / "normal_season", _drivers(), _constructors(), season=2026
    )

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "results", _kaggle_results())
        write_dataframe(conn, "races", _races())
        write_dataframe(conn, "raw_jolpica_results", jolpica_results)
        conn.execute(COVERAGE_VIEW_SQL_PATH.read_text())
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage ORDER BY round").fetch_df()

    assert coverage.set_index("round")["status"].to_dict() == EXPECTED_STATUS_BY_ROUND

    row4 = coverage[coverage["round"] == 4].iloc[0]
    assert row4["kaggle_row_count"] == 2
    assert row4["jolpica_row_count"] == 3

    row5 = coverage[coverage["round"] == 5].iloc[0]
    assert row5["kaggle_row_count"] == 0
    assert row5["jolpica_row_count"] == 0


def test_coverage_view_is_the_only_place_the_row_count_comparison_happens(tmp_path: Path):
    # An empty raw_jolpica_results table (as if nothing was ever fetched)
    # must still let the view run -- every round reads as kaggle_only or
    # no_data, never an error from a missing/None comparison.
    db_path = tmp_path / "test.duckdb"
    empty_jolpica = load_and_map_season_results(
        JOLPICA_DUMP_DIR / "normal_season", _drivers(), _constructors(), season=2026
    ).iloc[0:0]

    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "results", _kaggle_results())
        write_dataframe(conn, "races", _races())
        write_dataframe(conn, "raw_jolpica_results", empty_jolpica)
        conn.execute(COVERAGE_VIEW_SQL_PATH.read_text())
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage ORDER BY round").fetch_df()

    assert coverage.set_index("round")["status"].to_dict() == {
        1: "kaggle_only",
        2: "kaggle_only",
        3: "no_data",
        4: "kaggle_only",
        5: "no_data",
    }


# --- build_combined_results()/build_combined_standings(): function-level
# construction tests against the same fixtures.


def test_build_combined_results_applies_ad2_precedence_reading_view_tags():
    coverage = pd.DataFrame(
        [
            {"season": 2026, "round": 1, "status": "match"},
            {"season": 2026, "round": 2, "status": "kaggle_only"},
            {"season": 2026, "round": 3, "status": "jolpica_only"},
            {"season": 2026, "round": 4, "status": "row_count_diverges"},
            {"season": 2026, "round": 5, "status": "no_data"},
        ]
    )
    jolpica_results = load_and_map_season_results(
        JOLPICA_DUMP_DIR / "normal_season", _drivers(), _constructors(), season=2026
    )

    combined = _build_combined_dataset.build_combined_results(coverage, _kaggle_results(), jolpica_results)

    assert set(combined.loc[combined["round"] == 1, "source"]) == {"kaggle"}
    assert set(combined.loc[combined["round"] == 2, "source"]) == {"kaggle"}
    assert set(combined.loc[combined["round"] == 3, "source"]) == {"jolpica"}
    assert set(combined.loc[combined["round"] == 4, "source"]) == {"kaggle"}
    assert 5 not in set(combined["round"])
    # row_count_diverges keeps Kaggle's 2 rows, never Jolpica's 3.
    assert len(combined[combined["round"] == 4]) == 2


def test_build_combined_standings_reuses_compute_cumulative_standings_and_tags_source():
    coverage = pd.DataFrame(
        [
            {"season": 2026, "round": 1, "status": "match"},
            {"season": 2026, "round": 2, "status": "kaggle_only"},
            {"season": 2026, "round": 3, "status": "jolpica_only"},
            {"season": 2026, "round": 4, "status": "row_count_diverges"},
        ]
    )
    jolpica_results = load_and_map_season_results(
        JOLPICA_DUMP_DIR / "normal_season", _drivers(), _constructors(), season=2026
    )
    combined_results = _build_combined_dataset.build_combined_results(coverage, _kaggle_results(), jolpica_results)

    driver_standings, constructor_standings = _build_combined_dataset.build_combined_standings(
        combined_results, _races()
    )

    assert {"cumulative_points", "cumulative_wins", "standing_rank", "source"} <= set(driver_standings.columns)
    assert {"cumulative_points", "cumulative_wins", "standing_rank", "source"} <= set(constructor_standings.columns)

    ver = driver_standings[driver_standings["driver_id"] == "verstappen"].set_index("round")
    # 25 points every round he's classified P1 across all four rounds
    # (kaggle rounds 1/2/4, jolpica round 3) -> cumulative 25/50/75/100.
    assert ver.loc[1, "cumulative_points"] == 25
    assert ver.loc[2, "cumulative_points"] == 50
    assert ver.loc[3, "cumulative_points"] == 75
    assert ver.loc[4, "cumulative_points"] == 100
    assert ver.loc[1, "source"] == "kaggle"
    assert ver.loc[3, "source"] == "jolpica"
    assert ver.loc[4, "source"] == "kaggle"  # row_count_diverges kept Kaggle's row


# --- main(): the full orchestration, against a seeded tmp DuckDB and a
# fake (never-shells-out) fetch.


def test_main_builds_combined_tables_and_tags_all_five_ad2_statuses(tmp_path: Path, capsys: pytest.CaptureFixture):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fetch = _fake_fetch("pass", "normal_season")

    exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage ORDER BY round").fetch_df()
        combined_results = conn.execute("SELECT * FROM combined_results ORDER BY round, driver_id").fetch_df()

    assert coverage.set_index("round")["status"].to_dict() == EXPECTED_STATUS_BY_ROUND

    assert set(combined_results.loc[combined_results["round"] == 1, "source"]) == {"kaggle"}
    assert set(combined_results.loc[combined_results["round"] == 2, "source"]) == {"kaggle"}
    assert set(combined_results.loc[combined_results["round"] == 3, "source"]) == {"jolpica"}
    assert set(combined_results.loc[combined_results["round"] == 4, "source"]) == {"kaggle"}
    assert 5 not in set(combined_results["round"])  # no_data round: absent, per the I/O matrix
    assert len(combined_results[combined_results["round"] == 4]) == 2  # Kaggle's rows kept, not Jolpica's 3

    captured = capsys.readouterr()
    assert "row_count_diverges deviations (1 round(s)" in captured.out
    assert "season 2026 round 4" in captured.out


def test_main_builds_combined_standings_tables(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fetch = _fake_fetch("pass", "normal_season")

    build_combined_dataset_main(season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch)

    with connect_duckdb(db_path, read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        driver_standings = conn.execute(
            "SELECT * FROM combined_driver_standings_by_round ORDER BY round"
        ).fetch_df()

    assert {"combined_results", "combined_driver_standings_by_round", "combined_constructor_standings_by_round"} <= tables
    ver = driver_standings[driver_standings["driver_id"] == "verstappen"].set_index("round")
    assert ver.loc[4, "cumulative_points"] == 100
    assert ver.loc[4, "source"] == "kaggle"


def test_main_prints_no_deviations_message_when_nothing_diverges(tmp_path: Path, capsys: pytest.CaptureFixture):
    db_path = tmp_path / "test.duckdb"
    # Drop round 4's Kaggle rows so nothing diverges in this run.
    kaggle_no_diverge = _kaggle_results()
    kaggle_no_diverge = kaggle_no_diverge[kaggle_no_diverge["round"] != 4]
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "results", kaggle_no_diverge)
        write_dataframe(conn, "races", _races())
        write_dataframe(conn, "drivers", _drivers())
        write_dataframe(conn, "constructors", _constructors())

    fetch = _fake_fetch("pass", "normal_season")
    build_combined_dataset_main(season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch)

    captured = capsys.readouterr()
    assert "no row_count_diverges deviations" in captured.out


def test_main_degrades_gracefully_when_jolpica_fetch_fails(tmp_path: Path, capsys: pytest.CaptureFixture):
    # A live Jolpica fetch failure must never abort the build: it degrades
    # to zero Jolpica rows for this run, and the coverage view still tags
    # correctly from whatever landed (never a guessed/fabricated row).
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fetch = _fake_fetch("failed", None)

    exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage ORDER BY round").fetch_df()
        combined_results = conn.execute("SELECT * FROM combined_results").fetch_df()

    status_by_round = coverage.set_index("round")["status"].to_dict()
    assert status_by_round[1] == "kaggle_only"  # was "match"; no Jolpica rows landed this run
    assert status_by_round[3] == "no_data"  # was "jolpica_only"; genuinely no rows from either source now
    assert status_by_round[4] == "kaggle_only"  # was "row_count_diverges"
    assert set(combined_results["round"]) == {1, 2, 4}

    captured = capsys.readouterr()
    assert "Jolpica fetch did not land season 2026 data" in captured.out


def test_main_degrades_gracefully_when_jolpica_load_fails(tmp_path: Path, capsys: pytest.CaptureFixture):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fetch = _fake_fetch("pass", "unresolved_id")

    exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Jolpica load failed" in captured.out
    assert "unknown_driver" in captured.out

    with connect_duckdb(db_path, read_only=True) as conn:
        combined_results = conn.execute("SELECT * FROM combined_results").fetch_df()

    assert set(combined_results["source"]) == {"kaggle"}


def test_main_reuses_previous_jolpica_data_when_a_later_fetch_regresses(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    db_path = tmp_path / "test.duckdb"
    jolpica_raw_dir = tmp_path / "jolpica_raw"
    _seed_curated_tables(db_path)

    good_fetch = _fake_fetch("pass", "normal_season")
    first_exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=jolpica_raw_dir, fetch=good_fetch
    )
    assert first_exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        landed_after_first_run = conn.execute("SELECT COUNT(*) FROM raw_jolpica_results").fetchone()[0]
    assert landed_after_first_run == 7  # normal_season fixture: rounds 1, 3, 4

    # A later run whose live Jolpica fetch degrades to just round 1 (the
    # "incomplete" fixture, 1 row) must not overwrite the 7-row table a
    # prior, more-complete run already landed.
    degraded_fetch = _fake_fetch("pass", "incomplete")
    second_exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=jolpica_raw_dir, fetch=degraded_fetch
    )
    assert second_exit_code == 0

    with connect_duckdb(db_path, read_only=True) as conn:
        landed_after_second_run = conn.execute("SELECT COUNT(*) FROM raw_jolpica_results").fetchone()[0]
        coverage = conn.execute("SELECT * FROM kaggle_jolpica_coverage ORDER BY round").fetch_df()
        combined_results = conn.execute("SELECT * FROM combined_results").fetch_df()

    assert landed_after_second_run == 7  # unchanged -- the shrinking write was refused
    # combined_results/coverage were rebuilt from the reused (still-good) data,
    # not degraded to round 1 only.
    assert coverage.set_index("round")["status"].to_dict() == EXPECTED_STATUS_BY_ROUND
    assert set(combined_results.loc[combined_results["round"] == 3, "source"]) == {"jolpica"}

    captured = capsys.readouterr()
    assert "raw_jolpica_results" in captured.out
    assert "reusing the previously-landed table for this run" in captured.out


def test_main_raises_named_error_when_curated_tables_are_missing(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    # Deliberately do NOT seed results/races/drivers/constructors -- as if
    # Story 1.5's build script never ran. Create the empty db file itself
    # so the failure comes from the named require_curated_tables() check,
    # not a bare "file does not exist".
    with connect_duckdb(db_path):
        pass

    fetch = _fake_fetch("pass", "normal_season")

    with pytest.raises(RuntimeError) as excinfo:
        build_combined_dataset_main(
            season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
        )

    assert "results" in str(excinfo.value)
    assert "races" in str(excinfo.value)
    assert "Story 1.5" in str(excinfo.value)


def test_main_raises_named_error_when_only_results_and_races_are_missing(tmp_path: Path):
    # The frozen I/O matrix names results/races explicitly as the
    # missing-prerequisite scenario; drivers/constructors alone present
    # must still name the missing results/races tables.
    db_path = tmp_path / "test.duckdb"
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "drivers", _drivers())
        write_dataframe(conn, "constructors", _constructors())

    fetch = _fake_fetch("pass", "normal_season")

    with pytest.raises(RuntimeError) as excinfo:
        build_combined_dataset_main(
            season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
        )

    assert "results" in str(excinfo.value)
    assert "races" in str(excinfo.value)


def test_main_raises_named_error_when_the_database_file_does_not_exist_at_all(tmp_path: Path):
    # main() opens the db read-only BEFORE require_curated_tables() ever
    # runs (connect_duckdb(db_path, read_only=True) doesn't create a
    # missing file the way the read/write connection does) -- a totally
    # unbuilt database must still fail with the same clear, named error,
    # never a raw duckdb.IOException surfacing from inside connect_duckdb.
    db_path = tmp_path / "never_built.duckdb"  # deliberately never created
    fetch = _fake_fetch("pass", "normal_season")

    with pytest.raises(RuntimeError) as excinfo:
        build_combined_dataset_main(
            season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
        )

    assert "Story 1.5" in str(excinfo.value)
    assert str(db_path) in str(excinfo.value)


# --- Story 1.8: advisory validation + source_load logging ----------------


def test_main_logs_source_load_rows_for_kaggle_and_jolpica(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    _seed_curated_tables(db_path)
    fetch = _fake_fetch("pass", "normal_season")

    exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        combined_results = conn.execute("SELECT * FROM combined_results").fetch_df()
        load_log = conn.execute("SELECT * FROM source_load_log ORDER BY source_name").fetch_df()

    expected_kaggle_count = int((combined_results["source"] == "kaggle").sum())
    expected_jolpica_count = int((combined_results["source"] == "jolpica").sum())

    assert set(load_log["source_name"]) == {"kaggle", "jolpica"}
    assert (load_log["table_name"] == "combined_results").all()
    kaggle_row = load_log[load_log["source_name"] == "kaggle"].iloc[0]
    jolpica_row = load_log[load_log["source_name"] == "jolpica"].iloc[0]
    assert kaggle_row["row_count"] == expected_kaggle_count
    assert jolpica_row["row_count"] == expected_jolpica_count

    with connect_duckdb(db_path, read_only=True) as conn:
        registry = conn.execute("SELECT * FROM source_registry").fetch_df()
    assert set(registry["source_name"]) == {"kaggle", "jolpica"}


def test_main_logs_a_combined_results_orphan_violation_and_still_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    # orphan_referential/results.csv carries a "ghost_driver" row absent
    # from drivers.csv. With the Jolpica fetch degraded (kaggle_only for
    # this round), that Kaggle row flows straight into combined_results
    # unchanged -- so the orphan must surface as a failing validation row
    # for BOTH `results` and `combined_results`, not curated alone.
    db_path = tmp_path / "test.duckdb"
    scenario_dir = VALIDATION_FIXTURE_DIR / "orphan_referential"
    with connect_duckdb(db_path) as conn:
        write_dataframe(conn, "results", pd.read_csv(scenario_dir / "results.csv"))
        write_dataframe(conn, "races", pd.read_csv(scenario_dir / "races.csv"))
        write_dataframe(conn, "drivers", pd.read_csv(scenario_dir / "drivers.csv"))
        write_dataframe(conn, "constructors", pd.read_csv(scenario_dir / "constructors.csv"))
    fetch = _fake_fetch("failed", None)

    exit_code = build_combined_dataset_main(
        season=2026, db_path=db_path, jolpica_raw_dir=tmp_path / "jolpica_raw", fetch=fetch
    )

    assert exit_code == 0
    with connect_duckdb(db_path, read_only=True) as conn:
        findings = conn.execute(
            "SELECT * FROM validation_results "
            "WHERE column_name = 'driver_id' AND check_type = 'referential_integrity'"
        ).fetch_df()
        combined_results = conn.execute("SELECT * FROM combined_results").fetch_df()

    # round 2 is a clean round (both drivers resolve) -- only round 1's
    # ghost_driver row is the orphan.
    assert set(combined_results["driver_id"]) == {"verstappen", "ghost_driver", "hamilton"}

    findings_by_table = findings.set_index("table_name")
    assert not findings_by_table.loc["results", "passed"]
    assert not findings_by_table.loc["combined_results", "passed"]
    assert findings_by_table.loc["combined_results", "orphan_count"] == 1

    captured = capsys.readouterr()
    assert "validation" in captured.out
    assert "FAILED" in captured.out


# --- run_fetch_subprocess(): the real, live-Jolpica code path every actual
# invocation of the script takes (every other test above injects a fake
# `fetch=`) -- exercised here with `subprocess.run` monkeypatched out so
# broken CLI wiring fails a test instead of silently degrading to
# Kaggle-only in production with zero signal.


def test_fetch_script_path_resolves_to_a_real_file():
    assert _build_combined_dataset.FETCH_SCRIPT_PATH.is_file()


def test_run_fetch_subprocess_constructs_the_correct_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured_commands: list[list[str]] = []

    class _FakeCompleted:
        stdout = json.dumps({"season": 2026, "status": "pass", "row_count": 2, "rounds": [1]})
        stderr = ""
        returncode = 0

    def _fake_run(command, **kwargs):
        captured_commands.append(command)
        return _FakeCompleted()

    monkeypatch.setattr(_build_combined_dataset.subprocess, "run", _fake_run)

    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "2026"

    result = _build_combined_dataset.run_fetch_subprocess(2026, cache_dir, output_dir)

    assert result == {"season": 2026, "status": "pass", "row_count": 2, "rounds": [1]}
    assert len(captured_commands) == 1
    command = captured_commands[0]
    assert str(_build_combined_dataset.FETCH_SCRIPT_PATH) in command
    assert command[command.index("--season") + 1] == "2026"
    assert command[command.index("--cache-dir") + 1] == str(cache_dir)
    assert command[command.index("--output-dir") + 1] == str(output_dir)


def test_run_fetch_subprocess_preserves_empty_status_without_fabricating_an_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # jolpica_fetch.py's "empty" status (a genuinely rowless season) is not
    # an error -- run_fetch_subprocess must never overwrite it with a
    # fabricated "failed"/"fetch subprocess exited ..." message just
    # because the subprocess's own exit code happened to be non-zero.
    class _FakeCompleted:
        stdout = json.dumps({"season": 2026, "status": "empty", "row_count": 0})
        stderr = "some stray stderr noise"
        returncode = 1

    monkeypatch.setattr(_build_combined_dataset.subprocess, "run", lambda command, **kwargs: _FakeCompleted())

    result = _build_combined_dataset.run_fetch_subprocess(2026, tmp_path / "cache", tmp_path / "2026")

    assert result == {"season": 2026, "status": "empty", "row_count": 0}
    assert "exception" not in result


def test_run_fetch_subprocess_treats_non_dict_json_as_a_parse_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Valid JSON that isn't an object (a bare list here) must degrade the
    # same way a JSON parse failure does, not crash on a later result.get(...).
    class _FakeCompleted:
        stdout = json.dumps([1, 2, 3])
        stderr = "boom"
        returncode = 1

    monkeypatch.setattr(_build_combined_dataset.subprocess, "run", lambda command, **kwargs: _FakeCompleted())

    result = _build_combined_dataset.run_fetch_subprocess(2026, tmp_path / "cache", tmp_path / "2026")

    assert result["status"] == "failed"
    assert result["season"] == 2026
    assert "boom" in result["exception"]


def test_run_fetch_subprocess_degrades_gracefully_on_a_mkdir_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A real OSError (permission denied, disk full, ...) from cache_dir/
    # output_dir creation must be a statused failure like every other
    # failure mode here, never an uncaught crash that takes down the build.
    def _raise_permission_denied(self, *args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "mkdir", _raise_permission_denied)

    result = _build_combined_dataset.run_fetch_subprocess(2026, tmp_path / "cache", tmp_path / "2026")

    assert result["status"] == "failed"
    assert "Permission denied" in result["exception"]
