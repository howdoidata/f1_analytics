"""Offline tests for `fetch_all_race_result_pages`/`fetch_season_results` (Story 1.7, AD-13).

`jolpica_fetch.py` runs only inside the isolated pandas-<3.0 FastF1
environment -- but `retry_with_backoff` is dependency-free, and both
pagination-exhausting and dump/verify functions accept an injectable
`fastf1_module` seam, so this file loads the module directly by path
(mirrors `test_fastf1_fetch.py`) and exercises them with a fake fastf1/
Ergast-like object and a fake `sleep`, so tests never actually wait or need
the real `fastf1` package installed. No network (AD-11).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


_MODULE_PATH = Path(__file__).parent.parent / "src" / "f1_analytics" / "data_sources" / "jolpica_fetch.py"
_spec = importlib.util.spec_from_file_location("jolpica_fetch", _MODULE_PATH)
jolpica_fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jolpica_fetch)

retry_with_backoff = jolpica_fetch.retry_with_backoff
fetch_all_race_result_pages = jolpica_fetch.fetch_all_race_result_pages
fetch_season_results = jolpica_fetch.fetch_season_results


class ErgastErrorStub(Exception):
    """Stand-in for fastf1.exceptions.ErgastError in tests."""


def _fake_sleep_recorder() -> tuple[list[float], object]:
    calls: list[float] = []

    def sleep(seconds: float) -> None:
        calls.append(seconds)

    return calls, sleep


# --- Fake fastf1/Ergast object graph: `fastf1_module.Cache.enable_cache()`,
# `fastf1_module.exceptions.ErgastError`, and
# `fastf1_module.ergast.Ergast().get_race_results(season=, limit=)` returning
# a response exposing `.content`/`.description`/`.total_results`/
# `.get_next_result_page()` -- mirrors the real `fastf1.ergast.Ergast` /
# `ErgastMultiResponse` surface confirmed live against FastF1 3.8.3.


class _FakeCache:
    def __init__(self) -> None:
        self.enable_calls: list[str] = []

    def enable_cache(self, path: str) -> None:
        self.enable_calls.append(path)


class _FakeExceptions:
    ErgastError = ErgastErrorStub


class _FakeResponse:
    def __init__(self, content: list[pd.DataFrame], description: pd.DataFrame, total_results: int, next_pages=None):
        self.content = content
        self.description = description
        self.total_results = total_results
        self._next_pages = list(next_pages or [])

    def get_next_result_page(self) -> "_FakeResponse":
        if not self._next_pages:
            raise ValueError("No more data after this response.")
        return self._next_pages.pop(0)


def _description(rows: list[tuple[int, int, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["season", "round", "raceName"])


def _content(driver_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"driverId": driver_ids, "points": [25] * len(driver_ids)})


class _FakeErgastClient:
    def __init__(self, first_page_factory, *, fail_times: int = 0):
        self._first_page_factory = first_page_factory
        self._fail_times = fail_times
        self.calls: list[tuple[int, int]] = []

    def get_race_results(self, season: int, limit: int) -> _FakeResponse:
        self.calls.append((season, limit))
        if self._fail_times > 0:
            self._fail_times -= 1
            raise ErgastErrorStub("simulated transient Jolpica failure")
        return self._first_page_factory()


class _FakeErgastNamespace:
    def __init__(self, client: _FakeErgastClient) -> None:
        self._client = client

    def Ergast(self) -> _FakeErgastClient:
        return self._client


class _FakeFastF1:
    def __init__(self, client: _FakeErgastClient) -> None:
        self.Cache = _FakeCache()
        self.exceptions = _FakeExceptions()
        self.ergast = _FakeErgastNamespace(client)


# --- fetch_all_race_result_pages(): pagination exhaustion, retries, and the
# hourly-budget guard.


def test_single_complete_page_lands_all_rows_and_matches_total():
    page = _FakeResponse(
        content=[_content(["verstappen", "hamilton"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=2,
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page))
    sleep_calls, sleep = _fake_sleep_recorder()

    frames, landed_row_count, total_expected = fetch_all_race_result_pages(
        fastf1_module, 2026, sleep=sleep
    )

    assert landed_row_count == 2
    assert total_expected == 2
    assert len(frames) == 1
    assert frames[0]["season"].tolist() == [2026, 2026]
    assert frames[0]["round"].tolist() == [1, 1]
    assert frames[0]["race_name"].tolist() == ["Match Grand Prix", "Match Grand Prix"]
    # The loop always throttles once before checking for a next page --
    # even when that check turns out to find none -- since
    # get_next_result_page() is a single call that both checks for and
    # fetches the next page; there's no way to know in advance it will
    # raise. Over-throttling by one no-op sleep is harmless (AD-13 cares
    # about never exceeding the cap, not about shaving off a wasted 0.3s).
    assert len(sleep_calls) == 1


def test_follows_pagination_across_multiple_pages_until_exhausted():
    # Total is 4 but each page only carries 2 rows (simulates Jolpica's
    # server-side 100-row clamp truncating a season across page
    # boundaries) -- the real defect class AD-13 exists to prevent.
    page_2 = _FakeResponse(
        content=[_content(["alonso"])],
        description=_description([(2026, 2, "Second Grand Prix")]),
        total_results=4,
    )
    page_1 = _FakeResponse(
        content=[_content(["verstappen", "hamilton"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=4,
        next_pages=[page_2],
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page_1))
    sleep_calls, sleep = _fake_sleep_recorder()

    frames, landed_row_count, total_expected = fetch_all_race_result_pages(
        fastf1_module, 2026, sleep=sleep
    )

    assert landed_row_count == 3
    assert total_expected == 4
    assert len(frames) == 2
    assert frames[1]["round"].tolist() == [2]
    # Two throttle sleeps: between page 1 and page 2, and once more before
    # the (empty) page-3 attempt that discovers there's no more data (AD-13:
    # stay below the 4 req/sec burst cap).
    assert len(sleep_calls) == 2


def test_retries_a_transient_ergast_error_and_succeeds_before_the_cap():
    page = _FakeResponse(
        content=[_content(["verstappen"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=1,
    )
    client = _FakeErgastClient(lambda: page, fail_times=2)
    fastf1_module = _FakeFastF1(client)
    sleep_calls, sleep = _fake_sleep_recorder()

    frames, landed_row_count, total_expected = fetch_all_race_result_pages(
        fastf1_module, 2026, sleep=sleep, retry_cap=5
    )

    assert landed_row_count == 1
    assert total_expected == 1
    # Two failed attempts before the third succeeds -> two backoff sleeps
    # (retry_with_backoff), plus the one trailing throttle sleep before the
    # loop discovers (via ValueError) that there is no second page.
    assert len(sleep_calls) == 3


def test_raises_named_runtime_error_when_retry_cap_exhausted_on_persistent_error():
    client = _FakeErgastClient(lambda: pytest.fail("should never be reached"), fail_times=10**6)
    fastf1_module = _FakeFastF1(client)
    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(RuntimeError) as excinfo:
        fetch_all_race_result_pages(fastf1_module, 2026, sleep=sleep, retry_cap=2)

    assert "Retry cap (2) exhausted" in str(excinfo.value)
    assert "season 2026" in str(excinfo.value)
    assert "ErgastErrorStub" in str(excinfo.value)


def test_raises_named_runtime_error_when_hourly_request_budget_is_exhausted_mid_fetch():
    page_2 = _FakeResponse(
        content=[_content(["alonso"])],
        description=_description([(2026, 2, "Second Grand Prix")]),
        total_results=4,
    )
    page_1 = _FakeResponse(
        content=[_content(["verstappen", "hamilton"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=4,
        next_pages=[page_2],
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page_1))
    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(RuntimeError) as excinfo:
        fetch_all_race_result_pages(fastf1_module, 2026, sleep=sleep, hourly_request_cap=1)

    assert "hourly request budget (1)" in str(excinfo.value)
    assert "season 2026" in str(excinfo.value)


def test_hourly_request_budget_counts_every_retry_attempt_not_just_one_per_page():
    # Two transient failures before the first page succeeds -> three real
    # HTTP attempts. A budget of 2 must be exhausted on the third attempt,
    # proving retries are counted individually -- a budget tracker that
    # only incremented once per page-loop iteration (the prior defect)
    # would never trip here at all, since only one page was ever "in
    # progress".
    page = _FakeResponse(
        content=[_content(["verstappen"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=1,
    )
    client = _FakeErgastClient(lambda: page, fail_times=2)
    fastf1_module = _FakeFastF1(client)
    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(RuntimeError) as excinfo:
        fetch_all_race_result_pages(fastf1_module, 2026, sleep=sleep, retry_cap=5, hourly_request_cap=2)

    assert "hourly request budget (2)" in str(excinfo.value)
    # Only the two budgeted attempts actually reached the client; the third
    # was blocked before ever calling get_race_results again.
    assert client.calls == [(2026, 100), (2026, 100)]


def test_a_value_error_from_the_initial_page_call_is_a_real_failure_not_an_empty_season():
    # ValueError as "no more pages" is only a valid signal from
    # get_next_result_page() -- an unrelated ValueError out of the very
    # first get_race_results() call must propagate, never be swallowed
    # into "this season simply has zero rounds".
    def _raise_unrelated_value_error():
        raise ValueError("some unrelated ValueError, not a get_next_result_page() signal")

    client = _FakeErgastClient(_raise_unrelated_value_error)
    fastf1_module = _FakeFastF1(client)
    sleep_calls, sleep = _fake_sleep_recorder()

    with pytest.raises(ValueError, match="some unrelated ValueError"):
        fetch_all_race_result_pages(fastf1_module, 2026, sleep=sleep)


def test_fetch_season_results_fails_when_landed_rows_exceed_the_reported_total(tmp_path: Path):
    # An over-count is just as much a mismatch against the source's own
    # published total as an under-count -- AD-13 requires an exact match,
    # not merely "at least".
    page = _FakeResponse(
        content=[_content(["verstappen", "hamilton", "alonso"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=2,  # fewer than the 3 rows actually landed
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page))
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "IncompleteJolpicaFetch" in result["exception"]
    assert "3" in result["exception"] and "2" in result["exception"]
    assert not output_dir.exists()


def test_fetch_season_results_fails_when_initial_page_raises_an_unrelated_value_error(tmp_path: Path):
    def _raise_unrelated_value_error():
        raise ValueError("boom: not a real 'no more pages' signal")

    client = _FakeErgastClient(_raise_unrelated_value_error)
    fastf1_module = _FakeFastF1(client)
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "boom: not a real 'no more pages' signal" in result["exception"]
    assert not output_dir.exists()


# --- fetch_season_results(): the dump/verify wrapper around
# fetch_all_race_result_pages(), mirroring fetch_race()'s status contract.


def test_fetch_season_results_pass_dumps_csv_and_counts_sidecar(tmp_path: Path):
    page = _FakeResponse(
        content=[_content(["verstappen", "hamilton"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=2,
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page))
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, cache_dir, output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "pass"
    assert result["row_count"] == 2
    assert result["rounds"] == [1]
    assert sorted(path.name for path in output_dir.iterdir()) == ["counts.json", "race_results.csv"]

    landed = pd.read_csv(output_dir / "race_results.csv")
    assert len(landed) == 2
    assert landed["driverId"].tolist() == ["verstappen", "hamilton"]

    counts = json.loads((output_dir / "counts.json").read_text())
    assert counts == {"season": 2026, "row_count": 2, "rounds": [1]}

    assert fastf1_module.Cache.enable_calls == [str(cache_dir)]


def test_fetch_season_results_fails_and_writes_no_files_when_pagination_is_incomplete(tmp_path: Path):
    # total_results (3) exceeds what actually landed (2 rows across all
    # pages) -- a truncated fetch must be a statused failure, never a
    # silently shorter table (AD-13).
    page = _FakeResponse(
        content=[_content(["verstappen", "hamilton"])],
        description=_description([(2026, 1, "Match Grand Prix")]),
        total_results=3,
    )
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page))
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "IncompleteJolpicaFetch" in result["exception"]
    assert "2" in result["exception"] and "3" in result["exception"]
    assert not output_dir.exists()


def test_fetch_season_results_reports_empty_status_for_a_zero_row_season(tmp_path: Path):
    page = _FakeResponse(content=[], description=_description([]), total_results=0)
    fastf1_module = _FakeFastF1(_FakeErgastClient(lambda: page))
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "empty"
    assert result["row_count"] == 0
    assert not output_dir.exists()


def test_fetch_season_results_reports_failed_status_for_a_non_retryable_error(tmp_path: Path):
    # A plain (non-Ergast, non-request) exception is not in
    # fetch_all_race_result_pages's retryable tuple, so it propagates on
    # the first attempt -- no real backoff sleep, keeping this test fast
    # (fetch_season_results has no injectable `sleep` seam of its own, so
    # retry-cap-exhaustion paths are exercised instead at the
    # fetch_all_race_result_pages level above, with a fake sleep).
    def _raise():
        raise RuntimeError("boom: non-retryable failure")

    client = _FakeErgastClient(_raise)
    fastf1_module = _FakeFastF1(client)
    output_dir = tmp_path / "2026"

    result = fetch_season_results(2026, tmp_path / "cache", output_dir, fastf1_module=fastf1_module)

    assert result["status"] == "failed"
    assert "boom: non-retryable failure" in result["exception"]
    assert not output_dir.exists()
