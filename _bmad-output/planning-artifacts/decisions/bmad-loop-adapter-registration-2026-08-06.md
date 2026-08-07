# BMAD Loop Adapter Registration Decision

**Date:** 2026-08-06
**Status:** Accepted

## Decision

Register both the `claude` and `codex` adapters with the project's BMAD Loop
installation. Keep `claude` as the default adapter for dev, review, and triage
in `.bmad-loop/policy.toml`.

## Rationale

Both coding CLIs are available for future orchestration use. Keeping the
existing Claude default preserves the current workflow while allowing a
per-role Codex override to be added later without re-registering hooks.

## Consequences

- Claude and Codex hooks and bundled `bmad-loop-*` skills must remain
  installed and refreshed together during future Loop upgrades.
- Any future policy role set to `codex` is already registered; no additional
  `bmad-loop init` step is required.
