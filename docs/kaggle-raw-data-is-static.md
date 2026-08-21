---
type: convention
title: Kaggle main pipeline reads pre-populated static CSVs, not a live download
description: Where the current Kaggle data actually comes from, and why local_setup.md's download instructions are stale
tags: [kaggle, data-sources]
verified: 2026-08-20
sources: [src/f1_analytics/data_sources/kaggle_csv.py, src/f1_analytics/config.py, scripts/spike_fastf1_adoption.py, scripts/build_f1_dataset.py, _bmad-output/planning-artifacts/decisions/fastf1-source-adoption-decision-record.md, _bmad-output/implementation-artifacts/1-3-salvage-the-platform-snapshot-under-the-merge-rules.md]
---
Neither `kaggle_csv.py` nor `build_f1_dataset.py` imports `kagglehub` or touches `~/.kaggle/access_token` — the raw CSVs `kaggle_csv.py` reads from `KAGGLE_F1_RAW_DIR` (`data/raw/f1_complete_dataset/`) must already exist locally, populated by the Story 1.3 salvage restore, before the pipeline runs.

The only code that imports `kagglehub`/checks the Kaggle token is the separate, isolated `scripts/spike_fastf1_adoption.py`; per `fastf1-source-adoption-decision-record.md`, only its live Kaggle re-download call fails (unresolved `400 Bad Request`) — the FastF1 spike itself the script exists to run succeeds.

`docs/archive/local_setup-pre-rebuild-2026-07.md`'s Kaggle-download-script instructions describe the pre-rebuild (V1) pipeline; that script is gone from the current `scripts/` directory.
