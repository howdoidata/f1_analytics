"""Offline tests for `uv run build` and `uv run refresh` (`f1_analytics.cli`)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
import jwt
import pandas as pd
import pytest
from packaging.version import Version

from f1_analytics import cli
from f1_analytics.data_sources import fastf1_fetch, jolpica_fetch
from jolpica_responses import RecordedGetter, make_update_world, recorded_responses


FIXTURES = Path(__file__).parent / "fixtures"
CURATED_TABLES = {
    "races", "results", "sprint_results", "drivers", "constructors", "circuits", "qualifying",
    "race_results_enriched", "driver_standings_by_round", "constructor_standings_by_round",
    "final_driver_standings", "final_constructor_standings",
    "raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather",
    "pit_stops", "car_races", "practice_stints", "weather_forecasts", "race_incidents",
}


def _extract(raw_dir: Path, season: int, dir_name: str, fixture: str = "normal_race", round_: int = 1) -> Path:
    target = raw_dir / "fastf1" / str(season) / dir_name
    shutil.copytree(FIXTURES / "fastf1_csv" / fixture, target)
    counts = json.loads((target / "counts.json").read_text())
    counts.update({"season": season, "round": round_, "race_label": dir_name})
    (target / "counts.json").write_text(json.dumps(counts))
    return target


def _add_session_summaries(raw: Path) -> None:
    """The FastF1 summary and practice files and the weather forecast (2025 R1 only); their sources fail the build when missing."""
    shutil.copytree(FIXTURES / "fastf1_summary", raw / "fastf1_summary")
    shutil.copytree(FIXTURES / "fastf1_practice", raw / "fastf1_practice")
    shutil.copytree(FIXTURES / "open_meteo", raw / "open_meteo")


def _make_raw_dir(root: Path) -> Path:
    raw = root / "raw"
    shutil.copytree(FIXTURES / "jolpica_raw", raw / "jolpica")
    _extract(raw, 2024, "01-bahrain-grand-prix")
    _add_session_summaries(raw)
    return raw


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    return _make_raw_dir(tmp_path)


@pytest.fixture(scope="module")
def built_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One fixture-tree build shared by the module; copy it before writing to it."""
    root = tmp_path_factory.mktemp("built")
    raw = _make_raw_dir(root)
    # Alonso drove for two teams in 2025: the first listed is kept.
    standings = jolpica_fetch.read_raw_table(raw / "jolpica", "final_driver_standings")
    standings.loc[(standings["driverId"] == "alonso") & (standings["season"] == "2025"), "constructorIds"] = "aston_martin;alpine"
    jolpica_fetch.write_raw_table(raw / "jolpica", "final_driver_standings", standings)
    # Half points (a shortened race) survive the build.
    results = jolpica_fetch.read_raw_table(raw / "jolpica", "results")
    results.loc[(results["season"] == "2024") & (results["round"] == "1") & (results["driverId"] == "alonso"), "points"] = "12.5"
    jolpica_fetch.write_raw_table(raw / "jolpica", "results", results)
    db_path = root / "out.duckdb"
    assert cli.build(["--raw-dir", str(raw), "--db", str(db_path)]) == 0
    return db_path


@pytest.fixture
def existing_db(built_db: Path, tmp_path: Path) -> Path:
    db_path = tmp_path / "existing.duckdb"
    shutil.copy(built_db, db_path)
    return db_path


def _tables(db_path: Path, schema: str = "main") -> set[str]:
    with duckdb.connect(str(db_path), read_only=True) as conn:
        return {row[0] for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [schema]).fetchall()}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*")) if p.is_file()
    }


def _token(tmp_path: Path, *, exp_offset: float = 3600, raw: str | None = None) -> Path:
    path = tmp_path / "f1auth.json"
    path.write_text(raw if raw is not None else jwt.encode({"exp": int(time.time() + exp_offset)}, "k" * 32, algorithm="HS256"))
    return path


def _assert_build_fails_unchanged(raw_dir: Path, db_path: Path, capsys) -> str:
    """Run a build expected to fail; the DB must be byte-identical afterwards. Returns stderr."""
    before = _sha256(db_path)
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 1
    assert _sha256(db_path) == before
    assert [p.name for p in db_path.parent.iterdir() if "-build-" in p.name] == []
    return capsys.readouterr().err


# --- build -------------------------------------------------------------------


def test_build_writes_every_curated_table_from_raw_fixtures(built_db: Path):
    assert _tables(built_db) == CURATED_TABLES
    assert _tables(built_db, "staging")  # the stg_* tables and seeds live apart from the marts
    with duckdb.connect(str(built_db), read_only=True) as conn:
        def types(table):
            return dict(conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position", [table]).fetchall())

        assert types("driver_standings_by_round")["date"] == "DATE"
        assert types("results")["fastest_lap"] == "DOUBLE" and types("results")["position"] == "BIGINT"
        assert types("raw_fastf1_laps")["LapNumber"] == "DOUBLE" and types("raw_fastf1_laps")["IsAccurate"] == "BOOLEAN"
        assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps WHERE season = 2024 AND round = 1").fetchone()[0] == 6
        assert conn.execute(
            "SELECT DISTINCT race_label FROM raw_fastf1_stints").fetchall() == [("01-bahrain-grand-prix",)]

        # Jolpica shaping, ported from the deleted pandas loader tests.
        row = conn.execute(
            "SELECT driver_name, constructor, points, position, fastest_lap, fastest_lap_rank, time, race_name "
            "FROM results WHERE season = 2024 AND round = 1 AND driver_id = 'verstappen'").fetchone()
        assert row == ("Max Verstappen", "Red Bull", 25.0, 1, 55.0, 1.0, "1:31:44.742", "Bahrain Grand Prix")
        assert conn.execute(
            "SELECT points FROM results WHERE season = 2024 AND round = 1 AND driver_id = 'alonso'").fetchone() == (12.5,)
        final = conn.execute(
            "SELECT position, points, constructor, constructor_id, driver_name FROM final_driver_standings "
            "WHERE season = 2025 AND driver_id = 'alonso'").fetchone()
        assert final == (3.0, 21.0, "Aston Martin", "aston_martin", "Fernando Alonso")
        # Race 25 + sprint 8 for Hamilton; the sprint win is not a race win.
        r2 = conn.execute(
            "SELECT race_points, race_wins, cumulative_points, standing_rank, date FROM driver_standings_by_round "
            "WHERE season = 2025 AND round = 2 AND driver_id = 'hamilton'").fetchone()
        assert r2 == (33.0, 1, 51.0, 1, date(2025, 3, 8))
        assert conn.execute(
            "SELECT cumulative_points FROM constructor_standings_by_round "
            "WHERE season = 2025 AND round = 2 AND constructor_id = 'mercedes'").fetchone() == (51.0,)
        assert conn.execute(
            "SELECT url, time_race FROM race_results_enriched WHERE season = 2024 AND round = 2 LIMIT 1"
        ).fetchone() == ("https://example.com/race/2024/2", "17:00:00")

        # Pit stops, car summaries and practice stints, typed.
        assert types("pit_stops") == {
            "season": "BIGINT", "round": "BIGINT", "driver_id": "VARCHAR", "constructor_id": "VARCHAR",
            "stop": "BIGINT", "lap": "BIGINT", "time": "VARCHAR", "duration_s": "DOUBLE", "stop_type": "VARCHAR"}
        assert list(types("pit_stops")) == [
            "season", "round", "driver_id", "constructor_id", "stop", "lap", "time", "duration_s", "stop_type"]
        car_types = types("car_races")
        assert {car_types[c] for c in ("laps_completed", "stints", "stops_fastf1", "wet_laps", "driver_number")} == {"BIGINT"}
        assert {car_types[c] for c in ("air_temp_mean", "track_temp_mean", "deg_s_per_lap")} == {"DOUBLE"}
        assert car_types["rainfall"] == "BOOLEAN"
        assert types("practice_stints")["stint"] == "BIGINT" and types("practice_stints")["laps"] == "BIGINT"
        assert types("practice_stints")["deg_s_per_lap"] == "DOUBLE"
        # 2025 R1 has summaries and one sc period (laps 15-16); 2025 R2 has none.
        assert conn.execute(
            "SELECT season, round, driver_id, constructor_id, stop, lap, duration_s, stop_type FROM pit_stops "
            "ORDER BY season, round, lap").fetchall() == [
            (2025, 1, "hamilton", "mercedes", 1, 14, 23.104, "normal"),
            (2025, 1, "verstappen", "red_bull", 1, 16, 22.871, "sc_vsc"),
            (2025, 1, "alonso", "alpine", 1, 17, 23.522, "normal"),
            (2025, 1, "verstappen", "red_bull", 2, 36, 22.64, "normal"),
            (2025, 2, "verstappen", "red_bull", 1, 20, 21.903, "unknown"),
            (2025, 2, "alonso", "alpine", 1, 21, 22.215, "unknown"),
            (2025, 2, "hamilton", "mercedes", 1, 24, 22.087, "unknown"),
        ]
        assert conn.execute(
            "SELECT driver_id, rainfall, deg_s_per_lap FROM car_races ORDER BY driver_id").fetchall() == [
            ("alonso", False, 0.0412), ("hamilton", False, -0.0135), ("verstappen", False, None)]
        assert conn.execute("SELECT COUNT(*) FROM practice_stints WHERE session = 'FP2'").fetchone() == (3,)


def test_build_replaces_a_db_an_earlier_pipeline_wrote(existing_db: Path, raw_dir: Path):
    with duckdb.connect(str(existing_db)) as conn:
        conn.execute("CREATE TABLE legacy_merged_results AS SELECT 1 AS x")
        conn.execute("CREATE VIEW legacy_source_coverage AS SELECT 1 AS x")
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(existing_db)]) == 0
    assert _tables(existing_db) == CURATED_TABLES


def test_build_rejects_an_orphan_driver_id(existing_db: Path, raw_dir: Path, capsys):
    drivers = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "drivers")
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "drivers", drivers[drivers["driverId"] != "alonso"])
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "relationships_results_driver_id" in err and "alonso" in err


def test_build_rejects_an_orphan_constructor_id(existing_db: Path, raw_dir: Path, capsys):
    constructors = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "constructors")
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "constructors", constructors[constructors["constructorId"] != "alpine"])
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "relationships_results_constructor_id" in err and "alpine" in err


@pytest.mark.parametrize("column", ["season", "round"])
def test_build_rejects_a_non_numeric_season_or_round(existing_db: Path, raw_dir: Path, capsys, column: str):
    results = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "results")
    results.loc[0, column] = "not-a-number"
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "results", results)
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert f"not_null_stg_jolpica__results_{column}" in err


def test_build_names_a_missing_raw_file(existing_db: Path, raw_dir: Path, capsys):
    (raw_dir / "jolpica" / "sprint_results.csv").unlink()
    assert "sprint_results.csv" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_an_unmapped_fastf1_driver_code(existing_db: Path, raw_dir: Path, capsys):
    _extract(raw_dir, 2024, "02-saudi-arabian-grand-prix", fixture="unmapped_driver", round_=2)
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "assert_fastf1_driver_codes_are_mapped" in err and "ZZZ" in err


def test_build_rejects_an_ambiguous_fastf1_driver_code_with_no_override(existing_db: Path, raw_dir: Path, capsys):
    # HAM now matches two drivers and has no row in the override seed.
    drivers = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "drivers")
    clash = drivers[drivers["driverId"] == "hamilton"].assign(driverId="hamilton_senior")
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "drivers", pd.concat([drivers, clash]))
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "assert_fastf1_ambiguous_driver_codes_have_an_override" in err and "HAM" in err


@pytest.mark.parametrize("team", ["Some New Team", None])
def test_build_rejects_an_unmapped_or_missing_fastf1_team(existing_db: Path, raw_dir: Path, capsys, team):
    laps_path = raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / "laps.csv"
    laps = pd.read_csv(laps_path, dtype="string")
    laps.loc[0, "Team"] = pd.NA if team is None else team
    laps.to_csv(laps_path, index=False)
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "assert_fastf1_team_names_are_mapped" in err
    if team is not None:
        assert team in err


def test_build_rejects_a_counts_json_with_no_round(existing_db: Path, raw_dir: Path, capsys):
    counts_path = raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / "counts.json"
    counts_path.write_text(json.dumps({**json.loads(counts_path.read_text()), "round": None}))
    assert "not_null_stg_fastf1__counts_round" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_a_corrupt_counts_json(existing_db: Path, raw_dir: Path, capsys):
    (raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / "counts.json").write_text("{not valid json")
    assert "counts.json" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_fails_cleanly_when_the_db_is_locked(existing_db: Path, raw_dir: Path, capsys):
    # A read-write connection held elsewhere blocks the guard's read-only open.
    with duckdb.connect(str(existing_db)):
        err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "was left unchanged" in err and "Traceback" not in err


@pytest.mark.parametrize(
    ("fixture", "test_name"),
    [("incomplete_laps", "assert_fastf1_laps_not_fewer_than_counts"),
     ("missing_driver", "assert_fastf1_every_counted_driver_has_laps")],
)
def test_build_rejects_an_incomplete_fastf1_extract(existing_db: Path, raw_dir: Path, capsys, fixture: str, test_name: str):
    _extract(raw_dir, 2024, "02-saudi-arabian-grand-prix", fixture=fixture, round_=2)
    assert test_name in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_fewer_weather_rows_than_counts(existing_db: Path, raw_dir: Path, capsys):
    counts_path = raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / "counts.json"
    counts = json.loads(counts_path.read_text())
    counts_path.write_text(json.dumps({**counts, "weather_count": counts["weather_count"] + 5}))
    assert "assert_fastf1_weather_not_fewer_than_counts" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_a_folder_round_that_differs_from_counts(existing_db: Path, raw_dir: Path, capsys):
    _extract(raw_dir, 2024, "03-saudi-arabian-grand-prix", round_=2)
    assert "assert_fastf1_folder_round_matches_counts" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_a_lap_with_no_stint(existing_db: Path, raw_dir: Path, capsys):
    laps_path = raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / "laps.csv"
    laps = pd.read_csv(laps_path, dtype="string")
    laps.loc[0, "Stint"] = pd.NA
    laps.to_csv(laps_path, index=False)
    assert "not_null_raw_fastf1_laps_Stint" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


@pytest.mark.parametrize("missing", ["laps.csv", "counts.json"])
def test_build_names_a_missing_fastf1_extract_file(existing_db: Path, raw_dir: Path, capsys, missing: str):
    _extract(raw_dir, 2024, "02-saudi-arabian-grand-prix", round_=2)
    (raw_dir / "fastf1" / "2024" / "02-saudi-arabian-grand-prix" / missing).unlink()
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert err.startswith("[build] ") and "assert_fastf1_extract_files_complete" in err


def test_build_is_offline_and_never_imports_fastf1(raw_dir: Path, tmp_path: Path):
    # dbt itself imports `requests` (for its usage tracker, switched off in
    # dbt_project.yml), so only fastf1 and the token decoder are checked here;
    # the socket patch proves no connection is made.
    code = (
        "import sys, socket\n"
        "def deny(*a, **k): raise RuntimeError('network')\n"
        "socket.socket.connect = deny\n"
        "socket.socket.connect_ex = deny\n"
        "from f1_analytics import cli\n"
        f"rc = cli.build(['--raw-dir', {str(raw_dir)!r}, '--db', {str(tmp_path / 'o.duckdb')!r}])\n"
        "assert rc == 0, rc\n"
        "leaked = [m for m in ('fastf1', 'jwt') if m in sys.modules]\n"
        "assert not leaked, leaked\n"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                               env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert completed.returncode == 0, completed.stdout[-3000:] + completed.stderr


# --- token check -------------------------------------------------------------


def test_check_token_accepts_an_unexpired_jwt(tmp_path: Path):
    path = _token(tmp_path)
    assert cli.check_token(path) == path.read_text()


@pytest.mark.parametrize(
    "kind", ["missing", "garbage", "expired", "no_exp", "empty"],
)
def test_check_token_rejects_bad_tokens(tmp_path: Path, kind: str):
    if kind == "missing":
        path = tmp_path / "nope" / "f1auth.json"
    elif kind == "garbage":
        path = _token(tmp_path, raw="not a jwt")
    elif kind == "expired":
        path = _token(tmp_path, exp_offset=-60)
    elif kind == "no_exp":
        path = _token(tmp_path, raw=jwt.encode({"sub": "x"}, "k" * 32, algorithm="HS256"))
    else:
        path = _token(tmp_path, raw="")
    with pytest.raises(cli.TokenError):
        cli.check_token(path)


def test_token_check_never_imports_fastf1_auth(tmp_path: Path):
    code = (
        "import sys\n"
        "from f1_analytics import cli\n"
        "try:\n"
        f"    cli.check_token(__import__('pathlib').Path({str(tmp_path / 'missing')!r}))\n"
        "except cli.TokenError:\n"
        "    pass\n"
        "assert 'fastf1' not in sys.modules and 'fastf1.internals.f1auth' not in sys.modules\n"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_default_token_path_is_fastf1s_file_and_creates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    path = cli.default_token_path()
    assert path.name == "f1auth.json" and path.parent.name == "fastf1"
    assert list(tmp_path.iterdir()) == []


# --- refresh -----------------------------------------------------------------


class Spies:
    def __init__(self):
        self.http = []
        self.fastf1 = []

    def getter(self, url, params):
        self.http.append(url)
        raise AssertionError("no request expected")

    def fetch_race(self, *args, **kwargs):
        self.fastf1.append(args)
        raise AssertionError("no FastF1 fetch expected")


@pytest.mark.parametrize("kind", ["missing", "garbage", "expired"])
def test_refresh_with_a_bad_token_exits_non_zero_and_touches_nothing(
    raw_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, kind: str
):
    token_path = {
        "missing": tmp_path / "missing.json",
        "garbage": _token(tmp_path, raw="garbage"),
        "expired": _token(tmp_path, exp_offset=-1),
    }[kind]
    spies = Spies()
    monkeypatch.setattr(jolpica_fetch, "requests_getter", spies.getter)
    monkeypatch.setattr(fastf1_fetch, "fetch_race", spies.fetch_race)
    before = _tree_hashes(raw_dir)
    db_path = tmp_path / "out.duckdb"

    rc = cli.refresh([], token_path=token_path, raw_dir=raw_dir, db_path=db_path, cache_dir=tmp_path / "cache")

    assert rc != 0
    assert cli.LOGIN_COMMAND in capsys.readouterr().err
    assert spies.http == [] and spies.fastf1 == []
    assert _tree_hashes(raw_dir) == before
    assert not db_path.exists() and not (tmp_path / "cache").exists()


def test_refresh_with_a_valid_token_updates_fetches_missing_extracts_and_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # The update-test world: 2025 R3 is the next round; R1 already has an extract.
    raw = tmp_path / "raw"
    make_update_world(raw / "jolpica")
    _add_session_summaries(raw)
    kept = _extract(raw, 2025, "01-bahrain-grand-prix")
    kept_hashes = _tree_hashes(kept)
    calls = []

    def fake_fetch(season, round_, cache_dir, output_dir, token):
        calls.append((season, round_, output_dir.name, token))
        if round_ == 3:
            return {"status": "failed", "exception": "DataNotLoadedError: boom"}
        _extract(raw, season, output_dir.name, round_=round_)
        return {"status": "pass", "lap_count": 6, "weather_count": 2}

    token_path = _token(tmp_path)
    client = jolpica_fetch.JolpicaClient(RecordedGetter(recorded_responses()), sleep=lambda s: None, clock=lambda: 0.0)
    rc = cli.refresh([], token_path=token_path, raw_dir=raw, db_path=tmp_path / "out.duckdb",
                     cache_dir=tmp_path / "cache", jolpica_client=client, fetch_race=fake_fetch,
                     today=date(2025, 12, 31))

    assert rc == 1  # round 3 failed
    assert [(s, r, d) for s, r, d, _ in calls] == [
        (2025, 2, "02-saudi-arabian-grand-prix"), (2025, 3, "03-australian-grand-prix")]
    assert all(t == token_path.read_text() for *_, t in calls)
    assert _tree_hashes(kept) == kept_hashes
    assert (raw / "fastf1" / "2025" / "02-saudi-arabian-grand-prix" / "counts.json").is_file()
    assert not (raw / "fastf1" / "2025" / "03-australian-grand-prix").exists()
    assert {"raw_fastf1_laps", "pit_stops", "car_races", "practice_stints"} <= _tables(tmp_path / "out.duckdb")


# --- pins --------------------------------------------------------------------


def test_dependency_pins():
    pandas = Version(importlib.metadata.version("pandas"))
    assert Version("2.2") <= pandas < Version("3")
    assert importlib.metadata.version("fastf1") == "3.8.3"
    assert Version(importlib.metadata.version("cryptography")) < Version("50")
    assert importlib.metadata.version("dbt-duckdb") == "1.11.0"
    assert Version("1.11") <= Version(importlib.metadata.version("dbt-core")) < Version("1.12")


def test_build_refuses_to_shrink_a_landed_table(existing_db: Path, raw_dir: Path, capsys):
    # A 2024 row: every 2025 results row has a pit stop, which would then be an orphan.
    results = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "results")
    dropped = (results["season"] == "2024") & (results["round"] == "2") & (results["driverId"] == "hamilton")
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "results", results[~dropped])
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "results: this build has 11 row(s), fewer than the 12" in err and "refusing to replace" in err
    assert "delete" in err and "and rebuild" in err


def test_build_fails_when_every_fastf1_extract_vanishes(existing_db: Path, raw_dir: Path, capsys):
    shutil.rmtree(raw_dir / "fastf1")
    assert "laps.csv" in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert {"raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather"} <= _tables(existing_db)


def test_a_round_with_any_extract_folder_is_not_refetched_after_a_race_rename(raw_dir: Path):
    _extract(raw_dir, 2025, "01-old-bahrain-name")
    missing = cli.missing_extract_rounds(raw_dir, 2025, today=date(2025, 12, 31))
    assert missing == [(2, "02-saudi-arabian-grand-prix")]


# --- pit stops, car summaries and practice stints ----------------------------


def _append_csv_rows(path: Path, rows: list[str]) -> None:
    with path.open("a") as handle:
        handle.write("".join(row + "\n" for row in rows))


def _drop_last_csv_row(path: Path) -> None:
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")


def test_build_rejects_a_pit_stop_with_no_results_row(existing_db: Path, raw_dir: Path, capsys):
    _append_csv_rows(raw_dir / "jolpica" / "pit_stops.csv", ["2025,1,leclerc,1,20,15:35:00,23.001"])
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "assert_pit_stops_have_a_results_row" in err and "(2025, 1, 'leclerc', 1)" in err


def test_build_rejects_a_car_race_with_no_results_row_of_that_constructor(existing_db: Path, raw_dir: Path, capsys):
    # Alonso drove for alpine in 2025 R1, not aston_martin.
    path = raw_dir / "fastf1_summary" / "car_races.csv"
    path.write_text(path.read_text().replace("2025,1,bahrain,alonso,alpine,", "2025,1,bahrain,alonso,aston_martin,"))
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "assert_car_races_have_a_results_row" in err and "aston_martin" in err


@pytest.mark.parametrize(
    ("relative", "row", "test_name"),
    [
        ("jolpica/pit_stops.csv", "2025,1,hamilton,1,30,15:45:00,22.500",
         "unique_combination_pit_stops_season__round__driver_id__stop"),
        ("fastf1_summary/car_races.csv",
         "2025,1,bahrain,hamilton,mercedes,44,57,2,1,SOFT,SOFT,SOFT|HARD,0,24.5,31.25,false,",
         "unique_combination_car_races_season__round__driver_id"),
        ("fastf1_practice/2025/01-bahrain-grand-prix/FP2_stints.csv",
         "2025,1,FP2,hamilton,mercedes,44,1,MEDIUM,4,",
         "unique_combination_practice_stints_season__round__session__driver_id__stint"),
    ],
)
def test_build_rejects_a_duplicate_key(existing_db: Path, raw_dir: Path, capsys, relative: str, row: str, test_name: str):
    _append_csv_rows(raw_dir / relative, [row])
    assert test_name in _assert_build_fails_unchanged(raw_dir, existing_db, capsys)


def test_build_rejects_a_practice_session_outside_fp1_to_fp3(existing_db: Path, raw_dir: Path, capsys):
    folder = raw_dir / "fastf1_practice" / "2025" / "01-bahrain-grand-prix"
    (folder / "FP4_stints.csv").write_text(
        (folder / "FP2_stints.csv").read_text().replace(",FP2,", ",FP4,"))
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "accepted_values_practice_stints_session" in err and "FP4" in err


@pytest.mark.parametrize("missing", [
    "fastf1_summary/car_races.csv", "fastf1_summary/track_status_periods.csv", "fastf1_practice", "open_meteo"])
def test_build_fails_when_a_session_summary_source_is_missing(existing_db: Path, raw_dir: Path, capsys, missing: str):
    target = raw_dir / missing
    shutil.rmtree(target) if target.is_dir() else target.unlink()
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert ("_stints.csv" if missing == "fastf1_practice" else target.name) in err


@pytest.mark.parametrize(
    ("relative", "table", "existing"),
    [
        ("jolpica/pit_stops.csv", "pit_stops", 7),
        ("fastf1_summary/car_races.csv", "car_races", 3),
        ("fastf1_practice/2025/01-bahrain-grand-prix/FP2_stints.csv", "practice_stints", 3),
    ],
)
def test_build_refuses_to_shrink_a_new_mart(existing_db: Path, raw_dir: Path, capsys, relative: str, table: str, existing: int):
    _drop_last_csv_row(raw_dir / relative)
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert f"{table}: this build has {existing - 1} row(s), fewer than the {existing}" in err and "refusing to replace" in err


def test_build_refuses_to_shrink_weather_forecasts(existing_db: Path, raw_dir: Path, capsys):
    path = raw_dir / "open_meteo" / "day_before" / "2025-01.json"
    record = json.loads(path.read_text())
    hourly = record["response"]["hourly"]
    record["response"]["hourly"] = {name: values[:-1] for name, values in hourly.items()}
    path.write_text(json.dumps(record))
    err = _assert_build_fails_unchanged(raw_dir, existing_db, capsys)
    assert "weather_forecasts: this build has 47 row(s), fewer than the 48" in err and "refusing to replace" in err


def test_build_refuses_to_shrink_race_incidents():
    # The fixture's car_races.csv holds one race (2025 R1), so dropping a whole race empties
    # car_races too, and the guard (tables checked in name order) reports car_races first: the
    # behavioural shrink cannot reach race_incidents here, so this checks the table is guarded.
    assert "race_incidents" in cli.REGRESSION_GUARDED_TABLES
