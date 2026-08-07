---
title: "Daily-Pipeline Swap-Contract Check Decision Record"
status: active
created: 2026-07-21
source_material:
  - docs/decisions.md
  - scripts/verify_daily_pipeline_swap_contract.py
---

# Daily-Pipeline Swap-Contract Check Decision Record

## Purpose

This BMAD planning artifact is the durable decision record for keeping a standalone regression check on the daily pipeline's marker/swap contract. It replaces `docs/decisions.md` as the citable decision source for this rule while `docs/decisions.md` is retained only as historical/transitional evidence (see the cleanup-proof CP-016 disposition).

## Current Decision

Keep `scripts/verify_daily_pipeline_swap_contract.py` as a small standalone regression check for the daily pipeline marker/swap contract instead of relying only on one-off manual review.

## Enforcement State

Programmatically enforced: `scripts/verify_daily_pipeline_swap_contract.py` exists in the repository and can be run directly as a standalone check.

## Rationale

Story 4.3 already had a marker-write regression caught after review, and the deleted throwaway verification script left no repeatable guard. A standalone script preserves the no-test-framework convention while making the specific contract cheap to re-run.

## Tradeoffs

This adds one project script that behaves like a focused check, but it does not introduce pytest, a test directory, or a broader testing framework.

## Decision Lineage

- 2026-07-15: Original decision recorded in `docs/decisions.md` ("Retain a standalone daily-pipeline swap contract check").
- 2026-07-21: Duplicated here as a durable decision record during the cleanup-proof terminal closure story, after code review found this entry was still active but had no independent current-authority home under `_bmad-output/planning-artifacts/decisions/`, unlike the other still-active `docs/decisions.md` entries CP-016 cites.

## Status

Accepted.
