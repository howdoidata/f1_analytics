"""FastF1 race-session fetch: laps + weather for one round, dumped to plain CSVs.

Runs in the project environment (fastf1 3.8.3, pandas<3). `fastf1` is
imported lazily inside `fetch_race`, and every function takes an injectable
`fastf1_module`, so tests can pass a fake package and nothing here touches
the network at import time.

For one race: enables the mandatory FastF1 cache, applies the Fast-F1#978
auth-header workaround, loads laps + weather, retries a
`RateLimitExceededError` or a request failure with bounded exponential
backoff, and -- only on a genuine data pass -- dumps `laps.csv` /
`weather.csv` plus a `counts.json` sidecar (the session's own lap total and
driver roster) for the dbt tests in `dbt/tests/` to verify completeness against.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable


RETRY_CAP = 5
BACKOFF_BASE_SECONDS = 1.0
SESSION_IDENTIFIER = "R"  # race session only

FASTF1_978_URL = "https://github.com/theOehrly/Fast-F1/issues/978"


def exception_summary(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def round_dir_name(round_number: int, race_name: str) -> str:
    """`data/raw/fastf1/<season>/<RR>-<slug>/`, keyed by the Jolpica round."""
    slug = re.sub(r"[^a-z0-9]+", "-", race_name.lower()).strip("-")
    return f"{int(round_number):02d}-{slug}"


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
    exponential backoff; cap exhaustion raises `RuntimeError` naming `label`.
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


def _is_f1_host(url: str) -> bool:
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return host == "formula1.com" or host.endswith(".formula1.com")


def apply_archive_auth_header(fastf1: Any, token: str) -> None:
    """Workaround for Fast-F1#978: send the F1TV token to F1's live-timing archive.

    F1's archive now answers only requests carrying `Authorization: Bearer
    <token>`, and FastF1 3.8.3 does not send it (see
    https://github.com/theOehrly/Fast-F1/issues/978). Every
    `Cache.enable_cache()` builds a new `_requests_session_cached`, so this
    must run after each `enable_cache` call. The header is added only to
    requests for `formula1.com` hosts; the same session also calls GitHub,
    Jolpica and others, which must never see the token. Remove this once
    FastF1 ships the fix.
    """
    import requests

    class _F1BearerAuth(requests.auth.AuthBase):
        def __call__(self, request):
            if _is_f1_host(request.url):
                request.headers["Authorization"] = f"Bearer {token}"
            return request

    session = fastf1.Cache._requests_session_cached
    if session is None:
        raise RuntimeError(f"FastF1 cache session is not initialised; call enable_cache first ({FASTF1_978_URL})")
    session.auth = _F1BearerAuth()


def load_session_with_retry(
    fastf1: Any,
    cache_dir: Path,
    season: int,
    round_number: int,
    token: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Load one race session, retrying only rate-limit/request failures.

    Any other exception -- e.g. `DataNotLoadedError` for a session with no
    data -- is not retried: it is the statused failure.
    """
    import requests

    retryable = (fastf1.exceptions.RateLimitExceededError, requests.exceptions.RequestException)

    def _load() -> Any:
        # Reassert the cache before every load: a rerun against an already
        # cached race makes no fresh HTTP requests.
        fastf1.Cache.enable_cache(str(cache_dir))
        apply_archive_auth_header(fastf1, token)
        session = fastf1.get_session(season, round_number, SESSION_IDENTIFIER)
        session.load(laps=True, telemetry=False, weather=True, messages=False)
        return session

    return retry_with_backoff(_load, retryable_exceptions=retryable, label=f"{season} round {round_number}", sleep=sleep)


def fetch_race(
    season: int,
    round_number: int,
    cache_dir: Path,
    output_dir: Path,
    token: str,
    *,
    fastf1_module: Any = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch one race's laps+weather and dump plain CSVs plus a counts sidecar.

    Returns a JSON-serializable status document; ordinary live-service
    failures become `status: failed` with the exception named, never a
    raise. Nothing is written unless the race genuinely passed.
    """
    label = output_dir.name
    result: dict[str, Any] = {"race_label": label, "season": season, "round": round_number}

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
        session = load_session_with_retry(fastf1, cache_dir, season, round_number, token, sleep=sleep)
        laps = session.laps
        weather = session.weather_data
        results = session.results
    except Exception as error:  # Live services raise diverse public failure types.
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    lap_count = 0 if laps is None else len(laps)
    if not lap_count:
        result.update({"status": "empty", "lap_count": lap_count})
        return result

    if weather is None or len(weather) == 0:
        result.update(
            {"status": "failed", "exception": "MissingWeatherData: session.weather_data was None or empty"}
        )
        return result

    # Independent completeness totals from `session.results` (a separate
    # endpoint from the laps). FastF1 adds a synthetic extra lap for some
    # retiring drivers, so landed laps are expected to be >= this total.
    if results is not None and "Laps" in results.columns and "Abbreviation" in results.columns:
        participated = results.loc[results["Laps"] > 0]
        expected_lap_count = int(participated["Laps"].sum())
        expected_drivers = sorted({str(value) for value in participated["Abbreviation"].dropna().unique()})
    else:
        expected_lap_count = lap_count
        expected_drivers = (
            sorted({str(value) for value in laps["Driver"].dropna().unique()}) if "Driver" in laps.columns else []
        )

    try:
        event_name = str(session.event["EventName"])
    except Exception:
        event_name = None

    counts = {
        "race_label": label,
        "event": event_name,
        "season": season,
        "round": round_number,
        "lap_count": expected_lap_count,
        "weather_count": len(weather),
        "drivers": expected_drivers,
    }
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        laps.to_csv(output_dir / "laps.csv", index=False)
        weather.to_csv(output_dir / "weather.csv", index=False)
        (output_dir / "counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True))
    except OSError as error:
        result.update({"status": "failed", "exception": exception_summary(error)})
        return result

    result.update({"status": "pass", "lap_count": lap_count, "weather_count": len(weather)})
    return result
