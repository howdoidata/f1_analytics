# f1_analytics Documentation Index

Status: Current.

**Type:** monolith
**Primary Language:** Python
**Architecture:** Layered data pipeline (raw landing → DuckDB curated → combined/precedence-ruled → validation → notebook analysis)
**Last Updated:** 2026-07-13

## Project Overview

Portfolio Formula 1 analytics project. Ingests Kaggle historical data and Jolpica current-season data, builds DuckDB curated and precedence-ruled combined tables, validates them, and delivers one executed notebook-based insight (championship-leader identification and conversion analysis). No dashboard, dbt, Airflow, or ML scaffold exists yet.

## Quick Reference

- **Tech Stack:** Python 3.13.7, pandas 3.0.3, duckdb 1.5.4, kagglehub 1.0.2, plotly 6.8.0, jupyter 1.1.1/nbconvert 7.17.1 (all unpinned in `requirements.txt`; versions confirmed live against the repo's own `.venv`)
- **Entry Point:** No single entry point — script-orchestrated pipeline (`scripts/*.py`) plus one notebook
- **Architecture Pattern:** Layered data pipeline, no dbt/Airflow/dashboard
- **Database:** DuckDB (embedded, local file) — 32 tables/views confirmed live at `data/processed/f1_analytics.duckdb`
- **Deployment:** None — local-only project; a fresh repo-wide search found no Dockerfile, docker-compose, `.github/workflows`, or other CI/CD/IaC config

## Generated Documentation

### Core Documentation

- [Source Tree Analysis](./source-tree-analysis.md) - Annotated directory structure
- [Data Models](./data_sources.md) - Data-source architecture, DuckDB tables, and the combined Kaggle/Jolpica precedence rule (pre-existing, actively maintained — satisfies the `data` project type's data-models requirement; not regenerated to avoid diverging from the maintained original)
- [Development Guide](./local_setup.md) - Local setup / KaggleHub authentication workflow (pre-existing — satisfies the development-guide requirement)

### Optional Documentation

- Component Inventory, API Contracts, Deployment Guide: not applicable — `data` project type with `requires_ui_components=false`, `requires_api_scan=false`; no deployment configuration (Dockerfile, CI/CD, IaC) was found in the repository (verified by a fresh repo-wide search during this run).

## Existing Documentation

- [data_sources.md](./data_sources.md) - Kaggle + Jolpica sources, DuckDB tables, precedence rule
- [decisions.md](./decisions.md) - Historical/transitional decision log (most content has no current-authority duplicate; two entries do — see CP-016)
- [backlog.md](./backlog.md) - Historical/transitional backlog classification snapshot (superseded by `_bmad-output/implementation-artifacts/deferred-work.md`; see CP-014)
- [questions.md](./questions.md) - Historical/transitional question log (open questions migrated to `_bmad-output/implementation-artifacts/deferred-work.md`; see CP-015)
- [local_setup.md](./local_setup.md) - KaggleHub authentication and local dev setup
- [run_log.md](./run_log.md) - Append-only command/result history
- [implementation_notes/](./implementation_notes/) - Dated implementation notes (e.g. `016-combined-dataset-championship-leader-notebook.md`)
- [baselines/](./baselines/) - Earlier hand-authored Story 1.1 baseline narratives (now supplementary — see each file's own caveat pointing to this generated set as primary)

## Getting Started

### Prerequisites

Python 3.13.7 (matches the repo's own `.venv`); packages in `requirements.txt` (kagglehub, pandas, duckdb, plotly, jupyter, nbconvert); a KaggleHub API token at `~/.kaggle/access_token` (never committed — see `local_setup.md`).

### Setup

```bash
pip install -r requirements.txt
```

### Run Locally

```bash
python3 scripts/download_kagglehub_f1_data.py
python3 scripts/pull_jolpica_data.py
python3 scripts/build_f1_dataset.py
python3 scripts/build_combined_dataset.py
python3 scripts/analyze_championship_leaders.py
```

### Run Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

14 test modules under `tests/` (210 passing tests as of 2026-07-21) cover the question-catalog and backtest-analysis modules. Data-quality checks additionally run via `src/f1_analytics/validation/checks.py`, invoked as part of the pipeline scripts above.

## For AI-Assisted Development

This documentation set was generated to give AI agents (both within this repo and in the `platform` root-protocol migration) a grounded, dated snapshot of `f1_analytics`.

### When Planning New Features:

**Data pipeline / ingestion features:** → Reference: `data_sources.md`, `source-tree-analysis.md`, `../_bmad-output/project-context.md`

**Analysis / notebook features:** → Reference: `../_bmad-output/project-context.md` (Technology Stack & Critical Implementation Rules), `implementation_notes/016-combined-dataset-championship-leader-notebook.md`

**Full-repo / migration-relevant features:** → Reference all of the above

**Deployment changes:** → None applicable; no deployment configuration exists in this repository as of this scan.

---

_Documentation generated by the BMAD Method `document-project` skill (deep scan, full rescan), run for real and unattended as the genuine execution superseding the earlier fabricated run-log entry ("Story 1.1 Code-Review Follow-Up: Actual bmad-document-project / bmad-generate-project-context Execution", `docs/run_log.md`), 2026-07-12. Companion: `bmad-generate-project-context` output at `f1_analytics/_bmad-output/project-context.md`._
