#!/usr/bin/env python3
"""Download the selected Formula 1 Kaggle dataset with KaggleHub."""

from pathlib import Path
import sys


DATASET_HANDLE = "patelris/formula-1-complete-dataset-1950-2026"
TOKEN_PATH = Path.home() / ".kaggle" / "access_token"
OUTPUT_DIR = Path("data/raw/f1_complete_dataset")


def main() -> int:
    if not TOKEN_PATH.is_file():
        print(
            "KaggleHub token file missing. Expected token at "
            f"{TOKEN_PATH}. See docs/local_setup.md.",
            file=sys.stderr,
        )
        return 1

    if not TOKEN_PATH.read_text(encoding="utf-8").strip():
        print(
            "KaggleHub token file is empty. Expected token at "
            f"{TOKEN_PATH}. See docs/local_setup.md.",
            file=sys.stderr,
        )
        return 1

    try:
        import kagglehub
    except ImportError:
        print(
            "Missing dependency: kagglehub. Run `pip install -r requirements.txt`.",
            file=sys.stderr,
        )
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded_path = kagglehub.dataset_download(
        DATASET_HANDLE,
        output_dir=str(OUTPUT_DIR),
    )

    result_path = Path(downloaded_path) if downloaded_path else OUTPUT_DIR
    files = [path for path in OUTPUT_DIR.rglob("*") if path.is_file()]

    print(f"Downloaded path: {result_path}")
    print(f"Output directory: {OUTPUT_DIR.resolve()}")
    print(f"File count: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
