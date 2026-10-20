#!/usr/bin/env python3
"""One-time Jolpica dump: every season from 1950 into `data/raw/jolpica/*.csv`.

Per season it fetches the schedule (`races`), `results`, `sprint` (2021 on),
`qualifying`, the season-end `driverstandings`/`constructorstandings`, and
from 2011 each round's `pitstops` (one request per round with results).
Drivers, constructors and circuits are built from the objects embedded in
those responses, so no separate reference requests are made.

Every page is cached under the gitignored `data/cache/jolpica/` before it is
used, so an interrupted run resumes where it stopped: cached pages cost no
request. Requests are paced at 7.2 s (Jolpica's 500 req/hour cap), so a full
cold run takes a little over an hour.

    uv run python scripts/dump_jolpica.py            # 1950 .. current season
    uv run python scripts/dump_jolpica.py --last 2025

`--only pit_stops` backfills just `pit_stops.csv`: it reads the rounds with
results from the committed `results.csv` (within `--first`/`--last`), fetches
each round's pitstops and writes only that file. The file is rewritten with
only the `--first`/`--last` range: a partial run deletes every other season's
stops. Warm the cache a season at a time if needed, but the full-range run
must come last, before committing:

    uv run python scripts/dump_jolpica.py --only pit_stops --first 2011 --last 2011
    uv run python scripts/dump_jolpica.py --only pit_stops --first 2011
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from f1_analytics.config import JOLPICA_CACHE_DIR, JOLPICA_RAW_DIR
from f1_analytics.data_sources import jolpica_fetch as jf


ONLY_TABLES = ("pit_stops",)


def fetch_pit_stops(client: jf.JolpicaClient, rounds) -> pd.DataFrame:
    """Pit stops of every `(season, round)` in `rounds` from 2011 on, in round order.

    Raises `IncompleteJolpicaFetchError` on a short page, before anything is written.
    """
    frames = []
    for season, round_ in sorted(rounds):
        if season < jf.PIT_STOPS_FIRST_SEASON:
            continue
        frames.append(jf.fetch_round_pit_stops(client, season, round_))
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=jf.RAW_COLUMNS["pit_stops"])
    return pd.concat(frames, ignore_index=True)


def results_rounds(raw_dir: Path, first: int, last: int) -> list[tuple[int, int]]:
    """`(season, round)` keys with results in the committed `results.csv`, within `first..last`."""
    results = jf.read_raw_table(raw_dir, "results")
    keys = {(int(season), int(round_)) for season, round_ in zip(results["season"], results["round"])}
    return sorted(key for key in keys if first <= key[0] <= last)


def dump_pit_stops(raw_dir: Path, client: jf.JolpicaClient, first: int, last: int) -> int:
    """Rewrite only `pit_stops.csv` from the rounds with results in `first..last`."""
    rounds = results_rounds(raw_dir, first, last)
    stops = fetch_pit_stops(client, rounds)
    jf.write_raw_table(raw_dir, "pit_stops", stops)
    print(f"[dump] pit_stops: {len(rounds)} round(s) with results; {client.request_count} live request(s)", flush=True)
    return len(jf.read_raw_table(raw_dir, "pit_stops"))


def dump(raw_dir: Path, client: jf.JolpicaClient, first: int, last: int) -> dict[str, int]:
    frames: dict[str, list[pd.DataFrame]] = {table: [] for table in jf.RAW_COLUMNS}
    race_lists: list[list[dict]] = []
    standings_pages: list[list[dict]] = []

    for season in range(first, last + 1):
        schedule = jf.merge_race_pages(client.get_all(f"{season}/races"))
        if not schedule:
            print(f"[dump] {season}: no schedule, stopping", flush=True)
            break
        frames["races"].append(jf.flatten_races(schedule))
        frames["circuits"].append(jf.flatten_circuits(schedule))

        result_pages = client.get_all(f"{season}/results")
        jf.verify_total(result_pages, "Results", f"{season} results")
        results = jf.merge_race_pages(result_pages, "Results")
        frames["results"].append(jf.flatten_results(results, "Results"))

        sprints: list[dict] = []
        if season >= jf.SPRINT_FIRST_SEASON:
            sprint_pages = client.get_all(f"{season}/sprint")
            jf.verify_total(sprint_pages, "SprintResults", f"{season} sprint")
            sprints = jf.merge_race_pages(sprint_pages, "SprintResults")
            frames["sprint_results"].append(jf.flatten_results(sprints, "SprintResults"))

        qualifying_pages = client.get_all(f"{season}/qualifying")
        jf.verify_total(qualifying_pages, "QualifyingResults", f"{season} qualifying")
        qualifying = jf.merge_race_pages(qualifying_pages, "QualifyingResults")
        frames["qualifying"].append(jf.flatten_qualifying(qualifying))
        race_lists.extend([results, sprints, qualifying])
        frames["pit_stops"].append(
            fetch_pit_stops(client, [(int(race["season"]), int(race["round"])) for race in results if race.get("Results")])
        )

        if results:
            driver_pages = client.get_all(f"{season}/driverstandings")
            constructor_pages = client.get_all(f"{season}/constructorstandings")
            jf.verify_standings_total(driver_pages, "DriverStandings", f"{season} driver standings")
            jf.verify_standings_total(
                constructor_pages, "ConstructorStandings", f"{season} constructor standings"
            )
            frames["final_driver_standings"].append(jf.flatten_driver_standings(driver_pages))
            frames["final_constructor_standings"].append(jf.flatten_constructor_standings(constructor_pages))
            standings_pages.extend([driver_pages, constructor_pages])

        print(
            f"[dump] {season}: {len(schedule)} round(s), {len(frames['results'][-1])} result row(s); "
            f"{client.request_count} request(s) so far",
            flush=True,
        )

    drivers, constructors = jf.reference_rows(race_lists, standings_pages)
    frames["drivers"].append(drivers)
    frames["constructors"].append(constructors)

    counts = {}
    for table, parts in frames.items():
        parts = [part for part in parts if not part.empty] or [pd.DataFrame(columns=jf.RAW_COLUMNS[table])]
        frame = pd.concat(parts, ignore_index=True)
        jf.write_raw_table(raw_dir, table, frame)
        counts[table] = len(jf.read_raw_table(raw_dir, table))
    return counts


def main(argv: list[str] | None = None, *, client: jf.JolpicaClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--first", type=int, default=jf.FIRST_SEASON)
    parser.add_argument("--last", type=int, default=date.today().year)
    parser.add_argument("--raw-dir", type=Path, default=JOLPICA_RAW_DIR)
    parser.add_argument("--cache-dir", type=Path, default=JOLPICA_CACHE_DIR)
    parser.add_argument("--only", choices=ONLY_TABLES, help="rewrite only this table (from the committed results.csv)")
    args = parser.parse_args(argv)

    client = client or jf.JolpicaClient(cache_dir=args.cache_dir)
    if args.only == "pit_stops":
        count = dump_pit_stops(args.raw_dir, client, args.first, args.last)
        print(f"[dump] pit_stops.csv: {count} row(s)")
        return 0
    counts = dump(args.raw_dir, client, args.first, args.last)
    for table, count in counts.items():
        print(f"[dump] {table}.csv: {count} row(s)")
    print(f"[dump] {client.request_count} live request(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
