# Implementation Note 009: Consolidate Process Governance Layer

Handoff: `docs/handoffs/approved/009-consolidate-process-governance-layer.md`, Status: Completed.

## Summary

The recurring "compare current setup against proposed config" check was legitimate (a continual architectural fitness function, in the sense used by *Building Evolutionary Architectures*) but had no governed path for its findings, so it got patched into seven near-duplicate prompt files instead of one canonical checklist. This handoff consolidates that checklist into `docs/terminal_protocol.md`, adds the standard ADR supersede convention to decisions and handoffs, writes one explicit revise-vs-supersede procedure for handoffs, and adds `scripts/fitness_check.py` so the check is run mechanically rather than read from memory.

## Files Changed

Process/governance docs:

* `docs/terminal_protocol.md` — canonical "Source of Truth / Standing Fitness Check" list; new "Decision and Handoff Status" section with the revise-vs-supersede procedure.
* `docs/decisions.md` — retrofitted `Superseded by:`/`Supersedes:` on the Kaggle/Jolpica decision pair; four new process decision entries.
* `docs/handoffs/README.md` — extended Status enum; reference to the revise-vs-supersede procedure.
* `docs/active_context.md` — Current Repo State, Current Focus, Current Decisions, Current Approved Documents, Next Action updated.

Historical handoff cleanup:

* `docs/handoffs/approved/001-normalize-project-context-scaffold.md` — added missing `Status: Completed` line.
* `docs/handoffs/approved/002-cleanup-project-scaffold.md` — added missing `Status: Completed` line.

Prompt consolidation:

* `docs/prompts/planning/session_prompt.txt` — new, single reusable planning session template.
* `docs/prompts/planning/archive/` — new; holds the 7 retired files (`planning_prompt.txt`...`planning_prompt6.txt`, `planning_prompt8.txt`), moved not deleted.
* `docs/prompts/command_prompt.txt` — added a placeholder/fill-in legend.

New tooling:

* `scripts/fitness_check.py` — new. Mechanically checks: required docs exist, handoff status validity (value + folder match), supersede referential integrity, no stray prompt files, decision entries well-formed.

## Commands Run

```bash
python3 scripts/fitness_check.py
```

* Before the doc edits: `Fitness checks: 5 run, 2 failed` — correctly caught `docs/planning_prompt8.txt` as a stray file, 6 planning prompt files where 1 was expected, and missing `Status:` lines on handoffs 001/002. This confirmed the script detects real drift rather than trivially passing.
* After the doc edits and archive move: `Fitness checks: 5 run, 0 failed`.

`find docs/prompts/planning -type f`, `test -f docs/planning_prompt8.txt`, and `grep -n "Supersedes|Superseded by" docs/decisions.md docs/handoffs/README.md` were also run to confirm layout and field presence; all passed.

## Generated Outputs

None (no `outputs/`, `data/`, or DuckDB artifacts). This handoff is documentation and tooling only.

## Data Assumptions / Source-Cutoff Definitions

Not applicable — no analysis or data pipeline files were touched.

## Known Limitations

* `scripts/fitness_check.py` checks structural invariants (files exist, status values valid, references resolve) — it does not check that a handoff's Status accurately reflects whether it was actually executed (e.g., a handoff could still say `Approved` after being executed rather than `Completed`); handoffs 003-008 currently do this and were left as-is since the checker treats `Approved` as a valid status for a file in `approved/` regardless of execution state.
* `docs/prompts/execution_prompt.txt` has the same hardcoded-handoff-filename pattern that `command_prompt.txt` had before this handoff, but was left unchanged since it was out of scope for this request.

## Follow-Up Recommendations

* Consider flipping Status on handoffs 003-008 from `Approved` to `Completed` in a small follow-up, now that the value is meaningful.
* Consider applying the same placeholder-legend cleanup to `docs/prompts/execution_prompt.txt`.
* Consider wiring `scripts/fitness_check.py` into a pre-commit hook or CI step if this project ever gains automated tooling beyond manual script runs.
