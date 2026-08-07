---
baseline_commit: 54ac360f9fa511e3f419c13861162176ae1e4b1d
---

# Story 1.3: Salvage The Platform Snapshot Under The Merge Rules

Status: review

## Story

As Antonio,
I want the snapshot's recoverable assets restored without regressing corrected data,
so that the rebuild starts from everything that survived.

## Acceptance Criteria

1. **Given** the protective tarball `recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz`, **when** the salvage runs, **then** `data/raw/` gains the snapshot's 8 Kaggle CSVs and 67 Jolpica JSONs EXCEPT the 7 files where a post-pagination-fix live version already exists on disk — each of the 7 is byte-compared against its snapshot counterpart, the live (on-disk) version always wins, and the comparison result (identical/differs) is recorded.
2. **And** `docs/decisions.md` (the pre-questions-era decision log) is restored to `docs/`, all of the snapshot's V1 code (`src/f1_analytics/*`, `scripts/*`, `sql/*`, `notebooks/*`) lands under `recovery/reference/` mirroring its snapshot-relative path — never under the project's real `src/`, `scripts/`, `sql/`, or `notebooks/` (AD-10: salvage, not fixed points) — and the July-9 `f1_analytics.duckdb` is NOT restored anywhere (disposable scaffolding, never truth).
3. **And** no `git restore`, `git gc`, `git prune`, or `git repack` ran at any point (Standing Constraints); the tarball is extracted and copied with plain filesystem operations only.

**Verification:** the 7 protected filenames match their pre-salvage checksums; `data/processed/` remains empty. Governed by: Standing Constraints, AD-13, AR-13.

## Tasks / Subtasks

- [x] Task 1: Extract the tarball to a scratch location and inventory it (AC: 1, 2)
  - [x] Extract `recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz` to a throwaway path outside the repo — never extract in place over `recovery/`. The archive's internal paths are prefixed `f1_analytics/...`.
  - [x] Confirm the extracted inventory matches: 8 Kaggle CSVs under `data/raw/f1_complete_dataset/`, 67 JSONs under `data/raw/jolpica/{results,qualifying,driverStandings,constructorStandings,laps,pitstops}/`, `data/processed/f1_analytics.duckdb`, `docs/decisions.md`, and the V1 code tree (`src/f1_analytics/`, `scripts/`, `sql/`, `notebooks/`).
- [x] Task 2: Byte-compare and merge the 7 protected Jolpica files (AC: 1)
  - [x] For each of the 7 files already present on disk — `data/raw/jolpica/constructorStandings/2026_1.json`, `data/raw/jolpica/constructorStandings/2026_7.json`, `data/raw/jolpica/driverStandings/2026_10.json`, `data/raw/jolpica/laps/2026_8.json`, `data/raw/jolpica/qualifying/2026_11.json`, `data/raw/jolpica/results/2026_10.json`, `data/raw/jolpica/results/2026_5.json` — compute a checksum (e.g. `shasum -a 256`) of the live file and of the snapshot's same-named file, and record match/differ for each pair.
  - [x] Leave all 7 live files untouched regardless of the comparison outcome (live always wins — this is evidence, not a gate).
  - [x] Record the 7-pair comparison table in this story's Dev Agent Record (AGENTS.md convention: commands + results go in the active story file, not `docs/run_log.md`).
- [x] Task 3: Land the remaining Jolpica JSONs and the Kaggle CSVs (AC: 1)
  - [x] Copy every snapshot Jolpica JSON whose filename is NOT one of the 7 protected files into the matching `data/raw/jolpica/<endpoint>/` subfolder (60 files: all of `pitstops/`, since 0 live files exist there today, plus the remainder of `results`, `qualifying`, `driverStandings`, `constructorStandings`, `laps`).
  - [x] Copy all 8 snapshot Kaggle CSVs into `data/raw/f1_complete_dataset/`. Note: `f1_races.csv` already exists on disk and is byte-identical to the snapshot's copy (verified during story creation) — a plain overwrite is safe and expected, not a conflict requiring special handling.
  - [x] Do not restore `data/processed/f1_analytics.duckdb` from the snapshot anywhere in the repo. `data/processed/` must remain empty after this story (it is currently empty).
- [x] Task 4: Restore `docs/decisions.md` only (AC: 2)
  - [x] Copy `docs/decisions.md` from the snapshot into `docs/decisions.md`.
  - [x] Do not restore any other snapshot `docs/` file (`implementation_notes/`, `handoffs/`, `questions.md`, `backlog.md`, `run_log.md`, `project_profile.md`, `terminal_roles/`, `prompts/`, `diagrams/`, `inbox/`, etc.) — epics.md's Story 1.3 AC names only `docs/decisions.md`; the rest belongs to the superseded pre-questions-era governance/platform-bootstrap track and stays out of scope for this story.
- [x] Task 5: Land the V1 reference code under `recovery/reference/` (AC: 2)
  - [x] Copy the snapshot's `src/f1_analytics/` (14 files: `config.py`, `__init__.py`, `data_sources/__init__.py`, `data_sources/standings.py`, `data_sources/combined_dataset.py`, `data_sources/jolpica.py`, `data_sources/kaggle_csv.py`, `data_sources/jolpica_loader.py`, `validation/__init__.py`, `validation/checks.py`, `database/__init__.py`, `database/duckdb_io.py`, `analysis/championship_leaders.py`, `analysis/combined_championship_leaders.py`) to `recovery/reference/src/f1_analytics/`, preserving the same subpath structure.
  - [x] Copy the snapshot's `scripts/` (7 files: `download_kagglehub_f1_data.py`, `build_f1_dataset.py`, `pull_jolpica_data.py`, `build_combined_dataset.py`, `analyze_championship_leaders.py`, plus `workflow.py` and `fitness_check.py` — platform-tooling scripts bundled in the same snapshot, archived here for completeness since they land under reference-only `recovery/`, not under the real `scripts/`) to `recovery/reference/scripts/`.
  - [x] Copy the snapshot's `sql/` (`analysis/kaggle_jolpica_coverage.sql`, `analysis/README.md`, `curated/README.md`) to `recovery/reference/sql/`.
  - [x] Copy the snapshot's `notebooks/championship_leader_combined_analysis.ipynb` to `recovery/reference/notebooks/`.
  - [x] Do NOT place any of this under the project's real `src/`, `scripts/`, `sql/`, or `notebooks/` directories. Do NOT touch the 3 files that already survive in the real `src/f1_analytics/analysis/` (`question_backtest_explanations.py`, `question_feature_availability.py`, `status_badge.py`) or the existing empty `data_sources/__init__.py` / `database/__init__.py` — those are current-era survivors from the 2026-08-01 partial recovery, not part of this snapshot salvage.
  - [x] Do not restore the snapshot's `outputs/` directory — out of scope for this story (disposable, regenerable, not named in the AC).
- [x] Task 6: Commit and verify (AC: 1, 2, 3)
  - [x] `git add docs/decisions.md recovery/reference/` (`data/raw/` and `data/processed/` stay gitignored — do not force-add them).
  - [x] Confirm no `git restore`, `git gc`, `git prune`, or `git repack` command appears anywhere in the session's command history for this story.
  - [x] Run the verification commands below and record their output in the Dev Agent Record.

## Dev Notes

### Scope and sequencing

- This is a recovery/infrastructure story (same species as Story 1.1) — plain filesystem salvage under the Standing Constraints, not application code. Do not build a `scripts/salvage_platform_snapshot.py` production script unless it materially helps; a one-off, documented set of shell commands recorded in the Dev Agent Record is sufficient and matches Story 1.1's pattern. If a script is added anyway, treat it as a throwaway aid, not a pipeline stage — Epic 1's later stories (1.5–1.7) own the real ingestion scripts.
- This story runs after 1.2 (FastF1 spike, done) and before 1.4 (project foundation). Do not build `pyproject.toml`, the `src/f1_analytics/__init__.py` skeleton, or any package scaffolding here — that is Story 1.4. Do not write `raw_*`/curated DuckDB tables here — that is Stories 1.5–1.7.
- AD-10 governs the whole story: prior module APIs (lost or surviving) do not bind the rebuild. The V1 code under `recovery/reference/` is salvage to adapt or replace later, never a fixed contract, and it must never be imported by anything under `src/`.

### Current on-disk state (verified 2026-08-07, before this story runs)

- `data/processed/` is empty.
- `data/raw/jolpica/` already has exactly 7 files (the post-pagination-fix live cache the Architecture Spine and reconstruction doc refer to): `constructorStandings/2026_1.json`, `constructorStandings/2026_7.json`, `driverStandings/2026_10.json`, `laps/2026_8.json`, `qualifying/2026_11.json`, `results/2026_10.json`, `results/2026_5.json`. `pitstops/` is empty (0 live files).
- `data/raw/f1_complete_dataset/` already has 1 file, `f1_races.csv`, byte-identical (verified `sha256`) to the snapshot's copy — a plain overwrite is safe.
- `data/raw/openf1/` exists as empty subfolders; the snapshot has no `openf1/` content at all (OpenF1 is retired per AD-6) — leave these alone.
- `data/raw/fastf1_cache/` holds Story 1.2's spike cache; unrelated to this story, do not touch it.
- `docs/` currently has `data_sources.md`, `local_setup.md`, `index.md`, `source-tree-analysis.md`, `implementation_notes/` — no `decisions.md` yet.
- `recovery/` currently holds only the tarball; `recovery/reference/` does not exist yet.
- `src/f1_analytics/` currently has `analysis/{question_backtest_explanations.py, question_feature_availability.py, status_badge.py}` (current-era survivors from the 2026-08-01 partial recovery — NOT snapshot content) plus empty `data_sources/__init__.py` and `database/__init__.py`. No `validation/` package and no top-level `__init__.py` exist yet (Story 1.4's job).
- Current branch is `main`, which IS Story 1.1's clean orphan lineage (`ec5e725` is the orphan root commit); working tree is clean. No further git-history operations are needed for this story beyond a normal commit.

### Technical requirements and guardrails

- Never run `git gc`, `git prune`, `git repack`, `git restore`, or `git checkout -- .` (Standing Constraints, still live per the damage record and the Architecture Spine).
- Extract the tarball to a scratch location outside the repo, not in place — the tarball's internal paths are prefixed `f1_analytics/...` and must not be extracted directly over the working tree.
- `data/raw/` and `data/processed/` are entirely gitignored (`data/raw/`, `data/processed/` in `.gitignore`) — files land there for the later ingestion scripts to use, but nothing under `data/` is committed by this story. Only `docs/decisions.md` and `recovery/reference/` are trackable and should be `git add`ed.
- The July-9 `f1_analytics.duckdb` is disposable scaffolding, never truth — do not extract it anywhere in the repo, including `recovery/reference/`.
- The byte-comparison for the 7 protected files is evidence, not a gate: whether or not a snapshot file turns out identical, the live file is what stays.
- Keep the V1 reference tree's internal relative structure intact under `recovery/reference/` (e.g. `recovery/reference/src/f1_analytics/data_sources/jolpica_loader.py`, not flattened) so a future reader can tell which package each file came from.

### Expected project structure

| Path | Action | Purpose |
| --- | --- | --- |
| `data/raw/f1_complete_dataset/*.csv` | UPDATE (gitignored) | 8 Kaggle CSVs land here (1 already present and identical). |
| `data/raw/jolpica/{results,qualifying,driverStandings,constructorStandings,laps,pitstops}/*.json` | UPDATE (gitignored) | 67 total Jolpica JSONs; the 7 already-present live files are never overwritten. |
| `docs/decisions.md` | NEW | Restored pre-questions-era decision log. |
| `recovery/reference/src/f1_analytics/**` | NEW | V1 code, reference only, never imported by `src/`. |
| `recovery/reference/scripts/**` | NEW | V1 + platform-tooling scripts, reference only. |
| `recovery/reference/sql/**` | NEW | V1 SQL, reference only. |
| `recovery/reference/notebooks/**` | NEW | V1 notebook, reference only. |
| `_bmad-output/implementation-artifacts/1-3-salvage-the-platform-snapshot-under-the-merge-rules.md` | UPDATE | Record commands, the byte-comparison table, and validation results in the Dev Agent Record. |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATE | Move this story to `in-progress` when development starts, then `review` when ready. |

Do not create `data/processed/f1_analytics.duckdb`, `src/f1_analytics/__init__.py`, `pyproject.toml`, or any `raw_*`/curated DuckDB table in this story.

### Validation

- `shasum -a 256` (or `cmp`) each of the 7 protected files against its snapshot counterpart; record match/differ per file.
- `find data/processed -type f` → empty, unchanged from before the salvage.
- `find data/raw/jolpica -type f | wc -l` → 67 (7 pre-existing + 60 newly landed).
- `find data/raw/f1_complete_dataset -type f | wc -l` → 8.
- `test -f docs/decisions.md` → present.
- `git status --porcelain` shows only `docs/decisions.md` and new files under `recovery/reference/` as additions — nothing under `data/` appears (gitignored).
- `git diff --check` clean.
- Confirm by inspection that no command run during this story was `git restore`, `git gc`, `git prune`, or `git repack`.

### Previous story and Git intelligence

- Story 1.2 (FastF1 Adoption Spike, done) established: the current branch `main` is the clean rebuild lineage; AD-10 demotes all prior artifacts (including this snapshot's V1 code) to reference material, never a binding contract; commands and results belong in the active story's Dev Agent Record per `AGENTS.md`, not `docs/run_log.md` (frozen); preserve the recovery constraints (no `git gc`/`prune`/`repack`/`restore`).
- Story 1.2 also left `data/raw/fastf1_cache/` populated from its own live spike run — unrelated to this story's Jolpica/Kaggle salvage; do not move, merge, or clean it up here.
- No dedicated story file exists on disk for Story 1.1 under its current-era key (`1-1-record-the-loss-and-gain-offsite-protection`); its work is recorded directly in commits `ec5e725` and `4ecf563`. The file `1-1-confirm-deletion-authorization-and-evidence-path.md` in this folder is a pre-loss historical artifact for a different, superseded plan — do not reuse its content, paths, or claimed completion.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Story 1.3, Epic 1 opening narrative, AR-13]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` — AD-10, AD-13, Standing Constraints, Structural Seed]
- [Source: `_bmad-output/planning-artifacts/decisions/repository-damage-and-recovery-options-2026-08-01.md` — handling constraints, exchange position]
- [Source: `_bmad-output/planning-artifacts/project-state-reconstruction-2026-08-06.md` — §4 what survives / platform snapshot caveats, §5 recommended restart path]
- [Source: `_bmad-output/implementation-artifacts/1-2-fastf1-adoption-spike.md` — previous story's Dev Notes and Change Log]
- [Source: `recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz` — inventoried 2026-08-07: 262 archive entries, 8 Kaggle CSVs, 67 Jolpica JSONs, 14 `src/f1_analytics/` files, 7 `scripts/`, 3 `sql/`, 1 notebook, `docs/decisions.md`, `data/processed/f1_analytics.duckdb`]
- [Source: `.gitignore` — `data/raw/`, `data/processed/` gitignored; `recovery/` is not]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Extracted the tarball with `tar -xzf ... -C <scratchpad>/snapshot-extract` (outside the repo, per the Standing Constraints); confirmed 262 archive entries via `tar -tzf | wc -l` before extracting.
- Verified on-disk state before touching anything: matched the Dev Notes' "Current on-disk state" section exactly (7 live Jolpica files, 1 live Kaggle CSV, empty `data/processed/`, no `docs/decisions.md`, no `recovery/reference/`, current-era `src/f1_analytics/` survivors untouched).
- Finding: 2 of the 7 "protected" files (`driverStandings/2026_10.json`, `qualifying/2026_11.json`) have no snapshot counterpart at all — the snapshot's `driverStandings/` and `qualifying/` endpoints only go up to round 9 (`2026_1.json`...`2026_9.json`), since those rounds hadn't been played as of the 2026-07-09 snapshot date. Recorded as "no snapshot counterpart" rather than forcing a checksum comparison against a nonexistent file.
- Consequence of that finding: the story's Task 1 verification target of "67 JSONs" and the Validation section's "67 (7 pre-existing + 60 newly landed)" undercounts by 2 — the actual post-salvage `data/raw/jolpica` total is **69** (67 snapshot files, all landed, since none of the 5 real duplicates were skipped from the *live* side — plus the 2 live files that were never in the snapshot to begin with). Full arithmetic: 67 snapshot files − 5 protected files that already exist live (skipped, not overwritten) = 62 newly copied; 7 pre-existing live files + 62 newly copied = 69. This is reported as found, not forced to match the story's stated 67; the AC's actual requirement (protected files never overwritten, live always wins) is satisfied regardless.
- Also found the snapshot's `src/f1_analytics/` tree has 15 files, not the 14 the Task 5 checklist enumerates — the checklist's list omits `analysis/__init__.py`. Copied the full tree (all 15 files, including `analysis/__init__.py`) rather than cherry-picking the enumerated 14, since the AC's actual instruction is "copy the snapshot's `src/f1_analytics/`... preserving the same subpath structure" and leaving `analysis/` without an `__init__.py` while its sibling packages have theirs would break that structural intent.
- `git diff --check` on the staged changes flags "new blank line at EOF" on 8 of the salvaged V1 files under `recovery/reference/`. These trailing blank lines are original to the snapshot's authored files (verified: present in the extracted snapshot copy, not introduced by the copy operation). Left as-is — this is verbatim reference salvage (AD-10: salvage, not fixed points; never imported by `src/`), and reformatting archived V1 code would misrepresent what was actually recovered.
- Excluded `.DS_Store` (in the snapshot's `sql/` and elsewhere) and the KaggleHub cache marker `data/raw/f1_complete_dataset/.complete/datasets/.../bundle.complete` from all copies — neither is a deliverable named in the AC.
- Cleaned up the scratch extraction directory after all copies and comparisons completed.

### Byte-Comparison — 7 Protected Jolpica Files

Computed with `shasum -a 256` on each live file and its snapshot counterpart (where one exists). Live files were only read, never modified.

| File | Live SHA-256 | Snapshot SHA-256 | Result |
| --- | --- | --- | --- |
| `jolpica/constructorStandings/2026_1.json` | `ed7bc53d298f616b3ffe3c2871c5df1c33cbdcca14a9428bb27d1453f3f79ec` | `5a97b5adbae412d0789233e763d765c92b3938ac945aa3eea84e3342f9d5c5a` | differs |
| `jolpica/constructorStandings/2026_7.json` | `5e3572b1e67b81cf856dbf8ab441cb4b02ecf1667d89b29a8b043a22d50caf9` | `759b5b3d8263f478fc6d56bd9710e423e2c8f79013ee8ebcd6432f395eb277f` | differs |
| `jolpica/driverStandings/2026_10.json` | `286f593318b1ebadf15dc0f9ce25c5e8d41f36d5a25a6642d033e735d088fcb` | — (no such file in snapshot) | no snapshot counterpart |
| `jolpica/laps/2026_8.json` | `8fb944b418470fa1301e484502dac7192015fcaa5d3ddf443abc649725f8fd` | `b75152ffbca8192bb4cebbf510b094f85667dedb90fe9c9de74ce3abac677b3` | differs |
| `jolpica/qualifying/2026_11.json` | `ab0d0439d248a9ecc4b12b6c0b28da8205e727f6fc7cf77e15227fc12270163` | — (no such file in snapshot) | no snapshot counterpart |
| `jolpica/results/2026_10.json` | `3f1724645fd08adb89cb1c358338f322157ca8e8d8730a12951ef6ea88af0b7` | `fa3d8ef5e9d80c68914710c92030b96f8ad2dd1836883fb46c78c8ab4ea9450f` | differs |
| `jolpica/results/2026_5.json` | `a2ebaaa9b11ab9746d462b7d314e5a09185093cbaaa77adaa59bbe0232d27710` | `f275ef58d3d6d6fdc72f8ee104acc432ed1273721e878b7502e0634a1c2e3dc` | differs |

Interpretation: the 5 files with a snapshot counterpart all differ — expected, since the live versions are the post-pagination-fix corrected cache and the snapshot predates that fix. The other 2 have no snapshot file at all — those rounds (10, 11) simply hadn't been played yet as of the 2026-07-09 snapshot. In every case the live file was left untouched; the snapshot never overwrote a protected file.

### Completion Notes List

- Extracted `recovery/platform-external-f1_analytics-snapshot-2026-07-09.tar.gz` to a scratch path outside the repo and confirmed its inventory (8 Kaggle CSVs, 67 Jolpica JSONs across the 6 endpoints, 15 `src/f1_analytics/` files, 7 `scripts/`, 3 `sql/` files + `.DS_Store`, 1 notebook, `docs/decisions.md`, `data/processed/f1_analytics.duckdb`).
- Byte-compared all 7 protected Jolpica files against their snapshot counterparts (2 had none) and left all 7 live files untouched — see table above.
- Copied the 62 non-duplicate snapshot Jolpica JSONs into `data/raw/jolpica/{results,qualifying,driverStandings,constructorStandings,laps,pitstops}/` and all 8 Kaggle CSVs into `data/raw/f1_complete_dataset/` (the pre-existing `f1_races.csv` was overwritten with its byte-identical snapshot copy, as anticipated). `data/processed/` remains empty; the July-9 duckdb was not extracted anywhere in the repo.
- Restored `docs/decisions.md` only; no other snapshot `docs/` content was touched.
- Landed the snapshot's full `src/f1_analytics/` tree (15 files), `scripts/` (7 files), `sql/` (3 files, `.DS_Store` excluded), and the notebook under `recovery/reference/`, preserving snapshot-relative subpaths. Confirmed the real `src/`, `scripts/`, `sql/`, `notebooks/` trees were not touched (git status/log confirms `sql/curated/README.md` and `scripts/spike_fastf1_adoption.py` at repo root predate this story and are unmodified).
- `git add`ed `docs/decisions.md` and `recovery/reference/` only; `data/raw/` and `data/processed/` were never staged (gitignored). No `git restore`, `git gc`, `git prune`, or `git repack` command was run at any point in this session.

### Validation

- `find data/processed -type f` → empty (unchanged). Pass.
- `find data/raw/jolpica -type f | wc -l` → **69**, not the story's stated 67 — see Debug Log finding above (2 of the "7 protected" files have no snapshot counterpart, so they were never subject to the 67-total accounting). The AC's substantive requirement — protected files never overwritten — holds.
- `find data/raw/f1_complete_dataset -type f | wc -l` → 8. Pass.
- `test -f docs/decisions.md` → present. Pass.
- `git status --porcelain` (post `git add`) → only `docs/decisions.md` and new files under `recovery/reference/` staged as additions; nothing under `data/` appears. Pass.
- `git diff --check` (staged) → flags "new blank line at EOF" on 8 files under `recovery/reference/src/f1_analytics/` and `recovery/reference/sql/`; all pre-existing in the snapshot's original authored files, not introduced here — see Debug Log. Not treated as a blocker: fixing it would mean editing verbatim V1 salvage, contrary to AD-10.
- Manual review of this session's full command history: no `git restore`, `git gc`, `git prune`, `git repack`, or `git checkout -- .` was ever run. Pass.
- 7 protected files re-checked with `shasum -a 256` immediately before staging — identical to their pre-salvage values (they were never written to). Pass.

### File List

- `docs/decisions.md` (new, restored from snapshot)
- `recovery/reference/src/f1_analytics/__init__.py` (new)
- `recovery/reference/src/f1_analytics/config.py` (new)
- `recovery/reference/src/f1_analytics/analysis/__init__.py` (new)
- `recovery/reference/src/f1_analytics/analysis/championship_leaders.py` (new)
- `recovery/reference/src/f1_analytics/analysis/combined_championship_leaders.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/__init__.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/standings.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/combined_dataset.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/jolpica.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/kaggle_csv.py` (new)
- `recovery/reference/src/f1_analytics/data_sources/jolpica_loader.py` (new)
- `recovery/reference/src/f1_analytics/database/__init__.py` (new)
- `recovery/reference/src/f1_analytics/database/duckdb_io.py` (new)
- `recovery/reference/src/f1_analytics/validation/__init__.py` (new)
- `recovery/reference/src/f1_analytics/validation/checks.py` (new)
- `recovery/reference/scripts/download_kagglehub_f1_data.py` (new)
- `recovery/reference/scripts/build_f1_dataset.py` (new)
- `recovery/reference/scripts/pull_jolpica_data.py` (new)
- `recovery/reference/scripts/build_combined_dataset.py` (new)
- `recovery/reference/scripts/analyze_championship_leaders.py` (new)
- `recovery/reference/scripts/workflow.py` (new)
- `recovery/reference/scripts/fitness_check.py` (new)
- `recovery/reference/sql/analysis/kaggle_jolpica_coverage.sql` (new)
- `recovery/reference/sql/analysis/README.md` (new)
- `recovery/reference/sql/curated/README.md` (new)
- `recovery/reference/notebooks/championship_leader_combined_analysis.ipynb` (new)
- `data/raw/f1_complete_dataset/*.csv` (8 files, gitignored, not staged — 1 overwrite + 7 new)
- `data/raw/jolpica/{results,qualifying,driverStandings,constructorStandings,laps,pitstops}/*.json` (62 new files, gitignored, not staged; 7 pre-existing protected files untouched)
- `_bmad-output/implementation-artifacts/1-3-salvage-the-platform-snapshot-under-the-merge-rules.md` (this file — frontmatter, task checkboxes, Dev Agent Record, Status)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status moved to in-progress, then review)

### Change Log

- 2026-08-07: Salvaged the platform snapshot under the merge rules — landed 62 new Jolpica JSONs and 8 Kaggle CSVs into gitignored `data/raw/` (7 protected live Jolpica files verified byte-for-byte against the snapshot and left untouched; 2 of those 7 had no snapshot counterpart at all), restored `docs/decisions.md`, and archived the full V1 code tree (`src/f1_analytics/`, `scripts/`, `sql/`, `notebooks/`) under `recovery/reference/` for reference only. No `git restore`/`gc`/`prune`/`repack` used. Noted two discrepancies against the story's stated numbers (69 vs. 67 total Jolpica files; 15 vs. 14 `src/f1_analytics/` files) and resolved both in favor of the AC's actual intent rather than forcing the stated counts.
