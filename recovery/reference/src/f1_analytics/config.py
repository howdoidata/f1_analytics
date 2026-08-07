"""Project paths and source names."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
KAGGLE_F1_RAW_DIR = RAW_DATA_DIR / "f1_complete_dataset"
JOLPICA_RAW_DIR = RAW_DATA_DIR / "jolpica"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
TABLES_DIR = OUTPUTS_DIR / "tables"
DUCKDB_PATH = PROCESSED_DATA_DIR / "f1_analytics.duckdb"

KAGGLE_SOURCE_NAME = "kaggle_formula_1_complete_dataset"
JOLPICA_SOURCE_NAME = "jolpica_ergast_api"
KAGGLE_DATASET_HANDLE = "patelris/formula-1-complete-dataset-1950-2026"
JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"

