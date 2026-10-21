"""Offline tests for the Open-Meteo client (recorded responses, no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from f1_analytics.data_sources import open_meteo as om


RECORDED = Path(__file__).parent / "fixtures" / "open_meteo" / "day_before" / "2025-01.json"


def recorded_response() -> dict:
    return json.loads(RECORDED.read_text())["response"]


class RecordedGetter:
    """Replays one recorded response; records every call."""

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, params: dict) -> dict:
        self.calls.append((url, dict(params)))
        return self.response


def test_fetch_asks_for_the_hourly_race_window_at_the_circuit():
    getter = RecordedGetter(recorded_response())
    start = datetime(2025, 3, 1, 15, tzinfo=timezone.utc)

    response = om.OpenMeteoClient(getter).fetch_day_before(26.0325, 50.5106, start)

    assert response["hourly"]["time"][15] == "2025-03-01T15:00"
    assert getter.calls == [(om.HISTORICAL_FORECAST_URL, {
        "latitude": 26.0325, "longitude": 50.5106,
        "hourly": "precipitation,precipitation_probability,temperature_2m",
        "timezone": "UTC", "start_date": "2025-03-01", "end_date": "2025-03-02",
    })]


def test_the_live_fetch_asks_the_forecast_api_with_the_same_query():
    getter = RecordedGetter(recorded_response())
    start = datetime(2025, 3, 1, 15, tzinfo=timezone.utc)

    response = om.OpenMeteoClient(getter).fetch_forecast(26.0325, 50.5106, start)

    assert response == recorded_response()
    assert om.FORECAST_URL == "https://api.open-meteo.com/v1/forecast"
    assert getter.calls == [(om.FORECAST_URL, om.day_before_request(26.0325, 50.5106, start)[1])]
    assert om.forecast_request(26.0325, 50.5106, start) == (om.FORECAST_URL, getter.calls[0][1])


def test_a_live_response_without_hourly_data_raises():
    with pytest.raises(om.OpenMeteoRequestError, match=f"^response for {om.FORECAST_URL} has no hourly time"):
        om.OpenMeteoClient(RecordedGetter({})).fetch_forecast(1.0, 2.0, datetime(2025, 3, 1, 15))


def test_the_window_uses_the_utc_race_date():
    # 23:30 in UTC-5 is 04:30 UTC the next day.
    from datetime import timedelta

    start = datetime(2026, 10, 24, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    _, params = om.day_before_request(30.1, -97.6, start)
    assert (params["start_date"], params["end_date"]) == ("2026-10-25", "2026-10-26")


def test_a_response_without_hourly_data_raises():
    with pytest.raises(om.OpenMeteoRequestError, match="no hourly precipitation, precipitation_probability"):
        om.OpenMeteoClient(RecordedGetter({"hourly": {"time": [], "temperature_2m": []}})).fetch_day_before(
            1.0, 2.0, datetime(2025, 3, 1, 15))


@pytest.mark.parametrize("status", [400, 404, 500])
def test_a_non_200_response_raises_with_the_code_and_url(monkeypatch: pytest.MonkeyPatch, status: int):
    import requests

    seen = {}

    class Response:
        status_code = status
        url = "https://historical-forecast-api.open-meteo.com/v1/forecast?latitude=999"

        def json(self):
            return {"error": True, "reason": "Latitude must be in range of -90 to 90°."}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(om.OpenMeteoRequestError) as info:
        om.requests_getter(om.HISTORICAL_FORECAST_URL, {"latitude": 999})
    assert str(info.value) == f"HTTP {status} for {Response.url}"
    # Unauthenticated, with a timeout.
    assert "headers" not in seen and "auth" not in seen and seen["timeout"] == om.REQUEST_TIMEOUT_SECONDS


def test_the_default_getter_is_the_requests_one():
    assert om.OpenMeteoClient().getter is om.requests_getter
