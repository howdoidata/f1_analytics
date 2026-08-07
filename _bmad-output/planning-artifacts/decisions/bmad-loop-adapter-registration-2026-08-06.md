# BMAD Loop Adapter Registration Decision

**Date:** 2026-08-06
**Status:** Accepted

## Decision

Register both the `claude` and `codex` adapters with the project's BMAD Loop
installation. Keep `claude` as the default adapter for dev, review, and triage
in `.bmad-loop/policy.toml`.

Track `.codex/hooks.json` in the repository. Its commands resolve the Git
worktree root at runtime before invoking `.bmad-loop/bmad_loop_hook.py`, so no
developer-specific absolute path is required.

Do not ignore `.codex/` in this repository. Any additional project-local
Codex configuration remains visible in `git status` for an explicit review
rather than being silently hidden.

## Rationale

Both coding CLIs are available for future orchestration use. Keeping the
existing Claude default preserves the current workflow while allowing a
per-role Codex override to be added later without re-registering hooks.

## Consequences

- Claude and Codex hooks and bundled `bmad-loop-*` skills must remain
  installed and refreshed together during future Loop upgrades.
- Any future policy role set to `codex` is already registered; no additional
  `bmad-loop init` step is required.
- A Codex hook invoked outside a Git worktree fails instead of locating an
  unrelated hook; this configuration is intended only for this repository.
