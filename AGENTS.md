# AGENTS.md

Local Formula 1 data pipeline and analysis project. Python source lives in `src/f1_analytics/`, scripts in `scripts/`, SQL in `sql/`, tests in `tests/`.

Set up and run the tests with:

```bash
uv sync && uv run pytest
```

Build the DuckDB file from the committed `data/raw/` with `uv run build` (offline). `uv run refresh` needs an F1TV login; see `README.md`.

The test suite is offline: `tests/conftest.py` blocks all network access, so no credentials are needed.
