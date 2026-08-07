---
title: "Repository Damage And Recovery Options — 2026-08-01 Assessment"
status: open — assessment only; cause identified, losses confirmed permanent locally
created: 2026-08-01
updated: 2026-08-01 (third revision — addendum A1–A3: surviving administrative material, decisions.md anchor, zsh check trap)
source_material:
  - git status / git ls-files -s / git cat-file -e / git fsck (run 2026-08-01 in f1_analytics)
  - ../exchange/administrative-to-all-project-root-relocated-and-repository-damage-audit-2026-08-01.md
  - ../exchange/administrative-to-all-recovery-results-and-remote-protection-status-2026-08-01b.md
  - ../exchange/operations-to-all-audit-undercounts-untracked-loss-2026-08-01.md
  - ../exchange/gatherer-correction-recoverability-overstated-2026-08-01.md
  - ../exchange/gatherer-f1-next-story-intake-2026-07-30.md
  - ../exchange/platform-to-all-one-folder-live-and-what-each-of-you-must-do-2026-07-30.md
---

# Repository Damage And Recovery Options — 2026-08-01 Assessment

## Purpose

Records F1's own verified assessment of the 2026-08-01 data loss, the cause as
established on the exchange, and what remains recoverable. **This record takes no
recovery action and authorizes none.**

Administrative's audit explicitly instructed each project not to treat its numbers
as authoritative for its own tree. Every figure below was produced by read-only
commands run inside `f1_analytics` on 2026-08-01, and differs from administrative's
published table where the restore pass has since moved it.

## Cause — Established, Not Inferred

Antonio relocated the project root off iCloud onto local disk:

```
OLD:  /Users/antonio/Documents/howdoidata/     (iCloud "Desktop & Documents" sync)
NEW:  /Users/antonio/howdoidata/               (local disk)
```

Per `administrative-to-all-project-root-relocated-and-repository-damage-audit-2026-08-01.md`,
the move copied a tree whose contents were iCloud **online-only placeholders**:
directory entries came across, bytes did not. This dropped both working-tree files
and git objects across five repositories simultaneously. F1 is the second-worst hit
of the five.

This supersedes any reading of the loss as a local git accident. It was not a git
operation and no session caused it.

## F1's Position — Verified In F1's Own Tree

```
run at: 2026-08-01, in f1_analytics, read-only
git ls-files | wc -l                              -> 268 tracked
git status --porcelain | grep '^ D' | wc -l       -> 207 missing from disk
for each deleted path: git ls-files -s -> blob; git cat-file -e blob
                                                  -> recoverable 0, UNRECOVERABLE 207
git ls-files -s, blob present in object store     -> 61 present / 207 missing
find . -type f (excl .git/.venv/caches) | wc -l   -> 117 files on disk
```

**All 207 still-missing tracked files are permanently lost locally. Zero are
recoverable.** They comprise roughly 75 planning artifacts, 45 implementation
artifacts, 29 files under `src/f1_analytics/`, 12 `docs/implementation_notes`, and
several `tests/`. The `analysis`, `data_sources`, `database`, and `validation`
package directories survive as empty shells.

`git fsck` reports 231 broken objects and history does not traverse
(`fatal: Failed to traverse parents of commit ae7fd68`).

**Of what survives, everything tracked is backed.** All 61 surviving tracked files
have their blob in the object store. This is materially better than operations,
which found 88 of its 113 surviving files backed by nothing, and it means F1 has no
second class of at-risk files sitting on disk.

### Correction to this record's first revision

The first revision of this document reported **233** deleted and **17** recoverable.
Both figures are superseded:

- **233 → 207.** Administrative's second restore pass returned 26 files to F1's
  working tree, including `PROJECT.md`, `question_feature_availability.py`,
  `question_backtest_explanations.py`, and two `tests/` modules — all verified
  present on disk now.
- **17 → 0.** The 17 came from walking *dangling trees* and testing the blobs they
  named. That is a different population from the currently-deleted set, and stating
  it alongside the deletion count invited the reading that 17 of the deletions were
  recoverable. They were not. Run against the deleted paths themselves, the
  recoverable count is **0**. This is the same defect gatherer published a
  correction for on the same day — answering the cheap question (is the path named?)
  and reporting it as the expensive one (is the blob readable?).

The dangling-tree walk retains one use: it is an **inventory** of 145 lost paths,
not a recovery source.

## What Recovery Actually Returned

Per `administrative-to-all-recovery-results-and-remote-protection-status-2026-08-01b.md`:

```
restored to working trees (all projects) : 4,337 files
of which uniquely authored               :     0
```

The restore worked by content-duplicate recovery — hashing a working tree recreates
blobs by content, so any destroyed object whose bytes were duplicated in a surviving
file came back. **Uniquely authored work is unique by definition and was not
eligible.** F1's irreplaceable count was 206 at 08:00 and 206 at 19:53. What came
back was reinstallable BMad skill payload.

**Do not read the drop from 233 to 207 as recovery of F1's work.** None of it was
F1's work.

## Offsite Protection Now Exists, And It Is Not A Recovery Source

Under Antonio's explicit authorization, administrative created a private remote and
pushed a snapshot. Verified in F1's tree:

```
origin  git@github.com:howdoidata/f1_analytics.git
remotes/origin/snapshot-2026-08-01
```

Because F1's history cannot be read end-to-end, that branch is a **parentless
snapshot of the working tree**, not real history. Verified content:

```
files in origin/snapshot-2026-08-01           -> 63
overlap with the 207 lost files               ->  0
```

It protects what survives from a *future* event. It returns nothing. `master` could
not be pushed at all, so the snapshot branch is the remote's default.

Administrative did not move `HEAD`, did not commit to any branch, did not touch the
index, and did not modify or delete any file present on disk.

## Untracked Loss — F1's Count Is A Floor

Operations' correction establishes that `git status | grep '^ D'` is blind to
untracked loss by construction, and that every project keeping artifacts under
ignore rules is understating its real loss. Applied to F1:

`.gitignore` ignores `_bmad/*`, `.claude/`, `outputs/`, `data/raw/`,
`data/processed/`, and several `_bmad-output/` runtime paths. Measured:

| Untracked area | State now |
|---|---|
| `_bmad/bmm/` | **0 files** |
| `_bmad/core/` | **0 files** |
| `.claude/skills/` | 26 files; **22 of 49 skill directories empty** |

None of this appears in the 207. It is why `_bmad/_config/bmad-help.csv` is absent
and why much of the BMad workflow tooling no longer functions in this repo.

F1's exposure here is **materially lower than operations'** — F1 tracks its
`_bmad-output/` planning and implementation artifacts rather than ignoring them, so
the bulk of F1's real work was inside the tracked count and *is* reflected in the
207. The untracked losses are framework payload: reinstallable, not authored.

## What Has No Recovery Source

The 207, in full, with no local recovery and none on the remote. The concentration
that matters is `src/f1_analytics/` — substantially the entire question-catalog,
backtest, and OpenF1-adapter body of work, the through-line of Epics 1–6:

```
evidence_link.py              question_lap_answers.py
openf1.py                     question_lap_coverage.py
openf1_loader.py              question_participants.py
question_answers.py           question_predictions.py
question_backtest_report.py   question_result_answers.py
question_backtest_scoring.py  question_tyre_pit_coverage.py
question_baseline_predictions.py  question_workflow_surfaces.py
question_catalog.py           report_summary.py
```

`question_feature_availability.py` and `question_backtest_explanations.py` are the
two exceptions — both returned in the restore pass and are present on disk.

**iCloud "Recently Deleted" / iCloud version history is the only remaining candidate
for the 207, and it is on a rolling purge window.** No Time Machine destination is
configured (`tmutil destinationinfo` → "No destinations configured"), `~/.Trash` is
empty, and no intact copy exists on this machine. `/Users/antonio/dev/howdoidata/`
mirrors the layout but is a structure-only skeleton with empty `objects/` trees —
**it is not a backup and must not be restored from.**

This is the only avenue whose window closes on its own, and it is Antonio's to
pursue.

## Handling Constraints — Still Live

- **Do not run `git gc`, `git prune`, or `git repack`.** Nine of thirteen
  repositories still report broken objects. Operations' amplification is worth
  carrying: in this state a gc can prune the last backing of a file currently
  sitting in the working tree and looking perfectly safe.
- **Do not run a blanket `git restore .` or `git checkout -- .`.** Gatherer's
  finding: it overwrites uncommitted modifications in the same sweep. Restore
  explicit paths, or stash first.
- Re-point absolute paths from `/Users/antonio/Documents/howdoidata/` to
  `/Users/antonio/howdoidata/`.
- Any `git log`-based or commit-hash citation F1 has published is currently
  **unverifiable in F1's own repository**, because history does not traverse. Not
  withdrawn — recorded as uncheckable.

## Exchange Position

**The live folder is `/Users/antonio/howdoidata/projects/exchange/`** (117 packets).
`platform/exchange/`, `gatherer/platform/exchange/`, and
`operations/platform/exchange/` are retired per
`platform-to-all-one-folder-live-and-what-each-of-you-must-do-2026-07-30.md`. Note
that both that directive and `exchange/README.md:3` still cite the **dead** iCloud
root; platform owns that text and has not amended it.

Twenty packets exist only in retired folders and were never consolidated, all
authored after the cutover. **F1's own
`f1-council-directive-acknowledgement-2026-07-30.md` is among them** — F1 wrote to
retired folders after the directive. That is F1's defect to fix.

### Open items on F1

1. **`gatherer-f1-next-story-intake-2026-07-30.md`** (`to: f1_analytics`, thread
   `f1-next-story-scoping`) — Gatherer asks whether F1's next full story expects
   anything of Gatherer. **Unanswered.** A reply is welcome and not owed. The
   accurate answer now is that F1's next story is not scopeable: the question-catalog
   work that would define it is in the unrecoverable 207.
2. **`body_sha256: pending`** in `f1-r3-position-updated-and-prior-instance-2026-07-30.md`
   — platform's directive said fill it or remove it. **Verified still `pending`.**
   One-line fix, independent of any recovery decision.
3. **Administrative's §4.1** asked every project to re-run the checks in its own
   tree. **Done — this section is the result.** F1's numbers diverge from
   administrative's published table only because the restore pass moved them
   (26 recoverable → 0 remaining, 233 missing → 207).

The Story 1.3 items and the R6/G1 threads are answered and need nothing further.

## Addendum — 2026-08-01 20:12 CDT

Three findings produced after the revision above, all by read-only commands in
F1's own tree except where noted.

### A1. Two administrative-authored packets survive only inside F1

```
run at: 2026-08-01T20:1x-0500
find /Users/antonio/howdoidata/projects -name "<packet>" -not -path "*/.git/*"
  administrative-to-f1-project-authority-boundary-and-open-admin-blockers-2026-07-21.md
    -> 1 hit, in f1_analytics/_bmad-output/planning-artifacts/cross-repo-notes/
  administrative-to-f1-run-record-destination-clarification-recommendation-2026-07-22.md
    -> 1 hit, same directory
```

Neither is in the live exchange folder (118 packets), nor in any of the three
retired folders. Both are tracked, both have their blob in F1's object store,
and both are on `origin/snapshot-2026-08-01`, so both are offsite.

They matter beyond their own content because each cites administrative's
now-destroyed control plane by path and then **states the cited substance in
administrative's own prose** — `docs/control-plane/protocol.md#project-identity-and-enforcement-boundary`
and `docs/decisions.md#2026-07-21-administrative-tracking-does-not-imply-project-enforcement`.

### A2. That decisions.md anchor exists nowhere else that F1 can see

```
grep -rhoE 'docs/decisions\.md#[a-z0-9-]+'
  f1_analytics/            -> 1 distinct anchor (the one above)
  projects/exchange/       -> 0
```

Administrative's decision log is destroyed. The 118-packet exchange carries no
anchor from it. F1 carries exactly one, second-hand.

### A3. A false-positive trap in the shared unbacked-blob check

Operations' §7 check, rewritten with the loop variable named `path`, silently
destroys `PATH` under zsh — `path` is tied to `PATH`. Every subsequent
`git cat-file -e` then fails as *command not found*, `2>/dev/null` swallows it,
and the check reports **100% of tracked files unbacked.** Reproduced in F1:

```
$ git ls-files -s | head -3 | while read -r m h s path; do
      git cat-file -e "$h" 2>/dev/null || echo "UNBACKED: $path"; done
  UNBACKED: .bmad-loop/bmad_loop_hook.py
  UNBACKED: .bmad-loop/policy.toml
  UNBACKED: .gitignore
$ which git  -> git not found
```

F1 hit this on its own first pass. No published figure on the thread is
affected — operations' snippet uses `read m h s p`, and neither operations'
88/113 nor gatherer's 8/2444 is a 100% result. Recorded so the next project to
run the check does not read a clean tree as a total loss.

### A4. Granularity did not protect F1's decision records

```
F1 decision records tracked at HEAD    19
  surviving on disk                     6
  in the unrecoverable 207             13
docs/decisions.md (the monolith)       lost
```

F1's cleanup-proof work split the still-active content of `docs/decisions.md`
into per-decision records under `_bmad-output/planning-artifacts/decisions/` and
froze the monolith as historical evidence. The monolith was lost and so were two
thirds of the extracted records. What was lost is the **pack file**
(`git count-objects -v` → `in-pack 0, packs 0`), and a pack is indifferent to how
its contents are organised.

The split remains right on its own grounds — citability, single-authority homes —
but it is **not** a durability measure and F1 will not present it as one. Only
pushing would have been, and F1 was not pushing.

## Status

**Open.** Assessment only. No files were restored, moved, deleted, or committed by
F1 in producing this record. The recovery decision — specifically whether to pursue
iCloud Recently Deleted while the window is open — is Antonio's.
