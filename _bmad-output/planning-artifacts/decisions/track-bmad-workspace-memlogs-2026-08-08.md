---
title: "Track BMAD Workspace Memlogs Instead Of Gitignoring Them"
status: accepted
created: 2026-08-08
source_material:
  - .gitignore (pre-change: _bmad-output/**/.memlog.md)
  - _bmad-output/planning-artifacts/decisions/repository-damage-and-recovery-options-2026-08-01.md
---

# Track BMAD Workspace Memlogs Instead Of Gitignoring Them

## Purpose

Resolves a finding from a BMAD-functions gitignore audit (2026-08-08): the
`.gitignore` pattern `_bmad-output/**/.memlog.md` excluded every BMAD skill
memlog (bmad-prd, bmad-architecture, bmad-brainstorming, bmad-deep-recon,
bmad-spec, bmad-forge-idea, bmad-eval-runner, and others) from version
control, even though `memlog.py` describes memlogs as working memory meant
to "persist ACROSS sessions, so a fresh session can load it and continue."

## Decision

**Untrack the pattern; commit existing memlogs.** A gitignored memlog only
persists on the one machine/checkout that wrote it — invisible to a fresh
`git clone`, a teammate, or a disaster-recovery restore. This project already
lost 207 tracked files and their full history on 2026-08-01 specifically
because state lived only on local disk, not in git (see
`repository-damage-and-recovery-options-2026-08-01.md`). `docs/.memlog.md`
(bmad-project-context's own memlog) was already tracked; this makes every
BMAD workspace memlog consistent with that, not an exception.

**Accepted trade-off:** memlogs are append-only and grow every session, so
tracking them adds diff noise on every append — the same profile as the
already-ignored `daily-pipeline-run-records.jsonl`. Durability against a
repeat of the 2026-08-01 loss outweighs that noise for planning-artifact
memlogs; `daily-pipeline-run-records.jsonl` stays ignored because it is a
regenerated pipeline log with no unique-authorship content, not a decision or
planning record.

**Not addressed by this decision, deferred separately:** concurrent
`bmad-loop` worktree sessions appending to the same logical memlog can now
produce real git merge conflicts, which was structurally impossible while the
file was ignored (see deferred-work.md).

## Status

Accepted. `.gitignore` updated; existing memlog(s) queued for commit pending
a redaction check for personal machine paths (separate open question with
the user, not blocking this decision).
