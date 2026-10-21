"""Offline tests for `uv run scenarios`, on a DuckDB built from the chain fixture world."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from chain_world import CHAIN_SEASON, CHAIN_TEAM, make_chain_world
from f1_analytics import cli, scenarios
from f1_analytics.analysis.pit_stops import SCENARIO_COLUMNS


@pytest.fixture(scope="module")
def chain(tmp_path_factory) -> tuple[Path, Path]:
    """(raw dir, db path) of the built chain world; its only live forecast is 2023 R3."""
    root = tmp_path_factory.mktemp("scenarios_chain")
    raw = make_chain_world(root / "raw")
    db_path = root / "chain.duckdb"
    assert cli.build(["--raw-dir", str(raw), "--db", str(db_path)]) == 0
    return raw, db_path


def _run(chain, out_dir: Path, *argv: str, raw_dir: Path | None = None, db_path: Path | None = None) -> int:
    raw, db = chain
    return scenarios.main(list(argv), db_path=db_path or db, raw_dir=raw_dir or raw, out_dir=out_dir)


def _args(team: str = CHAIN_TEAM, round_: int = 3) -> list[str]:
    return ["--constructor", team, "--season", str(CHAIN_SEASON), "--round", str(round_)]


def test_writes_the_scenario_file(chain, tmp_path: Path, capsys):
    out = tmp_path / "scenarios"
    assert _run(chain, out, *_args()) == 0

    path = out / f"{CHAIN_SEASON}-03-{CHAIN_TEAM}.csv"
    assert [p.name for p in out.iterdir()] == [path.name]
    frame = pd.read_csv(path)
    assert frame.columns.tolist() == SCENARIO_COLUMNS
    assert frame["preset"].sum() == 1
    assert frame["probability"].sum() == pytest.approx(1, abs=1e-9)
    assert frame[["weather", "start_tyres"]].values.tolist() == [
        ["dry", "MEDIUM|MEDIUM"], ["mixed", "MEDIUM|MEDIUM"], ["wet", "MEDIUM|MEDIUM"]]
    assert (frame["mean"] == frame["mean"].round(1)).all()
    assert f"3 scenario(s), preset dry MEDIUM|MEDIUM" in capsys.readouterr().out


def test_a_missing_forecast_file_names_the_fetch_command(chain, tmp_path: Path, capsys):
    out = tmp_path / "scenarios"
    assert _run(chain, out, *_args(round_=2)) == 1
    err = capsys.readouterr().err
    assert err.startswith("[scenarios] no live forecast file ")
    assert f"`uv run fetch-weather --season {CHAIN_SEASON} --round 2`" in err
    assert not out.exists()


def test_a_forecast_file_not_built_names_the_build_command(chain, tmp_path: Path, capsys):
    raw, _ = chain
    copy = tmp_path / "raw"
    shutil.copytree(raw / "open_meteo", copy / "open_meteo")
    live = copy / "open_meteo" / "forecast"
    shutil.copy(live / f"{CHAIN_SEASON}-03.json", live / f"{CHAIN_SEASON}-02.json")
    out = tmp_path / "scenarios"

    assert _run(chain, out, *_args(round_=2), raw_dir=copy) == 1
    err = capsys.readouterr().err
    assert f"the database has no live forecast for {CHAIN_SEASON} round 2" in err and "`uv run build`" in err
    assert "fetch-weather" not in err
    assert not out.exists()


@pytest.mark.parametrize("argv, message", [
    (_args(team="nope"), "unknown constructor_id 'nope'"),
    (_args(round_=40), f"no round 40 in season {CHAIN_SEASON}"),
    (["--constructor", CHAIN_TEAM, "--season", "2030", "--round", "1"], "no races in season 2030"),
])
def test_an_unknown_input_writes_nothing(chain, tmp_path: Path, capsys, argv, message):
    out = tmp_path / "scenarios"
    assert _run(chain, out, *argv) == 1
    assert capsys.readouterr().err == f"[scenarios] {message}\n"
    assert not out.exists()


def test_a_missing_database_names_the_build_command(chain, tmp_path: Path, capsys):
    out = tmp_path / "scenarios"
    assert _run(chain, out, *_args(), db_path=tmp_path / "none.duckdb") == 1
    assert "`uv run build`" in capsys.readouterr().err
    assert not out.exists()


def test_the_script_is_registered():
    import tomllib

    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert pyproject["project"]["scripts"]["scenarios"] == "f1_analytics.scenarios:main"
