"""Project paths and source names."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
JOLPICA_RAW_DIR = RAW_DATA_DIR / "jolpica"
FASTF1_RAW_DIR = RAW_DATA_DIR / "fastf1"
# `fetch-sessions` output: per-car-per-race summaries and practice stints (committed).
FASTF1_SUMMARY_DIR = RAW_DATA_DIR / "fastf1_summary"
FASTF1_PRACTICE_DIR = RAW_DATA_DIR / "fastf1_practice"
# Gitignored caches: FastF1's HTTP cache and the Jolpica dump's page cache.
FASTF1_CACHE_DIR = RAW_DATA_DIR / "fastf1_cache"
JOLPICA_CACHE_DIR = DATA_DIR / "cache" / "jolpica"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DUCKDB_PATH = PROCESSED_DATA_DIR / "f1_analytics.duckdb"
# The dbt project `uv run build` runs (its profiles.yml lives there too).
DBT_DIR = PROJECT_ROOT / "dbt"
