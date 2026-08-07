"""Offline tests for `retry_with_backoff` and `fetch_race` (Story 1.6, AD-13).

`fastf1_fetch.py` runs only inside the isolated pandas-<3.0 FastF1
environment -- but `retry_with_backoff` is dependency-free (no
`fastf1`/`requests` import), and `fetch_race` accepts an injectable
`fastf1_module` seam, so this file loads the module directly by path
(rather than `import f1_analytics...`, which would work too, but this
mirrors how `scripts/pull_fastf1_data.py` is loaded in
`test_pull_fastf1_data.py`) and exercises both with a fake `sleep`/fake
fastf1-like object so tests never actually wait or need the real `fastf1`
package. No network, no `fastf1` install required (AD-11).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest


_MODULE_PATH = Path(__file__).parent.parent / "src" / "f1_analytics" / "data_sources" / "fastf1_fetch.py"
_spec = importlib.util.spec_from_file_location("fastf1_fetch", _MODULE_PATH)
fastf1_fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fastf1_fetch)

retry_with_backoff = fastf1_fetch.retry_with_backoff
fetch_race = fastf1_fetch.fetch_race


class RetryableError(Exception):
    """Stand-in for RateLimitExceededError/requests.RequestException in tests."""


class OtherError(Exception):
    """Stand-in for a non-retryable exception (e.g. DataNotLoadedError)."""


def _fake_sleep_recorder() -> tuple[list[float], object]:
    calls: list[float] = []

    def sleep(seconds: float) -> None:
        calls.append(seconds)

    return calls, sleep


def test_succeeds_immediately_when_load_fn_does_not_raise():
    calls = []

    def load_fn():
        calls.append(1)
        return "session"

    sleep_calls, sleep = _fake_sleep_recorder()

    result = retry_with_backoff(load_fn, retryable_exceptions=(RetryableError,), sleep=sleep, label="Test")

    assert result == "session"
    assert len(calls) == 1
    assert sleep_calls == []


def test_retries_a_matching_exception_and_succeeds_before_the_cap():
    attempts = {"count": 0}

    def load_fn():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RetryableError("rate limited")
        return "session"

    sleep_calls, sleep = _fake_sleep_recorder()

    result = retry_with_backoff(
        load_fn, retryable_exceptions=(RetryableError,), retry_cap=5, sleep=sleep, label="Test"
    )

    assert result == "session"
    assert attempts["count"] == 3
    # Two failures before the third (successful) attempt -> two backoff sleeps.
    assert len(sleep_calls) == 2
    # Bounded exponential backoff: base * 2**attempt for attempt 0, 1.
    assert sleep_calls == [1.0 * 2**0, 1.0 * 2**1]


def test_exhausts_retry_cap_on_persistent_matching_exception_and_raises_runtime_error():
    attempts = {"count": 0}

    def load_fn():
        attempts["count"] += 1
        raise RetryableError("always rate limited")

    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(RuntimeError) as excinfo:
        retry_with_backoff(load_fn, retryable_exceptions=(RetryableError,), retry_cap=3, sleep=sleep, label="Test")

    assert "Retry cap (3) exhausted for Test" in str(excinfo.value)
    assert "RetryableError" in str(excinfo.value)
    # attempt 0,1,2,3 all raise -> 4 calls to load_fn total (never a hot loop
    # beyond retry_cap + 1 attempts), and exactly retry_cap backoff sleeps
    # (after attempts 0,1,2; attempt 3 hits the cap and raises instead).
    assert attempts["count"] == 4
    assert len(sleep_calls) == 3


def test_does_not_retry_a_non_matching_exception_and_propagates_on_first_attempt():
    attempts = {"count": 0}

    def load_fn():
        attempts["count"] += 1
        raise OtherError("not a rate limit, e.g. DataNotLoadedError")

    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(OtherError):
        retry_with_backoff(load_fn, retryable_exceptions=(RetryableError,), sleep=sleep, label="Test")

    assert attempts["count"] == 1
    assert sleep_calls == []


# --- fetch_race(): a fake fastf1-like object exercises this function's own
# dump/verify logic (empty-session branch, None/empty-weather branch, the
# CSV + counts.json dump, and the independent-completeness-totals sourcing)
# without needing the real `fastf1` package installed in the main env.


class _FakeExceptions:
    RateLimitExceededError = RetryableError


class _FakeCache:
    def __init__(self) -> None:
        self.enable_calls: list[str] = []

    def enable_cache(self, path: str) -> None:
        self.enable_calls.append(path)


class _FakeSession:
    def __init__(self, laps: Any, weather_data: Any, results: Any, round_number: int = 1) -> None:
        self.laps = laps
        self.weather_data = weather_data
        self.results = results
        self.event = {"RoundNumber": round_number}

    def load(self, **kwargs: Any) -> None:
        pass  # The fake session is already "loaded" -- nothing to do.


class _FakeFastF1:
    def __init__(self, session: _FakeSession) -> None:
        self.Cache = _FakeCache()
        self.exceptions = _FakeExceptions()
        self._session = session
        self.get_session_calls: list[tuple] = []

    def get_session(self, season: int, event: str, identifier: str) -> _FakeSession:
        self.get_session_calls.append((season, event, identifier))
        return self._session


def _fake_laps() -> pd.DataFrame:
    # 4 dumped rows for VER (3) + HAM (1) -- deliberately more than the
    # results-derived expected total below, mirroring FastF1's real
    # behavior of adding a synthetic extra lap for some retiring drivers.
    return pd.DataFrame(
        {
            "Driver": ["VER", "VER", "VER", "HAM"],
            "Team": ["Red Bull", "Red Bull", "Red Bull", "Mercedes"],
            "LapNumber": [1, 2, 3, 1],
            "Stint": [1, 1, 1, 1],
            "Compound": ["SOFT", "SOFT", "SOFT", "MEDIUM"],
        }
    )


def _fake_weather(rows: int = 2) -> pd.DataFrame:
    return pd.DataFrame({"Time": ["0:00:00", "0:05:00"][:rows], "AirTemp": [22.0, 22.5][:rows]})


def _fake_results() -> pd.DataFrame:
    # Independent of `_fake_laps()`: sums to 3, not the 4 rows in laps --
    # this is the whole point of sourcing completeness totals from
    # session.results rather than len(laps)/laps["Driver"].unique().
    return pd.DataFrame({"Abbreviation": ["VER", "HAM"], "Laps": [2.0, 1.0]})


def test_fetch_race_pass_dumps_three_files_with_independent_completeness_totals(tmp_path: Path):
    session = _FakeSession(laps=_fake_laps(), weather_data=_fake_weather(), results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "Melbourne"

    result = fetch_race(
        "Melbourne", "Australian Grand Prix", 2026, cache_dir, output_dir, fastf1_module=fastf1_module
    )

    assert result["status"] == "pass"
    assert result["lap_count"] == 4  # the actual dumped laps.csv row count
    assert result["round"] == 1
    assert sorted(path.name for path in output_dir.iterdir()) == ["counts.json", "laps.csv", "weather.csv"]

    counts = json.loads((output_dir / "counts.json").read_text())
    # Independent totals sourced from session.results, NOT len(laps) (4) or
    # laps["Driver"].unique() -- the sidecar is genuinely independent of
    # the dumped laps.csv, so it can actually catch FastF1-side truncation.
    assert counts["lap_count"] == 3
    assert counts["drivers"] == ["HAM", "VER"]
    assert counts["round"] == 1
    assert counts["weather_count"] == 2

    assert fastf1_module.Cache.enable_calls == [str(cache_dir)]
    assert fastf1_module.get_session_calls == [(2026, "Australian Grand Prix", "R")]


def test_fetch_race_fails_when_weather_is_none_and_writes_no_files(tmp_path: Path):
    session = _FakeSession(laps=_fake_laps(), weather_data=None, results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Melbourne"

    result = fetch_race(
        "Melbourne", "Australian Grand Prix", 2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module
    )

    assert result["status"] == "failed"
    assert "MissingWeatherData" in result["exception"]
    assert not output_dir.exists()


def test_fetch_race_fails_when_weather_is_an_empty_dataframe_and_writes_no_files(tmp_path: Path):
    empty_weather = pd.DataFrame(columns=["Time", "AirTemp"])
    session = _FakeSession(laps=_fake_laps(), weather_data=empty_weather, results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Melbourne"

    result = fetch_race(
        "Melbourne", "Australian Grand Prix", 2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module
    )

    assert result["status"] == "failed"
    assert "MissingWeatherData" in result["exception"]
    assert not output_dir.exists()


def test_fetch_race_reports_empty_status_for_a_zero_row_laps_session(tmp_path: Path):
    empty_laps = pd.DataFrame(columns=["Driver", "Team", "LapNumber", "Stint", "Compound"])
    session = _FakeSession(laps=empty_laps, weather_data=_fake_weather(), results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Barcelona"

    result = fetch_race(
        "Barcelona", "Spanish Grand Prix", 2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module
    )

    assert result["status"] == "empty"
    assert result["lap_count"] == 0
    assert not output_dir.exists()
