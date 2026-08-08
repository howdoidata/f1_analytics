# Decisions

## 2026-07-10 — Accept Phase 3's Source-Of-Truth correction; require stop-and-report, not in-place repair, for future phase-boundary fitness findings

Decision:
Accept, without reverting, the correction made during Handoff 020 (platform-bootstrap Phase 3) execution to `TARGET_DIR`'s `docs/terminal_protocol.md` `## Source Of Truth` section, which added explicit coverage for the `docs/handoffs/` and `docs/inbox/` directory entries that the Phase 0-2 output had omitted — a gap discovered by that same phase's newly-written `required_docs_match_protocol_list` check on its first run. Direct verification against `TARGET_DIR` (2026-07-10) confirms the corrected list is accurate and `python3 scripts/fitness_check.py` now passes 10/10 there. Going forward, reaffirm that when a fitness-check-equivalent finding surfaces a gap in Phase 0-N content that is outside the exact edits a handoff's Steps authorize, the correct action is to stop and report to planning for a scoped correction — not to patch the file in place during execution, even when, as here, the patch itself later proves substantively correct.

Rationale:
Handoff 020 already specified this exact scenario as a stop condition ("Any Phase 0-2 fitness-equivalent check would fail before this phase's scripts are even added... stop and report rather than silently repairing Phase 0-2 content") and restricted Step 3's edit to `docs/terminal_protocol.md` to one named sentence, not the `## Source Of Truth` list's coverage. The Source-Of-Truth coverage gap was corrected directly instead. This repository's own Handoff 019 already demonstrates the intended alternative: a dry run caught an analogous Gate-2 scope problem before execution, and the draft was revised in place and re-approved rather than patched around during a live run. Reverting a correct fix to reintroduce a known bug would serve no purpose, so this decision accepts the outcome rather than the process by which it was reached, and restates the stop-and-report rule for Phase 4 onward, where a comparable situation is plausible again: Phase 4 (multi-project layer) is likely to surface its own Phase 0-3 gaps as `projects/` and `exchange/` are introduced.
This project's own terminal_protocol.md independently requires this: "If the fitness check surfaces a finding about what this list itself should require... that finding is a process decision and must be written into docs/decisions.md" — this entry is that required record for the platform-bootstrap thread, addressed here since `TARGET_DIR` remains read-only to any process other than an approved handoff's own Steps.

Tradeoffs:
No rollback or rework is required in `TARGET_DIR`, but this decision does not retroactively make the Phase 3 execution compliant with Handoff 020's own stop condition — it only prevents the same deviation from being treated as acceptable practice going forward. Phase 4's draft handoff should state this rule as an explicit stop condition rather than relying on this decision being read first, since an executing system per this project's own convention has no access to this repository's decision log.

Status:
Accepted.

## 2026-07-09 — Deliver the bootstrap specification as an incremental, phase-scoped handoff sequence starting with repository scaffold only

Supersedes: 2026-07-09 — Deliver the multi-project platform as a self-contained, order-strict bootstrap specification

Decision:
Split the single seven-phase bootstrap specification into a sequence of small, independently-reviewable handoffs, one phase at a time, instead of delivering all phases (0-6) inside one draft. Draft only Phase 0 (repository scaffold: `git init`, `AGENTS.md`, a generic platform `PROJECT.md`, `.gitignore` — no governance docs, no scripts, no `projects/`/`exchange/` yet) as `docs/handoffs/drafts/017-platform-bootstrap-phase0-repository-scaffold.md`. Every later phase (governance docs, terminal workflow layer, mechanical fitness/workflow scripts, the multi-project/template/exchange layer, the synthetic-project verification, the F1-onboarding verification) is drafted as its own follow-on handoff only after the previous phase has been reviewed and, if approved, executed — not written in advance. Each phase-scoped handoff must still satisfy the no-prior-history constraint (executable by a system with no access to this repository's history) and must templatize the real, load-bearing architecture rationale this project has already learned (e.g. why source boundaries stay explicit, why decisions carry tradeoffs, why handoffs freeze once approved) directly into generic instructional text, rather than leaving blank placeholders — carrying forward the underlying decisions without carrying forward the historical log entries that produced them.

Rationale:
The prior same-day decision produced one large draft covering all seven phases at once. The user asked instead to work on only the first handoff so basic adherence can be verified before more is drafted, and clarified that "no history" must not be satisfied by shallow, blank scaffolding — the specification needs enough embedded architectural substance (the actual rules this project's real incidents produced, restated generically) that an executing system does not drift, even though it must not inherit this repository's decision log, run log, or implementation notes verbatim. Incremental, gated delivery of the specification itself mirrors the same "prefer small, reversible changes" and "standing fitness function" discipline (`docs/architecture_principles.md`; *Building Evolutionary Architectures*) already applied to this project's own handoffs, applied here one level up to the act of specifying the platform.

Tradeoffs:
The full seven-phase roadmap is not committed to paper as executable instructions yet — only Phase 0, plus an informational (non-binding) outline of Phases 1-6 for continuity. Later phases cannot be drafted with full confidence until Phase 0's execution is observed, which means real project-agnostic-platform progress is slower than a single big-bang specification would have been, but each phase is verified in isolation before compounding. Keeping every phase genuinely history-free while still substantive requires deliberate rewriting (not copy-paste) of this project's real docs each time a phase is drafted, which is more planning effort per phase than a verbatim template would take.

Status:
Accepted.

## 2026-07-09 — Deliver the multi-project platform as a self-contained, order-strict bootstrap specification

Supersedes: 2026-07-09 — Adopt a monorepo platform/project separation with a phased migration

Decision:
Replace the six-handoff in-place migration plan with a single self-contained bootstrap handoff (`docs/handoffs/drafts/017-platform-bootstrap-specification.md`) that an AI system with no access to this repository's history, context, or decision log can execute in an empty directory. The handoff defines strict, ordered build phases (0 through 6), each closed by a mechanical verification gate that must pass before the next phase may begin: (0) repository scaffold, (1) platform governance documents, (2) three-terminal workflow layer, (3) mechanical fitness/workflow enforcement scripts, (4) multi-project layer with `projects/`, a project template/generator, and a gitignored `exchange/` staging convention, (5) Verification A — a fully-specified synthetic project built and run end-to-end, and (6) Verification B — onboarding an existing external project from a user-provided source bundle, with that project's stated goal artifact executing headlessly. Project-specific information (including everything about F1) appears only in clearly-separated test-fixture parameter blocks consumed by the generic onboarding procedure, never in platform content. The monorepo shape, `projects/<name>/` isolation, and `exchange/` staging convention carry forward from the superseded decision and are restated inside the specification so it remains self-contained. This repository is not restructured in place by this decision; whether it is later rebuilt or replaced using the specification is a separate future decision.

Rationale:
The six migration drafts (017-022) were removed from `docs/handoffs/drafts/` by the user without approval or execution, and the request was restated with new constraints: the instructions must work "without the past history, context, or information," must "stick with strict build rules in certain order, then adhered to," and must arrive as "a handoff that another system can understand and strictly adhere to." An in-place migration inherently depends on this repository's current file layout and history, so it cannot satisfy the no-prior-context constraint; a greenfield, gate-checked bootstrap specification can, and it simultaneously serves as the reusable normalization template the original inbox item (`docs/inbox/processed/2026-07-09-project-agnostic-platform.md`) asked for. Ordered phases with mechanical gates apply the standing-fitness-function discipline this project already uses (*Building Evolutionary Architectures*) to the act of building the architecture itself.

Tradeoffs:
One large specification is harder to review than six small handoffs, and it must embed enough document, workflow, and check detail to stand alone, which risks drift between the specification and this repository's live process docs if either evolves independently. The F1 onboarding test (Verification B) depends on a user-provided source-bundle path plus local Kaggle credentials and Jolpica API access, so it is reproducible by the user but not by an arbitrary third party without those inputs. This repository itself remains un-restructured, so the platform/project mixing the original inbox item objected to persists here until a future decision addresses it — the specification proves the target architecture in a separate environment first, which is lower-risk but defers the cleanup.

Status:
Superseded.

Superseded by: 2026-07-09 — Deliver the bootstrap specification as an incremental, phase-scoped handoff sequence starting with repository scaffold only

## 2026-07-09 — Adopt a monorepo platform/project separation with a phased migration

Decision:
Restructure the repository into a generic, reusable "platform" layer (root-level process, protocol, and governance assets that name no specific project) and isolated "project" layers under `projects/<project_name>/` (e.g. `projects/f1_analytics/`), each owning its own code, data, SQL, notebooks, generated outputs, and project-specific governance docs (decisions/questions/backlog/asset inventory). Keep this as a single repository (monorepo) rather than separate repositories per project. Add a shared, gitignored `exchange/` staging convention for moving files into or out of a project, modeled on the existing `docs/inbox/` triage pattern (raw material lands, gets triaged, and either gets claimed by a project or archived) rather than inventing new intake mechanics. Execute the separation as a phased series of draft handoffs (`017` through `022`) rather than one large handoff, each independently reviewable and validatable: (017) define the boundary, isolation rules, and exchange convention in new platform docs with no file moves; (018) split the currently mixed governance docs into platform-level and project-level copies; (019) physically migrate all F1-specific code/data/docs into `projects/f1_analytics/` and verify the existing notebook and build scripts still run unchanged; (020) make `scripts/fitness_check.py` and `scripts/workflow.py` project-aware, including new drift/isolation checks; (021) build a reusable project template/generator distilled from the now-generic platform assets; (022) generate a synthetic second project from that template and prove both projects operate independently end-to-end.

Rationale:
The 2026-07-09 inbox item ("Project-agnostic platform scope") asked to isolate project-specific (F1) information from reusable architecture/process assets so multiple, unrelated projects can share one operating model while each project's data, history, and assets stay isolated, with safety, risk, and architecture held as the highest priorities and the item's own `Constraints:` field flagging it as risky. A monorepo with per-project subfolders keeps the existing single-repo Markdown-as-memory model (2026-07-07 decision) intact and avoids duplicating the terminal/handoff/fitness-check machinery per repository, which would be heavier than the current early-stage need justifies (`docs/architecture_principles.md`, "Defer Tooling Until Repeated Need Justifies It"). Phasing the change into six small, sequentially-dependent handoffs instead of one large handoff follows the same principles document's "Prefer Small, Reversible Changes," keeps each step separately reviewable and revisable per the existing draft/approve lifecycle, and matches the sequencing already anticipated in `docs/backlog.md`. Reusing the `docs/inbox/` triage pattern for the new `exchange/` convention, rather than inventing new intake mechanics, follows "Let Governance Improve Speed." The second test project is synthetic rather than a real second project so the template and isolation boundary can be proven immediately without waiting on a real project's specific data-source details.

Tradeoffs:
This adds a new top-level `projects/` directory, a new `exchange/` convention, and six sequential handoffs' worth of process and migration work before any new F1 analysis can resume; F1-specific work is effectively paused mid-migration until Handoff 019 completes. Splitting the mixed governance docs (Handoff 018) requires classifying every existing decision/question/backlog/asset-inventory entry as platform-level or project-level without rewriting any accepted decision's body, which is manual and must be checked carefully against the ADR frozen-record rule. `scripts/fitness_check.py` and `scripts/workflow.py` must be generalized to operate over `projects/*` without hardcoding `f1_analytics`, which is a real rewrite of already-working scripts. The security/isolation rule set is intentionally lightweight (no OS-level sandboxing or credential-manager tooling) and relies on mechanical fitness checks plus documented convention rather than enforced runtime isolation; if a future project needs stronger isolation guarantees, that would require a new decision.

Status:
Superseded.

Superseded by: 2026-07-09 — Deliver the multi-project platform as a self-contained, order-strict bootstrap specification

## 2026-07-09 — Add a scoped, precedence-ruled combined dataset for current-season leader identification

Supersedes: 2026-07-08 — Load Jolpica/Ergast as a fully loaded, separate source

This supersession applies only to that decision's "never merge" clause; its loading, caching, and coverage-view mechanics are unchanged and remain in effect.

Decision:
Add three new, additive DuckDB objects — `combined_results`, `combined_driver_standings_by_round`, `combined_constructor_standings_by_round` — that union Kaggle curated per-round results with Jolpica per-round results under an explicit precedence rule: Kaggle wins for any season/round where Kaggle has at least one row (the existing `match`, `kaggle_only`, and `row_count_diverges` statuses in `kaggle_jolpica_coverage`); Jolpica fills a season/round only where Kaggle has zero rows (the `jolpica_only` status). Cumulative points, wins, and standing rank on the combined tables are recomputed across these combined per-round rows using the same cumulative logic already used for `driver_standings_by_round`/`constructor_standings_by_round`, not a new parallel implementation. Any season/round tagged `row_count_diverges` by `kaggle_jolpica_coverage` must be surfaced as a documented deviation in analysis output, not silently resolved. Existing Kaggle-only curated tables (`results`, `driver_standings_by_round`, `constructor_standings_by_round`, `final_driver_standings`, `final_constructor_standings`) are unchanged and remain the source of truth for historical (pre-current-season) analysis.

Rationale:
The Kaggle CSV snapshot is stale for the 2026 season (results only through round 3) while Jolpica has real data through round 9. Answering "how many times has the leader at this point in the season gone on to win" requires first knowing what "this point in the season" actually is right now, which a Kaggle-only cutoff cannot supply. A scoped, rule-based combination for current-season leader identification satisfies this concrete need without weakening the Kaggle-baseline precedent for historical/curated tables, and follows the architecture principle "Do Not Merge Sources Without Precedence Rules" by making the precedence explicit: Kaggle wins on any overlap, Jolpica fills only genuine gaps, and divergences are surfaced rather than auto-resolved.

Tradeoffs:
This adds one new precedence rule and three new combined tables/views instead of reusing the Kaggle-only tables as-is, and reopens a "never merge" decision that was accepted only one day earlier. Combined standings also depend on Jolpica per-round `driver_id`/`constructor_id` values matching Kaggle's id conventions at the row level, which has only been verified at the aggregate row-count level so far (via `kaggle_jolpica_coverage`); if the ids do not match cleanly, an id-reconciliation step (similar to the existing `driver_standings` constructor-name reconciliation) would be needed before this decision can be fully realized.

Status:
Accepted.

## 2026-07-09 — Keep architecture-principles documents source/tool-name-generic

Decision:
`docs/architecture_principles.md` must state architecture-level principles using generic language only, without naming specific sources, tools, or vendors. Concrete source, tool, or vendor treatment belongs solely in `docs/decisions.md` and topic-specific docs such as `docs/data_sources.md`.

Rationale:
While trying to reproduce and extend the project, two principles in `docs/architecture_principles.md` ("Keep Source Boundaries Explicit" and "Do Not Merge Sources Without Precedence Rules") were found to name Kaggle and Jolpica/Ergast directly. This made the document read as if it were specifically about Kaggle/Jolpica rather than a durable, reusable rule that Kaggle/Jolpica happens to currently illustrate.

Tradeoffs:
This requires rephrasing principle text to stay generic even when a concrete example would be more vivid, and requires remembering to keep new principles name-agnostic going forward. It avoids the recurring confusion between a reusable architecture rule and a one-time concrete source decision.

Status:
Accepted.

## 2026-07-09 — Adopt lightweight architecture governance documents

Decision:
Use `docs/asset_inventory.md`, `docs/architecture_operating_model.md`, and `docs/architecture_principles.md` as the project's lightweight architecture governance layer.

Rationale:
The project already has strong process memory through decisions, questions, handoffs, run logs, implementation notes, and inbox triage, but it needs a simple way to see important assets, route architecture findings, and apply project-specific principles as the environment evolves.

Tradeoffs:
This adds three maintained Markdown documents and requires future changes to update asset and governance context when relevant. It avoids heavier metadata tooling, automated lineage, scoring dashboards, or governance workflows until repeated use proves those are needed.

Status:
Accepted.

## 2026-07-09 — Require run-log records for command validation

Decision:
Command-terminal validation results must be recorded in `docs/run_log.md` before the command-terminal turn ends. `python3 scripts/fitness_check.py` records itself automatically; other validation commands still require manual run-log entries.

Rationale:
The repo is the source of truth, and validation results returned only in chat create ambiguity for later planning sessions. Recording validation results in the run log lets later terminals confirm the latest known fitness state from the repository.

Tradeoffs:
This adds a small recording step for command-terminal work and causes each fitness-check run to update `docs/run_log.md`, but it removes uncertainty about whether validation completed and what it reported.

Status:
Accepted.

## 2026-07-09 — Adopt docs/inbox as supplemental external-input intake

Decision:
Use `docs/inbox/` as a supplemental intake area for external files, corrections, short specs, questions, and reference material that need to influence planning or execution.

Rationale:
Some useful inputs are easier to provide as files or bundles than as prompt text. A lightweight repo-owned intake convention keeps those inputs visible to the workflow without replacing existing durable destinations such as questions, decisions, handoffs, implementation notes, raw data folders, or generated outputs.

Tradeoffs:
Planning must triage raw inbox items before planning work, and the fitness check now fails when untriaged items remain directly under `docs/inbox/`. This creates a small process obligation in exchange for clearer provenance and retention.

Status:
Accepted.

## 2026-07-07 — Use repo Markdown as project memory

Decision:
Use repo-based Markdown files as the durable source of truth for project context, decisions, handoffs, run logs, and implementation notes.

Rationale:
The project uses multiple terminals. Chat-only context will drift and create conflicting assumptions between planning, coding, and command execution.

Tradeoffs:
This adds lightweight documentation overhead, but reduces rework, context loss, and terminal confusion.

Status:
Accepted.

## 2026-07-08 — Use Kaggle as baseline and Jolpica as supplemental source

Decision:
Use the Kaggle Formula 1 complete CSV dataset as the Version 1 baseline source. Treat Jolpica/Ergast as a supplemental API source for future gap-fill or freshness checks. Keep shared Python under `src/f1_analytics/` and reusable SQL under `sql/`.

Rationale:
The Kaggle CSV dataset already supports the first local DuckDB build and report. Jolpica can add freshness or missing data later, but mixing sources without explicit precedence rules would weaken provenance.

Tradeoffs:
This keeps the first workflow stable and simple while adding a small structure for reuse. Future source merge rules must still define which source wins when data disagrees.

Status:
Superseded.

Superseded by: 2026-07-08 — Load Jolpica/Ergast as a fully loaded, separate source

## 2026-07-08 — Load Jolpica/Ergast as a fully loaded, separate source

Supersedes: 2026-07-08 — Use Kaggle as baseline and Jolpica as supplemental source

Decision:
Move Jolpica/Ergast from a documented-but-not-loaded supplemental source to a fully loaded, separate source. Load current-season results, qualifying, driver standings, constructor standings, laps, and pit stops into their own `raw_jolpica_*` DuckDB tables. Never merge Jolpica data into Kaggle curated tables. Add a `kaggle_jolpica_coverage` DuckDB view (`sql/analysis/kaggle_jolpica_coverage.sql`) comparing per season/round row counts between the two sources.

Rationale:
The Kaggle CSV snapshot was found to be stale for the 2026 season: `f1_races.csv` lists all 22 rounds, but `f1_results.csv`/`f1_qualifying.csv` only cover rounds 1-3, while Jolpica has results through round 9. This is a concrete, present need rather than a hypothetical future one.

Tradeoffs:
This adds a second live data source and API-pacing logic, but keeps Kaggle as the sole authority for curated tables. Jolpica is additive and comparison-only, so it does not introduce source-precedence ambiguity into existing reports.

Status:
Superseded.

Superseded by: 2026-07-09 — Add a scoped, precedence-ruled combined dataset for current-season leader identification

This supersession applies only to this decision's "never merge" clause; its loading, caching, and coverage-view mechanics are unchanged and remain in effect.

## 2026-07-08 — Load Kaggle circuits and qualifying CSVs

Decision:
Load `f1_circuits.csv` and `f1_qualifying.csv` as both raw (`raw_circuits`, `raw_qualifying`) and curated (`circuits`, `qualifying`) DuckDB tables.

Rationale:
Both files were already present locally and unused; loading them is low effort and the qualifying table is required to compare against Jolpica qualifying data in the coverage view.

Tradeoffs:
None significant. No existing curated table logic changed.

Status:
Accepted.

## 2026-07-08 — Reconcile driver_standings constructor name to constructor_id

Decision:
Add a reconciliation step that derives `constructor_id` for `final_driver_standings` by mapping the free-text `constructor` name in `f1_driver_standings.csv` against the id/name pairs already present in `results` and `constructor_standings`.

Rationale:
`f1_driver_standings.csv` has no `constructor_id` column, only a name, unlike `results` and `constructor_standings`. The name-to-id mapping built from the other two tables is unambiguous (no name maps to more than one id) and fully covers `driver_standings`, so reconciliation is low-risk.

Tradeoffs:
If a future Kaggle refresh introduces a genuinely ambiguous constructor name (e.g. two different constructors sharing a display name), rows would silently take the first matching id. This is judged acceptable for now since the current dataset has zero ambiguous names; it is covered by a null-rate validation check that would surface any newly *unmatched* names (not ambiguous ones) as nulls.

Status:
Accepted.

## 2026-07-07 — Use draft and approved handoff folders

Decision:
Use `docs/handoffs/drafts/` for proposed handoffs and `docs/handoffs/approved/` for execution-ready handoffs.

Rationale:
Future handoff instructions should be reviewed and approved through files in the repo instead of being manually pasted between terminals.

Tradeoffs:
This adds one lightweight approval step, but keeps planning work separate from execution work and reduces the risk of running unapproved instructions.

Status:
Accepted.

## 2026-07-08 — Treat the setup-comparison check as a standing fitness function

Decision:
Adopt the "architectural fitness function" framing (Ford/Parsons/Kua/Sadalage, *Building Evolutionary Architectures*) for the recurring "compare current setup against the proposed config" check. Consolidate the checklist itself, previously duplicated verbatim across seven planning prompt files, into one canonical list in `docs/terminal_protocol.md`.

Rationale:
The check itself was correct and should keep running on a recurring basis; the defect was that its checklist got copy-pasted into a new prompt file every time it needed to change, instead of living in one place. Findings from the check about project topics remain planning output as before; findings about what the checklist itself should require are process decisions and belong in this file.

Tradeoffs:
Planning sessions must now reference `docs/terminal_protocol.md` for the checklist instead of carrying it inline in the prompt; this is a small extra step to keep exactly one canonical copy instead of several drifting ones.

Status:
Accepted.

## 2026-07-08 — Adopt the ADR supersede convention for decisions and handoffs

Decision:
Add `Supersedes:`/`Superseded by:` fields to both `docs/decisions.md` and handoff files, using the standard ADR lifecycle (Nygard format / adr.github.io): a frozen record's body (Rationale/Tradeoffs/Context, or a handoff's implementation steps) is never rewritten; only its Status line may later be updated to point at what replaced it.

Rationale:
Without this, reconstructing "what's actually true now" required reading the entire decision log top to bottom and reconciling entries by hand (for example, the Kaggle/Jolpica decision pair above). This is a standard, named field from existing ADR practice, not an invented mechanism.

Tradeoffs:
Requires remembering to update the Status line on the old record when a new one supersedes it; the fitness check (`scripts/fitness_check.py`) validates that `Supersedes`/`Superseded by` references point at records that actually exist.

Status:
Accepted.

## 2026-07-08 — Adopt a binary revise-vs-supersede fork for handoffs

Decision:
Extend handoff Status values to `Draft`, `Needs Revision`, `Approved`, `Completed`, `Rejected`, `Superseded`. Define one procedure for handling a question or needed change on an approved handoff: if no part of it has executed yet, revise in place by moving it back to `docs/handoffs/drafts/` with `Status: Needs Revision` and a dated Revision Note; if any part has executed, leave it untouched and write a new handoff that supersedes it.

Rationale:
There was previously no documented answer for "I have a question about this handoff" or "this needs a small change" short of a full post-hoc correction, which meant this kept getting reinvented ad hoc in chat. The single fork (has execution started?) reuses the existing drafts/approved folder gate rather than adding new mechanism.

Tradeoffs:
None significant; this only adds one status value (`Needs Revision`) and one written procedure to a lifecycle that already existed.

Status:
Accepted.

## 2026-07-08 — Consolidate planning prompt files into one reusable template

Decision:
Replace the seven near-duplicate planning prompt files (`docs/prompts/planning/planning_prompt.txt` through `planning_prompt6.txt`, and the stray `docs/planning_prompt8.txt`) with one reusable `docs/prompts/planning/session_prompt.txt`. Move the retired files into `docs/prompts/planning/archive/` rather than deleting them.

Rationale:
Each prior file carried a full copy of the setup-comparison checklist plus that session's specific topic, so every planning session repeated the same heavyweight audit before reaching its actual topic. With the checklist now canonical in `docs/terminal_protocol.md` (see above), the prompt only needs to point at it and state the day's topic.

Tradeoffs:
None significant; archiving instead of deleting keeps the iteration history visible without it being mistaken for the current template.

Status:
Accepted.

## 2026-07-08 — Use python3 for repository commands

Decision:
Use `python3` in repository documentation, handoffs, and terminal commands unless an activated project virtual environment explicitly provides `python`.

Rationale:
The current macOS environment provides `python3` but no `python` executable. The standing fitness check could not start when invoked as `python scripts/fitness_check.py`, so the documented command was not portable to the project's actual environment.

Tradeoffs:
This favors compatibility with the current environment. A future managed virtual environment may expose `python`; that environment-specific convention can supersede this decision if adopted.

Status:
Accepted.

## 2026-07-08 — Adopt a workflow guide and read-only status router

Decision:
Use `docs/workflow_guide.md` as the intent-based terminal decision tree and `scripts/workflow.py` as a read-only status router that reports process fitness and current repo workflow state.

Rationale:
The existing three-terminal model and handoff lifecycle are sufficient, but users need one direct route for choosing a terminal, handling handoff revisions, and finding the next action without reconstructing state across several documents.

Tradeoffs:
This adds one guide and one small CLI to maintain. The CLI intentionally cannot edit files, approve handoffs, or run other scripts, so lifecycle changes remain explicit repository actions.

Status:
Accepted.

## 2026-07-08 — Require Revision Notes for all Needs-Revision handoffs

Decision:
Generalize the existing Revision Note procedure so it applies to any handoff set to `Status: Needs Revision`, including drafts that never left `docs/handoffs/drafts/`. Extend `scripts/fitness_check.py` by adding the Revision Note presence check inside the existing `check_handoff_statuses()` function rather than creating a new check.

Rationale:
The current lifecycle defined how to send an approved handoff back for changes, but not how to evaluate a draft and record why it was not yet ready. Handoff 011 exposed the gap directly: it sat in `Needs Revision` with no recorded reason, and that reasoning was later lost.

Tradeoffs:
This adds one structural requirement to handoffs in `Needs Revision`: they must carry a dated `## Revision Note` section. The fitness check remains detection-only and does not evaluate the quality of the note's content.

Status:
Accepted.

## 2026-07-08 — Keep process facts canonical by topic and enforce pointers structurally

Decision:
Make each duplicated process fact canonical in the document closest to its topic instead of restating it across prompts, role docs, workflow text, and the fitness script. Use `docs/terminal_roles/*.md` for terminal responsibilities and required inputs, `docs/handoffs/README.md` for handoff status values, and `docs/terminal_protocol.md` for workflow lifecycle and handoff field requirements. Extend `scripts/fitness_check.py` and `scripts/workflow.py` to detect structural drift against those canonical locations.

Rationale:
The same process facts had already drifted in multiple places: required-docs coverage, terminal naming, handoff statuses, execution stop conditions, required-reading lists, and terminal-purpose descriptions. Hand-edited duplication without a structural check was the recurring defect, not the content itself.

Tradeoffs:
This keeps process facts hand-authored and colocated by topic, but it adds several small structural checks that must be updated when canonical process docs change intentionally. The checks catch pointer/list drift, not paraphrased prose drift.

Status:
Accepted.
