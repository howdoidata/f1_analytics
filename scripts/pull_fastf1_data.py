#!/usr/bin/env python3
"""Land FastF1 laps/stints/weather facts for the five target 2026 races (Story 1.6).

Two-phase per race: subprocess-invoke the isolated pandas-<3.0
`fastf1_fetch.py` half (the fallback the FastF1 source-adoption decision
record settled on), then hand its dumped CSVs to the main-env
`fastf1_loader.py` half to id-map, verify completeness, and derive stints.
One race's fetch/mapping failure is caught, reported by name, and never
stops the remaining races (AD-13). Lands `raw_fastf1_laps`,
`raw_fastf1_stints`, and `raw_fastf1_weather` via the existing replace-sync
writer (AD-4); every row carries `driver_id`/`constructor_id` (AD-14).

Run from the repository root:

    uv run scripts/pull_fastf1_data.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import pandas as pd

from f1_analytics.config import DUCKDB_PATH, FASTF1_CACHE_DIR, FASTF1_RAW_DIR
from f1_analytics.data_sources.fastf1_loader import FastF1RaceLoadError, load_and_map_race
from f1_analytics.database.duckdb_io import connect_duckdb, write_dataframe


ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT_PATH = ROOT / "src" / "f1_analytics" / "data_sources" / "fastf1_fetch.py"
FETCH_TIMEOUT_SECONDS = 300
SEASON = 2026

# Story 1.2's already-verified TARGETS (spike_fastf1_adoption.py), reused verbatim.
TARGETS: tuple[tuple[str, str], ...] = (
    ("Melbourne", "Australian Grand Prix"),
    ("Miami", "Miami Grand Prix"),
    ("Canada", "Canadian Grand Prix"),
    ("Barcelona", "Spanish Grand Prix"),
    ("Silverstone", "British Grand Prix"),
)

FetchFn = Callable[[str, str, Path], dict]


def run_fetch_subprocess(label: str, event: str, season: int, cache_dir: Path, output_dir: Path) -> dict:
    """Invoke fastf1_fetch.py in the isolated pandas-<3.0 environment.

    FastF1 pins `pandas>=2.1.1,<3.0.0`; the 1.2 decision record's fallback
    is this isolated subprocess, never a project-wide pandas downgrade.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "uv",
        "run",
        "--isolated",
        "--python",
        "3.13",
        "--with",
        "fastf1==3.8.3",
        "python",
        str(FETCH_SCRIPT_PATH),
        "--label",
        label,
        "--event",
        event,
        "--season",
        str(season),
        "--cache-dir",
        str(cache_dir),
        "--output-dir",
        str(output_dir),
    ]
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=FETCH_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        return {
            "race_label": label,
            "status": "failed",
            "exception": f"TimeoutExpired: fetch exceeded {FETCH_TIMEOUT_SECONDS}s",
        }
    except OSError as error:
        return {"race_label": label, "status": "failed", "exception": f"{type(error).__name__}: {error}"}

    try:
        result = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        result = {}

    if result.get("status") != "pass":
        result.setdefault("race_label", label)
        result.setdefault("status", "failed")
        result.setdefault(
            "exception",
            f"fetch subprocess exited {completed.returncode}: {completed.stderr.strip()[-2000:]}",
        )
    return result


REQUIRED_CURATED_TABLES = ("drivers", "constructors")


def require_curated_tables(conn, db_path: Path) -> None:
    """Fail fast with a named error if Story 1.5's curated tables aren't landed yet.

    Mirrors `kaggle_csv.py`'s `require_raw_files()` precedent: a missing
    prerequisite is a named, immediate failure, not a raw DuckDB
    "table does not exist" exception surfacing from deep inside a query.
    """
    existing = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    missing = [table for table in REQUIRED_CURATED_TABLES if table not in existing]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"Missing curated table(s) in {db_path}: {missing_list}. "
            "Run scripts/build_f1_dataset.py (Story 1.5) first."
        )


def build_fetch(cache_dir: Path, season: int) -> FetchFn:
    def fetch(label: str, event: str, output_dir: Path) -> dict:
        return run_fetch_subprocess(label, event, season, cache_dir, output_dir)

    return fetch


def _fetch_failure_detail(fetch_result: dict) -> object:
    """A clean, human-readable detail for a failed/empty fetch result.

    `status: "empty"` (session loaded without raising but reported zero
    laps -- e.g. a still-future or cancelled session) carries no
    `"exception"` key, so falling back to the raw result dict there is
    noisy; give it its own message instead.
    """
    if fetch_result.get("status") == "empty":
        lap_count = fetch_result.get("lap_count", 0)
        return f"session loaded but reported {lap_count} laps (still-future or cancelled session?)"
    return fetch_result.get("exception", fetch_result)


def pull_race(
    label: str,
    event: str,
    output_dir: Path,
    season: int,
    fetch: FetchFn,
    drivers: pd.DataFrame,
    constructors: pd.DataFrame,
) -> dict:
    """Fetch + load one race independently; never raises -- always returns an outcome."""
    fetch_result = fetch(label, event, output_dir)
    if fetch_result.get("status") != "pass":
        return {
            "label": label,
            "status": "failed",
            "stage": "fetch",
            "detail": _fetch_failure_detail(fetch_result),
        }
    try:
        race = load_and_map_race(output_dir, drivers, constructors, label=label, season=season)
    except FastF1RaceLoadError as error:
        return {"label": label, "status": "failed", "stage": "load", "detail": str(error)}
    return {"label": label, "status": "pass", "race": race}


def main(
    targets: tuple[tuple[str, str], ...] = TARGETS,
    season: int = SEASON,
    fastf1_cache_dir: Path = FASTF1_CACHE_DIR,
    fastf1_raw_dir: Path = FASTF1_RAW_DIR,
    db_path: Path = DUCKDB_PATH,
    fetch: FetchFn | None = None,
) -> int:
    if fetch is None:
        fetch = build_fetch(fastf1_cache_dir, season)

    with connect_duckdb(db_path, read_only=True) as conn:
        require_curated_tables(conn, db_path)
        drivers = conn.execute("SELECT * FROM drivers").fetch_df()
        constructors = conn.execute("SELECT * FROM constructors").fetch_df()

    outcomes: list[dict] = []
    laps_frames: list[pd.DataFrame] = []
    stints_frames: list[pd.DataFrame] = []
    weather_frames: list[pd.DataFrame] = []

    for label, event in targets:
        outcome = pull_race(label, event, fastf1_raw_dir / label, season, fetch, drivers, constructors)
        outcomes.append(outcome)
        if outcome["status"] == "pass":
            race = outcome["race"]
            laps_frames.append(race["laps"])
            stints_frames.append(race["stints"])
            weather_frames.append(race["weather"])
            print(f"[pull_fastf1_data] {label}: landed ({len(race['laps'])} laps)")
        else:
            print(f"[pull_fastf1_data] {label}: FAILED at {outcome['stage']} -- {outcome['detail']}")

    with connect_duckdb(db_path) as conn:
        if laps_frames:
            write_dataframe(conn, "raw_fastf1_laps", pd.concat(laps_frames, ignore_index=True))
        if stints_frames:
            write_dataframe(conn, "raw_fastf1_stints", pd.concat(stints_frames, ignore_index=True))
        if weather_frames:
            write_dataframe(conn, "raw_fastf1_weather", pd.concat(weather_frames, ignore_index=True))

    landed = [outcome["label"] for outcome in outcomes if outcome["status"] == "pass"]
    failed = [outcome["label"] for outcome in outcomes if outcome["status"] != "pass"]
    print(f"Landed: {', '.join(landed) or 'none'}")
    print(f"Failed: {', '.join(failed) or 'none'}")

    return 0 if landed else 1


if __name__ == "__main__":
    raise SystemExit(main())
