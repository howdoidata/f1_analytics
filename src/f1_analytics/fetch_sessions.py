"""`uv run fetch-sessions`: summarise any FastF1 session into small committed files.

Race sessions (`R`) update `data/raw/fastf1_summary/car_races.csv` (one row
per Jolpica results row) and `track_status_periods.csv`; practice sessions
(`FP1`-`FP3`) write `data/raw/fastf1_practice/<s>/<RR>-<slug>/<SESSION>_stints.csv`.
The race list comes from Jolpica's `races` table, and drivers are matched on
car number against Jolpica `results`. Nothing is written under
`data/raw/fastf1/`, which dbt reads.

Downloads go through `fastf1_fetch.load_session_with_retry` (the FastF1 cache,
the Fast-F1#978 header and the retry), after the F1TV token check that
`refresh` uses. `--from-extracts --season <s>` summarises the committed
`data/raw/fastf1/<s>/*/laps.csv` + `weather.csv` instead, with no token and no
FastF1 call.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from f1_analytics.cli import LOGIN_COMMAND, TokenError, check_token
from f1_analytics.config import FASTF1_CACHE_DIR, FASTF1_PRACTICE_DIR, FASTF1_RAW_DIR, FASTF1_SUMMARY_DIR, RAW_DATA_DIR
from f1_analytics.data_sources import fastf1_summary as summary
from f1_analytics.data_sources.fastf1_fetch import load_session_with_retry, round_dir_name
from f1_analytics.data_sources.jolpica_fetch import read_raw_table


PREFIX = "[fetch-sessions]"
RACE_SESSION = "R"
PRACTICE_SESSIONS = ("FP1", "FP2", "FP3")
SESSIONS = (RACE_SESSION, *PRACTICE_SESSIONS)
CAR_RACES_FILE = "car_races.csv"
TRACK_STATUS_FILE = "track_status_periods.csv"
# Laps columns the summaries read; extracts are read with these as text so
# `TrackStatus` codes and car numbers keep their exact form.
EXTRACT_TEXT_COLUMNS = {"TrackStatus": str, "DriverNumber": str}


class UsageError(Exception):
    """Bad arguments or an unknown circuit/round; nothing has been written."""


def _err(message: str) -> None:
    print(f"{PREFIX} {message}", file=sys.stderr)


def _out(message: str) -> None:
    print(f"{PREFIX} {message}")


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fetch-sessions",
        description=(
            "Summarise FastF1 sessions into data/raw/fastf1_summary/ (race) and "
            "data/raw/fastf1_practice/ (FP1-FP3). Downloads need an F1TV login."
        ),
    )
    parser.add_argument("--circuit", help="Jolpica circuitId, e.g. americas (with --since)")
    parser.add_argument("--since", type=int, help="first season for --circuit")
    parser.add_argument("--season", type=int)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument(
        "--session", action="append", choices=SESSIONS, help="R, FP1, FP2 or FP3; repeatable (default R)"
    )
    parser.add_argument(
        "--from-extracts", action="store_true", help="summarise the committed data/raw/fastf1/<season>/ extracts (race only, no token)"
    )
    args = parser.parse_args(argv)
    args.session = list(dict.fromkeys(args.session or [RACE_SESSION]))
    if args.circuit is not None:
        if args.season is not None or args.round_number is not None or args.from_extracts:
            parser.error("--circuit can't be combined with --season, --round or --from-extracts")
    elif args.season is None:
        parser.error("give --circuit <id> [--since <season>] or --season <s> [--round <r>]")
    if args.since is not None and args.circuit is None:
        parser.error("--since needs --circuit")
    if args.from_extracts and args.session != [RACE_SESSION]:
        parser.error("--from-extracts summarises race sessions only")
    return args


# --------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------


def _races(jolpica_dir: Path) -> pd.DataFrame:
    races = read_raw_table(jolpica_dir, "races")
    races = races.assign(season=races["season"].astype(int), round=races["round"].astype(int))
    return races.sort_values(["season", "round"], kind="stable").reset_index(drop=True)


def _results(jolpica_dir: Path) -> pd.DataFrame:
    results = read_raw_table(jolpica_dir, "results")
    return results.assign(season=results["season"].astype(int), round=results["round"].astype(int))


def select_races(args: argparse.Namespace, races: pd.DataFrame, extracts_dir: Path) -> pd.DataFrame:
    """The races table rows to summarise; raises `UsageError` for an unknown circuit or round."""
    if args.circuit is not None:
        at_circuit = races[races["circuitId"] == args.circuit]
        if at_circuit.empty:
            raise UsageError(f"unknown circuit_id '{args.circuit}'")
        if args.since is not None:
            at_circuit = at_circuit[at_circuit["season"] >= args.since]
        return at_circuit
    season = races[races["season"] == args.season]
    if season.empty:
        raise UsageError(f"no races in season {args.season}")
    if args.round_number is not None:
        season = season[season["round"] == args.round_number]
        if season.empty:
            raise UsageError(f"no round {args.round_number} in season {args.season}")
    if args.from_extracts:
        rounds = _extract_dirs(extracts_dir, args.season)
        if not rounds:
            raise UsageError(f"no extracts under {extracts_dir / str(args.season)}")
        season = season[season["round"].isin(rounds)]
        if args.round_number is not None and season.empty:
            raise UsageError(f"no extract for {args.season} R{args.round_number}")
    return season


def _extract_dirs(extracts_dir: Path, season: int) -> dict[int, Path]:
    """`{round: <RR>-<slug> folder}` for every extract with laps and weather."""
    found: dict[int, Path] = {}
    for laps in sorted((extracts_dir / str(season)).glob("*/laps.csv")):
        prefix = laps.parent.name.split("-", 1)[0]
        if prefix.isdigit() and (laps.parent / "weather.csv").is_file():
            found[int(prefix)] = laps.parent
    return found


def _race_results(results: pd.DataFrame, season: int, round_number: int) -> pd.DataFrame:
    return results[(results["season"] == season) & (results["round"] == round_number)]


def _practice_results(results: pd.DataFrame, season: int, round_number: int) -> tuple[int, pd.DataFrame] | None:
    """The latest race of the season at or before `round_number` that has results."""
    earlier = results[(results["season"] == season) & (results["round"] <= round_number)]
    if earlier.empty:
        return None
    latest = int(earlier["round"].max())
    return latest, earlier[earlier["round"] == latest]


# --------------------------------------------------------------------------
# Loading sessions
# --------------------------------------------------------------------------


class SessionNotFound(Exception):
    pass


def _load_fastf1(fastf1: Any, cache_dir: Path, token: str, season: int, round_number: int, session_name: str):
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        session = load_session_with_retry(fastf1, cache_dir, season, round_number, token, identifier=session_name)
    except ValueError as error:  # FastF1: "Session type 'FP2' does not exist for this event"
        raise SessionNotFound(str(error)) from error
    laps = session.laps
    if laps is None or len(laps) == 0:
        raise SessionNotFound("no laps")
    return pd.DataFrame(laps), session.weather_data


def _load_extract(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    laps = pd.read_csv(folder / "laps.csv", dtype=EXTRACT_TEXT_COLUMNS)
    weather = pd.read_csv(folder / "weather.csv")
    return laps, weather


# --------------------------------------------------------------------------
# Summarising
# --------------------------------------------------------------------------


def summarise_race(
    summary_dir: Path, laps: pd.DataFrame, weather, results: pd.DataFrame, *, season: int, round_number: int, circuit_id: str
) -> tuple[int, int]:
    """Compute both summaries first, then upsert them; a `SummaryError` writes nothing."""
    cars = summary.car_race_rows(laps, weather, results, season=season, round_number=round_number, circuit_id=circuit_id)
    periods = summary.track_status_periods(laps, season=season, round_number=round_number)
    summary.upsert_race_rows(
        summary_dir / CAR_RACES_FILE, cars, season=season, round_number=round_number,
        columns=summary.CAR_RACE_COLUMNS, key=["driver_id"],
    )
    summary.upsert_race_rows(
        summary_dir / TRACK_STATUS_FILE, periods, season=season, round_number=round_number,
        columns=summary.TRACK_STATUS_COLUMNS, key=["start_lap"],
    )
    return len(cars), len(periods)


def main(
    argv: Sequence[str] | None = None,
    *,
    token_path: Path | None = None,
    raw_dir: Path = RAW_DATA_DIR,
    cache_dir: Path = FASTF1_CACHE_DIR,
    fastf1_module: Any = None,
) -> int:
    args = _parse(sys.argv[1:] if argv is None else list(argv))
    jolpica_dir = raw_dir / "jolpica"
    # Same layout as config's paths, under whichever raw dir is given.
    extracts_dir = raw_dir / FASTF1_RAW_DIR.name
    summary_dir = raw_dir / FASTF1_SUMMARY_DIR.name
    practice_dir = raw_dir / FASTF1_PRACTICE_DIR.name

    races = _races(jolpica_dir)
    results = _results(jolpica_dir)
    try:
        selected = select_races(args, races, extracts_dir)
    except UsageError as error:
        _err(str(error))
        return 1

    # Work items: (season, round, raceName, circuitId, session).
    targets = []
    for season, round_number, race_name, circuit_id in zip(
        selected["season"], selected["round"], selected["raceName"], selected["circuitId"]
    ):
        for session_name in args.session:
            if session_name == RACE_SESSION and _race_results(results, season, round_number).empty:
                _out(f"{season} R{round_number}: no results yet, skipped")
                continue
            targets.append((int(season), int(round_number), str(race_name), str(circuit_id), session_name))

    fastf1 = None
    token = ""
    if not args.from_extracts and targets:
        # The token, before any FastF1 call or write.
        try:
            token = check_token(token_path)
        except TokenError as error:
            _err(f"{error}.")
            _err(f"Log in to F1TV, then rerun:\n\n    {LOGIN_COMMAND}\n")
            return 1
        fastf1 = fastf1_module
        if fastf1 is None:
            import fastf1

    extract_dirs = _extract_dirs(extracts_dir, args.season) if args.from_extracts else {}
    failed: list[str] = []
    for season, round_number, race_name, circuit_id, session_name in targets:
        label = f"{season} R{round_number}" if session_name == RACE_SESSION else f"{season} R{round_number} {session_name}"
        try:
            if args.from_extracts:
                laps, weather = _load_extract(extract_dirs[round_number])
            else:
                laps, weather = _load_fastf1(fastf1, cache_dir, token, season, round_number, session_name)
        except SessionNotFound:
            _err(f"{label}: session not found")
            failed.append(label)
            continue
        except Exception as error:  # Live services raise diverse failure types.
            _err(f"{label}: FAILED -- {type(error).__name__}: {error}")
            failed.append(label)
            continue

        try:
            if session_name == RACE_SESSION:
                cars, periods = summarise_race(
                    summary_dir, laps, weather, _race_results(results, season, round_number),
                    season=season, round_number=round_number, circuit_id=circuit_id,
                )
                _out(f"{label}: {cars} car row(s), {periods} track-status period(s)")
            else:
                matched = _practice_results(results, season, round_number)
                if matched is None:
                    raise summary.SummaryError(f"no race with results at or before round {round_number}")
                results_round, practice_results = matched
                stints, skipped = summary.practice_stint_rows(
                    laps, practice_results, season=season, round_number=round_number, session=session_name
                )
                for number in skipped:
                    _err(f"{label}: car number {number} not in Jolpica results, skipped")
                path = practice_dir / str(season) / round_dir_name(round_number, race_name) / f"{session_name}_stints.csv"
                summary.write_rows(path, stints, summary.PRACTICE_STINT_COLUMNS)
                _out(f"{label}: {len(stints)} stint row(s), cars matched on R{results_round} results -> {path}")
        except summary.SummaryError as error:
            _err(f"{label}: {error}")
            failed.append(label)

    if failed:
        _err(f"{len(failed)} session(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
