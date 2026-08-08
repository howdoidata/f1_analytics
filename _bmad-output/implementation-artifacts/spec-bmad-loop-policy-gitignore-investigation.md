---
title: 'Investigate tracking .bmad-loop/policy.toml — keep gitignored'
type: 'chore'
created: '2026-08-08'
status: 'done'
route: 'one-shot'
---

## Intent

**Problem:** `.bmad-loop/policy.toml` is gitignored wholesale, but it mixes genuinely machine-specific settings ([tui] pane sizes, [mux] backend) with project-wide orchestration policy ([gates], [review], [scm], [adapter] CLI routing) that's invisible to git and unreviewable by the team — filed as deferred work during the 2026-08-08 memlog gitignore fix.

**Approach:** Attempted tracking the whole file (the deferred item's own recommendation), then reverted after finding the installed `bmad-loop` package's `init` command unconditionally re-adds the file to `.gitignore` on every run with no suppression flag — tracking it would fight the installer forever, not fix anything, and patching the uv-managed tool itself wouldn't survive the next reinstall. Kept the file gitignored, documented why in a decision record, and updated the deferred-work entry to record that this specific fix isn't available from this repo alone.

## Suggested Review Order

- Why tracking was reverted and what remains genuinely unresolved
  [`track-bmad-loop-policy-2026-08-08.md`](../planning-artifacts/decisions/track-bmad-loop-policy-2026-08-08.md)

- The gitignore comment now explains the investigation and points at the decision record
  [`.gitignore:39-45`](../../.gitignore#L39)

- Deferred-work entry updated in place (append-only) with the investigation outcome, not closed
  [`deferred-work.md:31`](deferred-work.md#L31)
