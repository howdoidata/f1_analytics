#!/usr/bin/env python3
"""Build the scoped, precedence-ruled combined Kaggle+Jolpica dataset."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from f1_analytics.config import DUCKDB_PATH
from f1_analytics.data_sources.combined_dataset import build_combined_dataset


def main() -> int:
    result = build_combined_dataset()

    print(f"Combined tables written to: {DUCKDB_PATH.relative_to(PROJECT_ROOT)}")
    for table_name, row_count in result["row_counts"].items():
        print(f"  {table_name}: {row_count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
