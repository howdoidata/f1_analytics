# f1_analytics - Source Tree Analysis

Status: Historical evidence.

**Date:** 2026-07-12

**Post-retirement note (2026-07-13):** The legacy local governance mechanism
listed in this generated snapshot was retired after the sibling `platform`
guardrail replacement was proven blocking. Removed items include
`scripts/fitness_check.py`, `scripts/workflow.py`,
`docs/terminal_protocol.md`, `docs/handoffs/`, and `docs/terminal_roles/`.
This document is retained as historical source-tree context, not as the active
file inventory.

## Overview

Single monolith Python data project. Reusable logic lives under the installable `src/f1_analytics/` package (data source loaders, DuckDB IO, validation, analysis); thin CLI wrappers live under `scripts/`; one executed notebook drives the current insight deliverable; `sql/` holds hand-written analysis/curated SQL; `data/` and `outputs/` are gitignored working directories for raw/processed data and generated artifacts respectively. This tree was rebuilt from a fresh `find` of the live repository (excluding `.git`, `.venv`, `__pycache__`, `.bmad-loop`, `_bmad`, `.claude`), not carried over from the prior (fabricated) run.

## Complete Directory Structure

```
f1_analytics/
  AGENTS.md              # Root operating instructions (read before any project change)
  PROJECT.md              # Project purpose/scope
  requirements.txt        # Unpinned Python dependencies (6 packages)
  data/                    # Gitignored — raw + processed data landing
    raw/
      f1_complete_dataset/       # Kaggle CSVs (8 files)
      jolpica/                   # Cached Jolpica JSON, by endpoint/season_round
    processed/
      f1_analytics.duckdb        # Live DB: 32 tables/views as of this scan
  docs/                    # Hand-maintained project documentation + BMAD output
    active_context.md
    architecture.md              # Authoritative architecture doc (pre-existing)
    architecture_operating_model.md
    architecture_principles.md
    asset_inventory.md
    backlog.md
    baselines/                    # Dated hand-authored Story 1.1 baseline narratives (supplementary; this generated set is now the primary dated artifact)
    data_sources.md               # Authoritative data-source / precedence-rule doc (pre-existing)
    decisions.md
    diagrams/
    implementation_notes/
    inbox/
    local_setup.md
    project_profile.md
    prompts/
    questions.md
    run_log.md                    # Command/result history (append-only)
    workflow_guide.md             # Historical note for retired local workflow guide
  notebooks/
    championship_leader_combined_analysis.ipynb   # Executed insight notebook
    .ipynb_checkpoints/                              # Jupyter autosave, not a source artifact
  outputs/                 # Gitignored — generated artifacts
    figures/
    reports/
    tables/
  scripts/                 # CLI entry-point wrappers (call into src/f1_analytics/)
    analyze_championship_leaders.py   # 34 lines
    build_combined_dataset.py         # 27 lines
    build_f1_dataset.py               # 29 lines
    download_kagglehub_f1_data.py     # 55 lines
    pull_jolpica_data.py              # 34 lines
  sql/
    analysis/
      kaggle_jolpica_coverage.sql     # Defines the kaggle_jolpica_coverage view
      README.md
    curated/
      README.md                        # No curated SQL files yet — Version 1 transformations are Python-driven
  src/
    f1_analytics/           # Installable package — reusable logic
      __init__.py
      config.py              # 22 lines — project paths and source names
      analysis/
        __init__.py
        championship_leaders.py            # 723 lines — largest module in the repo
        combined_championship_leaders.py   # 105 lines
      data_sources/
        __init__.py
        combined_dataset.py    # 189 lines — precedence-ruled Kaggle+Jolpica combined tables
        jolpica.py              # 43 lines — minimal Jolpica/Ergast HTTP client skeleton
        jolpica_loader.py       # 277 lines — full Jolpica load/parse/write pipeline
        kaggle_csv.py           # 197 lines
        standings.py            # 62 lines — shared points/standings logic (curated + combined)
      database/
        __init__.py
        duckdb_io.py            # 160 lines — connect/write/register/log helpers
      validation/
        __init__.py
        checks.py               # 91 lines — Kaggle null-rate + referential-integrity checks
```

## Critical Directories

### `src/f1_analytics/`

Installable package containing all reusable, non-CLI logic.

**Purpose:** Single source of truth for data loading, DB IO, validation, and analysis logic, shared between curated (Kaggle-only) and combined (Kaggle+Jolpica) pipelines.
**Contains:** `data_sources/` (loaders + combined-dataset precedence logic), `database/` (DuckDB IO), `analysis/` (championship-leader logic — the two largest modules in the repo), `validation/` (data-quality checks).
**Entry Points:** None directly executable — imported by `scripts/*.py`.

### `scripts/`

CLI wrappers that orchestrate `src/f1_analytics/` logic into runnable pipeline steps. The former legacy governance scripts were retired on 2026-07-13 and are not part of the active data pipeline.

**Purpose:** Provide `python3 scripts/<name>.py`-style entry points for ingestion, dataset building, and analysis.
**Contains:** `download_kagglehub_f1_data.py`, `build_f1_dataset.py`, `pull_jolpica_data.py`, `build_combined_dataset.py`, `analyze_championship_leaders.py` (pipeline, all under 60 lines, confirmed to only import and call into `src/f1_analytics/`).

### `sql/`

Hand-written SQL used for analysis, separate from the Python-generated DuckDB tables.

**Purpose:** Analyst-facing SQL for coverage checks and (eventually) curated views.
**Contains:** `analysis/kaggle_jolpica_coverage.sql` (the only `.sql` file in the repo as of this scan); `curated/` holds only a README — no curated SQL files exist yet.

### `notebooks/`

**Purpose:** Executed, notebook-based insight delivery (no dashboard/server exists).
**Contains:** `championship_leader_combined_analysis.ipynb` — the current-season championship-leader conversion analysis referenced in Implementation Note 016 — plus a `.ipynb_checkpoints/` autosave directory that is not itself a tracked source artifact.

### `docs/`

**Purpose:** Project documentation, decision records, and (as of this scan) the BMAD `document-project`/`generate-project-context` output.
**Contains:** Extensive hand-maintained docs (architecture, data sources, decisions, run log) plus `docs/baselines/` (the earlier Story 1.1 hand-authored narrative baselines, now supplementary to this generated set — see the caveat in `docs/baselines/*.md`) and this generated documentation set.

### `data/` and `outputs/`

**Purpose:** Working directories for raw/processed data and generated reports/tables/figures.
**Contains:** Gitignored; not committed to version control, not part of the reviewable source tree. `data/processed/f1_analytics.duckdb` was queried directly (read-only) as part of this scan and currently holds 32 tables/views.

## Entry Points

- **Main Entry:** No single main entry point — this is a script-orchestrated pipeline, not an application.
- **Additional:**
  - `scripts/download_kagglehub_f1_data.py`: Kaggle ingestion entry point
  - `scripts/pull_jolpica_data.py`: Jolpica ingestion entry point (auto-detects target season as `MAX(season)` from the `results` table)
  - `scripts/build_f1_dataset.py`: Kaggle-only curated table build
  - `scripts/build_combined_dataset.py`: Combined Kaggle+Jolpica table build (requires the two builds above to have already run)
  - `scripts/analyze_championship_leaders.py`: Championship-leader analysis entry point
  - `notebooks/championship_leader_combined_analysis.ipynb`: Executed analysis/report entry point

## File Organization Patterns

Reusable logic is isolated in `src/f1_analytics/` by concern (`data_sources/`, `database/`, `analysis/`, `validation/`); each `scripts/*.py` is a thin wrapper (all verified by full read: 27-55 lines each) that imports and calls into that package rather than embedding logic directly. No `tests/` directory exists as of this scan — confirmed by a fresh repo-wide search.

## Key File Types

### Python modules

- **Pattern:** `src/f1_analytics/**/*.py`
- **Purpose:** Reusable pipeline/analysis/validation logic
- **Examples:** `combined_dataset.py`, `standings.py`, `checks.py`

### CLI scripts

- **Pattern:** `scripts/*.py`
- **Purpose:** Runnable pipeline steps
- **Examples:** `build_combined_dataset.py`, `analyze_championship_leaders.py`

### SQL

- **Pattern:** `sql/**/*.sql`
- **Purpose:** Analyst-facing coverage query
- **Examples:** `sql/analysis/kaggle_jolpica_coverage.sql` (the repo's only SQL file)

## Asset Locations

No significant binary/media assets detected. `outputs/figures/` holds one generated Plotly HTML output (`constructor_comeback_cases.html`) but is gitignored and not a committed asset directory.

## Configuration Files

- **`requirements.txt`**: Unpinned Python dependency list (`kagglehub`, `pandas`, `duckdb`, `plotly`, `jupyter`, `nbconvert`) — 6 lines, confirmed by direct read.
- **`.vscode/settings.json`**: Editor configuration (not project-behavioral).
- **`.gitignore`**: Excludes `data/`, `outputs/`, `.venv/`, and other local-only artifacts.

## Notes for Development

No automated test suite exists (no `tests/` directory, no `test_*.py`/`*_test.py` files found anywhere in the repo outside third-party code in `.venv`). The former `scripts/fitness_check.py` and `scripts/workflow.py` governance/process-gate layer was retired on 2026-07-13 after replacement platform enforcement was proven blocking. The repository had zero git commits as of this scan (`git status --short --branch` reports "No commits yet on master").

---

_Generated using the BMAD Method `document-project` workflow (deep scan, full rescan) as the genuine execution superseding the earlier fabricated run-log entry, 2026-07-12._
