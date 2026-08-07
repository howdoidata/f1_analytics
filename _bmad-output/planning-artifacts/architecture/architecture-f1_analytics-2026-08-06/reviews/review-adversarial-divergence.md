# Adversarial Divergence Review — ARCHITECTURE-SPINE.md

- **Reviewed artifact:** `_bmad-output/planning-artifacts/architecture/architecture-f1_analytics-2026-08-06/ARCHITECTURE-SPINE.md` (status: draft, 2026-08-06)
- **Lens:** Adversarial divergence — construct units one level down (epic teams) that each obey every AD *to the letter* yet still build incompatibly. Every pair found is a hole to close with a new or tightened AD.
- **Units simulated:** the catalog epic team, the ingestion epic team, the extraction epic team, the feature-contract epic team, the coverage epic team, the scoring/reporting epic team, the storage-edge epic team, the gatherer-handoff epic team. Each reads only the spine (per AD-10, nothing else binds).
- **Ground truth checked:** the architecture folder contains only the spine — no companion pins any shape the spine names. Every unpinned shape below is genuinely unpinned.

**Verdict: FAIL-with-fixes.** The spine's invariants are individually strong, but at least five pairs of letter-compliant units build incompatibly. The dominant defect class: the spine names shared data shapes and identities (catalog rows, `component_key`, `build_id` ordering, the extraction record, `feature_group`) without pinning their schema or their single minting authority.

---

## Scenario 1 — CRITICAL — The chimera answer: sparse vs dense target-store writes under AD-5's per-key read rule

**Units:** extraction epic team (writer) vs scoring/reporting epic team and gatherer-handoff epic team (readers).

**Exact AD texts both units satisfy:**

> AD-4: "append-only history via `CREATE TABLE IF NOT EXISTS` + `INSERT`; a re-run adds rows under a new `build_id`, never updates or deletes."

> AD-5: "Every downstream consumer reads from the persisted tables … and resolves history identically: **the single row with the max `build_id` per key**. The discrepancy surface is the sole consumer permitted to read more than one row per key."

> AD-9: "Package ID = `{question_id}:{producer_run_id}`."

**The two letter-compliant builds:**

- **Extraction team, policy S (sparse):** on a re-run where FastF1 is unreachable, the extractor emits rows only for the components it could compute this run — say 10 of Q05's 14. AD-4 is satisfied to the letter: rows were appended under a new `build_id`; nothing was updated or deleted. *No AD requires a run to write one row per catalog (question, component) pair.*
- **Extraction team, policy D (dense):** the same run emits all 14 rows, the 4 uncomputable ones with status `source_blocked`. Equally AD-4-compliant, and encouraged by NFR-3's statused-value convention.

**The collision (either policy breaks a reader):**

- Under **policy S**, the reporting consumer's literal AD-5 read ("max `build_id` **per key**", key = `(question_id, component_key)`) assembles a **chimera answer**: 10 components from build B2 plus 4 stale components from build B1 — a row-set no single run ever produced. Since AD-7 makes Analysis Mode "a **run-level parameter** recorded on outputs," B1 and B2 may even have run in different modes: the chimera silently mixes pre_race and post_race provenance across components of one question, defeating the leakage boundary AD-7 exists to enforce, while every individual read was AD-5-compliant.
- Under **policy D**, the same literal read hides a previously **computed** value behind the newer `source_blocked` row — and AD-5 explicitly forbids the report from looking one build back ("the discrepancy surface is the **sole** consumer permitted to read more than one row per key"). The report team that falls back to the last computed value violates AD-5; the team that doesn't renders a regression as if the value never existed. Both teams can point at the same sentence.
- The **handoff team** then cannot stamp a Package ID. AD-9 admits exactly one `producer_run_id` per package, but the chimera's max-per-key rows span two producer runs. Whichever run id the packet stamps, `body` components cite `build_id`s (per Consistency Conventions / NFR-2) that don't resolve to the packaged `producer_run_id` — mechanically well-formed, semantically untraceable.

**Hole:** AD-4 pins write mechanics and AD-5 pins a read rule, but nothing pins **run row-set semantics** — what one build is obligated to contain — so "max per key" and "one coherent build" are different reads.

**Closure:** New AD (or AD-4 tightening): *an extraction run writes exactly one row per in-scope catalog (question_id, component_key) pair, statused; a component with no computable value this run is written as a statused row, never omitted.* Plus AD-5 tightening: *packet/report assembly for a question reads the single max `build_id` per `question_id` (one coherent build), never max-per-component;* or alternatively record a per-build manifest (catalog hash, mode, in-scope keys) and forbid cross-build assembly.

---

## Scenario 2 — CRITICAL — Two committed catalogs, two `component_key` mints, and AD-8's pairing gate that can't catch the mismatch

**Units:** catalog epic team vs extraction epic team (with scoring team as the casualty).

**Exact AD texts both units satisfy:**

> AD-1: "The Question Catalog and Answer Type taxonomy are **committed artifacts** (tracked seed file **or** module); their DuckDB projections are derived copies."

> AD-7: "Every question defines its feature-snapshot boundary in the catalog."

> AD-4: "**Target store** (`question_actual_answer_components`, key `(question_id, component_key, build_id)` …)"

> AD-8: "Any prediction↔actual pairing asserts `question_id` equality before scoring."

**The two letter-compliant builds:**

- **Catalog team** ships `data/catalog/questions.yaml` — a tracked seed file (AD-1's first disjunct) with fields `question_id`, `question_text`, `answer_type`, `team_aliases` (per the Deferred note "catalog schema already generalizes via aliases"), `snapshot_boundary` (satisfying AD-7's letter). It defines **no components** — no AD says the catalog enumerates components.
- **Extraction team** builds extractors against `analysis/catalog.py` — a module (AD-1's second disjunct) exporting `CatalogRow(qid, prompt, components: list[ComponentSpec])`, because AD-4 obligates them to write `(question_id, component_key, build_id)` and *someone* must mint `component_key` values. They mint per-extractor: `start_tyre`, `first_change_lap`, …

Both teams satisfied AD-1 verbatim — "seed file **or** module" is a disjunction with no named path, no named format, and **no field schema anywhere in the spine**. The spine's only catalog-shape commitments are the question-ID naming convention and AD-7's boundary-lives-in-catalog sentence.

**The collision:**

1. **Two artifacts both claiming to be "the committed catalog";** no shared loader, no shared field names. The DuckDB "derived projection" (AD-1) is derived from *which one*?
2. **Two minting authorities for the item set.** AD-9 requires corrections to restate "the item set owned by the receiver's spec (**14 items for Q05**)" — that enumeration must live in a committed spec-owned place, and both teams can claim it. If the catalog team later says Q05 has 12 items while the extractors emit 14 keys, the gatherer-handoff team cannot build a valid restatement table at all.
3. **AD-8's gate passes the mismatch.** Scoring pairs a prediction labeled `first_stop_lap` with the actual component `first_change_lap`. AD-8's letter demands only `question_id` equality — satisfied. The mispairing (or silent non-pairing → "actual_unscoreable") sails through the exact check AD-8 installed to prevent wrong-output classes.

**Hole:** the spine names the catalog and `component_key` as load-bearing shared shapes but pins neither the artifact (path/format/fields) nor the single authority that mints `component_key` values and the AD-9 item set.

**Closure:** Tighten AD-1: *name the one committed catalog artifact (exact path, format) and its minimum row schema — `question_id`, `components[].component_key`, `answer_type`, snapshot boundary, aliases; the catalog is the sole minting authority for `component_key` values, and the AD-9 item set for a question is exactly its catalog component list.* Tighten AD-8: *pairing asserts `(question_id, component_key)` equality, both drawn from the catalog vocabulary.*

---

## Scenario 3 — HIGH — "Max `build_id`" is not one ordering, and the target store has two letter-compliant writers

**Units:** scoring epic team vs gatherer-handoff epic team (ordering); extraction epic team vs feature-contract epic team (two writers).

**Exact AD texts all units satisfy:**

> AD-4: "`build_id` is one value per orchestration run: `{UTC ISO-8601 basic timestamp}-{producer_run_id}`."

> AD-5: "One orchestration script runs extractors over catalog rows and writes the target store. … resolves history identically: the single row with the max `build_id` per key."

> Structural Seed: "`scripts/` — thin uv-run entry points, **one per pipeline stage**."

**The letter-compliant divergences:**

- **Ordering.** `producer_run_id`'s shape is pinned nowhere. Scoring implements "max" as SQL `max(build_id)` — lexicographic over the composite string. The handoff team parses the timestamp prefix and orders on it. With non-monotone run ids (UUIDs, `run-2` vs `run-10`) under equal timestamps — and "ISO-8601 **basic** timestamp" has no pinned precision, so same-second collisions are possible — the two consumers select **different "latest" rows** while both implementing AD-5's sentence faithfully. AD-5's whole purpose ("per-surface latest-row rules silently diverging") is defeated by its own unpinned ordering.
- **Two writers.** AD-4 classes `question_feature_availability_contract` as target-store, but AD-5's "**one** orchestration script … writes the target store" sits beside the seed's "one script per pipeline stage." The extraction team reads "the target store" as `question_actual_answer_components` (their table); the feature-contract team ships its own stage script writing `question_feature_availability_contract`. Each team's script is "the one orchestration script" for *its* table — letter satisfied twice. Now each run mints its **own** `build_id`, and scoring (which per the spine's flowchart joins T1 and T2) combines max-build rows across two tables with **no cross-table build coherence**: the latest feature contract may predate the catalog state the extraction ran over, so the leakage gate (AD-7/AD-8) is evaluated against a stale contract — with every individual read AD-5-compliant.
- **Same name, two mints.** `producer_run_id` appears in AD-4 (embedded in `build_id` — the *build's* producer) and in AD-9 (an evidence-delivery property — the *package's* producer). The handoff team stamps the packaging run's id; gatherer traces `{question_id}:{producer_run_id}` back toward build rows minted under the extraction run's id, and the join fails. Both teams used "producer_run_id" exactly as their AD spelled it.

**Hole:** an ordering-bearing composite identifier with unpinned component format and unpinned comparison rule; one sentence ("one orchestration script") stretched over two AD-4-classified tables; one identifier name with two minting contexts.

**Closure:** Tighten AD-4: *pin `producer_run_id` to a fixed-width, lexicographically monotone form (or declare the timestamp prefix at pinned precision the sole ordering key with a uniqueness rule), and define "max `build_id`" as bytewise string comparison — one rule, stated once.* Tighten AD-5: *name which stage script owns each target-store table, and require that any consumer joining across target-store tables record both `build_id`s on its output (or pin a shared-run rule).* Rename or qualify one of the two `producer_run_id`s (e.g. `package_run_id` in AD-9, with an explicit link field to the source rows' `build_id`s).

---

## Scenario 4 — HIGH — The record at the seam: extractor output vs append-helper schema

**Units:** extraction epic team (`analysis/`) vs storage-edge epic team (`database/`).

**Exact AD texts both units satisfy:**

> Layer table: `analysis/` — "importable functions; **no HTTP, no direct file/DB IO**"; dependency rule: "`analysis/` never imports … `database/`".

> AD-4: "Enforcement lives in `database/`: the replace helper **rejects** `question_*` targets; the append helper is the only writer for them."

> AD-8: "Lap numbers and positions are integers end-to-end."

> Conventions: "every Actual Answer Component cites source table/file, method, and `build_id` (NFR-2)."

**The two letter-compliant builds:**

- **Storage team** owns the append helper — and therefore, implicitly, the `CREATE TABLE IF NOT EXISTS` DDL inside it. They design a narrow table: `(question_id, component_key, build_id, value_text VARCHAR, status, source_ref, method)`. AD-4's letter fully satisfied; conventions' citation fields present.
- **Extraction team** — forbidden from touching the DB — emits records with **typed** values: `value: int` for lap numbers (AD-8: integers *end-to-end*), a duration type for lap times, plus `value_type`, expecting NFR-7's "absorbs new answer types **by data**, not migration" to mean a wide or JSON value column. Their records also carry `analysis_mode` (AD-7: "recorded on outputs") — a column the storage team never created, because no AD lists the table's columns.

**The collision:** the seam record — extractor output → script → append helper — is the one shape both teams must agree on, and the spine never states it. Integration either fails loudly (helper rejects unknown fields) or, worse, quietly: the helper stringifies `value`, and scoring's later numeric comparison reads VARCHAR — exactly the float/type-promotion wrongness class AD-8 was written to kill, produced by two teams each holding an AD-8-compliant frame ("we stored what we were given" / "we emitted ints").

**Hole:** AD-4 pins keys and write mechanics; the conventions pin three citation fields; nobody pins the full column set, the value-typing strategy, or which side owns the DDL.

**Closure:** New AD: *the Actual Answer Component record schema is defined once, in a committed schema module both `analysis/` (producer) and `database/` (DDL + writer) import — column list, value typing (how int / duration / text answers are represented without migration per NFR-7), status, citation fields, `analysis_mode`. Same for `question_feature_availability_contract`.* (The dependency rules already permit a shared leaf module; the spine just never demands one.)

---

## Scenario 5 — HIGH — The coverage gate that can't fire: unpinned `feature_group`/fact vocabulary and an unclassified coverage table

**Units:** coverage epic team (FR-10..11) vs feature-contract epic team (FR-14..16).

**Exact AD texts both units satisfy:**

> AD-3 (vocab 2 gate): "Gate: no downstream tyre/scoring feature is marked ready while a required fact's coverage is unknown."

> AD-4: "the replace helper **rejects** `question_*` targets" — and its three-class table list, which never names a coverage table.

> AD-7: "Post-race **fact groups** are forbidden inputs for pre-race features, enforced by the feature-availability contract."

**The letter-compliant divergences:**

- **Vocabulary.** AD-3 pins the *status* values on both sides (`available | derivable | …` and `already_available | …`) but pins **no vocabulary for the facts/feature-groups those statuses attach to**. AD-4's key says `feature_group`; AD-7 says "fact groups"; the coverage matrix names "required facts." The coverage team mints `tyre_stint_facts`; the feature team mints `feature_group = 'tyre'`; the AD-3 gate — which requires *joining* a feature's required facts to coverage rows — has no join key. Each team's enum is "defined in exactly one module and imported everywhere" (AD-3's letter) — everywhere *in its own epic*.
- **Persistence class.** The coverage matrix fits none of AD-4's three classes. Team choice A persists `question_coverage_matrix` — the `question_*` prefix makes the replace helper **reject** it, forcing append-only history nobody asked for. Team choice B names it `coverage_matrix` — bare curated, replace-in-place, history destroyed. Team choice C writes only `outputs/coverage_matrix.md` — whereupon AD-5's "every downstream consumer reads from the persisted tables" leaves the feature team with **nothing machine-readable to enforce the gate against**. All three are letter-compliant; a *table-naming choice* silently selects the write semantics.

**Hole:** the gate that AD-3 declares load-bearing has no pinned join vocabulary and no pinned home for the coverage state it reads.

**Closure:** Extend AD-3 with a fifth controlled vocabulary: *fact/feature-group names, defined once, used identically by the coverage matrix's `required fact` axis, AD-4's `feature_group` key, and AD-7's forbidden-input rule.* Tighten AD-4: *explicitly classify the coverage matrix table (name + class), so its write pattern is chosen by the spine, not by a filename.*

---

## Additional findings

### F6 — MEDIUM — Catalog edits between extraction and scoring: no build↔catalog binding

The catalog is a committed artifact (AD-1); the store is derived history (AD-4); consumers read the store (AD-5). Nothing records *which catalog state* a build ran over. Edit a `component_key` or retire a question after extraction but before reporting: the report team joins the **live** catalog to **stale** store rows. One letter-compliant surface drops orphaned rows silently; another renders them as catalog-less mystery components; the gatherer restatement (AD-9's "14 items") counts against the *new* catalog while the packaged rows answer the *old* one. Closure: record the catalog content hash (and mode, per AD-7) in the per-build metadata class; define the orphan-row policy once.

### F7 — MEDIUM — The status→token module has an owner but no address

AD-3: "one module owns the status→token mapping; `DESIGN.md` frontmatter is the token authority." Which layer? The reporting team puts it in `analysis/` (rendering logic) and bakes tokens into persisted outputs; the notebooks team — told consumers "render from persisted tables/artifacts only; never compute" — treats token-mapping as presentation and re-derives at render from `DESIGN.md`. Two application points, both "importing one module" in their own tree; when `DESIGN.md` frontmatter changes, persisted outputs and freshly-rendered notebooks disagree about the same status. Closure: name the module's home in the layer table, and state whether persisted surfaces carry raw status values (tokens applied only at render) or pre-rendered tokens — one, not both.

### F8 — LOW — Answer Type taxonomy values unpinned

AD-1 commits the taxonomy as an artifact but the spine never enumerates it; scoring (AD-8) must dispatch on answer types the catalog team mints. Largely mitigated by NFR-7 ("absorbs new answer types by data") plus NFR-3 (unknown type → statused unscoreable, not exception) — but only if the scoring team reads those the same way. Closure: fold the taxonomy's enumeration (or its committed location) into the tightened AD-1 of Scenario 2.

---

## Summary of holes → required AD actions

| # | Tier | Hole | Action |
| --- | --- | --- | --- |
| 1 | Critical | Run row-set semantics unpinned; AD-5 per-key read assembles cross-build chimeras; AD-9 Package ID can't span them | New AD: dense per-run row-sets; AD-5: one-coherent-build assembly rule |
| 2 | Critical | Catalog artifact/schema unpinned ("seed file or module"); `component_key` + AD-9 item set have no single mint; AD-8 pairs on `question_id` only | Tighten AD-1 (path, format, field schema, minting authority); tighten AD-8 (component-level pairing) |
| 3 | High | `build_id` "max" ordering undefined over composite string; two letter-compliant target-store writers; `producer_run_id` minted in two contexts | Tighten AD-4 (id format + comparison rule); AD-5 (per-table writer, cross-table join rule); disambiguate AD-9's run id |
| 4 | High | Extractor→append-helper record schema and DDL ownership unpinned; int-end-to-end breakable at the seam | New AD: shared committed record-schema module |
| 5 | High | No fact/feature-group join vocabulary for AD-3's gate; coverage table unclassified in AD-4 | Extend AD-3 (fifth vocabulary); tighten AD-4 (classify coverage table) |
| 6 | Medium | No catalog-version↔build binding; orphan-row policy undefined | Per-build catalog hash in metadata class; one orphan policy |
| 7 | Medium | status→token module home unaddressed; two token application points | Name the module home; pin raw-status-persisted vs render-time tokens |
| 8 | Low | Answer Type taxonomy values/location unenumerated | Fold into tightened AD-1 |

*Reviewer: adversarial-divergence lens, 2026-08-06.*
