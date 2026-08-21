---
title: bmad-loop orchestration policy (mirror of the gitignored policy.toml)
description: The project-wide orchestration settings the loop runs under, mirrored here because .bmad-loop/policy.toml is gitignored and therefore unreviewable
mirrors: .bmad-loop/policy.toml
verified_against_source: 2026-08-20
---

<!-- Reference documentation, deliberately outside the docs/ agent-context bundle:
     that bundle is a small set of high-signal conventions, and this is a long
     lookup table. Not indexed by _bmad/scripts/context.py. -->

# bmad-loop orchestration policy

**This document mirrors `.bmad-loop/policy.toml` and is the reviewable copy.** The
generated file is gitignored and cannot practically be tracked: `bmad_loop/install.py`'s
`init` unconditionally re-appends the ignore line on every run, with no suppression flag.
Tracking it was attempted and reverted on 2026-08-08 — see
[`decisions/track-bmad-loop-policy-2026-08-08.md`](../../_bmad-output/planning-artifacts/decisions/track-bmad-loop-policy-2026-08-08.md)
for that decision, and DW-15 in the deferred-work ledger for the gap it leaves.

**This mirror can drift from the generated file.** That is the accepted cost of the
approach. `.bmad-loop/policy.toml` is authoritative; if the two disagree, the TOML wins
and this document is wrong. Update this file in the same change whenever a project-wide
section of the policy changes.

Scope: the project-wide sections only. `[tui]` (pane sizes) and `[mux]` (terminal
multiplexer backend) are genuinely machine-specific and deliberately omitted — they are
the only sections the file's own comments justify keeping local.

## Gates

| Key | Value | Meaning |
| --- | --- | --- |
| `gates.mode` | `per-epic` | Human gate at each epic boundary, not per story |
| `gates.retrospective` | `notify` | Notify at an epic's end; never auto-run the retro |

`gates.on_escalation` is not set in the file; it resolves to the engine default `pause`
(a CRITICAL escalation pauses the run for `/bmad-loop-resolve`), as seen in a run's
`state.json` `policy_snapshot`.

## Verification gates

Deterministic commands run after a clean review, before commit. A non-zero exit fails
the story rather than landing the change.

```toml
[verify]
commands = [
  "uv run .github/scripts/validate-records.py",
  "bash tools/artifact-status-assertions.sh",
]
```

These are the two planning-record drift guards. They also run in CI (`ci.yml`'s
"Planning records" job) and at commit time (`tools/hooks/pre-commit`). An unattended loop
run is exactly where a spec status advances without the board following, so catching it
here fails the story instead of reconciling the drift reactively later.

## Review

| Key | Value | Meaning |
| --- | --- | --- |
| `review.enabled` | `true` | Run a follow-up review session after a dev pass |
| `review.trigger` | `recommended` | Only when the dev pass sets `followup_review_recommended: true` |

Bounded by `limits.max_review_cycles` (hard cap) and damped by
`limits.max_followup_reviews`.

## Story queue

| Key | Value | Meaning |
| --- | --- | --- |
| `stories.source` | `sprint-status` | Walks `sprint-status.yaml` from bmad-sprint-planning |
| `stories.spec_folder` | `""` | Unused under `sprint-status` |

## Adapter (CLI routing)

| Key | Value | Meaning |
| --- | --- | --- |
| `adapter.name` | `claude` | Which coding CLI runs sessions |
| `adapter.model` | `""` | Empty = CLI default model |
| `adapter.cleanup_session_on_finish` | `true` | Kill the run's tmux session when it finishes |

No per-stage overrides (`[adapter.dev]`, `[adapter.review]`, `[adapter.triage]`) are
active — every stage inherits the settings above.

## Limits

| Key | Value |
| --- | --- |
| `max_review_cycles` | 3 |
| `max_dev_attempts` | 2 |
| `max_followup_reviews` | 1 |
| `session_timeout_min` | 90 |
| `stop_without_result_nudges` | 1 |
| `dev_stall_grace_s` | 600 |
| `dev_stall_nudges` | 2 |
| `workflow_stall_nudges_cap` | 3 |
| `max_tokens_per_story` | 2,000,000 |
| `cache_read_weight` | 0.1 |

## Sweep

| Key | Value | Meaning |
| --- | --- | --- |
| `sweep.auto` | `never` | Sweeps are never auto-triggered; run them explicitly |
| `sweep.max_bundles` | 5 | Bundles executed per sweep; **triage excess is truncated** |
| `sweep.max_triage_attempts` | 2 | Triage validation retries before escalating |
| `sweep.max_migration_attempts` | 2 | Legacy-ledger migration retries before escalating |
| `sweep.repeat` | `false` | Do not re-triage and continue after a cycle |
| `sweep.max_cycles` | 5 | Safety cap when `repeat = true` |

`max_bundles = 5` has bitten once: the 2026-08-08 sweep run truncated 5 bundles
(`sweep-bundles-truncated` in its journal), so that work was triaged but never executed.

## Source control

| Key | Value | Meaning |
| --- | --- | --- |
| `scm.isolation` | `none` | Work happens in place on the checked-out branch |
| `scm.branch_per` | `story` | Worktree mode only; inert under `isolation = none` |
| `scm.target_branch` | `""` | The branch checked out at run start |
| `scm.merge_strategy` | `merge` | Worktree mode only |
| `scm.delete_branch` | `true` | Delete the unit branch after a successful merge |
| `scm.keep_failed` | `true` | Keep a failed unit's worktree/branch for inspection |
| `scm.rollback_on_failure` | `false` | Never auto-touch the tree; pause with manual recovery steps |
| `scm.preserve_keep` | 20 | Attempt-preserve branches kept at run start |
| `scm.max_parallel` | 1 | Parallel fan-out unbuilt; values > 1 clamp to 1 |
| `scm.seed_adapter_defaults` | `true` | Seed adapter gitignored configs into worktrees |
| `scm.worktree_seed` | `[]` | No extra gitignored paths seeded |

`isolation = none` means loop runs modify your working checkout directly. Combined with
`rollback_on_failure = false`, a failed attempt leaves its changes in place for manual
recovery rather than being reverted.

## Notifications and cleanup

| Key | Value |
| --- | --- |
| `notify.desktop` | `true` |
| `notify.file` | `true` (the `ATTENTION` file in the run dir) |
| `cleanup.run_retention` | 10 |
| `cleanup.retention_days` | 0 (disabled) |
| `cleanup.trim_artifacts` | `true` |
| `cleanup.archive_old` | `true` |
| `cleanup.auto_clean_on_finish` | `true` |
| `cleanup.clean_tmp` | `true` |
