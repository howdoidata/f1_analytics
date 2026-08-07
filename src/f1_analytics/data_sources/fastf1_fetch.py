#!/usr/bin/env python3
"""Isolated-env-only FastF1 fetch worker (Story 1.6, AD-13).

This module runs ONLY inside the pandas-<3.0 exploratory environment the
FastF1 source-adoption decision record established -- never inside the
project's own pandas-3 environment:

    uv run --isolated --python 3.13 --with fastf1==3.8.3 python \\
        src/f1_analytics/data_sources/fastf1_fetch.py \\
        --label Melbourne --event "Australian Grand Prix" --season 2026 \\
        --cache-dir data/raw/fastf1_cache --output-dir data/raw/fastf1/Melbourne

Deliberately stdlib + fastf1 + pandas only -- no `f1_analytics`-internal
imports, because the isolated venv this runs in does not have the project
package installed. `fastf1`/`requests` imports are deferred into the
functions that need them so this file stays importable even where fastf1
isn't installed (e.g. accidental collection by the main-env test suite).

For one race: (re)asserts the mandatory FastF1 cache (AD-13) immediately
before every session load, loads laps + weather, retries a
`RateLimitExceededError` or a request failure with bounded exponential
backoff up to a named retry cap, and -- only on a genuine data pass --
dumps `laps.csv` / `weather.csv` plus a `counts.json` sidecar (the
session's own total lap count and driver roster) for the offline-testable
main-env half (`fastf1_loader.py`) to verify completeness against.

Reports its outcome as one JSON document on stdout (fastf1's own logging
goes to stderr, per its `logging.StreamHandler()` default), mirroring
`spike_fastf1_adoption.py`'s evidence-document convention so the
orchestrating `scripts/pull_fastf1_data.py` can parse a subprocess's result
without depending on any file existing.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable


# Rate/retry constants named beside the fetch client (AD-13): bounded
# exponential backoff, then a statused failure -- never a hot retry loop.
RETRY_CAP = 5
BACKOFF_BASE_SECONDS = 1.0
SESSION_IDENTIFIER = "R"  # Race session only -- this story's scope.


def exception_summary(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def retry_with_backoff(
    load_fn: Callable[[], Any],
    *,
    retryable_exceptions: tuple[type[BaseException], ...],
    retry_cap: int = RETRY_CAP,
    base_backoff_seconds: float = BACKOFF_BASE_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    label: str = "",
) -> Any:
    """Call `load_fn()`, retrying only `retryable_exceptions` with bounded
    exponential backoff (AD-13): a hot loop is never acceptable, so retry
    cap exhaustion raises `RuntimeError` naming `label` instead of retrying
    forever. Deliberately stdlib-only and dependency-free -- no `fastf1`/
    `requests` import anywhere in this function -- so it's importable and
    unit-testable in the main pytest env even though this module otherwise
    only runs in the isolated FastF1 environment.
    """
    attempt = 0
    while True:
        try:
            return load_fn()
        except retryable_exceptions as error:
            if attempt >= retry_cap:
                raise RuntimeError(
                    f"Retry cap ({retry_cap}) exhausted for {label}: {exception_summary(error)}"
                ) from error
            sleep(base_backoff_seconds * (2**attempt))
            attempt += 1


def load_session_with_retry(fastf1: Any, cache_dir: Path, season: int, event: str) -> Any:
    """Load one race session, retrying only rate-limit/request failures.

    Bounded exponential backoff up to RETRY_CAP attempts (AD-13), via
    `retry_with_backoff`. Any other exception -- e.g. `DataNotLoadedError`
    for a still-future session like Barcelona's 2026 race -- is not
    retried: it IS the statused failure, never routed around as a bug (per
    the 1.6 spec's Never clause).

    `RateLimitExceededError` is read off the passed-in `fastf1` object
    itself (`fastf1.exceptions.RateLimitExceededError`) rather than via a
    fresh `from fastf1.exceptions import ...` statement, so a fake
    fastf1-like object can be injected here in tests without the real
    package installed -- the real package exposes this attribute too
    (`fastf1.req` imports `fastf1.exceptions` internally), so production
    behavior is unchanged.
    """
    import requests

    retryable = (fastf1.exceptions.RateLimitExceededError, requests.exceptions.RequestException)

    def _load() -> Any:
        # Reassert the mandatory managed cache immediately before every
        # load (AD-13): a second run against an already-cached race must
        # show zero fresh HTTP requests.
        fastf1.Cache.enable_cache(str(cache_dir))
        session = fastf1.get_session(season, event, SESSION_IDENTIFIER)
        session.load(laps=True, telemetry=False, weather=True, messages=False)
        return session

    return retry_with_backoff(_load, retryable_exceptions=retryable, label=event)


def fetch_race(
    label: str,
    event: str,
    season: int,
    cache_dir: Path,
    output_dir: Path,
    *,
    fastf1_module: Any = None,
) -> dict[str, Any]:
    """Fetch one race's laps+weather and dump plain CSVs plus a counts sidecar.

    Returns a JSON-serializable status document; never raises for ordinary
    live-service failures (those become `status: failed` with the exact
    exception named), matching the "statused failure, never a crash" rule.

    `fastf1_module` is an injectable seam: production callers always leave
    it `None` (the real package is imported below), but tests can pass a
    fake fastf1-like object -- a stand-in exposing `.Cache.enable_cache()`,
    `.get_session()` returning a fake session, and `.exceptions.
    RateLimitExceededError` -- to exercise this function's own dump/verify
    logic in the main pytest env, which doesn't have the real `fastf1`
    package installed.
    """
    result: dict[str, Any] = {"race_label": label, "event": event, "season": season}

    fastf1 = fastf1_module
    if fastf1 is None:
        try:
            import fastf1
        except ImportError as error:
            result.update({"status": "preflight_failed", "exception": exception_summary(error)})
            return result

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        result.update({"status": "preflight_failed", "exception": exception_summary(error)})
        return result

    try:
        session = load_session_with_retry(fastf1, cache_dir, season, event)
    except Exception as error:  # Live services raise diverse public failure types.
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    try:
        laps = session.laps
        weather = session.weather_data
        results = session.results
    except Exception as error:
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    lap_count = 0 if laps is None else len(laps)
    if not lap_count:
        # A session that "loaded" without raising but produced zero laps
        # (e.g. a still-future/cancelled session) is not a verified pass.
        result.update({"status": "empty", "lap_count": lap_count})
        return result

    if weather is None or len(weather) == 0:
        # Weather is a required fact class for this story's happy path; a
        # session with laps but no weather rows at all (None, or present-
        # but-empty) is a statused failure, not a race silently landed
        # without it.
        result.update(
            {"status": "failed", "exception": "MissingWeatherData: session.weather_data was None or empty"}
        )
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    laps.to_csv(output_dir / "laps.csv", index=False)
    weather_count = len(weather)
    weather.to_csv(output_dir / "weather.csv", index=False)

    # Independent completeness totals (AD-13): sourced from `session.results`
    # -- loaded by FastF1 from a separate classification/results endpoint,
    # never from `laps` itself -- so the sidecar `verify_completeness()`
    # checks against in the main env can actually catch FastF1-side
    # truncation, not just a CSV round-trip bug. FastF1 adds a synthetic
    # extra lap for some retiring drivers that `results['Laps']` doesn't
    # count, so landed rows are expected to be >= this total, not exactly
    # equal to it (verified empirically against all four cached 2026 races).
    if results is not None and "Laps" in results.columns and "Abbreviation" in results.columns:
        participated = results.loc[results["Laps"] > 0]
        expected_lap_count = int(participated["Laps"].sum())
        expected_drivers = sorted({str(value) for value in participated["Abbreviation"].dropna().unique()})
    else:
        # Degrade to the laps-derived totals rather than failing a race
        # whose laps+weather genuinely landed just because `results` came
        # back unexpectedly shaped.
        expected_lap_count = lap_count
        expected_drivers = (
            sorted({str(value) for value in laps["Driver"].dropna().unique()}) if "Driver" in laps.columns else []
        )

    try:
        round_number = int(session.event["RoundNumber"])
    except Exception:
        round_number = None

    counts = {
        "race_label": label,
        "event": event,
        "season": season,
        "round": round_number,
        "lap_count": expected_lap_count,
        "weather_count": weather_count,
        "drivers": expected_drivers,
    }
    (output_dir / "counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True))

    result.update({"status": "pass", "lap_count": lap_count, "weather_count": weather_count, "round": round_number})
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Short race label, e.g. Melbourne")
    parser.add_argument("--event", required=True, help="FastF1 event selector, e.g. 'Australian Grand Prix'")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True, help="Mandatory FastF1 cache directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Where laps.csv/weather.csv/counts.json land")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = fetch_race(args.label, args.event, args.season, args.cache_dir, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
