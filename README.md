# F1 Analytics

Local Formula 1 data pipeline and questions-analysis/backtesting project. See [`PROJECT.md`](PROJECT.md) for scope and audience.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) 0.12+.

```bash
uv sync
uv run pytest
```

`uv sync` builds the project from `pyproject.toml` (src layout, editable install) and creates `.venv/`. It also resolves the pinned interpreter (`.python-version`: 3.13) — if Python 3.13 isn't already installed locally, `uv` downloads it, which requires network access on that first run. `uv run pytest` runs the offline test suite — tests never touch the network (see `tests/conftest.py`).

## Credentials

Every source's credential requirement, in full:

| Source | Credential |
| --- | --- |
| Kaggle | None. `kaggle_csv.py` reads static CSVs already present at `KAGGLE_F1_RAW_DIR` (`data/raw/f1_complete_dataset/`) — no KaggleHub download or token check in the current pipeline. |
| FastF1 | None. |

No other setup is required to run the test suite. Some scripts under `scripts/` have their own separate environment requirements documented in their module docstring — check a script's docstring before running it directly.
