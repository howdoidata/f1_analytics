"""Project paths and source names."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
KAGGLE_F1_RAW_DIR = RAW_DATA_DIR / "f1_complete_dataset"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DUCKDB_PATH = PROCESSED_DATA_DIR / "f1_analytics.duckdb"
