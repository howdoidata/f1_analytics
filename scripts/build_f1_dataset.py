#!/usr/bin/env python3
"""Build the local DuckDB dataset from the Kaggle curated layer (Story 1.5)."""

from pathlib import Path

from f1_analytics.config import DUCKDB_PATH, KAGGLE_F1_RAW_DIR
from f1_analytics.data_sources.kaggle_csv import build_curated_tables, read_raw_csvs
from f1_analytics.database.duckdb_io import connect_duckdb, write_dataframe


def main(raw_dir: Path = KAGGLE_F1_RAW_DIR, db_path: Path = DUCKDB_PATH) -> int:
    raw = read_raw_csvs(raw_dir)
    curated = build_curated_tables(raw)

    with connect_duckdb(db_path) as conn:
        for name, frame in raw.items():
            write_dataframe(conn, f"raw_{name}", frame)
        for name, frame in curated.items():
            write_dataframe(conn, name, frame)

    print(f"DuckDB database built: {db_path}")
    print(f"Raw tables: {', '.join(f'raw_{name}' for name in raw)}")
    print(f"Curated tables: {', '.join(curated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
