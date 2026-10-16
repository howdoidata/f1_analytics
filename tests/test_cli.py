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
import pytest
from packaging.version import Version

from f1_analytics import cli
from f1_analytics.data_sources import fastf1_fetch, jolpica_fetch
from jolpica_responses import RecordedGetter, make_update_world, recorded_responses


FIXTURES = Path(__file__).parent / "fixtures"
CURATED_TABLES = {
    "races", "results", "sprint_results", "drivers", "constructors", "circuits", "qualifying",
    "driver_standings_by_round", "constructor_standings_by_round",
    "final_driver_standings", "final_constructor_standings",
    "raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather",
}


def _extract(raw_dir: Path, season: int, dir_name: str, fixture: str = "normal_race", round_: int = 1) -> Path:
    target = raw_dir / "fastf1" / str(season) / dir_name
    shutil.copytree(FIXTURES / "fastf1_csv" / fixture, target)
    counts = json.loads((target / "counts.json").read_text())
    counts.update({"season": season, "round": round_, "race_label": dir_name})
    (target / "counts.json").write_text(json.dumps(counts))
    return target


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURES / "jolpica_raw", raw / "jolpica")
    _extract(raw, 2024, "01-bahrain-grand-prix")
    return raw


def _tables(db_path: Path) -> set[str]:
    with duckdb.connect(str(db_path), read_only=True) as conn:
        return {row[0] for row in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*")) if p.is_file()
    }


def _token(tmp_path: Path, *, exp_offset: float = 3600, raw: str | None = None) -> Path:
    path = tmp_path / "f1auth.json"
    path.write_text(raw if raw is not None else jwt.encode({"exp": int(time.time() + exp_offset)}, "k" * 32, algorithm="HS256"))
    return path


# --- build -------------------------------------------------------------------


def test_build_writes_every_curated_table_from_raw_fixtures(raw_dir: Path, tmp_path: Path):
    db_path = tmp_path / "out.duckdb"
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 0

    tables = _tables(db_path)
    assert CURATED_TABLES <= tables
    assert not any(t.startswith("combined") or "coverage" in t for t in tables)
    with duckdb.connect(str(db_path), read_only=True) as conn:
        types = dict(conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'driver_standings_by_round'"
        ).fetchall())
        assert types["date"] == "DATE"
        assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM raw_fastf1_laps WHERE season = 2024 AND round = 1").fetchone()[0] > 0
        result_types = dict(conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'results'"
        ).fetchall())
        assert result_types["fastest_lap"] == "DOUBLE" and result_types["position"] == "BIGINT"


def test_build_drops_tables_an_earlier_pipeline_left_behind(raw_dir: Path, tmp_path: Path):
    db_path = tmp_path / "out.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE legacy_merged_results AS SELECT 1 AS x")
        conn.execute("CREATE VIEW legacy_source_coverage AS SELECT 1 AS x")
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 0
    tables = _tables(db_path)
    assert "legacy_merged_results" not in tables and "legacy_source_coverage" not in tables

    # The append-only logs survive a rebuild.
    with duckdb.connect(str(db_path), read_only=True) as conn:
        first = conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0]
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 0
    with duckdb.connect(str(db_path), read_only=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0] == 2 * first > 0


def test_build_names_a_missing_raw_file(raw_dir: Path, tmp_path: Path, capsys):
    (raw_dir / "jolpica" / "sprint_results.csv").unlink()
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(tmp_path / "out.duckdb")]) == 1
    assert "sprint_results.csv" in capsys.readouterr().err


def test_build_is_offline_and_never_imports_fastf1_or_requests(raw_dir: Path, tmp_path: Path):
    code = (
        "import sys, socket\n"
        "def deny(*a, **k): raise RuntimeError('network')\n"
        "socket.socket.connect = deny\n"
        "from f1_analytics import cli\n"
        f"rc = cli.build(['--raw-dir', {str(raw_dir)!r}, '--db', {str(tmp_path / 'o.duckdb')!r}])\n"
        "assert rc == 0, rc\n"
        "leaked = [m for m in ('fastf1', 'requests', 'jwt') if m in sys.modules]\n"
        "assert not leaked, leaked\n"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                               env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert completed.returncode == 0, completed.stderr


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
    assert "raw_fastf1_laps" in _tables(tmp_path / "out.duckdb")


# --- pins --------------------------------------------------------------------


def test_dependency_pins():
    pandas = Version(importlib.metadata.version("pandas"))
    assert Version("2.2") <= pandas < Version("3")
    assert importlib.metadata.version("fastf1") == "3.8.3"
    assert Version(importlib.metadata.version("cryptography")) < Version("50")


def test_build_refuses_to_shrink_a_landed_table(raw_dir: Path, tmp_path: Path, capsys):
    db_path = tmp_path / "out.duckdb"
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 0
    results = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "results")
    jolpica_fetch.write_raw_table(raw_dir / "jolpica", "results", results.iloc[:-1])
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 1
    assert "refusing to replace" in capsys.readouterr().err


def test_build_refuses_to_drop_landed_fastf1_tables_when_extracts_vanish(raw_dir: Path, tmp_path: Path, capsys):
    db_path = tmp_path / "out.duckdb"
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 0
    shutil.rmtree(raw_dir / "fastf1")
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(db_path)]) == 1
    assert "raw_fastf1_laps: this write has 0 row(s)" in capsys.readouterr().err
    assert {"raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather"} <= _tables(db_path)


@pytest.mark.parametrize("missing", ["laps.csv", "counts.json"])
def test_build_names_a_missing_fastf1_extract_file(raw_dir: Path, tmp_path: Path, capsys, missing: str):
    (raw_dir / "fastf1" / "2024" / "01-bahrain-grand-prix" / missing).unlink()
    assert cli.build(["--raw-dir", str(raw_dir), "--db", str(tmp_path / "out.duckdb")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("[build] ") and missing in err


def test_a_round_with_any_extract_folder_is_not_refetched_after_a_race_rename(raw_dir: Path):
    _extract(raw_dir, 2025, "01-old-bahrain-name")
    missing = cli.missing_extract_rounds(raw_dir, 2025, today=date(2025, 12, 31))
    assert missing == [(2, "02-saudi-arabian-grand-prix")]
