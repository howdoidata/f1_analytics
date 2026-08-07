---
baseline_commit: 1dcdf795b53f15d2be0ac799fd62c62cd0914af7
---

# Story 1.4: Project Foundation That Survives A Fresh Clone

Status: done

## Story

As a downstream dev agent,
I want the package skeleton, invocation convention, and offline-test harness committed,
so that every later story builds and tests identically from a bare checkout.

## Acceptance Criteria

1. **Given** a fresh clone plus the documented Kaggle credential, **when** `uv sync` and `uv run pytest` run, **then** the environment builds against `pyproject.toml` (src layout, editable install, uv 0.12 conventions per its changed `uv init` defaults) and an initial test passes, offline.
2. **And** the `src/f1_analytics/` skeleton matches the spine's Structural Seed (empty `data_sources/`, `database/`, `analysis/`, `validation/` packages), and a repo-wide autouse pytest fixture blocks network access so any test touching a socket fails loudly (AD-11).
3. **And** the README-level run instructions name every credential per source (Kaggle: token file; FastF1/Jolpica: none).

**Verification:** `uv run pytest` green on a scratch clone; a deliberately network-touching test fails. Governed by: AD-11, AR-1, AR-12.

## Tasks / Subtasks

- [x] Task 1: Establish `pyproject.toml` on uv 0.12 conventions (AC: 1)
  - [x] Upgrade local `uv` from 0.11.29 to 0.12.x — `brew upgrade uv` (0.12.2 is bottled and available; confirmed via `brew info uv`). This is required, not optional: uv 0.12.0 changed `uv init`'s packaged-project defaults (src layout + `[build-system]`), and AR-1/AC-1 explicitly bind to "uv 0.12 conventions." Verify with `uv --version`.
  - [x] Pin the interpreter: `uv python pin 3.13` (writes `.python-version`; Python 3.13.7 is already present locally at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`). This lets a fresh clone resolve the right interpreter automatically even without a prior manual Python install.
  - [x] Hand-author `pyproject.toml` at the repo root — do **not** run `uv init` in place. The directory is a non-empty, pre-existing git repo with an already-partial `src/f1_analytics/` tree; `uv init`'s generative/interactive behavior on top of that is unpredictable and risks clobbering or misnaming existing content. Write directly:
    - `[project]`: `name = "f1_analytics"`, `version = "0.1.0"`, `requires-python = ">=3.13,<3.14"` (matches the spine's deliberate 3.13 pin).
    - `[build-system]`: `requires = ["uv_build>=0.12.2,<0.13"]`, `build-backend = "uv_build"` — this is uv 0.12's packaged-by-default backend; it auto-discovers `src/f1_analytics/` because the package name matches, giving src-layout + editable install with no extra config.
    - `[dependency-groups]`: `dev = ["pytest>=9.1,<10"]` (spine Stack: pytest 9.x, 9.1.1 verified).
    - Do **not** add `pandas`, `duckdb`, `fastf1`, `kagglehub`, or `plotly` as dependencies yet — nothing under `src/f1_analytics/` imports them at this point in the rebuild (Stories 1.5–1.7 add runtime deps when their loaders/scripts actually need them). Adding them now is premature and, for `fastf1` specifically, actively wrong: the FastF1 decision record requires it to run in a *separate* `pandas<3.0` environment via `uv run --isolated --with fastf1==3.8.3 ...` (see Story 1.2's spike script), never as a main-project dependency alongside the spine's `pandas 3.0.x` baseline.
    - Do **not** add a `[project.scripts]` entry point — the Structural Seed uses thin `uv run scripts/*.py` invocations, not installed console commands.
  - [x] Run `uv sync` to generate `uv.lock` and `.venv/` (`.venv/` is already gitignored). Confirm `uv.lock` is **not** gitignored — it must be committed (NFR-1 reproducibility). **Finding:** `uv sync` failed on the first attempt (`Expected a Python module at: src/f1_analytics/__init__.py`) — `uv_build` requires the top-level package marker to exist before it can build the project at all, which Task 3 doesn't create until after this step in the story's written order. Fixed by creating `src/f1_analytics/__init__.py` here (its final Task 3 content, one-line docstring) rather than blocking Task 1 on Task 3. Re-ran `uv sync` — succeeded, resolved 7 packages incl. `pytest==9.1.1`.

- [x] Task 2: Empty the `analysis/` package per the Structural Seed (AC: 2)
  - [x] Current state: `src/f1_analytics/analysis/` holds 3 non-empty files — `question_backtest_explanations.py`, `question_feature_availability.py`, `status_badge.py` — committed in the initial post-loss commit (`ec5e725`). These are forward-built implementations for future stories (2.6 feature contract, 3.4 explanations, 3.5 status badges); each imports sibling modules that don't exist anywhere in `src/` yet (`question_catalog`, `question_backtest_report`, `question_backtest_scoring`, `question_answers`, `question_predictions`). The architecture spine's AD-10 explicitly demotes **all** surviving modules — this pre-loss code included — to "reference material," never a fixed point (the same status Story 1.3 gave the tarball's V1 code). This story's AC literally says "empty ... `analysis/` ... packages," so these 3 files must move out, not stay.
  - [x] `git mv` the 3 files (preserve history) into `recovery/reference/src/f1_analytics/analysis/` — that directory already exists from Story 1.3's tarball salvage and has no filename collision with its existing `championship_leaders.py` / `combined_championship_leaders.py` / `__init__.py`.
  - [x] `git mv` their 2 matching orphaned test files — `tests/test_question_backtest_explanations.py` and `tests/test_question_backtest_report.py` — into a new `recovery/reference/tests/` directory (does not exist yet; create it).
  - [x] `git mv` the other 2 currently-broken test files in `tests/` into the same new `recovery/reference/tests/` — `tests/test_jolpica_loader.py` and `tests/test_championship_leaders_report.py`. Both predate this story and test code that Story 1.3 already relocated to `recovery/reference/src/f1_analytics/{data_sources/jolpica*.py, analysis/championship_leaders.py}`; as committed they currently fail collection (`ModuleNotFoundError`) because nothing under the live `src/` exports those modules anymore.
  - [x] This is a relocation, not a deletion — every moved file stays fully readable and git-tracked for its rightful future story (Epic 2.6, 3.4, 3.5, or 1.6/1.5's reconciliation with the V1 reference code) to consciously adapt or replace per AD-10. None of it may be imported by anything under the live `src/`.
  - [x] Verify: `find src/f1_analytics/analysis -type f` returns nothing (before Task 3 adds `__init__.py`); `find tests -name 'test_*.py'` returns nothing (before Task 5 adds this story's own test file). Both confirmed empty; git recognized all 7 as renames (`R`), preserving history. Also removed stale `__pycache__` bytecode left behind under `src/f1_analytics/analysis/` and `tests/` from the pre-move files (gitignored, not tracked, just tidy-up).

- [x] Task 3: Build the empty package skeleton (AC: 2)
  - [x] Create `src/f1_analytics/__init__.py` (top-level package marker — currently missing entirely). One-line docstring only: `"""F1 Analytics: local questions-analysis and backtesting pipeline."""` (already created during Task 1's `uv sync` fix; re-normalized here to match the sibling packages' exact docstring+blank-line byte layout).
  - [x] Create `src/f1_analytics/analysis/__init__.py` (now empty after Task 2). One-line docstring, matching the style of the existing `database/__init__.py` / `data_sources/__init__.py`: `"""Catalog loading, extractors, coverage, scoring, and reporting logic."""`
  - [x] Create the new `src/f1_analytics/validation/` package (does not exist on disk at all today — confirmed, not just empty). `__init__.py`: `"""Advisory post-build validation checks."""`
  - [x] Leave `src/f1_analytics/database/__init__.py` and `src/f1_analytics/data_sources/__init__.py` untouched — already correctly empty, 2-line docstring style.
  - [x] Verify: `uv run python -c "import f1_analytics, f1_analytics.analysis, f1_analytics.data_sources, f1_analytics.database, f1_analytics.validation"` succeeds with no output. Confirmed — printed `OK`.

- [x] Task 4: Add the repo-wide network-blocking pytest fixture (AC: 2)
  - [x] Create `tests/conftest.py` with an `autouse=True` fixture that monkeypatches `socket.socket.connect` **and** `socket.socket.connect_ex` (covers both the blocking and non-blocking connect paths) to raise a `RuntimeError` naming the blocked `(host, port)`. No per-test opt-in should be required — every test in the suite gets this automatically (AD-11: "a network call inside pytest is a defect"). Implemented via pytest's built-in `monkeypatch` fixture (auto-restores after each test).
  - [x] Do not add `pytest-socket` or any other new dependency for this — a small stdlib-only autouse fixture is simpler to reason about and matches AGENTS.md's "prefer simple, maintainable solutions... do not create unnecessary abstractions."
  - [x] Manually verify the "fails loudly" half of the story's Verification line, and record the evidence in the Dev Agent Record — do not leave a permanently-failing test in the committed suite: temporarily add a throwaway test calling `socket.create_connection(("example.com", 80), timeout=2)` with **no** `pytest.raises` wrapper, run `uv run pytest`, confirm it fails with the fixture's `RuntimeError` (not a hang, not a real network attempt), then delete the throwaway test. Confirmed: failed in 0.09s with `RuntimeError: Network access is blocked in tests (AD-11): blocked connect to (...)` — no hang, no real connection attempted. Throwaway test deleted afterward.

- [x] Task 5: Add the initial offline smoke test (AC: 1, 2)
  - [x] Create `tests/test_project_foundation.py`:
    - `test_package_and_subpackages_importable()` — imports `f1_analytics` and its 4 sub-packages, asserts each module object exists (proves the editable install + src layout work end-to-end; this is the AC's "initial test [that] passes, offline").
    - `test_network_access_is_blocked()` — wraps a `socket.create_connection(...)` call in `pytest.raises(RuntimeError)` (permanent regression coverage for Task 4's guard — this test itself is green).
  - [x] Verify: `uv run pytest -v` exits 0 with exactly these 2 tests collected — no leftover broken tests from Task 2's relocation. **Finding (corrects Dev Notes' "Testing standards" claim):** relocating the 4 legacy test files out of `tests/` was *not* sufficient on its own — pytest's default rootdir-recursive collection still discovered them under `recovery/reference/tests/` and failed with 4 `ModuleNotFoundError`/`ImportError` collection errors (`pandas` not installed; `f1_analytics.data_sources.jolpica`, `f1_analytics.analysis.question_answers` don't exist under live `src/`). Fixed by adding `[tool.pytest.ini_options]` / `testpaths = ["tests"]` to `pyproject.toml` (a necessary addition beyond Task 1's originally-specified `pyproject.toml` content). Re-ran: `2 passed in 0.02s`, exactly the 2 new tests, `recovery/reference/` correctly excluded.

- [x] Task 6: Document credentials in a root `README.md` (AC: 3)
  - [x] Create `README.md` at the repo root — none exists today (only `PROJECT.md` and `AGENTS.md`, neither states run instructions).
  - [x] Content: a brief pointer to `PROJECT.md` for project scope; setup steps (`uv sync`, `uv run pytest`); a **Credentials** section naming exactly what AC 3 requires, per source:
    - **Kaggle** — local token file at `~/.kaggle/access_token`; link to `docs/local_setup.md` for the full KaggleHub Option 3 steps, don't duplicate them.
    - **FastF1** — no credential.
    - **Jolpica** — no credential.
  - [x] Do not restate the full Kaggle walkthrough or the data-source catalog already in `docs/local_setup.md` / `docs/data_sources.md` — link out to them; the README is an entry point, not a duplicate.

- [x] Task 7: Verify and record (AC: 1, 2, 3)
  - [x] `uv --version` → confirm `0.12.x`. Confirmed: `uv 0.12.2 (Homebrew 2026-08-05 x86_64-apple-darwin)`.
  - [x] Simulate a scratch clone: either `rm -rf .venv uv.lock && uv sync` in place, or clone the pushed branch to a scratch path — pick one, record which, then `uv run pytest -v`. Used the in-place `rm -rf .venv uv.lock && uv sync` form. Result: fresh `.venv` built, 7 packages resolved, `uv run pytest -v` → `2 passed in 0.02s`.
  - [x] `git status --porcelain` — confirm only the expected new/moved/modified files appear. Confirmed: 7 renames (the Task 2 relocations, git recognized them all as `R`), 1 modified (`sprint-status.yaml`), and untracked new files exactly matching the plan (`.python-version`, `README.md`, `pyproject.toml`, `uv.lock`, `src/f1_analytics/__init__.py`, `src/f1_analytics/analysis/__init__.py`, `src/f1_analytics/validation/__init__.py`, `tests/conftest.py`, `tests/test_project_foundation.py`, plus this story file). Nothing under `data/` or `.venv/` appears (both correctly gitignored).
  - [x] Record all command output (uv version, pytest run, the throwaway network-touching-test failure, git status) in the Dev Agent Record.

### Review Findings

- [x] [Review][Patch] `sprint-status.yaml`'s comment-header `last_updated` and the real YAML `last_updated` field diverge by 5+ hours within the same diff [_bmad-output/implementation-artifacts/sprint-status.yaml:2,52]
- [x] [Review][Patch] README omits the literal Kaggle credential path (`~/.kaggle/access_token`) that Task 6's own checked-off subtask says it includes [README.md:22]
- [x] [Review][Patch] README's "No other setup is required to run... the scripts under `scripts/`" is false — `scripts/spike_fastf1_adoption.py`'s own docstring requires a separate `uv run --isolated --with fastf1==3.8.3 --with kagglehub ...` invocation [README.md:26]
- [x] [Review][Patch] `test_network_access_is_blocked` depends on DNS resolution succeeding — `socket.create_connection` calls `getaddrinfo` before the patched `.connect()`, so in a genuinely offline sandbox it raises `socket.gaierror`, not the expected `RuntimeError`, undermining the very regression test meant to prove AC2's guard [tests/test_project_foundation.py:29]
- [x] [Review][Patch] Neither the README nor `.python-version` note that `uv sync` may need to download the Python 3.13 interpreter (network access) on a fresh clone that doesn't already have it — a gap against AC1's "offline" fresh-clone promise [README.md:7-12, .python-version:1]
- [x] [Review][Patch] `docs/index.md` is still marked "Status: Current" and its Setup section instructs `pip install -r requirements.txt` — directly contradicting the new canonical `uv sync` build path this story establishes. **Resolved via user decision 2026-08-07: patch now** (update Status and Setup section to point at the new uv-based flow) [docs/index.md:3,54]
- [x] [Review][Defer] `conftest.py`'s `connect_ex` override breaks the real method's contract (production `connect_ex` never raises — it returns an errno int) — deferred, currently unreachable: no code in the repo calls `connect_ex` [tests/conftest.py:15-16]
- [x] [Review][Defer] The network-blocking fixture only patches `connect`/`connect_ex`; a connectionless UDP socket's `sendto`/`send` would escape it — deferred, currently unreachable: no UDP usage exists in the repo [tests/conftest.py:19-27]
- [x] [Review][Defer] A `multiprocessing` (spawn) worker or `subprocess` re-imports `socket` fresh and escapes the `monkeypatch` guard — deferred, no test spawns child processes today [tests/conftest.py:19-27]
- [x] [Review][Defer] README states "uv 0.12+" (open-ended) while `pyproject.toml` pins the build backend to `uv_build<0.13` — potential mismatch for a reader who installs a newer `uv` — deferred, not confirmed to actually break `uv sync` [README.md:7, pyproject.toml:11]
- [x] [Review][Defer] Nothing enforces "builds identically from a bare checkout" on an ongoing basis (no CI workflow) — deferred, likely Story 1.8's ("Advisory Build Validation, Logged") territory, not this scaffolding story's [repo-wide]
- [x] [Review][Defer] `requirements.txt` (6 unpinned packages) is now an orphaned, contradictory dependency manifest since `pyproject.toml` declares zero deps. **Resolved via user decision 2026-08-07: defer** — Story 1.5 adds `pandas`/`duckdb`/`kagglehub` as real `pyproject.toml` dependencies (confirmed in epics.md), making `requirements.txt` naturally redundant then; reconcile/remove it as part of that story rather than now [requirements.txt]

Dismissed as noise (5): the "fails loudly" manual-then-deleted throwaway test (matches Task 4's explicit instructions verbatim); the network block's lack of a loopback carve-out (AC2 requires blocking "any test touching a socket," no carve-out specified); the file relocations lacking in-diff explanation (fully explained in this story file, which is the diff's own context); the missing inline rationale comment for `requires-python`'s upper bound in `pyproject.toml` (cosmetic, no established convention requires it); `pyproject.toml` missing `readme`/`description`/`authors`/`license` metadata (not required by any AC/task; this story deliberately scopes `pyproject.toml` to the minimum).

## Dev Notes

### Scope and sequencing

- This is the project-scaffolding story — same infrastructure species as 1.1/1.3, but the deliverable is a buildable package skeleton, not a data salvage. It runs after 1.3 (salvage, review) and before 1.5 (Kaggle curated layer), which explicitly depends on "the 1.4 skeleton."
- Do not write any `raw_*`/curated DuckDB tables, build any ingestion script, or add `catalog/question_catalog.yaml` — those are Stories 1.5–1.7 and 2.x. This story only builds the empty package shell, the invocation convention, and the offline-test harness.
- Do not add FastF1/Kaggle/DuckDB/pandas as pyproject dependencies (see Task 1) — no code in this story imports them, and FastF1 in particular has its own separate-environment requirement recorded in `decisions/fastf1-source-adoption-decision-record.md`.

### Current on-disk state (verified 2026-08-07, before this story runs)

- No `pyproject.toml`, no `uv.lock`, no `.python-version` exist anywhere in the repo. `uv run pytest` currently fails immediately (`ModuleNotFoundError: No module named 'pytest'`) — there is no project for `uv` to build against.
- Installed `uv` is **0.11.29** (Homebrew), not the 0.12.x this story's AC requires. `brew info uv` confirms 0.12.2 is bottled and available (`brew upgrade uv`).
- `src/f1_analytics/` has `database/__init__.py` and `data_sources/__init__.py` (both already a correct 2-line docstring, empty otherwise), and `analysis/` with 3 non-empty files and **no** `__init__.py` of its own. There is **no** top-level `src/f1_analytics/__init__.py` and **no** `validation/` directory at all. (Story 1.3's own Dev Notes flagged exactly this gap as "Story 1.4's job.")
- `tests/` has 4 pre-existing files — `test_championship_leaders_report.py`, `test_jolpica_loader.py`, `test_question_backtest_explanations.py`, `test_question_backtest_report.py` — all committed in the same initial post-loss commit as the 3 `analysis/` survivor files. **All 4 currently fail collection**: every one imports a module that does not exist anywhere under the live `src/` tree today (confirmed by grepping their imports and cross-checking against `src/f1_analytics/**` and `recovery/reference/src/f1_analytics/**`). There is no `tests/conftest.py`.
- The architecture spine's own `.memlog.md` records that these 3 survivor files were originally treated as "pinning" the not-yet-built modules' contracts (`question_feature_availability.py` imports 7 symbols from a `question_catalog` that doesn't exist; `question_backtest_explanations.py` imports from `question_backtest_report` and `question_backtest_scoring`, neither of which exist). AD-10 **explicitly supersedes** that framing: prior/surviving module APIs never bind the rebuild. Treat this as settled, not an open question — the correct action is documented in Task 2.
- `docs/local_setup.md` (Status: Current) already documents the Kaggle credential fully; `docs/data_sources.md` documents Jolpica needing no credential, but its text still references `src/f1_analytics/data_sources/jolpica_loader.py` as if live in `src/` — it currently only exists under `recovery/reference/`. Fixing that doc's stale path is **not** this story's AC; link to it as-is in the new README, don't silently "fix" its content as a drive-by.
- Current branch is `main` (Story 1.1's clean orphan lineage); working tree is clean except for the routine `sprint-status.yaml` status-transition edit this workflow makes.

### Technical requirements and guardrails

- **uv 0.12.0 changed `uv init` defaults** (verified via GitHub release notes + Astral docs, 2026-07-28 release, current is 0.12.2): a fresh `uv init` now defaults to a *packaged* project — `[build-system]` using the `uv_build` backend, source under `src/<project-name>/` — where the pre-0.12 default was an unpackaged flat layout with no build system at all. This is exactly what AD-11's "src layout, editable install" requires, and exactly why the spine calls out "0.12.0 changed `uv init` defaults" by name. Since this story hand-authors `pyproject.toml` rather than running `uv init`, the practical requirement is: write the `[build-system]`/`uv_build` block yourself in the 0.12 shape (Task 1) — the `uv init` behavior change is the *reason* this shape is required, not a command to run.
- `uv_build` auto-discovers `src/<normalized-project-name>/` as the package root when the project name matches — no extra `[tool.uv_build]` module-root config needed since `name = "f1_analytics"` already matches `src/f1_analytics/`.
- Dependency direction rule (spine, binds this story too): `analysis/` never imports `data_sources/`, `database/`, `validation/`, or `scripts/`. All 4 new `__init__.py` files are docstring-only, so this is trivially satisfied now — flag it here so nobody adds a convenience import later without checking.
- AD-16 (fail-early) is a light touch on this story specifically: there's no business logic yet to fail-early on. Its relevant application here is Task 2 — the "empty package" requirement itself *is* a fail-early enforcement: no unverified/unwired forward code should sit in the live tree looking real.

### Expected project structure

| Path | Action | Purpose |
| --- | --- | --- |
| `pyproject.toml` | NEW | src layout, `uv_build` backend, pytest dev dependency group (AR-1). |
| `uv.lock` | NEW (commit) | Reproducible resolution (NFR-1). Not gitignored. |
| `.python-version` | NEW | `3.13` — lets a fresh clone resolve the pinned interpreter automatically. |
| `README.md` | NEW | Setup + per-source credential instructions (AC 3). |
| `src/f1_analytics/__init__.py` | NEW | Top-level package marker — currently missing. |
| `src/f1_analytics/analysis/__init__.py` | NEW | Empty package marker, after Task 2 relocates its 3 non-empty files out. |
| `src/f1_analytics/validation/__init__.py` | NEW | New empty package — doesn't exist at all today. |
| `src/f1_analytics/database/__init__.py`, `src/f1_analytics/data_sources/__init__.py` | UNCHANGED | Already correctly empty. |
| `tests/conftest.py` | NEW | Repo-wide autouse network-blocking fixture. |
| `tests/test_project_foundation.py` | NEW | The AC's "initial test" + the network-guard regression test. |
| `recovery/reference/src/f1_analytics/analysis/question_backtest_explanations.py`, `question_feature_availability.py`, `status_badge.py` | MOVED (git mv) | Forward-built code for future Epic 2.6/3.4/3.5 stories; salvage, not a fixed point (AD-10). |
| `recovery/reference/tests/test_question_backtest_explanations.py`, `test_question_backtest_report.py`, `test_jolpica_loader.py`, `test_championship_leaders_report.py` | MOVED (git mv), new directory | Orphaned tests for the above + Story 1.3's V1 salvage; preserved for their rightful future stories. |
| `_bmad-output/implementation-artifacts/1-4-project-foundation-that-survives-a-fresh-clone.md` | UPDATE | Record commands and validation results in the Dev Agent Record. |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATE | Move this story to `in-progress` when development starts, then `review` when ready. |

Not in scope: `catalog/question_catalog.yaml` (Epic 2), `exports/`, `notebooks/`, `sql/` views beyond what already exists (later stories, populated when something actually writes to them — untracked empty directories add nothing).

### Testing standards

- Tests live in `tests/`, run via `uv run pytest`, and must never touch the network (AD-11, AR-12) — the whole point of Task 4.
- No test framework beyond `pytest` + stdlib `unittest.mock`/`socket` monkeypatching is needed for this story.
- The 4 relocated legacy test files are excluded from collection simply by no longer being under `tests/` after Task 2 — no `pytest.ini` exclude list or marker is needed.

### Previous story and Git intelligence

- Story 1.3 (Salvage, status `review`) established the `recovery/reference/` convention for AD-10 salvage and explicitly deferred this story's scope: *"No `validation/` package and no top-level `__init__.py` exist yet (Story 1.4's job)"* and *"Do NOT touch the 3 files that already survive in the real `src/f1_analytics/analysis/`... those are current-era survivors... not part of this snapshot salvage"* — that was a scope boundary for 1.3's tarball-only salvage, not a permanent instruction to leave those 3 files in `src/` forever; this story's own AC (`empty analysis/ packages`) is what settles their fate now.
- Story 1.3 also set the working pattern for non-destructive relocation under Standing Constraints: plain filesystem/`git` operations, preserve internal relative structure, record everything (including surprises vs. the story's stated numbers) in the Dev Agent Record rather than silently reconciling them.
- Story 1.2 (FastF1 spike, done) established the precedent this story's Task 1 depends on: FastF1 lives in an **isolated** `uv run --isolated --python 3.13 --with fastf1==3.8.3 ...` environment, never in the main project's dependency graph — see `decisions/fastf1-source-adoption-decision-record.md`. Do not "complete" `pyproject.toml` by adding it.
- Commit convention observed across 1.1–1.3: one commit per story, a trailing `Story: <story-key>` line, `Co-Authored-By` trailer. Not this story's job to commit, but useful for the eventual commit message.

### Latest technical information (verified 2026-08-06/07)

- **uv 0.12.0** (released 2026-07-28; current 0.12.2, 2026-08-05): `uv init` now defaults to a packaged project — `[build-system]` with the `uv_build` backend, source under `src/<name>/`, a `[project.scripts]` entry. The pre-0.12 default was an unpackaged flat layout (`main.py`, no build system). Existing projects are unaffected by the change; `uv init --no-package` still gives the old flat layout if ever needed elsewhere. [Source: github.com/astral-sh/uv/releases/tag/0.12.0; pydevtools.com "uv 0.12 Makes Every New Project a Package"]
- Local Homebrew has 0.12.2 bottled and ready (`brew upgrade uv`) — no build-from-source or manual download needed.
- Python 3.13.7 is already installed locally at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`; `uv python pin 3.13` will use it directly without a new download.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.4, Epic 1 opening narrative, AR-1, AR-12]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` — AD-10, AD-11, Structural Seed, Stack table]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/reviews/review-version-currentness.md` — F1 finding: uv 0.11.x stale, 0.12.0 breaking `uv init` default change]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/.memlog.md` — survivor-module constraint note on `question_feature_availability.py`/`question_backtest_explanations.py`]
- [Source: `_bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md` — FastF1's separate pandas<3.0 environment requirement]
- [Source: `_bmad-output/implementation-artifacts/1-3-salvage-the-platform-snapshot-under-the-merge-rules.md` — previous story's Dev Notes on current on-disk state and the `recovery/reference/` convention]
- [Source: `docs/local_setup.md`, `docs/data_sources.md` — existing credential/source documentation to link from, not duplicate]
- [Source: github.com/astral-sh/uv/releases/tag/0.12.0 — uv 0.12.0 release notes]
- [Source: `AGENTS.md` — "prefer simple, maintainable solutions... do not create unnecessary abstractions"]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- `brew upgrade uv` → `uv 0.11.29 -> 0.12.2`. `uv --version` confirmed `uv 0.12.2 (Homebrew 2026-08-05 x86_64-apple-darwin)`.
- `uv python pin 3.13` → wrote `.python-version` containing `3.13`; used the already-installed `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13` (3.13.7), no download needed.
- First `uv sync` attempt failed: `Expected a Python module at: src/f1_analytics/__init__.py` — `uv_build` requires the top-level package marker to exist before it will build the project at all, ahead of where Task 3 creates it in the story's written task order. Created `src/f1_analytics/__init__.py` (Task 3's intended final content) to unblock Task 1, rather than leaving Task 1 incomplete. Re-ran `uv sync` — succeeded: resolved 7 packages including `pytest==9.1.1` (matches spine Stack table exactly).
- `git mv` (7 files: 3 `analysis/` survivor modules + 4 orphaned test files) into `recovery/reference/src/f1_analytics/analysis/` and a newly-created `recovery/reference/tests/`. `git status` recognized all 7 as renames (`R`), preserving history. Removed stale `__pycache__/*.pyc` left behind under `src/f1_analytics/analysis/` and `tests/` from the pre-move files (gitignored, not tracked; pure tidy-up).
- `uv run python -c "import f1_analytics, f1_analytics.analysis, f1_analytics.data_sources, f1_analytics.database, f1_analytics.validation"` → printed `OK`, no errors.
- Manual network-guard verification: added a throwaway `tests/test_throwaway_network_probe.py` calling `socket.create_connection(("example.com", 80), timeout=2)` with no `pytest.raises` wrapper. `uv run pytest tests/test_throwaway_network_probe.py -v` → failed in `0.09s` with `RuntimeError: Network access is blocked in tests (AD-11): blocked connect to (...)` — no hang, no real network attempt. Deleted the throwaway file immediately after.
- **Finding that corrects a Dev Notes claim:** after adding `tests/test_project_foundation.py` and running the full suite, `uv run pytest -v` failed with 4 collection errors — pytest's default rootdir-recursive discovery still found the relocated files under `recovery/reference/tests/` (`ModuleNotFoundError: pandas`, `ModuleNotFoundError: f1_analytics.data_sources.jolpica`, `ModuleNotFoundError: f1_analytics.analysis.question_answers` ×2). The Dev Notes' "Testing standards" section asserted relocation alone would exclude them from collection ("no `pytest.ini` exclude list or marker is needed") — that assumption was wrong. Fixed by adding `[tool.pytest.ini_options]` / `testpaths = ["tests"]` to `pyproject.toml` (an addition beyond Task 1's originally-specified content, made here since it's what made Task 5's own verification target achievable). Re-ran: `2 passed in 0.02s`, exactly the 2 new tests, `recovery/reference/` correctly excluded from collection.
- Final scratch-clone simulation (Task 7): `rm -rf .venv uv.lock && uv sync` → fresh `.venv`, 7 packages resolved, `f1-analytics==0.1.0` installed editable. `uv run pytest -v` → `2 passed in 0.02s`. `uv --version` → `uv 0.12.2`.
- Final `git status --porcelain`: 7 renames (Task 2), 1 modified (`sprint-status.yaml`), untracked new files exactly as planned (`.python-version`, `README.md`, `pyproject.toml`, `uv.lock`, `src/f1_analytics/__init__.py`, `src/f1_analytics/analysis/__init__.py`, `src/f1_analytics/validation/__init__.py`, `tests/conftest.py`, `tests/test_project_foundation.py`, this story file). Nothing under `data/` or `.venv/` — both correctly gitignored.

### Completion Notes List

- Upgraded local `uv` to 0.12.2 and hand-authored `pyproject.toml` (src layout via the `uv_build` backend, `pytest>=9.1,<10` as a dev dependency group, `requires-python = ">=3.13,<3.14"`) — no runtime dependencies added, matching the guardrail against premature `pandas`/`duckdb`/`fastf1`/`kagglehub` additions. `uv sync` builds cleanly; `uv.lock` is committed (not gitignored).
- Relocated the 3 pre-loss `analysis/` survivor files and all 4 orphaned test files (that tested either those survivors or Story 1.3's already-relocated V1 salvage) into `recovery/reference/` via `git mv`, preserving history — nothing deleted, nothing importable from live `src/` anymore. `src/f1_analytics/analysis/` is now genuinely empty except its package marker.
- Built the full empty package skeleton: top-level `src/f1_analytics/__init__.py` (new), `analysis/__init__.py` (new, package now empty), the brand-new `validation/` package (didn't exist before), matching the Structural Seed and the existing `database/`/`data_sources/` docstring style byte-for-byte.
- Added `tests/conftest.py` with a stdlib-only, `monkeypatch`-based autouse fixture blocking `socket.socket.connect`/`connect_ex` for every test — no new dependency. Verified it fails loudly (not a hang) against a real hostname, then added a permanent `tests/test_project_foundation.py` with 2 tests: package/sub-package importability, and a green regression test for the network guard.
- Added `README.md` at the repo root with setup steps and the required per-source credential table (Kaggle: token file, linked to `docs/local_setup.md`; FastF1/Jolpica: none), without duplicating existing docs.
- Discovered and fixed one real gap the story's Dev Notes didn't anticipate: pytest's default collection reaches everywhere under rootdir, so relocating the 4 broken legacy tests out of `tests/` wasn't sufficient by itself — added `testpaths = ["tests"]` to `pyproject.toml` to confine collection and keep `recovery/reference/` excluded going forward.
- Full verification: fresh scratch-clone simulation (`rm -rf .venv uv.lock && uv sync`) builds cleanly and `uv run pytest -v` passes both tests in 0.02s. `git status` shows exactly the expected changes.

### File List

**New:**
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `README.md`
- `src/f1_analytics/__init__.py`
- `src/f1_analytics/analysis/__init__.py`
- `src/f1_analytics/validation/__init__.py`
- `tests/conftest.py`
- `tests/test_project_foundation.py`

**Renamed (git mv, history preserved):**
- `src/f1_analytics/analysis/question_backtest_explanations.py` → `recovery/reference/src/f1_analytics/analysis/question_backtest_explanations.py`
- `src/f1_analytics/analysis/question_feature_availability.py` → `recovery/reference/src/f1_analytics/analysis/question_feature_availability.py`
- `src/f1_analytics/analysis/status_badge.py` → `recovery/reference/src/f1_analytics/analysis/status_badge.py`
- `tests/test_question_backtest_explanations.py` → `recovery/reference/tests/test_question_backtest_explanations.py`
- `tests/test_question_backtest_report.py` → `recovery/reference/tests/test_question_backtest_report.py`
- `tests/test_jolpica_loader.py` → `recovery/reference/tests/test_jolpica_loader.py`
- `tests/test_championship_leaders_report.py` → `recovery/reference/tests/test_championship_leaders_report.py`

**Modified:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status transitions: `ready-for-dev` → `in-progress` → `review`)
- `_bmad-output/implementation-artifacts/1-4-project-foundation-that-survives-a-fresh-clone.md` (this file — frontmatter, task checkboxes, Dev Agent Record, Status)

### Change Log

- 2026-08-07: Built the project foundation — `pyproject.toml` on uv 0.12 conventions (src layout, `uv_build` backend, pytest dev group, no premature runtime deps), the empty `src/f1_analytics/{analysis,validation}` packages plus the missing top-level `__init__.py`, a repo-wide network-blocking pytest fixture with regression coverage, and a root `README.md` naming every source's credential requirement. Relocated 3 pre-loss `analysis/` survivor files and 4 orphaned/broken test files into `recovery/reference/` (git mv, history preserved) per AD-10 — none were deleted. Found and fixed one gap beyond the story's original plan: pytest's default collection needed an explicit `testpaths = ["tests"]` to actually exclude the relocated legacy tests. `uv run pytest` is green (2/2) on a simulated scratch clone.
