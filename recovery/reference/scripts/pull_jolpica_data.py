#!/usr/bin/env python3
"""Pull Jolpica/Ergast data for the current target season into DuckDB."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.data_sources.jolpica_loader import build_jolpica_dataset
from f1_analytics.database.duckdb_io import connect_duckdb


def determine_target_season() -> int:
    with connect_duckdb(DUCKDB_PATH, read_only=True) as conn:
        return int(conn.execute("SELECT MAX(season) FROM results").fetchone()[0])


def main() -> int:
    season = determine_target_season()
    result = build_jolpica_dataset(season)

    print(f"Jolpica target season: {result['season']}")
    for table_name, row_count in result["row_counts"].items():
        print(f"  {table_name}: {row_count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
