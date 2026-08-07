#!/usr/bin/env python3
"""Build the local DuckDB dataset for the first F1 analytics workflow."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.data_sources.kaggle_csv import build_database


def main() -> int:
    result = build_database()

    print(f"DuckDB database built: {DUCKDB_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Curated tables: {', '.join(result['curated_tables'])}")
    print(f"Validation checks: {result['validation_checks']} run, {result['validation_failures']} failed")
    for check in result["failed_checks"]:
        print(f"  FAILED: {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
