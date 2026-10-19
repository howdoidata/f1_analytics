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

`uv run build` runs `dbt build` on the project in `dbt/`: staging tables (schema `staging`) type the raw CSVs, the marts in `main` are the tables the analysis reads, and the dbt tests check them. It builds into a fresh temporary file and swaps it in only if every model and test passes and no guarded table (`results`, `sprint_results`, `qualifying`, `raw_fastf1_*`) has shrunk; otherwise it exits 1 and leaves the previous DuckDB file as it was. Each build's test results are in `dbt/target/run_results.json`.

To run dbt directly, from the repo root (this writes straight to `data/processed/f1_analytics.duckdb`, with no swap or shrink guard):

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt
```

Paths resolve from the package location, so `uv run build` writes to this repo's `data/processed/` whatever the current directory.

Other scripts, run from the repo root:

```bash
uv run python scripts/golden_check.py   # compare the golden report values with the built DuckDB
uv run python scripts/dump_jolpica.py   # one-time Jolpica dump (already committed; about 90 min at the API rate limit)
```

## Credentials

| Command | Credential |
| --- | --- |
| `uv run build` | None. It reads only `data/raw/` and makes no network calls. |
| `uv run refresh` | An F1TV subscription login for FastF1. Run `uv run python -m fastf1 auth f1tv --authenticate` first (it waits for the browser login to finish); `refresh` checks the token before doing anything and exits if it is missing or expired. Jolpica needs no credential. |

The test suite needs no credentials.
