---
title: 'Portable Codex Hook Configuration'
type: 'chore'
created: '2026-08-06'
status: 'done'
route: 'one-shot'
---

# Portable Codex Hook Configuration

## Intent

**Problem:** Codex hooks were excluded from version control because their commands embedded a developer-specific absolute path.

**Approach:** Track the shared hook manifest with commands that locate the current Git worktree at runtime, while continuing to ignore all other local Codex state.

## Suggested Review Order

- Hook commands resolve the checked-out repository, not a developer’s home directory.
  [`hooks.json:8`](../../.codex/hooks.json#L8)

- The ignore rules track only the portable manifest and contain future local Codex files.
  [`.gitignore:4`](../../.gitignore#L4)

- The durable decision records the ownership boundary and failure behavior.
  [`bmad-loop-adapter-registration-2026-08-06.md:12`](../planning-artifacts/decisions/bmad-loop-adapter-registration-2026-08-06.md#L12)
