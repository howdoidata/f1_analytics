# AGENTS.md

## Root Conventions

- Shared, root-level BMAD process conventions (agents, skills, module install layout) come from the `platform` repo (sibling project at `../platform`), which is the source of truth for those root-level rules. This project remains an independent repo — no code, data, or history moves between the two; `platform` only supplies the shared root protocol via `bmad-method install`.

## Universal Project Rules

- The rules below are this project's own local conventions and take precedence for anything specific to `f1_analytics` (not covered by `platform`'s root conventions above).
- The repo is the source of truth.
- Read `PROJECT.md` and `_bmad-output/project-context.md` before making project changes.
- Prefer simple, maintainable solutions.
- Do not create unnecessary abstractions.
- Record durable decisions in BMAD planning artifacts under `_bmad-output/planning-artifacts/decisions/`.
- Record commands and validation results in the current story's Dev Agent Record at `_bmad-output/implementation-artifacts/<story-id>.md` (or equivalent active BMAD implementation artifact). `docs/run_log.md` is frozen historical evidence. Automated `scripts/run_daily_pipeline.py` telemetry writes to `_bmad-output/implementation-artifacts/daily-pipeline-run-records.jsonl` using the contract in `_bmad-output/planning-artifacts/decisions/daily-pipeline-run-record-contract-decision-record.md`.
- Do not rely on chat history when repo context exists.
