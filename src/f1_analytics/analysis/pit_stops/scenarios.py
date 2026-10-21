"""The scenario grid: a team's race stop total for every weather × start-tyre scenario.

`scenario_grid` runs the count model's `forecast` once per scenario, with one
shared fit, the live forecast's air temperature (`race_weather(..., kind=LIVE)`)
and the race's incident chance. A scenario's probability is its weather weight
(`weather_weights(p)` of the live forecast's p) times its start-tyre weight.

Start-tyre options are the start pairs the team used in the season's earlier
rounds: one option per race with both cars' compounds known (`team_start_compounds`),
the two compounds in `COMPOUNDS` order joined by `|`. Each weather's weights are
the team's shares in the earlier races of that weather (story 4's
`_weather_category`); a weather with no team starts uses the nearest weather
that has some (`WEATHER_FALLBACK`: wet → mixed → dry). Every weather lists every
option seen in any weather, so an option unseen in a weather has weight 0 there.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pandas as pd

from f1_analytics.analysis.pit_stops.history import _weather_category, check_inputs, team_start_compounds
from f1_analytics.analysis.pit_stops.model import COMPOUNDS, WEATHER_FALLBACK, fit_count_model, forecast
from f1_analytics.analysis.pit_stops.weather import LIVE, WEATHER_CATEGORIES, race_weather, weather_weights

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


SCENARIO_COLUMNS = ["weather", "start_tyres", "probability", "mean", "p10", "p90", "preset"]
CARS_PER_TEAM = 2


def _option(compounds: list[str]) -> str:
    return "|".join(sorted(compounds, key=COMPOUNDS.index))


def _option_order(option: str) -> tuple[int, ...]:
    return tuple(COMPOUNDS.index(c) for c in option.split("|"))


def start_tyre_weights(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> dict[str, dict[str, float]]:
    """Per weather (`dry`, `mixed`, `wet`), each start-tyre option's weight; each weather's weights sum to 1.

    Options are in `COMPOUNDS` order of their compounds. Raises
    `ValueError("no start compounds for <team> before <s> round <r>")` when the
    team has no earlier race this season with both cars' compounds known.
    """
    starts = team_start_compounds(tables, constructor_id, circuit_id, season, round)
    cars = tables.car_races
    counts: dict[str, Counter] = {w: Counter() for w in WEATHER_CATEGORIES}
    for (s, r), group in starts.groupby(["season", "round"], sort=True):
        compounds = [str(c).upper() for c in group["start_compound"] if isinstance(c, str)]
        if len(group) != CARS_PER_TEAM or len(compounds) != CARS_PER_TEAM or any(c not in COMPOUNDS for c in compounds):
            continue
        weather = _weather_category(cars[(cars["season"] == s) & (cars["round"] == r)])
        counts[weather][_option(compounds)] += 1
    options = sorted(set().union(*counts.values()), key=_option_order)
    if not options:
        raise ValueError(f"no start compounds for {constructor_id} before {season} round {round}")
    weights = {}
    for weather in WEATHER_CATEGORIES:
        source = next(w for w in (weather, *WEATHER_FALLBACK[weather]) if counts[w])
        total = sum(counts[source].values())
        weights[weather] = {option: counts[source][option] / total for option in options}
    return weights


def scenario_grid(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """One row per weather × start-tyre option, in that order: `SCENARIO_COLUMNS`.

    `mean` is the forecast's total to one decimal (`Forecast.total.mean`),
    `p10` and `p90` its percentiles. Exactly one row is the `preset`: the
    highest probability, ties going to the earlier weather, then the earlier
    option. Raises `ValueError("no live forecast for <s> round <r>")` when the
    `weather_forecasts` mart has no live forecast for the race.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)
    p, air_temp = race_weather(tables, season, round, kind=LIVE)
    tyres = start_tyre_weights(tables, constructor_id, circuit_id, season, round)
    weather_weight = weather_weights(p)
    model = fit_count_model(tables, season, round)
    rows = []
    for weather in WEATHER_CATEGORIES:
        for option, tyre_weight in tyres[weather].items():
            result = forecast(
                tables, constructor_id, circuit_id, season, round,
                start_compounds=option.split("|"), air_temp=air_temp, weather=weather,
                incident=None, model=model,
            )
            rows.append({
                "weather": weather, "start_tyres": option,
                "probability": weather_weight[weather] * tyre_weight,
                "mean": result.total.mean, "p10": result.total.p10, "p90": result.total.p90,
                "preset": False,
            })
    grid = pd.DataFrame(rows, columns=SCENARIO_COLUMNS)
    # idxmax returns the first maximum: rows are in weather, then option order.
    grid.loc[grid["probability"].idxmax(), "preset"] = True
    return grid.astype({"probability": "float64", "mean": "float64", "p10": "float64", "p90": "float64",
                        "preset": "bool"})
