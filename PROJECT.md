# F1 Analytics

## What it is

A small, reproducible Formula 1 analytics project. It turns a committed copy of the public Jolpica results data and FastF1 lap extracts into a tested DuckDB database, answers questions about races with tested Python functions, and publishes each answer as a Quarto report. Anyone can clone it, rebuild the database offline with one command, and re-render the reports.

It is a portfolio piece. It shows how the author handles data engineering (sourcing, modelling, testing, a guarded build), analysis (reusable, tested functions behind every number) and communication (short reports that state a question and answer it).

## Who it is for

Hiring managers and analytics leads who want to see how the author works, and data people interested in F1 analysis they can reproduce.

## What is in the code

| Area | Tools | Where |
| --- | --- | --- |
| Language and environment | Python 3.13, uv | `pyproject.toml`, `uv.lock` |
| Data sources | Jolpica F1 API over `requests`; FastF1 for lap and weather data | `src/f1_analytics/data_sources/`, `scripts/dump_jolpica.py` |
| Storage | DuckDB, one local file built from `data/raw/` | `src/f1_analytics/database/` |
| Modelling and data tests | dbt with dbt-duckdb, in SQL | `dbt/` |
| Analysis | pandas | `src/f1_analytics/analysis/` |
| Figures | Plotly, with kaleido for the PDFs' static images | `src/f1_analytics/analysis/figures.py` |
| Reports | Quarto, running Python through Jupyter (nbclient, ipykernel) | `reports/` |
| Tests | pytest (offline) and the dbt tests | `tests/`, `dbt/` |
| CI and publishing | GitHub Actions: one test job, and a GitHub Pages deploy of the committed report HTML | `.github/workflows/` |

The commands are `uv run build` (raw data to DuckDB, offline), `uv run refresh` (new rounds, maintainer only), `uv run gallery` (the report gallery) and `uv run quarto render reports`. The README explains each one, and [`docs/decisions.md`](docs/decisions.md) explains why the project is built this way.

## Scope

- Results history from 1950 to the latest round, from Jolpica only. Standings after each round are derived from results.
- Lap and weather data for each completed 2026 race, from FastF1.
- Reports that each answer one question. Today there are three: Williams' combined finish at Zandvoort, Albon's grid-to-finish change at Singapore, and how often the championship leader at this point of the season goes on to win.

## Intentionally not used

- **Airflow.** The pipeline is one command, `uv run build`, run by hand after each race on about 10 MB of data. A scheduler would add infrastructure without adding value.
- **Tableau.** The reports live in the repo as Quarto documents so that every figure is reproducible from code. A Tableau Public dashboard, if one is made, lives outside the repo.
- **scikit-learn.** No report question needs a machine-learning model yet. It is deferred until one does.
- **Kaggle.** Results used to come from a Kaggle dataset merged with Jolpica. Jolpica alone covers 1950 to the latest round, so a single source removes the reconciliation between two datasets and the rules for choosing between them.
