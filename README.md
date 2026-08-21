# F1 Analytics

Local Formula 1 data pipeline and questions-analysis/backtesting project. See [`PROJECT.md`](PROJECT.md) for scope and audience, and `_bmad-output/planning-artifacts/` for the active PRD, architecture, and epics.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) 0.12+.

```bash
uv sync
uv run pytest
```

`uv sync` builds the project from `pyproject.toml` (src layout, editable install) and creates `.venv/`. It also resolves the pinned interpreter (`.python-version`: 3.13) — if Python 3.13 isn't already installed locally, `uv` downloads it, which requires network access on that first run. `uv run pytest` runs the offline test suite — tests never touch the network (see `tests/conftest.py`).

## Planning-record guards

Two read-only guards keep the BMad planning records from drifting apart. Both run in
CI (`ci.yml`'s "Planning records" job) and as `bmad-loop` verify gates. Run them locally:

```bash
uv run .github/scripts/validate-records.py    # each record against its own schema
bash tools/artifact-status-assertions.sh      # a done spec vs. its sprint-status.yaml row
```

The second one catches the class the first cannot see: a board and a spec can each be
individually well-formed and still contradict each other.

Optional but recommended, one-time per clone (not tracked by git itself):

```bash
git config core.hooksPath tools/hooks
```

This blocks a commit that stages `sprint-status.yaml` or a spec file without the two
agreeing — the same check CI runs, moved earlier. Commits outside that surface pay nothing.

## Credentials

Every source's credential requirement, in full:

| Source | Credential |
| --- | --- |
| Kaggle | None. `kaggle_csv.py` reads static CSVs already present at `KAGGLE_F1_RAW_DIR` (`data/raw/f1_complete_dataset/`) — no KaggleHub download or token check in the current pipeline. |
| FastF1 | None. |

No other setup is required to run the test suite. Some scripts under `scripts/` have their own separate environment requirements documented in their module docstring (e.g. `scripts/spike_fastf1_adoption.py` runs in an isolated `uv run --isolated --with fastf1==3.8.3 ...` environment, never the main project environment) — check a script's docstring before running it directly.
