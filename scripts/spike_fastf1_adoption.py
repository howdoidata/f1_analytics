#!/usr/bin/env python3
"""Run the bounded, live FastF1 adoption evidence spike.

This script is deliberately a spike, not an ingestion entry point.  It writes
no repository data other than FastF1's ignored managed cache and downloads the
Kaggle dataset only to a temporary directory.  Its stdout is a JSON evidence
document suitable for copying into the source-decision record.

Run from the repository root with the compatible exploratory environment:

    uv run --isolated --python 3.13 --with fastf1==3.8.3 --with kagglehub python scripts/spike_fastf1_adoption.py
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "raw" / "fastf1_cache"
KAGGLE_TOKEN = Path.home() / ".kaggle" / "access_token"
KAGGLE_DATASET = "patelris/formula-1-complete-dataset-1950-2026"
TARGETS = (
    ("Melbourne", "Australian Grand Prix"),
    ("Miami", "Miami Grand Prix"),
    ("Canada", "Canadian Grand Prix"),
    ("Barcelona", "Spanish Grand Prix"),
    ("Silverstone", "British Grand Prix"),
)


def exception_summary(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def pandas_3_compatibility_gate() -> dict[str, Any]:
    """Use the resolver rather than a forced install to test declared support."""
    command = [
        "uv",
        "run",
        "--isolated",
        "--python",
        "3.13",
        "--with",
        "pandas==3.0.5",
        "--with",
        "fastf1==3.8.3",
        "python",
        "-c",
        "import fastf1, pandas; print(fastf1.__version__, pandas.__version__)",
    ]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as error:
        return {"status": "preflight_failed", "command": command, "exception": exception_summary(error)}
    return {
        "status": "pass" if completed.returncode == 0 else "failed",
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def lap_evidence(session: Any) -> dict[str, Any]:
    laps = session.laps
    columns = set(laps.columns)
    compounds = laps["Compound"].dropna() if "Compound" in columns else []
    stints = laps["Stint"].dropna() if "Stint" in columns else []
    return {
        "laps_present": laps is not None,
        "lap_count": len(laps),
        "stint_column_present": "Stint" in columns,
        "stint_count": int(stints.nunique()) if "Stint" in columns else None,
        "compound_column_present": "Compound" in columns,
        "compound_count": int(compounds.nunique()) if "Compound" in columns else None,
        "fastf1_generated_count": int(laps["FastF1Generated"].fillna(False).sum())
        if "FastF1Generated" in columns
        else None,
        "is_accurate_true_count": int(laps["IsAccurate"].fillna(False).sum())
        if "IsAccurate" in columns
        else None,
    }


def weather_evidence(session: Any) -> dict[str, Any]:
    weather = session.weather_data
    return {"weather_present": weather is not None, "weather_count": len(weather) if weather is not None else None}


def load_session(fastf1: Any, event: str) -> tuple[Any | None, dict[str, Any]]:
    # Reassert the mandatory managed cache immediately before every load.
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    try:
        session = fastf1.get_session(2026, event, "R")
        session.load(laps=True, telemetry=False, weather=True, messages=False)
    except Exception as error:  # Live services have diverse public failure types.
        return None, {"status": "failed", "exception": exception_summary(error)}
    result: dict[str, Any] = {
        "status": "pass",
        "session": {
            "event_name": session.event["EventName"],
            "session_name": session.name,
            "session_date": str(session.date),
        },
    }
    try:
        result.update(lap_evidence(session))
    except Exception as error:
        result.update({"status": "failed", "lap_evidence_exception": exception_summary(error)})
    try:
        result.update(weather_evidence(session))
    except Exception as error:
        result.update({"status": "failed", "weather_evidence_exception": exception_summary(error)})
    return session, result


def exploratory_fastf1_leg() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import fastf1
    except ImportError as error:
        failure = {"status": "preflight_failed", "exception": exception_summary(error)}
        return failure, failure

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    live_results: dict[str, Any] = {}
    for label, event in TARGETS:
        _, evidence = load_session(fastf1, event)
        evidence["event_selector"] = event
        live_results[label] = evidence

    replay_results: dict[str, Any] = {}
    fastf1.Cache.offline_mode(True)
    try:
        for label, event in TARGETS:
            _, evidence = load_session(fastf1, event)
            evidence["event_selector"] = event
            replay_results[label] = evidence
    finally:
        fastf1.Cache.offline_mode(False)

    return (
        {
            "status": "pass" if all(item["status"] == "pass" for item in live_results.values()) else "failed",
            "cache_directory": str(CACHE_DIR.relative_to(ROOT)),
            "races": live_results,
        },
        {
            "status": "pass" if all(item["status"] == "pass" for item in replay_results.values()) else "failed",
            "offline_mode": True,
            "races": replay_results,
        },
    )


def kaggle_redownload_leg() -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset": KAGGLE_DATASET,
        "credential_present": KAGGLE_TOKEN.is_file() and KAGGLE_TOKEN.stat().st_size > 0,
        "kagglehub_version": package_version("kagglehub"),
    }
    if not result["credential_present"]:
        result.update({"status": "failed", "exception": "KaggleCredentialMissing: ~/.kaggle/access_token is absent or empty"})
        return result
    try:
        import kagglehub

        with tempfile.TemporaryDirectory(prefix="fastf1-kaggle-spike-") as destination:
            downloaded = kagglehub.dataset_download(KAGGLE_DATASET, path=destination)
            result.update({"status": "pass", "downloaded_path_present": Path(downloaded).exists()})
    except Exception as error:
        result.update({"status": "failed", "exception": exception_summary(error)})
    return result


def main() -> int:
    compatibility = pandas_3_compatibility_gate()
    exploratory, replay = exploratory_fastf1_leg()
    evidence = {
        "spike": "fastf1_adoption",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "fastf1": package_version("fastf1"),
            "pandas": package_version("pandas"),
            "kagglehub": package_version("kagglehub"),
        },
        "pandas_3_compatibility": compatibility,
        "exploratory_fastf1": exploratory,
        "offline_cache_replay": replay,
        "kaggle_redownload": kaggle_redownload_leg(),
    }
    print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
