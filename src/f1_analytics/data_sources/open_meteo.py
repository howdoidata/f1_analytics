"""Open-Meteo client for the race-window weather forecasts the pit-stop analysis uses.

The HTTP call is an injectable `getter(url, params) -> dict`, like the Jolpica
client's, so tests replay recorded responses with no network. Requests carry
no credentials (Open-Meteo needs none).

Endpoint: the Historical Forecast API (`HISTORICAL_FORECAST_URL`). The
Previous Runs API's `_previous_day1` variables have rain probability for only
two of 2026's first 17 rounds (Miami and Canada), so they are not used. The
pit-stop analysis sets p to the higher hourly precipitation probability of the
race-start hour and the next. The Historical Forecast API keeps the latest
forecast for each hour, and these files were fetched after the races: they are
not a true day-before forecast, so the backtest's weather is optimistic.

Live endpoint: the Forecast API (`FORECAST_URL`), with the same query, for an
upcoming race (`fetch_forecast`). Its files are the scenario grid's weather.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable


HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES = ("precipitation", "precipitation_probability", "temperature_2m")
REQUEST_TIMEOUT_SECONDS = 30

Getter = Callable[[str, dict], dict]


class OpenMeteoRequestError(RuntimeError):
    """An Open-Meteo request returned a non-200 response, or a response without the hourly data."""


def requests_getter(url: str, params: dict) -> dict:
    """The production getter: one unauthenticated GET, parsed as JSON."""
    import requests

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise OpenMeteoRequestError(f"HTTP {response.status_code} for {response.url}")
    return response.json()


def _utc(start_utc: datetime) -> datetime:
    if start_utc.tzinfo is None:
        return start_utc.replace(tzinfo=timezone.utc)
    return start_utc.astimezone(timezone.utc)


def _window_params(lat: float, lng: float, start_utc: datetime) -> dict:
    day = _utc(start_utc).date()
    return {
        "latitude": float(lat),
        "longitude": float(lng),
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
        "start_date": day.isoformat(),
        "end_date": (day + timedelta(days=1)).isoformat(),
    }


def day_before_request(lat: float, lng: float, start_utc: datetime) -> tuple[str, dict]:
    """The URL and query of the race-window forecast: hourly, UTC, race date to the day after."""
    return HISTORICAL_FORECAST_URL, _window_params(lat, lng, start_utc)


def forecast_request(lat: float, lng: float, start_utc: datetime) -> tuple[str, dict]:
    """`day_before_request`'s query, for the live Forecast API."""
    return FORECAST_URL, _window_params(lat, lng, start_utc)


class OpenMeteoClient:
    """Fetches the hourly forecast around one race start."""

    def __init__(self, getter: Getter | None = None) -> None:
        self.getter = getter or requests_getter

    def fetch_day_before(self, lat: float, lng: float, start_utc: datetime) -> dict:
        """The Open-Meteo response for the circuit at `lat`, `lng` and the race starting at `start_utc`."""
        return self._fetch(*day_before_request(lat, lng, start_utc))

    def fetch_forecast(self, lat: float, lng: float, start_utc: datetime) -> dict:
        """`fetch_day_before` from the live Forecast API, for an upcoming race."""
        return self._fetch(*forecast_request(lat, lng, start_utc))

    def _fetch(self, url: str, params: dict) -> dict:
        response = self.getter(url, params)
        hourly = response.get("hourly") if isinstance(response, dict) else None
        missing = [name for name in ("time", *HOURLY_VARIABLES) if not isinstance((hourly or {}).get(name), list)]
        if missing:
            raise OpenMeteoRequestError(f"response for {url} has no hourly {', '.join(missing)}")
        return response
