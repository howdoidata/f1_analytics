"""Race-window weather from the `weather_forecasts` mart, and the weather weights.

`race_weather` reads the forecast rows of the race-start hour and the next
hour. p is the higher of the two hours' precipitation probability (0-1, from
Open-Meteo's Historical Forecast API for kind `day_before`, its Forecast API
for the live kind `forecast`); the air temperature is the mean over the same
hours.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


DAY_BEFORE = "day_before"
LIVE = "forecast"
WEATHER_CATEGORIES = ("dry", "mixed", "wet")
RACE_WINDOW_HOURS = 2


def race_window(tables: PitStopTables, season: int, round: int, kind: str = DAY_BEFORE) -> pd.DataFrame:
    """The forecast rows of the race-start hour and the next hour, in hour order.

    Raises `ValueError("no day-before forecast for <s> round <r>")` (the kind
    named; `no live forecast` for `LIVE`) when the race has no rows of that
    kind or lacks either hour.
    """
    label = "live" if kind == LIVE else kind.replace("_", "-")
    forecasts = tables.weather_forecasts
    rows = forecasts[(forecasts["season"] == season) & (forecasts["round"] == round) & (forecasts["kind"] == kind)]
    if rows.empty:
        raise ValueError(f"no {label} forecast for {season} round {round}")
    hours = pd.to_datetime(rows["hour_utc"])
    first = pd.to_datetime(rows["race_start_utc"].iloc[0]).floor("h")
    wanted = [first + pd.to_timedelta(h, unit="h") for h in range(RACE_WINDOW_HOURS)]
    window = rows[hours.isin(wanted)].assign(hour_utc=hours).sort_values("hour_utc")
    if len(window) != RACE_WINDOW_HOURS or window[["precipitation_probability", "air_temp"]].isna().any().any():
        raise ValueError(f"no {label} forecast for {season} round {round}")
    return window.reset_index(drop=True)


def race_weather(tables: PitStopTables, season: int, round: int, kind: str = DAY_BEFORE) -> tuple[float, float]:
    """(p, air_temp) over the race-start hour and the next: the highest precipitation probability and the mean °C."""
    window = race_window(tables, season, round, kind)
    p = float(window["precipitation_probability"].astype(float).max())
    return p, float(window["air_temp"].astype(float).mean())


def weather_weights(p: float) -> dict[str, float]:
    """P(dry) = 1 - p, P(mixed) = p/2, P(wet) = p/2."""
    if not 0 <= p <= 1:
        raise ValueError(f"p must be between 0 and 1, got {p}")
    return {"dry": 1 - p, "mixed": p / 2, "wet": p / 2}
