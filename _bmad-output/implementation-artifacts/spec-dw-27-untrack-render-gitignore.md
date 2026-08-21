---
title: 'DW-27: Untrack _bmad/render/.gitignore'
type: 'chore'
created: '2026-08-08'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `bmad-loop validate` permanently warns that `_bmad/render/` is tracked by git, but the only tracked file there (`_bmad/render/.gitignore`) was committed deliberately as a second defense-in-depth guard against ever committing ephemeral rendered skill output — untracking it trades that guard for a clean `validate` run.

**Approach:** Human chose to untrack the file. Run `git rm --cached` on it (keeping it on disk, now implicitly covered by the top-level `.gitignore`'s existing `_bmad/render/` rule), and record the decision and resolution on the DW-27 ledger entry.

## Boundaries & Constraints

**Always:** Leave `_bmad/render/.gitignore` on disk untouched; leave the top-level `.gitignore` untouched.

**Ask First:** None remaining — the human already chose between "keep tracked, accept the warning" and "untrack, accept the single-layer guard" via AskUserQuestion.

**Never:** Do not re-track `_bmad/render/.gitignore`. Do not attempt to patch the installed `bmad-loop` package's `validate` check (out of this repo's control; confirmed no per-warning suppression/allowlist exists in v0.9.1).

</frozen-after-approval>

## Code Map

- `_bmad/render/.gitignore` -- the file being untracked; stays on disk, now implicitly excluded by the top-level `.gitignore` instead of being self-excluding
- `.gitignore:52` -- pre-existing top-level `_bmad/render/` rule that becomes the sole remaining guard
- `_bmad-output/implementation-artifacts/deferred-work.md` -- DW-27 entry closed with a `decision:` and `resolution:` line

## Tasks & Acceptance

**Execution:**
- [x] `_bmad/render/.gitignore` -- `git rm --cached` -- untrack while keeping the file on disk
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- record decision + resolution on DW-27 -- close the ledger entry

**Acceptance Criteria:**
- Given the prior state where `_bmad/render/.gitignore` was tracked, when `git rm --cached` is run and committed, then `git ls-files _bmad/render` returns nothing.
- Given the untracked state, when `bmad-loop validate` runs, then it no longer emits the `git.render-tracked` finding.
- Given DW-27's previously open ledger entry, when this spec lands, then the entry carries `status: done`, a `resolution:` line (convention shared with e.g. DW-6, DW-7, DW-17) and a `decision:` line recording the human's sweep-time choice (convention shared with e.g. DW-8, DW-15, DW-16, DW-18, DW-20, DW-23).
- Given the sole remaining `_bmad/render/` rule (`.gitignore:52`), when `git check-ignore -v` is run against every file under `_bmad/render/`, then each one resolves to that rule (not just `.gitignore` itself) — confirming the guard's actual payload (rendered `bmad-build`/`bmad-build-auto` output, `config.yaml`) stays covered, not only the file that was untracked.

## Spec Change Log

## Verification

**Commands:**
- `git ls-files _bmad/render` -- expected: empty output
- `bmad-loop validate 2>&1 | grep -i render` -- expected: no output (warning gone)
- `find _bmad/render -type f -exec git check-ignore -v {} \;` -- expected: every path resolves to `.gitignore:52:_bmad/render/`
- Rollback if ever needed: `git add -f _bmad/render/.gitignore && git commit`

## Suggested Review Order

- Confirms the file is untracked but still present locally, now relying on the top-level rule below.
  [`_bmad/render/.gitignore`](../../_bmad/render/.gitignore)

- The single remaining guard against ever committing rendered skill output again.
  [`.gitignore:52`](../../.gitignore#L52)

- Ledger entry closed with the human's decision and the concrete resolution taken.
  [`deferred-work.md:212`](deferred-work.md#L212)
