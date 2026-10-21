"""`uv run scenarios --constructor <id> --season <s> --round <r>`: write one race's scenario file.

Reads the built DuckDB (never the raw files) and writes
`data/processed/scenarios/<s>-<RR>-<constructor>.csv`: one row per weather ×
start-tyre scenario (`SCENARIO_COLUMNS`), exactly one of them the preset. The
weather is the live forecast `uv run fetch-weather --season <s> --round <r>`
saves to `data/raw/open_meteo/forecast/` and `uv run build` loads, so the
command runs offline.

Exits 1 and writes nothing for an unknown constructor, season or round, a
missing forecast file (names the `fetch-weather` command), a forecast file the
database does not hold yet (names `uv run build`), or a missing database.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from f1_analytics.analysis.data import MissingDatabaseError, PitStopTables, load_pit_stop_tables
from f1_analytics.analysis.pit_stops import UnknownInputError, scenario_grid
from f1_analytics.analysis.pit_stops.model import _check_race
from f1_analytics.analysis.pit_stops.weather import LIVE
from f1_analytics.config import DUCKDB_PATH, PROCESSED_DATA_DIR, RAW_DATA_DIR
from f1_analytics.fetch_weather import FORECAST_KIND, OPEN_METEO_DIR


PREFIX = "[scenarios]"


def _err(message: str) -> None:
    print(f"{PREFIX} {message}", file=sys.stderr)


def _out(message: str) -> None:
    print(f"{PREFIX} {message}")


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scenarios",
        description="Write the weather × start-tyre scenario file for one team and race from the built database.",
    )
    parser.add_argument("--constructor", required=True, help="Jolpica constructor id, e.g. williams")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--round", type=int, dest="round_number", required=True)
    return parser.parse_args(argv)


def _circuit(tables: PitStopTables, constructor_id: str, season: int, round_number: int) -> str:
    """The race's circuit; story 4's message for an unknown constructor, season or round."""
    if constructor_id not in set(tables.constructors["constructor_id"]):
        raise UnknownInputError(f"unknown constructor_id '{constructor_id}'")
    _check_race(tables, season, round_number)
    races = tables.races
    return str(races.loc[(races["season"] == season) & (races["round"] == round_number), "circuit_id"].iloc[0])


def _has_live_rows(tables: PitStopTables, season: int, round_number: int) -> bool:
    rows = tables.weather_forecasts
    return bool(((rows["season"] == season) & (rows["round"] == round_number) & (rows["kind"] == LIVE)).any())


def main(
    argv: Sequence[str] | None = None,
    *,
    db_path: Path = DUCKDB_PATH,
    raw_dir: Path = RAW_DATA_DIR,
    out_dir: Path = PROCESSED_DATA_DIR / "scenarios",
) -> int:
    args = _parse(sys.argv[1:] if argv is None else list(argv))
    team, season, round_number = args.constructor, args.season, args.round_number
    try:
        tables = load_pit_stop_tables(db_path)
        circuit = _circuit(tables, team, season, round_number)
    except (MissingDatabaseError, UnknownInputError) as error:
        _err(str(error))
        return 1

    forecast_file = Path(raw_dir) / OPEN_METEO_DIR / FORECAST_KIND / f"{season}-{round_number:02d}.json"
    if not forecast_file.exists():
        _err(f"no live forecast file {forecast_file}; fetch it with "
             f"`uv run fetch-weather --season {season} --round {round_number}`, then `uv run build`")
        return 1
    if not _has_live_rows(tables, season, round_number):
        _err(f"the database has no live forecast for {season} round {round_number}, though {forecast_file} "
             f"exists; load it with `uv run build`")
        return 1

    try:
        grid = scenario_grid(tables, team, circuit, season, round_number)
    except ValueError as error:
        _err(f"{season} R{round_number} {team}: {error}")
        return 1

    path = Path(out_dir) / f"{season}-{round_number:02d}-{team}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    grid.to_csv(tmp, index=False)
    tmp.replace(path)
    preset = grid[grid["preset"]].iloc[0]
    _out(f"{season} R{round_number} {team} at {circuit}: {len(grid)} scenario(s), preset {preset['weather']} "
         f"{preset['start_tyres']} (probability {preset['probability']:.3f}, mean {preset['mean']}) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
