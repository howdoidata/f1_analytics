# AGENTS.md

Local Formula 1 data pipeline and analysis project. Python source lives in `src/f1_analytics/`, scripts in `scripts/`, the dbt project (SQL models and tests) in `dbt/`, tests in `tests/`.

Set up and run the tests with:

```bash
uv sync && uv run pytest
```

Build the DuckDB file from the committed `data/raw/` with `uv run build` (offline). `uv run refresh` needs an F1TV login; see `README.md`.

The test suite is offline: `tests/conftest.py` blocks all network access, so no credentials are needed.

Reports are Quarto files at `reports/<date>-<slug>/report.qmd`; they only call `f1_analytics.analysis` (no plotly, SQL or computation in a `.qmd`), and `uv run quarto render reports` re-renders them after `uv run build`.

Every dbt mart is tagged `core` or `one_off` (with `meta.question` naming its report folder), and `tests/test_mart_check.py` enforces rules 1–7 of the mart conventions: all report SQL lives in `analysis/data.py`, whose loaders declare their tables with `@reads(...)`.

Report frontmatter may carry the optional `status: provisional | validated` and a `gaps:` list (one known gap per `- ` line); the gallery shows both, and any other `status` fails `uv run gallery`.

`reports/README.md` and `reports/index.html` are generated: after adding a report or changing its frontmatter, run `uv run gallery` (a test fails until you do).
