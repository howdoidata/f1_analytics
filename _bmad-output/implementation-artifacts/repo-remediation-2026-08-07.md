# Repo Remediation — 2026-08-07

## Scope

A `/bmad-code-review` of the FastF1 constructor-name-reconciliation decision record surfaced a live data-correctness bug, which led to fixing it, then proving the repo could pass its own tests from a fresh clone, which surfaced two more real problems (an unreproducible BMAD toolchain, a broken project context bundle). All four are fixed and re-verified end to end. Commits: `0821611`, `d410401`, `316df37`, `5fff4dd` on `main`, not yet pushed.

## Problems and root causes

### 1. Silent driver-id mismapping (the serious one)

**Symptom:** none visible — that's the point. Story 1.6 was marked `done`; `raw_fastf1_laps` looked populated and correct.

**Root cause:** `map_driver_ids()` in `fastf1_loader.py` built its FastF1-code → curated-id lookup with `drivers.drop_duplicates(subset=["code"]).set_index("code")["driver_id"]`. The curated `drivers` table has six 3-letter codes that each match two different historical drivers (F1 reuses codes across eras). `drop_duplicates()` silently keeps whichever row comes first — no error, no warning.

**Actual damage, confirmed against the live database:** `VER` resolved to `vergne` (Jean-Éric Vergne, retired ~2014) instead of `max_verstappen`; `ALB` resolved to `albers` (Christijan Albers) instead of `albon` (Alexander Albon). The already-landed `raw_fastf1_laps` table contained 230 laps under `vergne` and 169 under `albers`, and **zero** laps under `max_verstappen` or `albon`, across all four already-pulled 2026 races.

**Why the review layers alone didn't catch the real damage:** all four review layers (Blind Hunter, Edge Case Hunter, Verification Gap, Acceptance Auditor) flagged the `drop_duplicates()` pattern as a *theoretical* risk. None of them queried the actual curated table or the actual landed data. The live-database check — required by this repo's own triage step ("read the code before rating... judge reachability... do not rate from the diff hunk alone") — is what turned "theoretical risk" into "already-shipped wrong data for the sport's headline driver."

### 2. Four smaller, related gaps in the same file

Found and fixed in the same review: alias-resolved `constructor_id` values weren't checked against the live curated table (a stale alias would silently inject a dangling id); `round` could land as `None` with nothing catching it, silently defeating a planned season+round join; the row-tagging code ran *outside* the function's own `try/except`, contradicting its documented "never an uncaught crash" guarantee; `NaN`-`Stint` laps merged into one artificial stint spanning non-contiguous laps with zero test coverage; the `verify_completeness` missing-driver branch had zero test coverage independent of the lap-undercount check that always fired first.

### 3. The repo wasn't reproducible from a clone

**Symptom:** asked to "ensure you can pass all these tests on a cloned branch," using a detailed test report as the spec. That report described tooling — a `bmad-toolchain-parity.py` guard, Firebase deploy gating, BigQuery erasure, GCP IAM tightening — that exists nowhere on this machine: not in `f1_analytics`, not in any of the 27 sibling projects under `~/howdoidata/projects/`, not even in `platform`. Redirected to verify this repo's *own* real tests on a clone instead.

**Root cause:** `.claude/`, `.agents/`, and `_bmad/*` (except `_bmad/custom/`) were gitignored as "installed tool payloads — not project-owned." A `git clone` therefore produced a repo with `pyproject.toml`/`src`/`tests` but no `.claude/skills/`, no `.agents/skills/`, no `_bmad/scripts/context.py` — none of the BMAD skill machinery this whole session (and every prior BMAD session on this project) depends on.

### 4. The project context bundle was broken

**Symptom:** once `context.py` existed in a clone, `context.py validate` returned `ok: false`.

**Root cause:** `docs/index.md` was a stale, hand-authored, pre-rebuild snapshot (generated 2026-07-12/13, predating the 2026-08-01 data-loss/rebuild) — 0 conformant bundle entries, and its own index rows pointed at 8 targets, 3 of which (`backlog.md`, `questions.md`, `run_log.md`) don't exist in `docs/` at all anymore. Confirmed this predated any change made today (identical failure in the original real repo before the toolchain-tracking fix), so it wasn't something the tracking change caused — it had simply never been exercised for real before.

**A buried consequence of the same staleness:** `docs/local_setup.md` self-labeled "Status: Current" but described running `scripts/download_kagglehub_f1_data.py` — a script confirmed gone from the current `scripts/` directory. The actual current pipeline (`kaggle_csv.py`) reads pre-populated static CSVs from `data/raw/f1_complete_dataset/` and never imports `kagglehub` at all; only the separate, already-known-broken `spike_fastf1_adoption.py` touches Kaggle credentials.

## BMAD tools used to fix them

| Tool | Used for |
|---|---|
| `bmad-code-review` skill (4-layer review: Blind Hunter, Edge Case Hunter, Verification Gap, Acceptance Auditor) | Surfaced the initial findings against the constructor-alias decision record and the Story 1.6 loader diff |
| Decision-record convention (`_bmad-output/planning-artifacts/decisions/`) | Authored and got explicit approval for `fastf1-driver-code-reconciliation-decision-record.md` before writing any code — same evidence bar as the existing constructor-alias record |
| `npx bmad-method@next install` (BMAD installer CLI) | Bootstrapped the exact toolchain versions from `_bmad/_config/manifest.yaml` (core/bmm `6.10.1-next.51`, `bmb` and `bmad-loop` on `main`) into the scratch clone |
| `_bmad/scripts/context.py` (`validate`, `sweep`, `index`, `config`) | Diagnosed the broken doc bundle; proved the fix, including a deliberate red/green test with a fabricated `sources:` path |
| `bmad-project-context` skill (full invocation) | Drove the actual kernel/bundle build: placement decision → memlog → brownfield ingest → kernel + 3 verified entries → index regen → fresh-eyes polish → finalize |
| `_bmad/scripts/memlog.py` | Logged the decision/event/note trail for the context-bundle work per the skill's own "log the moment it happens" rule |
| `resolve_config.py` / `resolve_customization.py` | Traced exactly which config layer `context.py` actually reads (`_bmad/context.yaml`'s flat-YAML chain, not the nested-TOML resolver, which is non-functional for this project's config shape) — this is how `context_placement: bmad` ended up in the right file |

## What was already protecting this project

- **`tests/conftest.py`'s autouse network-blocking fixture (AD-11).** Every test fails loudly on any real network attempt instead of possibly passing by accident — this is why re-running the suite on a fresh clone was trustworthy proof, not a check that could quietly cheat.
- **AD-13 (per-race failure isolation).** Barcelona's future-session fetch failure never took down the other four races' landing. This is exactly why the corrupted VER/ALB data could be *re-derived* by simply re-running `pull_fastf1_data.py` against the existing FastF1 cache — no hand-patching the database, no re-fetching from the network.
- **AD-14 / AD-16 (exactly-one-sanctioned-reconciliation; fail loud, never guess).** The reason `map_constructor_ids` was under review in the first place, and the reason the driver-code fix could be held to the same bar (a decision record + a named error) instead of shipping an ad hoc patch.
- **`_bmad/render/`'s own nested `.gitignore`** (`*` / `!.gitignore`). Meant un-ignoring the parent `_bmad/*` didn't accidentally sweep an ephemeral, session-specific rendered workflow cache into git history.
- **`.bmad-loop/policy.toml`'s self-documented machine-local rationale**, written into the file by `bmad-loop init` itself. Caught before "un-ignore everything" would have leaked per-machine settings (mux backend, TUI sizing) into shared history.
- **`context.py sweep`'s literal path-existence check.** Caught a mistake in my own freshly-drafted bundle entry (a dead path named in prose) before it was ever committed — the tool doesn't care about intent, only whether the path resolves. Cleanest proof-of-work in the whole session.
- **The project's own evidence-first culture** (`AGENTS.md`: "Record durable decisions... Do not rely on chat history when repo context exists"). Existing convention, not something built today — but it's what made holding two new fixes to a written, approved decision-record standard the obvious move rather than an extra step.
- **The Story 1.3 salvage/rebuild discipline.** A clean, known-good `data/raw/fastf1_cache/` already existed, so every re-verification and re-landing in this session ran fully offline against cached data — never touched FastF1's live API.

## Exact steps through the clone

1. `git clone` the real repo (local filesystem) into a scratch directory, HEAD at the driver-code fix commit. `uv sync && uv run pytest -v` → 62/62, confirming the fix held on a clean install.
2. `npx bmad-method@next install --action update --tools claude-code,codex --modules core,bmm,bmb --custom-source https://github.com/bmad-code-org/bmad-loop.git --directory <clone> --yes` — the same command already on record from `bmad-install-upgrade-2026-08-07.md` — to materialize `.claude/skills`, `.agents/skills`, `_bmad/` into the clone.
3. Edited the clone's `.gitignore`: removed the `.claude/`/`.agents/`/`_bmad/*` block; kept `.bmad-loop/policy.toml` ignored after reading its own header (self-documented as machine-local).
4. `git add` the newly-unignored trees; checked `git diff --cached --stat` (842 files, ~93.5k insertions) and grepped for secret-shaped strings before trusting it — found only generic doc mentions. Confirmed `_bmad/render/`'s nested `.gitignore` would still self-exclude. Committed.
5. Cloned the clone again to prove a truly fresh, zero-install checkout now had the full skill set with no manual step. `uv run pytest` → 62/62. `context.py validate` there surfaced the real, pre-existing `docs/index.md` breakage — confirmed identical in the original real repo, so not caused by the tracking change.
6. Invoked the `bmad-project-context` skill (audit intent) against the first clone. Activation → `context.py config --json` (confirmed no `context_placement`, no `kernel.md` — a genuine first run) → asked for and got the placement decision (`bmad`) → traced `context.py`'s config-resolution code to find `_bmad/context.yaml` is where that key actually needs to live → verified by re-running `config --json`.
7. `memlog.py init`, then logged the placement decision and the validate failure as they happened.
8. Spot-checked claims directly against code before writing anything: confirmed `scripts/download_kagglehub_f1_data.py` doesn't exist; confirmed `kaggle_csv.py` reads static CSVs and never imports `kagglehub`.
9. Wrote `docs/kernel.md` + 3 bundle entries per `kernel-contract.md`/`bundle-contract.md`.
10. `context.py index` refused — foreign `docs/index.md`, no generation marker. `git mv` it to `docs/archive/index-pre-rebuild-2026-07.md`.
11. Re-ran `index` → generated. `validate` still failed: `sweep` caught a dead path named in prose inside my own new entry. Fixed the wording, re-ran — clean.
12. Red/green proof: wrote a temporary entry with a fabricated `sources:` path, ran `sweep` → caught; deleted it, ran `sweep` again → clean.
13. Logged the remaining memlog entries. Spawned a fresh-eyes polish subagent (contracts + written files only, no session context) — found 7 real contract violations (2 pruning-test failures, banned edit-story prose, a code-paraphrase, 3 unlinked sources, one factual overstatement). Applied all 7, re-verifying every newly-cited path first.
14. Re-ran `index`/`validate`/`sweep` → clean. `uv run pytest` → 62/62. Logged closing memlog entries. Committed in the clone.
15. Back in the real repo: `git fetch <clone-path> main` + `git merge --ff-only FETCH_HEAD` — never a direct push, which would hit "refusing to update checked out branch," the exact topology failure already on record from an earlier report. Fast-forwarded cleanly.
16. Re-ran `validate`/`sweep`/`pytest` directly in the real repo to confirm the merge carried everything.
17. `git status` in the real repo turned up 5 more untracked files the clone's install snapshot hadn't caught (`.claude/settings.json`, `_bmad/config.toml.bak`, `_bmad/config.yaml`, `_bmad/config.user.yaml`, `_bmad/module-help.csv`). Inspected each; tracked the 4 genuine project-owned ones (`.claude/settings.json` turned out to be the real bmad-loop hook wiring, not personal preference); gitignored `_bmad/*.bak` specifically (a stale pre-`@next`-upgrade snapshot, pure diff noise). Committed.
18. Final proof: cloned the real repo fresh one more time, zero manual steps. `uv sync && uv run pytest` → 62/62. `context.py validate` → `ok: true`, 0 findings. `context.py sweep` → clean.

## Status

All four problems fixed and independently re-verified. `main` is 9 commits ahead of `origin/main`, not pushed. `docs/data_sources.md`, `decisions.md`, `local_setup.md`, `source-tree-analysis.md` remain as stale, unindexed foreign files (flagged in the new kernel's landmines) — archiving them is a recommended follow-up, not done unilaterally.
