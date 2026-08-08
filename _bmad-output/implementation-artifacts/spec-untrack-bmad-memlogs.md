---
title: 'Track BMAD workspace memlogs in git'
type: 'chore'
created: '2026-08-08'
status: 'done'
route: 'one-shot'
---

## Intent

**Problem:** `.gitignore` excluded `_bmad-output/**/.memlog.md`, so every BMAD skill's session memlog (bmad-prd, bmad-architecture, bmad-brainstorming, bmad-deep-recon, etc.) lived only on the local machine — invisible to a fresh clone, a teammate, or a disaster-recovery restore, despite `memlog.py`'s own design intent that memlogs "persist ACROSS sessions." This project already lost 207 files this way on 2026-08-01.

**Approach:** Remove the `.gitignore` pattern, document the rationale (`.gitignore` comment + a decision record), commit the one memlog that already existed untracked, and record the two real findings a review surfaced (`.bmad-loop/policy.toml`'s mixed machine/project config, and the new memlog merge-conflict risk under concurrent worktree sessions) as deferred work rather than silently fixing or ignoring them.

## Suggested Review Order

- Why the pattern was removed and what replaces it as the rationale trail
  [`.gitignore:11-16`](../../.gitignore#L11)

- Full reasoning: the durability argument, the accepted diff-noise trade-off, and why `daily-pipeline-run-records.jsonl` stays ignored by contrast
  [`track-bmad-workspace-memlogs-2026-08-08.md`](../planning-artifacts/decisions/track-bmad-workspace-memlogs-2026-08-08.md)

- The one memlog this decision immediately un-ignores, now trackable
  [`architecture-f1_analytics-2026-08-06/.memlog.md`](../planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/.memlog.md)

- Two review-surfaced findings filed as deferred work rather than patched: `.bmad-loop/policy.toml`'s mixed machine/project settings, and the new concurrent-worktree memlog merge-conflict risk this change introduces
  [`deferred-work.md:26-36`](deferred-work.md#L26)
