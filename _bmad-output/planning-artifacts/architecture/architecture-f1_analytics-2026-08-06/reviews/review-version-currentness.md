# Reviewer Lens: Version Currentness & Reality-Check Verification

- **Target:** `ARCHITECTURE-SPINE.md` (architecture-f1_analytics-2026-08-06)
- **Charge:** Verify every committed decision was web-researched or reality-checked rather than asserted from training data: current library/framework versions, that each named technology still exists and fits, and the live defaults of anything the greenfield rebuild leans on.
- **Reviewed:** 2026-08-06
- **Method:** Live web checks (duckdb.org, pandas.pydata.org, docs.fastf1.dev, plotly CHANGELOG, pypi.org/pytest, github.com/astral-sh/uv releases, python.org, jolpica/jolpica-f1 rate_limits.md) plus on-disk reality checks of `/Users/antonio/howdoidata/projects/exchange/` and `data/raw/`.

## Verdict

The spine's "verified 2026-08-06" claims are genuine — every version and limit that carries a verification date checked out against the live web — but the three Stack rows *without* a verification note are exactly where the problems are (uv 0.11.x is already superseded by a breaking 0.12.x), and two AD-9 contract details are asserted beyond what the cited authority packet actually contains.

---

## Findings

### F1 — HIGH — uv "0.11.x" is stale and carries no verification note

Stack table pins `uv (env + lock) 0.11.x`. Live check (github.com/astral-sh/uv/releases, fetched 2026-08-06): current release is **0.12.2 (2026-08-05)**; **0.12.0 shipped 2026-07-28 with explicitly breaking changes** ("correctness, safety, and compatibility" — including `uv init` defaulting to defining a build system, and stricter validation of package archives and lockfiles). This matters doubly for this spine:

- Greenfield: a fresh `uv` install today gets 0.12.x, so the very first `uv init` / lockfile of the rebuild will run under defaults the spine did not check. The `uv init` build-system default change directly touches AD-11's "pyproject.toml with src layout and an editable install."
- The row conspicuously lacks the "verified 2026-08-06" annotation that the four checked rows carry — consistent with it being asserted from memory, not researched.

**Fix:** re-verify and either pin 0.12.x (checking the new `uv init` defaults against the AD-11 layout) or state an explicit reason to hold at 0.11.x.

### F2 — HIGH — AD-9's packet-standing vocabulary cannot express the authority packet's own restatement

AD-9 declares the restatement-row vocabulary as closed: `source_backed | [ASSUMPTION] | explicitly_out_of_scope | waiting_on_input`. But the cited authority packet (`gatherer-handoff-spec-item-set-declaration-2026-07-30.md`, items 12–14) — and gatherer's position packet restatement (`gatherer-q05-position-2026-07-30.md`) — both use a fifth standing, **`current`**, for Handoff level / Portfolio status / Required inputs. A conforming f1 correction packet must restate all 14 items, yet AD-9 as written forbids the only standing the declared set carries for three of them. Gatherer's mechanical check "fails when the declared set and any restatement of it disagree in either direction," so this is not cosmetic: an f1 restatement authored strictly to AD-9 risks mechanical non-conformance — the precise failure class AD-9 exists to prevent.

**Fix:** either add `current` to the vocabulary (with its scope: meta-items whose value is a state, not evidence) or record where the four-value list was actually declared by gatherer, because it is not in the named authority packet.

### F3 — MEDIUM — AD-9 asserts contract elements not traceable to the cited authority packet

Two details in AD-9 are stated as contract but cannot be found anywhere in the channel:

- **"one row per item: item, current value, standing, sourcing packet"** — both gatherer restatements in the channel are three-column tables (Item / Value / Standing). The string "sourcing packet" appears in **zero** packets in the exchange folder (verified by grep across all 135 files). The fourth column appears to be invented or inferred.
- **"requires all six elements (class, frontmatter relation …, an explicit authority statement, authored_at, date, non-contradicting filename)"** — no packet enumerates six correction elements; "authority statement" and "non-contradicting" as terms appear nowhere. The individual elements are plausible syntheses of the 2026-07-30 protocol threads, but the spine presents the enumeration as a definite learned contract with the declaration packet as authority, and that packet contains no such list.

Since AD-9's own rule is that the contract is "learned only through channel packets," each of these must cite the packet that declares it — or be marked `[ASSUMPTION]` per the spine's own convention. The Deferred item "In-repo interchange companion" is the natural place to force per-element sourcing.

### F4 — MEDIUM — Python 3.13 pinned without verification while 3.14 is the current stable

Stack pins Python 3.13 with no verification note or rationale. Live check: **Python 3.14.7 is the current stable (released 2026-08-05); 3.13.15 remains in maintenance**. 3.13 is a defensible pin (ecosystem compatibility for pandas 3.0 / FastF1 under AD-6's compat-spike gate), but the spine records neither that the 3.13-vs-3.14 choice was checked nor why 3.14 (free-threading officially supported, t-strings) was passed over. As written it reads as a training-data default, not a decision.

**Fix:** one line: either "3.13 pinned for <reason>, 3.14 evaluated 2026-08-06" or move to 3.14 after the pandas-3/FastF1 spike confirms support.

### F5 — LOW — pytest "9.x" is accurate but unannotated; FastF1 "mandatory cache" is stricter than the library default

- pytest 9.x is real and current (9.1.1, 2026-06-19; 9.0.0 late 2025) — but like uv and Python, the row lacks the verification note the other four rows carry. Accurate by luck or by unrecorded check; annotate it.
- AD-13 calls FastF1's cache "**mandatory**." The library's actual live semantics (docs.fastf1.dev, fetched 2026-08-06): caching is *enabled by default*, disabling is "highly discouraged" — not mandatory. As an internal architecture rule ("we always run with the cache at `data/raw/fastf1_cache/`") the stricture is fine and arguably good; the wording just shouldn't be read as the library's own requirement. The load-bearing claim — "cached requests do not count towards any rate limits" — is confirmed **verbatim** in the docs, as are the soft-throttle-then-`RateLimitExceededError` semantics.

---

## Claims verified GOOD (no action)

| Claim | Result |
| --- | --- |
| DuckDB 1.5.x / 1.5.5 verified 2026-08-06 | **Confirmed.** 1.5.5 is the latest (published 2026-07-21; 1.5.0 "Variegata" 2026-03-09). |
| pandas 3.0.x / 3.0.5; "behavior changes vs the lost 2.x-era code" | **Confirmed.** 3.0.0 released 2026-01-21; docs currently at 3.0.5. Breaking changes are real and material to a 2.x-era rebuild: default `str` dtype, Copy-on-Write, non-nanosecond datetime default. |
| FastF1 3.8.x / 3.8.3; pandas-3 compat spike gate | **Confirmed.** docs.fastf1.dev is currently versioned 3.8.3. Gating adoption on a pandas-3 spike is prudent given pandas 3.0's breaking changes. |
| Plotly 6.x / 6.9.0 | **Confirmed.** 6.9.0 released 2026-07-09 per plotly.py CHANGELOG. |
| Jolpica limits: 4 req/sec burst, 500 req/hour sustained, HTTP 429 "throttled", limits **will decrease** | **Confirmed verbatim** against jolpica/jolpica-f1 `docs/rate_limits.md` (unauthenticated tier; token access still being rolled out). The spine's "treat as ceilings" posture matches the source's own warning. |
| FastF1 internal rate limiter; cached requests exempt | **Confirmed.** Soft throttle then `RateLimitExceededError`; "Requests that can be served from the cache do not count towards any rate limits." |
| Exchange folder exists at `/Users/antonio/howdoidata/projects/exchange/`; README §1 path is stale | **Confirmed on disk.** Folder exists (135 files); `README.md` §1 states `/Users/antonio/Documents/howdoidata/projects/exchange/` — a path with a `Documents` segment that does not match the real location. AD-9's "raise via the channel, never create a second folder" handling is the right call. |
| The 7 live Jolpica JSONs AD-13 protects | **Confirmed.** Exactly 7 JSONs under `data/raw/jolpica/`: qualifying/2026_11, laps/2026_8, constructorStandings/2026_1 + 2026_7, results/2026_5 + 2026_10, driverStandings/2026_10. (`pitstops/` exists but is empty — consistent with the count.) |
| HS-f1-gatherer **v2**; 14-item Q05 set; three packet classes; total-restatement rule; R6 stands | **Confirmed** in the declaration packet: title "HS-f1-gatherer v2", 14-row closed item set, `packet_classes` = `evidence_delivery | correction | intake`, restatement rule stated and self-applied, "R6 stands … plan nothing against it." |
| Evidence-delivery required properties "by v2 key names" | **Confirmed verbatim** — the 11 keys (`source_scope`, `authorization`, `portfolio_status`, `analysis_status`, `decision_question`, `evidence_refs`, `findings`, `assumptions`, `known_gaps`, `handoff_level`, `producer_run_id`) match `gatherer-q05-verification-response-and-requests-2026-07-29.md` lines 280–282 exactly. |
| Envelope frontmatter fields, `body_sha256`, version-stamped quotes, `to:` governs standing | **Confirmed** against exchange `README.md` §Packet conventions. (Note: the declaration packet itself carries no `body_sha256` — gatherer's omission, not f1's problem; AD-9 only obligates f1's own packets.) |
| Filename suffix pattern `[b..g]` | **Consistent with observed channel usage** (f1 `…2026-07-30b.md`; administrative suffixes run through `g` on 2026-08-01). |

## Scope note

`waiting_on_input` does exist in the channel (`gatherer-f1-protocol-answers-2026-07-30.md` and six other packets), so three of AD-9's four standing values are channel-attested; only the closed-set claim and the missing `current` are at issue (F2). The `source_blocked → waiting_on_input` mapping is an f1-internal rule and needs no external verification.
