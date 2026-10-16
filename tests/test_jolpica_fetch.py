"""Offline tests for the Jolpica client and the incremental update.

Every response is a recorded `MRData` payload replayed through the client's
injectable getter. No network: `tests/conftest.py` blocks sockets.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from f1_analytics.data_sources import jolpica_fetch as jf
from jolpica_responses import (
    SCHEDULE_2025,
    RecordedGetter,
    _qualifying,
    _race,
    _race_table,
    _result,
    make_update_world,
    recorded_responses,
)


def _client(getter) -> jf.JolpicaClient:
    return jf.JolpicaClient(getter, sleep=lambda s: None, clock=lambda: 0.0)


def _hashes(directory: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.csv"))}


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    return make_update_world(tmp_path / "jolpica")


# --- the incremental update ------------------------------------------------


def test_update_appends_exactly_the_one_new_round_and_a_rerun_appends_nothing(raw_dir: Path):
    getter = RecordedGetter(recorded_responses())
    before = {t: len(jf.read_raw_table(raw_dir, t)) for t in jf.RAW_COLUMNS}

    outcome = jf.update_raw_dir(raw_dir, _client(getter), log=lambda m: None)

    assert outcome["appended"] == [(2025, 3)]
    results = jf.read_raw_table(raw_dir, "results")
    assert len(results) == before["results"] + 3
    new = results[(results["season"] == "2025") & (results["round"] == "3")]
    assert list(new["driverId"]) == ["piastri", "verstappen", "hamilton"]
    assert len(jf.read_raw_table(raw_dir, "qualifying")) == before["qualifying"] + 3
    assert len(jf.read_raw_table(raw_dir, "sprint_results")) == before["sprint_results"]
    # A debut driver and constructor arrive with their round.
    assert "piastri" in set(jf.read_raw_table(raw_dir, "drivers")["driverId"])
    assert "mclaren" in set(jf.read_raw_table(raw_dir, "constructors")["constructorId"])
    # The season's final standings were replaced, not appended.
    standings = jf.read_raw_table(raw_dir, "final_driver_standings")
    assert list(standings[standings["season"] == "2025"]["points"]) == ["69", "68", "25"]
    assert len(standings[standings["season"] == "2024"]) == 3

    snapshot = _hashes(raw_dir)
    rerun = jf.update_raw_dir(raw_dir, _client(getter), log=lambda m: None)
    assert rerun["appended"] == []
    assert _hashes(raw_dir) == snapshot


def test_update_requests_carry_no_auth_header_and_only_url_and_paging_params(raw_dir: Path):
    getter = RecordedGetter(recorded_responses())
    jf.update_raw_dir(raw_dir, _client(getter), log=lambda m: None)
    assert getter.calls
    for url, params in getter.calls:
        assert set(params) == {"limit", "offset"}


def test_requests_getter_sends_no_authorization_header(monkeypatch: pytest.MonkeyPatch):
    import requests

    seen = {}

    class Response:
        status_code = 200
        url = "u"

        def json(self):
            return {"MRData": {}}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    jf.requests_getter(jf.BASE_URL + "2025/races.json", {"limit": 100, "offset": 0})
    assert "headers" not in seen and "auth" not in seen


def test_update_when_the_next_round_has_not_run_writes_nothing(raw_dir: Path):
    getter = RecordedGetter(recorded_responses(round3_run=False))
    snapshot = _hashes(raw_dir)
    messages = []

    outcome = jf.update_raw_dir(raw_dir, _client(getter), log=messages.append)

    assert outcome == {"appended": [], "races_changed": False}
    assert _hashes(raw_dir) == snapshot
    assert messages[-1] == "[jolpica] up to date"


def test_update_season_rollover_with_an_empty_next_schedule_changes_nothing(raw_dir: Path):
    jf.update_raw_dir(raw_dir, _client(RecordedGetter(recorded_responses())), log=lambda m: None)
    snapshot = _hashes(raw_dir)
    getter = RecordedGetter(recorded_responses())

    outcome = jf.update_raw_dir(raw_dir, _client(getter), log=lambda m: None)

    assert outcome == {"appended": [], "races_changed": False}
    assert any(url.endswith("2026/races.json") for url, _ in getter.calls)
    assert _hashes(raw_dir) == snapshot


def test_update_season_rollover_adds_the_published_next_schedule(raw_dir: Path):
    jf.update_raw_dir(raw_dir, _client(RecordedGetter(recorded_responses())), log=lambda m: None)
    next_season = [_race(2026, 1, "Australian Grand Prix", "albert_park", "2026-03-08", "04:00:00Z", "https://example.com/race/2026/1")]

    outcome = jf.update_raw_dir(raw_dir, _client(RecordedGetter(recorded_responses(next_season=next_season))), log=lambda m: None)

    assert outcome == {"appended": [], "races_changed": True}
    races = jf.read_raw_table(raw_dir, "races")
    assert ("2026", "1") in set(zip(races["season"], races["round"]))
    assert len(jf.read_raw_table(raw_dir, "results")[lambda f: f["season"] == "2026"]) == 0


def test_update_refuses_a_round_whose_pages_do_not_add_up(raw_dir: Path):
    responses = recorded_responses()
    responses["2025/3/results"]["MRData"]["total"] = "4"
    snapshot = _hashes(raw_dir)
    with pytest.raises(jf.IncompleteJolpicaFetchError, match="landed 3 row"):
        jf.update_raw_dir(raw_dir, _client(RecordedGetter(responses)), log=lambda m: None)
    assert _hashes(raw_dir) == snapshot


# --- client ---------------------------------------------------------------


def test_get_all_follows_offsets_and_merge_joins_a_race_split_across_pages():
    r1 = SCHEDULE_2025[0]
    page1 = _race_table([_race(2025, *r1, Results=[_result(1, "verstappen", "red_bull", 25, 1)])], total=2, limit=1)
    page2 = _race_table([_race(2025, *r1, Results=[_result(2, "hamilton", "mercedes", 18, 2)])], total=2, limit=1, offset=1)
    pages = {0: page1, 1: page2}
    calls = []

    def getter(url, params):
        calls.append(params["offset"])
        return copy.deepcopy(pages[params["offset"]])

    result_pages = _client(getter).get_all("2025/results")
    jf.verify_total(result_pages, "Results", "2025 results")
    races = jf.merge_race_pages(result_pages, "Results")
    assert calls == [0, 1]
    assert len(races) == 1 and [r["Driver"]["driverId"] for r in races[0]["Results"]] == ["verstappen", "hamilton"]


def test_client_paces_requests_at_the_hourly_cap_interval():
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = jf.JolpicaClient(lambda url, params: {"MRData": {"total": "0"}}, sleep=sleep, clock=lambda: now[0])
    for path in ("a", "b", "c"):
        client.get_page(path)
    assert jf.MIN_REQUEST_INTERVAL_SECONDS == pytest.approx(7.2)
    assert sleeps == [pytest.approx(7.2), pytest.approx(7.2)]
    # 3600 / 7.2 = 500 requests an hour at most, and well under 4 per second.
    assert 3600 / jf.MIN_REQUEST_INTERVAL_SECONDS <= jf.HOURLY_REQUEST_CAP


def test_client_hourly_window_blocks_the_request_past_the_cap():
    now = [0.0]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = jf.JolpicaClient(
        lambda url, params: {"MRData": {"total": "0"}}, sleep=sleep, clock=lambda: now[0], min_interval=0, hourly_cap=2
    )
    for path in ("a", "b", "c"):
        client.get_page(path)
    assert sleeps == [pytest.approx(3600)]


def test_client_retries_transient_errors_with_backoff_then_gives_up():
    sleeps = []
    attempts = []

    def getter(url, params):
        attempts.append(1)
        raise jf.TransientJolpicaError("HTTP 429")

    client = jf.JolpicaClient(getter, sleep=sleeps.append, clock=lambda: 1e9, min_interval=0, retry_cap=2, backoff_base=1)
    with pytest.raises(jf.JolpicaRequestError, match="retry cap"):
        client.get_page("2025/races")
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_page_cache_makes_a_rerun_free(tmp_path: Path):
    calls = []

    def getter(url, params):
        calls.append(url)
        return {"MRData": {"total": "0", "RaceTable": {"Races": []}}}

    jf.JolpicaClient(getter, cache_dir=tmp_path, sleep=lambda s: None).get_page("2025/races")
    second = jf.JolpicaClient(getter, cache_dir=tmp_path, sleep=lambda s: None)
    assert second.get_page("2025/races") == {"total": "0", "RaceTable": {"Races": []}}
    assert len(calls) == 1 and second.request_count == 0


def test_flatteners_produce_the_raw_csv_columns():
    r3 = SCHEDULE_2025[2]
    race = _race(2025, *r3, Results=[_result(1, "piastri", "mclaren", 25, 1)],
                 QualifyingResults=[_qualifying(1, "piastri", "mclaren")])
    results = jf.flatten_results([race])
    assert list(results.columns) == jf.RAW_COLUMNS["results"]
    assert results.iloc[0][["driverId", "constructorName", "fastestLapNumber", "totalRaceTime"]].tolist() == [
        "piastri", "McLaren", "40", "1:23:20.000"]
    assert list(jf.flatten_qualifying([race]).columns) == jf.RAW_COLUMNS["qualifying"]
    assert list(jf.flatten_races([race]).iloc[0][["circuitId", "date"]]) == ["albert_park", "2025-03-16"]
    drivers, constructors = jf.reference_rows([[race]])
    assert set(drivers["driverId"]) == {"piastri"} and set(constructors["constructorId"]) == {"mclaren"}


def test_completed_rounds_needs_results_and_a_past_date(raw_dir: Path):
    from datetime import date

    assert jf.completed_rounds(raw_dir, 2025, today=date(2025, 3, 5)) == [1]
    assert jf.completed_rounds(raw_dir, 2025, today=date(2026, 1, 1)) == [1, 2]
