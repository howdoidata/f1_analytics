"""`uv run fetch-weather --season <s> --round <r> --day-before`: commit one race's forecast.

Writes `data/raw/open_meteo/day_before/<s>-<RR>.json` holding the endpoint, the
query, the fetch time (UTC), the race start (UTC) and Open-Meteo's response,
for the circuit's latitude and longitude (Jolpica `circuits`) and the race
start (Jolpica `races` date and time). dbt reads these files into the
`weather_forecasts` mart; the analysis reads the mart, never the files.

No token is needed. An unknown round writes nothing and exits 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from f1_analytics.config import RAW_DATA_DIR
from f1_analytics.data_sources.jolpica_fetch import read_raw_table
from f1_analytics.data_sources.open_meteo import OpenMeteoClient, day_before_request


PREFIX = "[fetch-weather]"
OPEN_METEO_DIR = "open_meteo"
DAY_BEFORE_KIND = "day_before"


class UsageError(Exception):
    """An unknown round or a race without a start time; nothing has been written."""


def _err(message: str) -> None:
    print(f"{PREFIX} {message}", file=sys.stderr)


def _out(message: str) -> None:
    print(f"{PREFIX} {message}")


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fetch-weather",
        description="Fetch the Open-Meteo forecast for one race into data/raw/open_meteo/. No login needed.",
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--round", type=int, dest="round_number", required=True)
    parser.add_argument(
        "--day-before", action="store_true", required=True,
        help="the forecast for the race window, written to open_meteo/day_before/",
    )
    return parser.parse_args(argv)


def race_start_utc(date: str, time: str | None) -> datetime:
    """The race start from Jolpica's `date` and `time` (`HH:MM:SSZ`, the `Z` optional)."""
    if time is None or pd.isna(time) or not str(time).strip():
        raise UsageError(f"race on {date} has no start time")
    clock = str(time).strip().removesuffix("Z")
    return datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=timezone.utc)


def _target(jolpica_dir: Path, season: int, round_number: int) -> tuple[datetime, float, float]:
    races = read_raw_table(jolpica_dir, "races")
    race = races[(races["season"] == str(season)) & (races["round"] == str(round_number))]
    if race.empty:
        raise UsageError(f"no round {round_number} in season {season}")
    row = race.iloc[0]
    circuits = read_raw_table(jolpica_dir, "circuits")
    circuit = circuits[circuits["circuitId"] == row["circuitId"]]
    if circuit.empty or pd.isna(circuit.iloc[0]["lat"]) or pd.isna(circuit.iloc[0]["long"]):
        raise UsageError(f"no latitude and longitude for circuit '{row['circuitId']}'")
    start = race_start_utc(row["date"], row["time"])
    return start, float(circuit.iloc[0]["lat"]), float(circuit.iloc[0]["long"])


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(
    argv: Sequence[str] | None = None,
    *,
    raw_dir: Path = RAW_DATA_DIR,
    client: OpenMeteoClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> int:
    args = _parse(sys.argv[1:] if argv is None else list(argv))
    try:
        start, lat, lng = _target(raw_dir / "jolpica", args.season, args.round_number)
    except UsageError as error:
        _err(str(error))
        return 1

    client = client or OpenMeteoClient()
    endpoint, params = day_before_request(lat, lng, start)
    try:
        response = client.fetch_day_before(lat, lng, start)
    except Exception as error:  # Live services raise diverse failure types.
        _err(f"{args.season} R{args.round_number}: FAILED -- {type(error).__name__}: {error}")
        return 1

    record = {
        "endpoint": endpoint,
        "params": params,
        "fetched_at": _iso(now()),
        "race_start_utc": _iso(start),
        "response": response,
    }
    path = raw_dir / OPEN_METEO_DIR / DAY_BEFORE_KIND / f"{args.season}-{args.round_number:02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record) + "\n")
    tmp.replace(path)
    _out(f"{args.season} R{args.round_number}: {len(response['hourly']['time'])} hour(s) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
