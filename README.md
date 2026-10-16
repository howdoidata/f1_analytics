# F1 Analytics

Local Formula 1 data pipeline and questions-analysis/backtesting project. See [`PROJECT.md`](PROJECT.md) for scope and audience.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) 0.12+.

```bash
uv sync
uv run pytest
```

`uv sync` builds the project from `pyproject.toml` (src layout, editable install) and creates `.venv/`. It also resolves the pinned interpreter (`.python-version`: 3.13) — if Python 3.13 isn't already installed locally, `uv` downloads it, which requires network access on that first run. `uv run pytest` runs the offline test suite — tests never touch the network (see `tests/conftest.py`).

## Data

`data/raw/` is committed: the Jolpica CSVs (1950 to the latest round) and the FastF1 extracts. See [`data/raw/NOTICE.md`](data/raw/NOTICE.md) for sources and licences.

```bash
uv run build     # data/raw/ -> data/processed/f1_analytics.duckdb (offline, no credentials)
uv run refresh   # append new Jolpica rounds, fetch missing FastF1 extracts, then build
```

## Credentials

| Command | Credential |
| --- | --- |
| `uv run build` | None. It reads only `data/raw/` and makes no network calls. |
| `uv run refresh` | An F1TV subscription login for FastF1. Run `python -m fastf1 auth f1tv --authenticate` first; `refresh` checks the token before doing anything and exits if it is missing or expired. Jolpica needs no credential. |

The test suite needs no credentials.
