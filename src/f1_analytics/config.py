"""Project paths and source names."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
JOLPICA_RAW_DIR = RAW_DATA_DIR / "jolpica"
FASTF1_RAW_DIR = RAW_DATA_DIR / "fastf1"
# Gitignored caches: FastF1's HTTP cache and the Jolpica dump's page cache.
FASTF1_CACHE_DIR = RAW_DATA_DIR / "fastf1_cache"
JOLPICA_CACHE_DIR = DATA_DIR / "cache" / "jolpica"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DUCKDB_PATH = PROCESSED_DATA_DIR / "f1_analytics.duckdb"
