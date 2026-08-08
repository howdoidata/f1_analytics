---
status: generated
---
# Project Kernel — f1_analytics

## Commands
- Test: `uv run pytest` (offline only — see Landmines)

## Conventions that differ from defaults
- Kaggle pipeline reads static CSVs at `data/raw/f1_complete_dataset/` — no live download in the current build path — [kaggle-raw-data-is-static](kaggle-raw-data-is-static.md).
- A source-name → curated-id mismatch (FastF1 `Team`/`Driver` vs Kaggle `constructors`/`drivers`) is reconciled by exactly one sanctioned mechanism per source/field pairing, authorized by a dated decision record under `_bmad-output/planning-artifacts/decisions/` — never a fuzzy match, never silently picking one match among several — [name-reconciliation-pattern](name-reconciliation-pattern.md).
- One race's fetch/mapping failure is caught and reported by name; it never aborts the other races in a multi-race run — [per-race-failure-isolation](per-race-failure-isolation.md).

## Landmines
- Every test blocks all network access automatically (`tests/conftest.py`, autouse fixture) — a test that reaches the network fails loudly, it never hits a real host.

## Org requirements
- Record durable decisions in `_bmad-output/planning-artifacts/decisions/`; record command/validation evidence in the active story's Dev Agent Record under `_bmad-output/implementation-artifacts/` — see `AGENTS.md`.
