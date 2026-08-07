"""Load Jolpica/Ergast data as a fully loaded, separate current-season source."""

from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from f1_analytics.config import DUCKDB_PATH, JOLPICA_RAW_DIR, JOLPICA_SOURCE_NAME, PROJECT_ROOT
from f1_analytics.data_sources.jolpica import fetch_json
from f1_analytics.database.duckdb_io import connect_duckdb, log_source_load, register_source, write_dataframe


HEAVY_ENDPOINTS = ("qualifying", "driverStandings", "constructorStandings", "laps", "pitstops")

TABLE_NAMES = {
    "results": "raw_jolpica_results",
    "qualifying": "raw_jolpica_qualifying",
    "driverStandings": "raw_jolpica_driver_standings",
    "constructorStandings": "raw_jolpica_constructor_standings",
    "laps": "raw_jolpica_laps",
    "pitstops": "raw_jolpica_pitstops",
}

COVERAGE_VIEW_SQL_PATH = PROJECT_ROOT / "sql" / "analysis" / "kaggle_jolpica_coverage.sql"


def cache_path(endpoint: str, season: int, round_: int, *, cache_dir: Path = JOLPICA_RAW_DIR) -> Path:
    return cache_dir / endpoint / f"{season}_{round_}.json"


def fetch_and_cache(
    endpoint: str,
    season: int,
    round_: int,
    *,
    cache_dir: Path = JOLPICA_RAW_DIR,
) -> dict:
    payload = fetch_json(f"{season}/{round_}/{endpoint}.json", params={"limit": 100})
    path = cache_path(endpoint, season, round_, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def discover_season_rounds(season: int) -> list[int]:
    payload = fetch_json(f"{season}/races.json", params={"limit": 100})
    races = payload["MRData"]["RaceTable"]["Races"]
    return sorted(int(race["round"]) for race in races)


def parse_results(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for race in payload["MRData"]["RaceTable"]["Races"]:
        for result in race.get("Results", []):
            driver = result.get("Driver", {})
            constructor = result.get("Constructor", {})
            fastest_lap = result.get("FastestLap", {})
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "race_name": race.get("raceName"),
                    "date": race.get("date"),
                    "driver_id": driver.get("driverId"),
                    "driver_code": driver.get("code"),
                    "constructor_id": constructor.get("constructorId"),
                    "grid": result.get("grid"),
                    "position": result.get("position"),
                    "position_text": result.get("positionText"),
                    "points": result.get("points"),
                    "laps": result.get("laps"),
                    "status": result.get("status"),
                    "time": result.get("Time", {}).get("time"),
                    "fastest_lap_rank": fastest_lap.get("rank"),
                    "fastest_lap_time": fastest_lap.get("Time", {}).get("time"),
                }
            )
    return pd.DataFrame(rows)


def parse_qualifying(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for race in payload["MRData"]["RaceTable"]["Races"]:
        for entry in race.get("QualifyingResults", []):
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "driver_id": entry.get("Driver", {}).get("driverId"),
                    "constructor_id": entry.get("Constructor", {}).get("constructorId"),
                    "position": entry.get("position"),
                    "q1": entry.get("Q1"),
                    "q2": entry.get("Q2"),
                    "q3": entry.get("Q3"),
                }
            )
    return pd.DataFrame(rows)


def parse_driver_standings(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for standings_list in payload["MRData"]["StandingsTable"].get("StandingsLists", []):
        for entry in standings_list.get("DriverStandings", []):
            constructors = entry.get("Constructors", [])
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "driver_id": entry.get("Driver", {}).get("driverId"),
                    "constructor_id": constructors[0].get("constructorId") if constructors else None,
                    "position": entry.get("position"),
                    "points": entry.get("points"),
                    "wins": entry.get("wins"),
                }
            )
    return pd.DataFrame(rows)


def parse_constructor_standings(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for standings_list in payload["MRData"]["StandingsTable"].get("StandingsLists", []):
        for entry in standings_list.get("ConstructorStandings", []):
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "constructor_id": entry.get("Constructor", {}).get("constructorId"),
                    "position": entry.get("position"),
                    "points": entry.get("points"),
                    "wins": entry.get("wins"),
                }
            )
    return pd.DataFrame(rows)


def parse_laps(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for race in payload["MRData"]["RaceTable"]["Races"]:
        for lap in race.get("Laps", []):
            lap_number = lap.get("number")
            for timing in lap.get("Timings", []):
                rows.append(
                    {
                        "season": season,
                        "round": round_,
                        "lap": lap_number,
                        "driver_id": timing.get("driverId"),
                        "position": timing.get("position"),
                        "time": timing.get("time"),
                    }
                )
    return pd.DataFrame(rows)


def parse_pitstops(payload: dict, season: int, round_: int) -> pd.DataFrame:
    rows = []
    for race in payload["MRData"]["RaceTable"]["Races"]:
        for stop in race.get("PitStops", []):
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "driver_id": stop.get("driverId"),
                    "lap": stop.get("lap"),
                    "stop": stop.get("stop"),
                    "time": stop.get("time"),
                    "duration": stop.get("duration"),
                }
            )
    return pd.DataFrame(rows)


PARSERS = {
    "results": parse_results,
    "qualifying": parse_qualifying,
    "driverStandings": parse_driver_standings,
    "constructorStandings": parse_constructor_standings,
    "laps": parse_laps,
    "pitstops": parse_pitstops,
}


def load_jolpica_season(
    season: int,
    *,
    sleep_seconds: float = 0.3,
    cache_dir: Path = JOLPICA_RAW_DIR,
) -> dict[str, pd.DataFrame]:
    rounds = discover_season_rounds(season)
    frames: dict[str, list[pd.DataFrame]] = {endpoint: [] for endpoint in TABLE_NAMES}

    for round_ in rounds:
        results_payload = fetch_and_cache("results", season, round_, cache_dir=cache_dir)
        time.sleep(sleep_seconds)
        results_frame = parse_results(results_payload, season, round_)
        frames["results"].append(results_frame)

        if results_frame.empty:
            # Scheduled but not yet run: skip the heavier endpoints for this round.
            continue

        for endpoint in HEAVY_ENDPOINTS:
            payload = fetch_and_cache(endpoint, season, round_, cache_dir=cache_dir)
            time.sleep(sleep_seconds)
            frames[endpoint].append(PARSERS[endpoint](payload, season, round_))

    return {
        endpoint: (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame())
        for endpoint, parts in frames.items()
    }


def create_coverage_view(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(COVERAGE_VIEW_SQL_PATH.read_text(encoding="utf-8"))


def write_jolpica_tables(
    frames: dict[str, pd.DataFrame],
    *,
    db_path: Path = DUCKDB_PATH,
) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    with connect_duckdb(db_path) as conn:
        landing_tables = []
        for endpoint, frame in frames.items():
            table_name = TABLE_NAMES[endpoint]
            write_dataframe(conn, table_name, frame)
            log_source_load(
                conn,
                source_name=JOLPICA_SOURCE_NAME,
                table_name=table_name,
                source_path=JOLPICA_RAW_DIR,
                row_count=len(frame),
            )
            landing_tables.append(table_name)
            row_counts[table_name] = len(frame)

        register_source(
            conn,
            source_name=JOLPICA_SOURCE_NAME,
            source_type="public_api",
            description=(
                "Jolpica/Ergast API, loaded as a separate current-season source landed in its own "
                "raw_jolpica_* tables for comparison against Kaggle, never merged into Kaggle curated tables."
            ),
            landing_tables=landing_tables,
            credential_required=False,
            status="loaded",
        )

        create_coverage_view(conn)

    return row_counts


def build_jolpica_dataset(season: int, *, sleep_seconds: float = 0.3) -> dict[str, object]:
    if not DUCKDB_PATH.is_file():
        raise FileNotFoundError(
            f"DuckDB database missing: {DUCKDB_PATH}. Run scripts/build_f1_dataset.py first."
        )

    with connect_duckdb(DUCKDB_PATH, read_only=True) as conn:
        existing_tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    required_kaggle_tables = {"results", "raw_qualifying"}
    missing = required_kaggle_tables - existing_tables
    if missing:
        raise RuntimeError(
            f"Kaggle tables missing before Jolpica load: {sorted(missing)}. Run scripts/build_f1_dataset.py first."
        )

    frames = load_jolpica_season(season, sleep_seconds=sleep_seconds)
    row_counts = write_jolpica_tables(frames)
    return {"season": season, "row_counts": row_counts}
