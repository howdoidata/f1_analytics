---
reviewer: rubric-walker
target: ARCHITECTURE-SPINE.md (architecture-f1_analytics-2026-08-06)
date: 2026-08-06
verdict: conditional-pass
---

# Rubric Walker Review — ARCHITECTURE-SPINE.md

**Verdict: CONDITIONAL PASS.** This is a strong, unusually well-evidenced spine — verified against the PRD, the surviving code, `docs/data_sources.md`, `DESIGN.md`, the reconstruction doc, and the live exchange folder. It passes six of seven checklist items outright. One high-severity internal contradiction (AD-1 "derived and disposable" vs AD-4/AD-12 durable history and manual promotions) must be resolved before target-store stories are cut; the remaining findings are tightening, not redesign.

---

## Checklist Walk

### 1. Fixes the real divergence points for epics/stories, and misses none — MOSTLY PASS (two misses)

The spine names and closes the genuinely dangerous forks: source-conflict resolution (AD-2, single arbiter view), status enums (AD-3, one module per vocabulary), write semantics (AD-4, helper-enforced split), latest-row resolution (AD-5, max `build_id` per key), source roles (AD-6), leakage boundary (AD-7), publication gating (AD-8), packet mechanics (AD-9 — exhaustive, and rightly so given the correction-class restatement trap), contract-free rebuild (AD-10), invocation convention (AD-11 — directly targeting the lost-`PYTHONPATH` trap), seed-answer laundering (AD-12), pagination/rate discipline (AD-13), and id space (AD-14). The dependency-direction mermaid plus "nothing imports `scripts/`" is a real rule, not decoration.

**Missed fork #1 (HIGH — see F1):** durable-state identity of the target store. AD-1 declares the DuckDB file "derived and disposable: rebuildable from committed code plus raw caches," while AD-4 makes `question_*` tables append-only history whose destruction is the very failure AD-4 exists to prevent, AD-5's discrepancy surface consumes that multi-row history, and AD-12 admits `user_manual_approved` promotions — user decisions with **no committed source**, hence not rebuildable from code plus caches. Two builders will legitimately diverge: one wipes and rebuilds `data/processed/f1_analytics.duckdb` freely (per AD-1), the other treats it as the only home of un-reproducible history and promotions (per AD-4/AD-12). `data/processed/` is gitignored (PRD §9), so nothing rescues this. NFR-1 (reproducibility) is contradicted for the promotion rows as written.

**Missed fork #2 (MEDIUM — see F2):** the committed Question Catalog's physical form. AD-1 says "tracked seed file **or** module" and leaves the disjunction open. The catalog is the single most-consumed artifact (extractors, feature contract, scoring, reports, coverage matrix all take catalog rows); a data-file catalog and a Python-module catalog imply different loading, typing, and test surfaces. This fork is not under Deferred and not an open question — it is silent.

### 2. Every AD's Rule is enforceable and prevents its stated divergence — PASS (minor gaps)

- AD-2, AD-3, AD-4, AD-6, AD-9, AD-12, AD-13, AD-14: enforceable at a named single point (view, module, helper, decision-record gate, constants) — each mechanically prevents its stated divergence. AD-4's "replace helper rejects `question_*` targets" is the right kind of enforcement: at the choke point, not by convention.
- AD-5: the resolution rule is stated precisely ("the single row with the max `build_id` per key" — correctly distinguishing per-key-latest from latest-build), but no single resolver function is designated; each consumer writing its own `max(build_id)` SQL is drift waiting to happen. The "shared derived logic is computed by one function" convention arguably covers it, but naming one helper in `database/` would close it (F6).
- Layer import rules (`analysis/` imports nothing from `data_sources/`/`database/`) have no named enforcement mechanism; a trivial import-check test satisfies AD-10's "tests prove it" and costs nothing (F6).
- AD-7: enforcement is delegated to the feature-availability contract ("not each consumer's discretion") — adequate at this altitude.
- AD-8's "a numeric comparison that could see float promotion normalizes types first" is judgment-worded but backed by the int-end-to-end convention; acceptable.

### 3. Nothing under Deferred could let two units diverge — PASS (one interaction noted)

Walked all eleven Deferred items. Each is either gated behind a single future decision point (OQ1 at epics; OpenF1 revival behind an AD-6 decision record), rendered non-forking by a binding default that holds meanwhile (OQ2 — AD-12's default-deny binds now; only the relaxation is deferred), rendering-only (OQ3), sequence-blocked (Track-2 surfaces, forecast models), or explicitly "plan nothing against it" (registry edge). The in-repo interchange companion deferral is safe because AD-9 carries the full contract in the spine meanwhile. FR-10's `[ASSUMPTION]` is protected by the AD-3 coverage gate. One interaction: OQ4 (the `user_manual_*` promotion mechanism) is safely deferred **only if** F1 resolves promotion durability — the mechanism can be anything, but whatever it is must leave a committed or re-appliable record (folded into F1).

### 4. Named tech verified-current — MOSTLY PASS

DuckDB 1.5.5, pandas 3.0.5, FastF1 3.8.3, Plotly 6.9.0 all carry 2026-08-06 verification dates and are plausible for August 2026; the pandas-3-vs-lost-2.x behavioral warning and the FastF1 compat-spike gate (AD-6) show real verification discipline, as do the dated Jolpica rate limits in AD-13 (4 req/s / 500 req/h, "limits will decrease"). Three of seven stack rows carry **no** verification date: Python 3.13, uv 0.11.x, pytest 9.x (F4). Python 3.13 is plausibly a deliberate ratification of the surviving environment (`cpython-313` bytecode is present in the repo) rather than "current," but the spine doesn't say so; by 2026-08 a newer minor exists, so the pin should state its reason and date. uv 0.11.x and pytest 9.x are plausible but unverified as written.

### 5. Ratifies rather than contradicts the surviving codebase reality — PASS (verified)

Checked against the surviving tree:
- Structural seed matches the surviving `src/f1_analytics/{analysis,data_sources,database,validation}` layout exactly.
- AD-3's seven-value answer-status vocabulary matches `DESIGN.md` §Components status-badge tokens verbatim (verified against `_bmad-output/planning-artifacts/ux-designs/ux-f1_analytics-2026-07-22/DESIGN.md` lines 149–174, 248) and is consistent with the surviving generic `status_badge.py` renderer.
- AD-2 restates `docs/data_sources.md`'s precedence rule word-faithfully, and its promotion of `kaggle_jolpica_coverage` from "comparison only" to "single arbiter" is a declared tightening, not a contradiction.
- AD-10's supersession claim is accurate: reconstruction doc §5 step 4 (line ~280) does say the intact modules "pin the exact symbol contracts of `question_catalog` and `question_backtest_report`," and AD-10 explicitly names and demotes that framing — the right move given the memlog-recorded user decision.
- AD-11's pyproject/pytest pivot contradicts the surviving `requirements.txt`/no-pyproject reality, but deliberately, with the lost-convention trap as rationale and user ratification in the memlog — ratify-by-declared-supersession, which AD-10 authorizes.
- AD-9's channel claims verified: the exchange folder exists and is populated; the authority packet `gatherer-handoff-spec-item-set-declaration-2026-07-30.md` exists in-channel with matching frontmatter (`packet_class: correction`, `record: docs/specs/f1-gatherer/v2.md`), so learning the contract "only through channel packets" is real, not aspirational.
- Standing constraints correctly carry the damage-record prohibitions (`repository-damage-and-recovery-options-2026-08-01.md` exists in `decisions/`).

### 6. Covers the driving PRD's capabilities — PASS

The Capability → Architecture Map covers FR-1..18 with governing ADs, and all seven NFRs land: NFR-1 (AD-1 committed artifacts — but see F1's promotion-row exception), NFR-2/NFR-3 (Consistency Conventions), NFR-4 (AD-7), NFR-5 (AD-1), NFR-6 (AD-6 five-field decision record, matching PRD §9's exact field list), NFR-7 (absorb-by-data convention, SM-8). PRD §6 guardrails (no betting framing, manual-entry-is-user-decision, forecast-models-post-MVP) all bind. Two declared deviations, both legitimate: (a) FR-7 names `raw_jolpica_laps` but the spine routes lap facts to FastF1 — permitted by FR-7's own "or another approved source" clause and gated by AD-6's decision record; (b) the gatherer interchange (AD-9) exceeds PRD §7 scope but is declared in the frontmatter scope line with its trace. PRD OQ1–OQ4 are each explicitly dispositioned under Deferred. No PRD capability is silently dropped.

### 7. Every feature-altitude dimension decided, deferred, or open — MOSTLY PASS

- **Operational envelope:** explicitly decided ("decided, not deferred") — local macOS, single user, manual `uv run`, no scheduler/CI/deploy — with the superseded artifacts named. Exemplary.
- **Error handling:** decided — the statused-value (analysis core, NFR-3) vs fail-fast (shells, source-identity) split in Consistency Conventions, plus AD-13's backoff/statused-failure rules.
- **Security/credentials:** thin but present — AD-11 names per-source credential requirements (Kaggle token; FastF1/Jolpica none). Missing only a one-line "credentials are never committed / live outside the repo" rule (F7). Adequate for a local single-user tool.
- **Observability:** decided at the right altitude — `source_registry`/`source_load_log`/`validation_results` append-per-build logs (AD-4 class 3), advisory-and-logged validation (AD-8). Script logging convention unspecified; trivial (folded into F6).
- **Testing strategy:** partially silent — the runner (pytest), invocation (AD-11), and burden of proof (AD-10 "a capability exists only when this rebuild's tests prove it") are decided, but nothing decides whether tests may touch the network. Given AD-13's hard 500 req/hour Jolpica budget and last rebuild's rate-limit error storms, a test suite hitting live APIs is a concrete, spine-relevant hazard, and fixture policy (cached payloads as goldens?) is a real per-story divergence point (F3).
- **Data lifecycle/retention:** the weakest dimension — cache precedence and snapshot disposability are decided, but target-store history durability is contradicted (F1) and append-only growth is unbounded with no statement that unbounded is acceptable (one sentence fixes it; folded into F1's resolution).

---

## Findings

| ID | Tier | Finding |
| --- | --- | --- |
| F1 | HIGH | AD-1 vs AD-4/AD-5/AD-12 contradiction: the DuckDB file is declared "derived and disposable," yet it is the only home of append-only discrepancy history and of `user_manual_approved` promotions — user decisions with no committed source, hence not "rebuildable from committed code plus raw caches." Two builders can legitimately adopt opposite treatments of `data/processed/f1_analytics.duckdb`, and NFR-1 is violated for promotion rows. Resolve by either (a) carving `question_*` history + promotions out of "disposable" and giving promotions a committed record (e.g. a tracked promotions file the append helper replays), or (b) declaring history disposable-across-rebuilds and scoping AD-4's guarantee to within-store lifetime — but decide it in the spine. State whether unbounded append growth is accepted while there. |
| F2 | MEDIUM | The Question Catalog's committed form is an undecided disjunction ("tracked seed file or module," AD-1) — the most-consumed artifact in the system has an open format fork that is neither decided, deferred, nor an open question. Pick one (or explicitly defer it to the catalog epic's first story). |
| F3 | MEDIUM | Testing strategy decides the runner but not the doctrine: no rule on network isolation in tests (live-API tests would burn AD-13's 500 req/hour Jolpica budget — the exact failure class AD-13 was hardened against), and no fixture/golden policy. One rule closes it: tests never touch the network; cached raw payloads are the fixtures. |
| F4 | LOW | Stack table: Python 3.13, uv 0.11.x, and pytest 9.x carry no verification dates (rubric requires them); Python 3.13 appears to be a ratification of the surviving `cpython-313` environment rather than "current," which the row should say. |
| F5 | LOW | Status-tag inconsistency: AD-10, AD-11, AD-13, AD-14 lack the `[ADOPTED]` marker the other ten ADs carry, while the doc is `status: draft` — the memlog shows all four were user-decided, so untagged-but-binding is ambiguity a story writer could exploit (e.g. treating AD-13's rate discipline as advisory). Tag them. |
| F6 | LOW | Enforcement gaps closable for free: designate one latest-per-key resolver helper in `database/` (AD-5) and one import-direction test (layer rules); optionally name a script logging convention. |
| F7 | LOW | Credentials: add the one-line rule that credentials live outside the repo and are never committed (AD-11 names them per source but not their handling). |

## Recommendation

Approve for epic derivation once F1 is resolved in the spine text (it gates the target-store and promotion stories specifically; ingestion and catalog epics are unaffected). F2–F3 should be fixed in the same editing pass; F4–F7 are hygiene.
