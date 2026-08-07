"""Load Kaggle Formula 1 CSVs and build local curated tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from f1_analytics.config import (
    DUCKDB_PATH,
    KAGGLE_DATASET_HANDLE,
    KAGGLE_F1_RAW_DIR,
    KAGGLE_SOURCE_NAME,
    PROCESSED_DATA_DIR,
)
from f1_analytics.data_sources.standings import compute_cumulative_standings
from f1_analytics.database.duckdb_io import (
    connect_duckdb,
    log_source_load,
    log_validation_results,
    register_source,
    write_dataframe,
)
from f1_analytics.validation.checks import run_kaggle_validations


RAW_FILES = {
    "races": "f1_races.csv",
    "results": "f1_results.csv",
    "drivers": "f1_drivers.csv",
    "constructors": "f1_constructors.csv",
    "driver_standings": "f1_driver_standings.csv",
    "constructor_standings": "f1_constructor_standings.csv",
    "circuits": "f1_circuits.csv",
    "qualifying": "f1_qualifying.csv",
}


def discover_raw_files(raw_dir: Path = KAGGLE_F1_RAW_DIR) -> dict[str, Path]:
    return {table: raw_dir / filename for table, filename in RAW_FILES.items()}


def require_raw_files(raw_dir: Path = KAGGLE_F1_RAW_DIR) -> None:
    missing = [path.name for path in discover_raw_files(raw_dir).values() if not path.is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing raw CSV file(s) under {raw_dir}: {missing_list}")


def read_raw_csvs(raw_dir: Path = KAGGLE_F1_RAW_DIR) -> dict[str, pd.DataFrame]:
    require_raw_files(raw_dir)
    return {table: pd.read_csv(path) for table, path in discover_raw_files(raw_dir).items()}


def coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def build_curated_tables(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    races = raw["races"].copy()
    results = raw["results"].copy()
    drivers = raw["drivers"].copy()
    constructors = raw["constructors"].copy()
    driver_final = raw["driver_standings"].copy()
    constructor_final = raw["constructor_standings"].copy()
    circuits = raw["circuits"].copy()
    qualifying = raw["qualifying"].copy()

    races = coerce_numeric(races, ["season", "round"])
    races["date"] = pd.to_datetime(races["date"], errors="coerce").dt.date

    results = coerce_numeric(
        results,
        ["season", "round", "grid", "position", "points", "laps", "fastest_lap", "fastest_lap_rank"],
    )

    qualifying = coerce_numeric(qualifying, ["season", "round", "position"])

    driver_final = coerce_numeric(driver_final, ["season", "position", "points", "wins"])
    constructor_final = coerce_numeric(constructor_final, ["season", "position", "points", "wins"])
    driver_final = driver_final.merge(
        drivers.assign(driver_name=drivers["given_name"].fillna("") + " " + drivers["family_name"].fillna(""))[
            ["driver_id", "driver_name"]
        ],
        on="driver_id",
        how="left",
    )

    # f1_driver_standings.csv only carries a free-text constructor name, so
    # reconcile it to constructor_id using the id/name pairs already present
    # in results and constructor_standings (both keyed on constructor_id).
    constructor_name_lookup = (
        pd.concat(
            [
                results[["constructor", "constructor_id"]],
                constructor_final[["constructor", "constructor_id"]],
            ],
            ignore_index=True,
        )
        .dropna(subset=["constructor", "constructor_id"])
        .drop_duplicates(subset=["constructor"])
        .set_index("constructor")["constructor_id"]
    )
    driver_final["constructor_id"] = driver_final["constructor"].map(constructor_name_lookup)

    race_results = results.merge(
        races[["season", "round", "date", "time", "circuit_id", "url"]],
        on=["season", "round"],
        how="left",
        suffixes=("", "_race"),
    )

    driver_round = compute_cumulative_standings(race_results, "driver_id", "driver_name")
    constructor_round = compute_cumulative_standings(race_results, "constructor_id", "constructor")

    return {
        "races": races,
        "results": results,
        "drivers": drivers,
        "constructors": constructors,
        "circuits": circuits,
        "qualifying": qualifying,
        "race_results_enriched": race_results,
        "driver_standings_by_round": driver_round,
        "constructor_standings_by_round": constructor_round,
        "final_driver_standings": driver_final,
        "final_constructor_standings": constructor_final,
    }


def write_duckdb(
    raw: dict[str, pd.DataFrame],
    curated: dict[str, pd.DataFrame],
    *,
    db_path: Path = DUCKDB_PATH,
) -> pd.DataFrame:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    raw_paths = discover_raw_files()
    with connect_duckdb(db_path) as conn:
        raw_tables = [f"raw_{name}" for name in raw]
        curated_tables = list(curated)
        register_source(
            conn,
            source_name=KAGGLE_SOURCE_NAME,
            source_type="local_csv",
            description=f"Baseline Kaggle CSV dataset: {KAGGLE_DATASET_HANDLE}",
            landing_tables=raw_tables + curated_tables,
            credential_required=True,
            status="loaded",
        )

        for name, frame in raw.items():
            table_name = f"raw_{name}"
            write_dataframe(conn, table_name, frame)
            log_source_load(
                conn,
                source_name=KAGGLE_SOURCE_NAME,
                table_name=table_name,
                source_path=raw_paths[name],
                row_count=len(frame),
            )

        for name, frame in curated.items():
            write_dataframe(conn, name, frame)
            log_source_load(
                conn,
                source_name=KAGGLE_SOURCE_NAME,
                table_name=name,
                source_path=DUCKDB_PATH,
                row_count=len(frame),
            )

        validation_results = run_kaggle_validations(curated)
        log_validation_results(conn, validation_results)

    return validation_results


def build_database() -> dict[str, object]:
    raw = read_raw_csvs()
    curated = build_curated_tables(raw)
    validation_results = write_duckdb(raw, curated)
    failed = validation_results[~validation_results["passed"]]
    return {
        "raw_tables": [f"raw_{name}" for name in raw],
        "curated_tables": list(curated),
        "validation_checks": len(validation_results),
        "validation_failures": len(failed),
        "failed_checks": failed.to_dict("records"),
    }

