#!/usr/bin/env python3
"""Isolated-env-only Jolpica fetch worker (Story 1.7, AD-2/AD-13).

This module runs ONLY inside an isolated pandas-<3.0 environment (FastF1
pins pandas<3.0) -- never inside the project's own pandas-3 environment
(mirrors `fastf1_fetch.py`):

    uv run --isolated --python 3.13 --with fastf1==3.8.3 python \\
        src/f1_analytics/data_sources/jolpica_fetch.py \\
        --season 2026 --cache-dir data/raw/fastf1_cache \\
        --output-dir data/raw/jolpica/2026

Deliberately stdlib + fastf1 + pandas only -- no `f1_analytics`-internal
imports, because the isolated venv this runs in does not have the project
package installed (same constraint as `fastf1_fetch.py`, including the
duplicated `exception_summary`/`retry_with_backoff` helpers below rather
than a cross-module import). `fastf1`/`requests` imports are deferred into
the functions that need them so this file stays importable even where
fastf1 isn't installed.

Current-season results gap-fill is read through FastF1 3.8.3's
Ergast-compatible client (`fastf1.ergast.Ergast`) -- confirmed live to
expose `get_race_results(season=...)`, and its ids already resolve to the
Ergast/Jolpica id space AD-14 requires (no name-based reconciliation
needed, unlike FastF1's raw telemetry `Driver`/`Team` strings). Jolpica
clamps its own `limit` query parameter to 100 rows server-side regardless
of what is requested (verified empirically against the live API), so a
season's results are routinely spread across multiple pages; this module
exhausts that pagination and verifies the landed row count against the
source's own reported total before writing anything (AD-13's "prevents
the Jolpica pagination class of defect" is exactly this scenario).

Reports its outcome as one JSON document on stdout, mirroring
`fastf1_fetch.py`'s evidence-document convention so the orchestrating
`scripts/build_combined_dataset.py` can parse a subprocess's result
without depending on any file existing.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable


# Rate/retry constants named beside the client (AD-13): bounded exponential
# backoff, then a statused failure -- never a hot retry loop.
RETRY_CAP = 5
BACKOFF_BASE_SECONDS = 1.0
# Jolpica's published ceiling (verified 2026-08-06) is 4 req/sec burst / 500
# req/hour sustained; this throttles every page request comfortably below
# the burst cap and guards a single run against the hourly cap.
MIN_REQUEST_INTERVAL_SECONDS = 0.3
HOURLY_REQUEST_CAP = 500
# Verified empirically: Jolpica clamps `limit` to 100 server-side regardless
# of the value requested, so this is the real per-page size, not a choice.
PAGE_LIMIT = 100


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
    exponential backoff (AD-13). Identical in behavior to
    `fastf1_fetch.retry_with_backoff`; duplicated rather than imported
    because this module must stay importable stand-alone in the isolated
    FastF1 environment (see module docstring).
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


def fetch_all_race_result_pages(
    fastf1_module: Any,
    season: int,
    *,
    page_limit: int = PAGE_LIMIT,
    retry_cap: int = RETRY_CAP,
    base_backoff_seconds: float = BACKOFF_BASE_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    min_request_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
    hourly_request_cap: int = HOURLY_REQUEST_CAP,
) -> tuple[list[Any], int, int | None]:
    """Exhaust Ergast/Jolpica pagination for one season's race results (AD-13).

    Follows `ErgastMultiResponse.get_next_result_page()` -- the library's
    own end-of-pages signal (`ValueError`) -- rather than trusting
    `is_complete`, which (per FastF1 3.8.3's own implementation) only
    describes whether a *single* response page happens to contain the
    entire result set; it is never `True` once paging has actually begun,
    so looping on it would either stop after one page or spin forever. This
    is a documented quirk of the upstream library, not a bug introduced
    here.

    `ValueError` is treated as "no more pages" ONLY for
    `get_next_result_page()` calls (the one API surface that raises it for
    that reason). The initial `get_race_results()` call is never wrapped in
    that handling: a `ValueError` there is a real failure (e.g. a malformed
    query), never mistaken for "season has zero rounds".

    Each page is one live request; `retryable_exceptions` covers
    `fastf1.exceptions.ErgastError` (Jolpica's HTTP-level failures,
    including 429 throttling, surface through this) and
    `requests.exceptions.RequestException` (network-level failures),
    mirroring `fastf1_fetch.py`'s retryable tuple. `ValueError` is
    deliberately excluded from that tuple so it propagates immediately
    (never retried) rather than being treated as a transient failure.

    The hourly request budget is enforced per actual HTTP attempt -- every
    call `retry_with_backoff` makes, including retries after a transient
    `ErgastError`/`RequestException`, counts against `hourly_request_cap`,
    not just one increment per successful page (a flaky connection could
    otherwise burn several real requests per counted "page").

    Returns `(tagged_frames, landed_row_count, total_expected)` --
    `total_expected` is Jolpica's own published total for this query
    (`None` only if the season has zero rounds/results at all), which the
    caller verifies landed data against before writing anything.
    """
    import requests

    retryable = (fastf1_module.exceptions.ErgastError, requests.exceptions.RequestException)
    ergast = fastf1_module.ergast.Ergast()
    request_count = 0

    def _budgeted(inner_load_fn: Callable[[], Any]) -> Callable[[], Any]:
        """Wrap a load function so every actual call attempt -- including
        every retry -- is checked and counted against the hourly budget."""

        def wrapped() -> Any:
            nonlocal request_count
            if request_count >= hourly_request_cap:
                raise RuntimeError(
                    f"Jolpica hourly request budget ({hourly_request_cap}) exhausted mid-fetch "
                    f"for season {season} (AD-13)"
                )
            request_count += 1
            return inner_load_fn()

        return wrapped

    # The initial page: deliberately outside any `except ValueError` --
    # see the "no more pages" note above.
    first_page = retry_with_backoff(
        _budgeted(lambda: ergast.get_race_results(season=season, limit=page_limit)),
        retryable_exceptions=retryable,
        retry_cap=retry_cap,
        base_backoff_seconds=base_backoff_seconds,
        sleep=sleep,
        label=f"jolpica race results season {season} (page 1)",
    )
    pages: list[Any] = [first_page]

    page = first_page
    page_index = 2
    while True:
        sleep(min_request_interval)
        try:
            page = retry_with_backoff(
                _budgeted((lambda current_page: lambda: current_page.get_next_result_page())(page)),
                retryable_exceptions=retryable,
                retry_cap=retry_cap,
                base_backoff_seconds=base_backoff_seconds,
                sleep=sleep,
                label=f"jolpica race results season {season} (page {page_index})",
            )
        except ValueError:
            break
        pages.append(page)
        page_index += 1

    # `pages` always has at least `first_page`; the real "zero rounds"
    # signal is `total_results` itself being `None`, not an empty list.
    total_expected = int(pages[0].total_results) if pages[0].total_results is not None else None

    frames = []
    for page in pages:
        description = page.description
        for i, content_frame in enumerate(page.content):
            row = description.iloc[i]
            tagged = content_frame.copy()
            tagged.insert(0, "season", int(row["season"]))
            tagged.insert(1, "round", int(row["round"]))
            tagged.insert(2, "race_name", row["raceName"])
            frames.append(tagged)

    landed_row_count = sum(len(frame) for frame in frames)
    return frames, landed_row_count, total_expected


def fetch_season_results(
    season: int,
    cache_dir: Path,
    output_dir: Path,
    *,
    fastf1_module: Any = None,
) -> dict[str, Any]:
    """Fetch one season's race results and dump a single CSV plus a counts sidecar.

    Returns a JSON-serializable status document; never raises for ordinary
    live-service failures (those become `status: failed` with the exact
    exception named), matching `fastf1_fetch.fetch_race`'s contract.

    `fastf1_module` is an injectable seam mirroring `fetch_race`'s
    `fastf1_module`: production callers always leave it `None` (the real
    package is imported below), but tests can pass a fake fastf1-like
    object exposing `.Cache.enable_cache()`, `.ergast.Ergast`, and
    `.exceptions.ErgastError` to exercise this function's dump/verify logic
    without the real `fastf1` package installed.
    """
    result: dict[str, Any] = {"season": season}

    fastf1 = fastf1_module
    if fastf1 is None:
        try:
            import fastf1
            import fastf1.ergast  # noqa: F401 -- ensure the submodule is attached
        except ImportError as error:
            result.update({"status": "preflight_failed", "exception": exception_summary(error)})
            return result

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        result.update({"status": "preflight_failed", "exception": exception_summary(error)})
        return result

    try:
        # Reassert the mandatory managed cache immediately before every fetch
        # (AD-13): a second run against already-cached pages must show zero
        # fresh HTTP requests.
        fastf1.Cache.enable_cache(str(cache_dir))
        frames, landed_row_count, total_expected = fetch_all_race_result_pages(fastf1, season)
    except Exception as error:  # Live services raise diverse public failure types.
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    if total_expected is not None and landed_row_count != total_expected:
        # A truncated (or, just as suspect, an over-counted -- e.g. an
        # overlapping-page double-count) fetch is a statused failure, never
        # silently accepted as long as it's "at least" the source's total
        # (AD-13: "verified against the source's own published total").
        result.update(
            {
                "status": "failed",
                "exception": (
                    f"IncompleteJolpicaFetch: landed {landed_row_count} row(s), "
                    f"source reported {total_expected}"
                ),
            }
        )
        return result

    if not landed_row_count:
        # A genuinely rowless season (e.g. queried before any round has
        # results yet) is not a verified data-presence pass.
        result.update({"status": "empty", "row_count": 0})
        return result

    import pandas as pd

    combined = pd.concat(frames, ignore_index=True)
    rounds = sorted(int(value) for value in combined["round"].dropna().unique())
    counts = {"season": season, "row_count": len(combined), "rounds": rounds}
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output_dir / "race_results.csv", index=False)
        (output_dir / "counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True))
    except OSError as error:
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    result.update({"status": "pass", "row_count": len(combined), "rounds": rounds})
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True, help="Mandatory FastF1 cache directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Where race_results.csv/counts.json land")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = fetch_season_results(args.season, args.cache_dir, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in ("pass", "empty") else 1


if __name__ == "__main__":
    raise SystemExit(main())
