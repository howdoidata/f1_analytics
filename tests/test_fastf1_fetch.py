"""Offline tests for `fastf1_fetch.py`: retry/backoff, `fetch_race`, and the #978 workaround.

`fetch_race` takes an injectable `fastf1_module`, so a fake fastf1-like object
exercises its dump/verify logic with no network. The #978 test runs the real
`fastf1.Cache.enable_cache` against a temporary directory, which makes no
request.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from f1_analytics.data_sources import fastf1_fetch
from f1_analytics.data_sources.fastf1_fetch import fetch_race, retry_with_backoff, round_dir_name


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


class _FakeCachedSession:
    def __init__(self) -> None:
        self.auth = None

    def authorization_for(self, url: str) -> str | None:
        import requests

        if self.auth is None:
            return None
        prepared = self.auth(requests.Request("GET", url).prepare())
        return prepared.headers.get("Authorization")


class _FakeCache:
    """Like the real Cache: every enable_cache builds a new cached session."""

    def __init__(self) -> None:
        self.enable_calls: list[str] = []
        self._requests_session_cached: _FakeCachedSession | None = None

    def enable_cache(self, path: str) -> None:
        self.enable_calls.append(path)
        self._requests_session_cached = _FakeCachedSession()


class _FakeSession:
    def __init__(self, laps: Any, weather_data: Any, results: Any, round_number: int = 1) -> None:
        self.laps = laps
        self.weather_data = weather_data
        self.results = results
        self.event = {"RoundNumber": round_number, "EventName": "Australian Grand Prix"}

    def load(self, **kwargs: Any) -> None:
        pass  # The fake session is already "loaded" -- nothing to do.


class _FakeFastF1:
    def __init__(self, session: _FakeSession) -> None:
        self.Cache = _FakeCache()
        self.exceptions = _FakeExceptions()
        self._session = session
        self.get_session_calls: list[tuple] = []
        self.auth_at_get_session: list[str | None] = []

    def get_session(self, season: int, round_number: int, identifier: str) -> _FakeSession:
        self.get_session_calls.append((season, round_number, identifier))
        self.auth_at_get_session.append(
            self.Cache._requests_session_cached.authorization_for("https://livetiming.formula1.com/static/x.json")
        )
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
    output_dir = tmp_path / "01-australian-grand-prix"

    result = fetch_race(2026, 1, cache_dir, output_dir, "tok", fastf1_module=fastf1_module)

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
    assert counts["race_label"] == "01-australian-grand-prix"

    assert fastf1_module.Cache.enable_calls == [str(cache_dir)]
    assert fastf1_module.get_session_calls == [(2026, 1, "R")]
    # The #978 header was on the session before the load ran.
    assert fastf1_module.auth_at_get_session == ["Bearer tok"]


def test_fetch_race_fails_when_weather_is_none_and_writes_no_files(tmp_path: Path):
    session = _FakeSession(laps=_fake_laps(), weather_data=None, results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Melbourne"

    result = fetch_race(2026, 1, tmp_path / "cache", output_dir, "tok", fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "MissingWeatherData" in result["exception"]
    assert not output_dir.exists()


def test_fetch_race_fails_when_weather_is_an_empty_dataframe_and_writes_no_files(tmp_path: Path):
    empty_weather = pd.DataFrame(columns=["Time", "AirTemp"])
    session = _FakeSession(laps=_fake_laps(), weather_data=empty_weather, results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Melbourne"

    result = fetch_race(2026, 1, tmp_path / "cache", output_dir, "tok", fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "MissingWeatherData" in result["exception"]
    assert not output_dir.exists()


def test_fetch_race_reports_empty_status_for_a_zero_row_laps_session(tmp_path: Path):
    empty_laps = pd.DataFrame(columns=["Driver", "Team", "LapNumber", "Stint", "Compound"])
    session = _FakeSession(laps=empty_laps, weather_data=_fake_weather(), results=_fake_results())
    fastf1_module = _FakeFastF1(session)
    output_dir = tmp_path / "Barcelona"

    result = fetch_race(2026, 7, tmp_path / "cache", output_dir, "tok", fastf1_module=fastf1_module)

    assert result["status"] == "empty"
    assert result["lap_count"] == 0
    assert not output_dir.exists()


def test_fetch_race_reports_a_load_failure_and_writes_nothing(tmp_path: Path):
    class Broken(_FakeFastF1):
        def get_session(self, season, round_number, identifier):
            raise OtherError("DataNotLoadedError: no data for this session")

    output_dir = tmp_path / "17-singapore-grand-prix"
    result = fetch_race(2026, 17, tmp_path / "cache", output_dir, "tok", fastf1_module=Broken(None))
    assert result["status"] == "failed"
    assert "DataNotLoadedError" in result["exception"]
    assert not output_dir.exists()


def test_the_978_header_is_reapplied_after_every_enable_cache(tmp_path: Path):
    attempts = {"n": 0}
    session = _FakeSession(laps=_fake_laps(), weather_data=_fake_weather(), results=_fake_results())

    class Flaky(_FakeFastF1):
        def get_session(self, season, round_number, identifier):
            attempts["n"] += 1
            result = super().get_session(season, round_number, identifier)
            if attempts["n"] == 1:
                raise RetryableError("rate limited")
            return result

    fake = Flaky(session)
    result = fetch_race(2026, 1, tmp_path / "cache", tmp_path / "01-x", "tok", fastf1_module=fake, sleep=lambda s: None)
    assert result["status"] == "pass"
    assert len(fake.Cache.enable_calls) == 2
    assert fake.auth_at_get_session == ["Bearer tok", "Bearer tok"]


def _authorization(session, url: str) -> str | None:
    import requests

    return session.prepare_request(requests.Request("GET", url)).headers.get("Authorization")


F1_URL = "https://livetiming.formula1.com/static/2026/Index.json"
OTHER_URLS = (
    "https://raw.githubusercontent.com/theOehrly/f1schedule/master/schedule_2026.json",
    "https://api.jolpi.ca/ergast/f1/2026/races.json",
)


def test_978_workaround_sends_the_bearer_token_to_f1_hosts_only(tmp_path: Path):
    import fastf1

    previous = (fastf1.Cache._CACHE_DIR, fastf1.Cache._requests_session_cached)
    try:
        fastf1.Cache.enable_cache(str(tmp_path))
        fastf1_fetch.apply_archive_auth_header(fastf1, "abc.def.ghi")
        session = fastf1.Cache._requests_session_cached
        assert _authorization(session, F1_URL) == "Bearer abc.def.ghi"
        for url in OTHER_URLS:
            assert _authorization(session, url) is None, url
        assert _authorization(session, "https://formula1.com.evil.example/x") is None

        # enable_cache rebuilds the session and drops the auth -- which is why
        # the workaround runs after every enable_cache.
        fastf1.Cache.enable_cache(str(tmp_path))
        assert _authorization(fastf1.Cache._requests_session_cached, F1_URL) is None
        fastf1_fetch.apply_archive_auth_header(fastf1, "abc.def.ghi")
        assert _authorization(fastf1.Cache._requests_session_cached, F1_URL) == "Bearer abc.def.ghi"
    finally:
        session = fastf1.Cache._requests_session_cached
        if session is not None:
            session.close()
        fastf1.Cache._CACHE_DIR, fastf1.Cache._requests_session_cached = previous


def test_978_workaround_names_the_issue_in_its_docstring():
    assert "https://github.com/theOehrly/Fast-F1/issues/978" in fastf1_fetch.apply_archive_auth_header.__doc__


def test_round_dir_name_is_keyed_by_the_jolpica_round():
    assert round_dir_name(17, "Singapore Grand Prix") == "17-singapore-grand-prix"
    assert round_dir_name(16, "Bahrain Grand Prix in Malaysia") == "16-bahrain-grand-prix-in-malaysia"
