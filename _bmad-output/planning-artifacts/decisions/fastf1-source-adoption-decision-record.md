# FastF1 Source Adoption Decision Record

Date: 2026-08-06 (local run); evidence timestamp: 2026-08-07T03:55:46.375092+00:00. Reproducibility re-verified 2026-08-07T05:29:36.108812+00:00 by re-running the committed script with the exact documented "Runnable Evidence Command" below — identical five-race matrix, pandas-3 failure, and Kaggle failure were reproduced under Python 3.13.7 (see Reproducibility Verification below).

## Decision

Adopt FastF1 3.8.3 in an explicitly separate, pandas-<3.0 exploratory and future ingestion environment for lap timing, tyre/stint, weather, and Ergast-compatible Jolpica gap-fill. Do not claim pandas-3 compatibility and do not force-install it. Kaggle remains the authority for curated historical results; its attempted re-download failed with a `400 Bad Request` whose root cause is undetermined, and must be retried after an operator investigates directly in the Kaggle console.

The selected fallback is a pandas pin below 3.0 for FastF1 only. This is a source-environment boundary, not a change to the project's pandas-3 baseline.

## Runnable Evidence Command

```bash
uv run --isolated --python 3.13 --with fastf1==3.8.3 --with kagglehub python scripts/spike_fastf1_adoption.py
```

The script enables `data/raw/fastf1_cache/` before every `Session.load`, runs one live pass over the target selectors, then runs one offline-cache replay. It creates only ignored cache/download payloads.

## Observed Environment And Commands

| Item | Evidence |
| --- | --- |
| Host Python | 3.13.7 at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` |
| Compatible exploratory environment | FastF1 3.8.3, pandas 2.3.3, KaggleHub 1.0.2. The original 2026-08-06 evidence capture ran under ambient Python 3.14.6 (the script's internal pandas-3 gate command was `--python python3` at that time). The script was then edited to pin `--python 3.13` explicitly, and re-run on 2026-08-07 to confirm reproducibility: it reported Python 3.13.7 and produced an identical five-race matrix, pandas-3 failure, and Kaggle failure (see Reproducibility Verification below). |
| pandas-3 resolver command | `uv run --isolated --python 3.13 --with pandas==3.0.5 --with fastf1==3.8.3 python -c 'import fastf1, pandas; print(fastf1.__version__, pandas.__version__)'` — verified 2026-08-07 as the exact command the committed script executes. |
| pandas-3 result | Failed, exit 1. Verbatim resolver output:<br>`× No solution found when resolving `--with` dependencies:`<br>`  ╰─▶ Because fastf1>=3.8.3 depends on pandas>=2.1.1,<3.0.0 and you require`<br>`      pandas==3.0.5, we can conclude that your requirements and fastf1>=3.8.3`<br>`      are incompatible.`<br>`      And because you require fastf1==3.8.3, we can conclude that your`<br>`      requirements are unsatisfiable.` |
| Cache result | `data/raw/fastf1_cache/` was populated for the four completed races and replayed offline without a second live pass. |
| Kaggle command | The named script called `kagglehub.dataset_download('patelris/formula-1-complete-dataset-1950-2026', path=<temporary directory>)`. |
| Kaggle result | Local `~/.kaggle/access_token` was non-empty, but download failed: `KaggleApiHTTPError: 400 Client Error: Bad Request for url: https://api.kaggle.com/v1/datasets.DatasetApiService/DownloadDataset`. No token or payload was recorded. |

## Reproducibility Verification

Re-ran the committed `scripts/spike_fastf1_adoption.py` on 2026-08-07T05:29:36Z with the exact "Runnable Evidence Command" above, from the same populated `data/raw/fastf1_cache/`. Result: identical to the original 2026-08-06 capture in every field — five-race lap/stint/compound/weather counts, `FastF1Generated`/`IsAccurate` counts, the pandas-3 resolver failure, the Barcelona future-session failure, and the Kaggle `400 Bad Request` failure all matched exactly. The only prior discrepancy (ambient Python 3.14.6 vs. the documented 3.13 pin) is resolved: the re-run correctly reported Python 3.13.7. This confirms the committed script, as documented, reproduces the recorded evidence.

The re-run's terminal log (not captured in the script's JSON output) also verifies the lap-accuracy warning claim below: FastF1 logged `Failed to perform lap accuracy check - all laps marked as inaccurate` for driver 81 and driver 27 during the Melbourne load, and for driver 41 during the Canada load.

## Five-Race Evidence Matrix

| Target label / public selector | Live session, laps, stints/compounds, weather | FastF1Generated / IsAccurate | Offline replay |
| --- | --- | --- | --- |
| Melbourne / Australian Grand Prix | pass; 1,006 laps; 5 stints; 3 compounds; 148 weather rows | 2 / 835 | pass, same fact presence |
| Miami / Miami Grand Prix | pass; 1,040 laps; 4 stints; 3 compounds; 168 weather rows | 2 / 858 | pass, same fact presence |
| Canada / Canadian Grand Prix | pass; 1,211 laps; 5 stints; 4 compounds; 160 weather rows | 3 / 1,045 | pass, same fact presence |
| Barcelona / Spanish Grand Prix | failed; FastF1 calendar resolves it to 2026-09-13, after the 2026-08-06 run. `Session.load` yielded no loaded laps or weather. | n/a | failed for the same uncached/future session |
| Silverstone / British Grand Prix | pass; 1,113 laps; 6 stints; 3 compounds; 156 weather rows | 2 / 856 | pass, same fact presence |

The raw named failure for Barcelona is `DataNotLoadedError: The data you are trying to access has not been loaded yet. See Session.load`. Its future-date context explains the missing fact classes; it is not treated as zero values or a compatibility pass. FastF1 emitted lap-accuracy warnings for individual drivers in Melbourne and Canada (verified 2026-08-07 in the terminal log — see Reproducibility Verification above); flag counts above are recorded as quality evidence, not completeness claims.

## PRD §9 Decision Fields

### access model

Public FastF1 Python APIs only: `Cache.enable_cache`, `get_session`, and `Session.load`. FastF1 requires no API key. KaggleHub accesses the named public dataset only through the local Kaggle credential.

### cost

FastF1 and the target Kaggle dataset are accessed without a paid API plan. This decision introduces no paid source.

### license/terms risk

FastF1's upstream terms and its underlying timing-data providers can change and event availability can lag or be absent, as the future Barcelona result demonstrates. Use FastF1 only for the source role stated above and preserve source/provenance in later loaders. Kaggle's dataset terms/access remain a separate operator-verified condition.

### authentication

FastF1 has no credential requirement. The existing Kaggle token file was present but the redownload request returned `400 Client Error: Bad Request` — the response body was not captured, so the root cause (credential validity, dataset-terms acceptance, or a malformed request) is undetermined. An operator must investigate directly against the Kaggle console before future Kaggle ingestion can rely on this credential.

### maintenance burden

Maintain a separate FastF1 environment pinned to `pandas<3.0` until a FastF1 release resolves the declared pandas-3 conflict. Retain managed cache-then-parse behavior, run live checks only through the named script, and treat incomplete/future sessions as explicit statused failures rather than retries or fabricated zero facts.

## Follow-up Conditions

- Re-run the named spike once Barcelona's 2026 race has occurred; do not turn its current future-session failure into a retry loop.
- Investigate the Kaggle `400 Bad Request` directly in the Kaggle operator console (credential validity, dataset-terms acceptance, and request format are all untested causes), then rerun the named spike to verify the disposable re-download.
