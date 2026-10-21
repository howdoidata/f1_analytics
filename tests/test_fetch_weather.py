"""Offline tests for `uv run fetch-weather` (recorded Open-Meteo responses)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from f1_analytics import fetch_weather
from f1_analytics.data_sources import open_meteo as om
from f1_analytics.data_sources.jolpica_fetch import read_raw_table, write_raw_table
from test_open_meteo import RecordedGetter, recorded_response


FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 20, 9, 30, 5, tzinfo=timezone.utc)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURES / "jolpica_raw", raw / "jolpica")
    return raw


def _run(raw_dir: Path, *argv: str, getter=None) -> int:
    client = om.OpenMeteoClient(getter or RecordedGetter(recorded_response()))
    return fetch_weather.main(list(argv), raw_dir=raw_dir, client=client, now=lambda: NOW)


def test_writes_the_response_endpoint_and_fetch_time(raw_dir: Path, capsys):
    getter = RecordedGetter(recorded_response())

    assert _run(raw_dir, "--season", "2025", "--round", "1", "--day-before", getter=getter) == 0

    path = raw_dir / "open_meteo" / "day_before" / "2025-01.json"
    record = json.loads(path.read_text())
    assert record["endpoint"] == om.HISTORICAL_FORECAST_URL
    assert record["fetched_at"] == "2026-10-20T09:30:05Z"
    # races.csv: 2025-03-01, 15:00:00 (no Z); circuits.csv: bahrain's lat and long.
    assert record["race_start_utc"] == "2025-03-01T15:00:00Z"
    assert record["params"] == getter.calls[0][1]
    assert (record["params"]["latitude"], record["params"]["longitude"]) == (26.0325, 50.5106)
    assert record["response"] == recorded_response()
    assert "2025 R1: 48 hour(s)" in capsys.readouterr().out
    assert [p.name for p in path.parent.iterdir()] == ["2025-01.json"]


def test_a_time_with_a_z_suffix_is_utc(raw_dir: Path):
    races = read_raw_table(raw_dir / "jolpica", "races")
    races.loc[(races["season"] == "2025") & (races["round"] == "2"), "time"] = "17:00:00Z"
    write_raw_table(raw_dir / "jolpica", "races", races)
    assert _run(raw_dir, "--season", "2025", "--round", "2", "--day-before") == 0
    record = json.loads((raw_dir / "open_meteo" / "day_before" / "2025-02.json").read_text())
    assert record["race_start_utc"] == "2025-03-08T17:00:00Z"


@pytest.mark.parametrize("season, round_", [(2025, 40), (2030, 1)])
def test_an_unknown_round_exits_1_and_writes_nothing(raw_dir: Path, capsys, season: int, round_: int):
    getter = RecordedGetter(recorded_response())
    assert _run(raw_dir, "--season", str(season), "--round", str(round_), "--day-before", getter=getter) == 1
    assert capsys.readouterr().err == f"[fetch-weather] no round {round_} in season {season}\n"
    assert not (raw_dir / "open_meteo").exists()
    assert getter.calls == []


def test_a_race_without_a_start_time_writes_nothing(raw_dir: Path, capsys):
    races = read_raw_table(raw_dir / "jolpica", "races")
    races.loc[(races["season"] == "2025") & (races["round"] == "1"), "time"] = None
    write_raw_table(raw_dir / "jolpica", "races", races)
    assert _run(raw_dir, "--season", "2025", "--round", "1", "--day-before") == 1
    assert "has no start time" in capsys.readouterr().err
    assert not (raw_dir / "open_meteo").exists()


@pytest.mark.parametrize("change", ["drop_row", "blank_lat"])
def test_a_circuit_without_coordinates_writes_nothing(raw_dir: Path, capsys, change: str):
    circuits = read_raw_table(raw_dir / "jolpica", "circuits")
    if change == "drop_row":
        circuits = circuits[circuits["circuitId"] != "bahrain"]
    else:
        circuits.loc[circuits["circuitId"] == "bahrain", "lat"] = None
    write_raw_table(raw_dir / "jolpica", "circuits", circuits)
    getter = RecordedGetter(recorded_response())
    assert _run(raw_dir, "--season", "2025", "--round", "1", "--day-before", getter=getter) == 1
    assert capsys.readouterr().err == "[fetch-weather] no latitude and longitude for circuit 'bahrain'\n"
    assert not (raw_dir / "open_meteo").exists()
    assert getter.calls == []


def test_a_failed_request_writes_nothing(raw_dir: Path, capsys):
    def failing(url, params):
        raise om.OpenMeteoRequestError(f"HTTP 400 for {url}")

    assert _run(raw_dir, "--season", "2025", "--round", "1", "--day-before", getter=failing) == 1
    assert f"FAILED -- OpenMeteoRequestError: HTTP 400 for {om.HISTORICAL_FORECAST_URL}" in capsys.readouterr().err
    assert not (raw_dir / "open_meteo").exists()


def test_without_day_before_the_live_forecast_is_written(raw_dir: Path, capsys):
    getter = RecordedGetter(recorded_response())

    assert _run(raw_dir, "--season", "2025", "--round", "1", getter=getter) == 0

    path = raw_dir / "open_meteo" / "forecast" / "2025-01.json"
    record = json.loads(path.read_text())
    assert getter.calls[0][0] == om.FORECAST_URL
    assert record["endpoint"] == om.FORECAST_URL
    assert record["params"] == getter.calls[0][1]
    assert record["fetched_at"] == "2026-10-20T09:30:05Z"
    assert record["race_start_utc"] == "2025-03-01T15:00:00Z"
    assert record["response"] == recorded_response()
    assert f"2025 R1: 48 hour(s) -> {path}" in capsys.readouterr().out
    assert [p.name for p in (raw_dir / "open_meteo").iterdir()] == ["forecast"]


def test_a_failed_live_request_writes_nothing(raw_dir: Path, capsys):
    def failing(url, params):
        raise om.OpenMeteoRequestError(f"HTTP 500 for {url}")

    assert _run(raw_dir, "--season", "2025", "--round", "1", getter=failing) == 1
    assert f"FAILED -- OpenMeteoRequestError: HTTP 500 for {om.FORECAST_URL}" in capsys.readouterr().err
    assert not (raw_dir / "open_meteo").exists()


def test_the_committed_2026_round_18_live_forecast_covers_its_race_start():
    """data/raw/open_meteo/forecast/2026-18.json is from the Forecast API and holds both race-window hours."""
    record = json.loads((Path(fetch_weather.RAW_DATA_DIR) / "open_meteo" / "forecast" / "2026-18.json").read_text())
    assert record["endpoint"] == om.FORECAST_URL
    assert record["race_start_utc"] == "2026-10-25T20:00:00Z"
    hours = record["response"]["hourly"]["time"]
    index = hours.index("2026-10-25T20:00")
    for name in om.HOURLY_VARIABLES:
        assert None not in record["response"]["hourly"][name][index:index + 2], name


def test_every_committed_2026_forecast_covers_its_race_start():
    """data/raw/open_meteo/day_before/2026-01..17.json exist and hold both race-window hours."""
    folder = Path(fetch_weather.RAW_DATA_DIR) / "open_meteo" / "day_before"
    for round_ in range(1, 18):
        record = json.loads((folder / f"2026-{round_:02d}.json").read_text())
        assert set(record) >= {"endpoint", "params", "fetched_at", "race_start_utc", "response"}
        start = record["race_start_utc"][:13] + ":00"
        hours = record["response"]["hourly"]["time"]
        index = hours.index(start)
        for name in om.HOURLY_VARIABLES:
            assert None not in record["response"]["hourly"][name][index:index + 2], (round_, name)
