"""Rolling-origin backtest of the count model against two simple benchmarks.

For each round the model is fitted once on races before it, and every team in
the race's results is forecast with the round's day-before weather (weights
from p, air temperature from the same race-start hours) and its cars' start
compounds as on the grid (a car with none takes the race's most common one),
and the race's incident chance from what was known before it (`incident_chance`,
once per round). The model and both benchmarks are scored against the team's actual total (all
of its stops, red-flag stops included). Two benchmarks predict 2 x a
stops-per-car rate (all stops): the circuit's history from 2011 and the team's form this season
(the previous season's in round 1), each falling back to the field mean.

The table splits each method's MAE by whether the race had a safety car or red
flag (`incident` from the `race_incidents` mart, 0 for a race missing from it),
and gives the model's hit rate and mean p10-p90 width.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

import numpy as np
import pandas as pd

from f1_analytics.analysis.pit_stops.model import _check_race, _fit, _History, _race_incidents, forecast, incident_chance
from f1_analytics.analysis.pit_stops.weather import race_weather, weather_weights

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


CARS_PER_TEAM = 2
METHODS = ("model", "circuit_history", "season_form")
TABLE_COLUMNS = ["method", "mae", "mae_clean", "mae_incident", "hit_rate", "width", "n"]
ROW_COLUMNS = [
    "season", "round", "circuit_id", "constructor_id", "actual", "incident", "incident_chance",
    "model", "model_p10", "model_p90", "model_hit",
    "circuit_history", "season_form",
]


@dataclass(frozen=True)
class Backtest:
    """`rows`: one per round and team; `table`: one per method (`TABLE_COLUMNS`)."""

    rows: pd.DataFrame
    table: pd.DataFrame


def _start_compounds(tables: PitStopTables, season: int, round: int, drivers: Iterable[str]) -> list[str]:
    cars = tables.car_races[(tables.car_races["season"] == season) & (tables.car_races["round"] == round)]
    known = cars["start_compound"].dropna()
    if known.empty:
        raise ValueError(f"no start compounds for {season} round {round}")
    counts = known.value_counts()
    most_common = sorted(counts[counts == counts.max()].index)[0]
    by_driver = dict(zip(cars["driver_id"], cars["start_compound"]))
    return [by_driver[d] if isinstance(by_driver.get(d), str) else most_common for d in drivers]


def _team_stops(tables: PitStopTables, season: int, round: int, constructor_id: str) -> int:
    """All of the team's stops at the race (every `stop_type`)."""
    stops = tables.pit_stops
    team = stops[(stops["season"] == season) & (stops["round"] == round) & (stops["constructor_id"] == constructor_id)]
    return len(team)


def backtest(tables: PitStopTables, season: int, rounds: Iterable[int]) -> Backtest:
    """Forecast every team of each round from what was known before it, and score the three methods."""
    history = _History(tables)
    incidents = {(s, r): i for s, r, i in _race_incidents(tables).itertuples(index=False)}
    rows = []
    for round_ in rounds:
        _check_race(tables, season, round_)
        p, air_temp = race_weather(tables, season, round_)
        weights = weather_weights(p)
        model = _fit(tables, season, round_, history)
        race = tables.races[(tables.races["season"] == season) & (tables.races["round"] == round_)]
        circuit_id = race["circuit_id"].iloc[0]
        chance = incident_chance(tables, circuit_id, season, round_)
        incident = int(incidents.get((season, round_), 0))
        results = tables.results[(tables.results["season"] == season) & (tables.results["round"] == round_)]
        for constructor_id in sorted(results["constructor_id"].unique()):
            drivers = sorted(results.loc[results["constructor_id"] == constructor_id, "driver_id"])
            result = forecast(
                tables, constructor_id, circuit_id, season, round_,
                start_compounds=_start_compounds(tables, season, round_, drivers),
                air_temp=air_temp, weather=weights, incident=chance, model=model,
            )
            actual = _team_stops(tables, season, round_, constructor_id)
            circuit_rate, team_rate = history.rates(constructor_id, circuit_id, season, round_)
            band = result.total
            rows.append({
                "season": season, "round": round_, "circuit_id": circuit_id, "constructor_id": constructor_id,
                "actual": actual, "incident": incident, "incident_chance": chance, "model": band.raw_mean,
                "model_p10": band.p10, "model_p90": band.p90, "model_hit": bool(band.p10 <= actual <= band.p90),
                "circuit_history": CARS_PER_TEAM * circuit_rate, "season_form": CARS_PER_TEAM * team_rate,
            })
    frame = pd.DataFrame(rows, columns=ROW_COLUMNS)
    return Backtest(rows=frame, table=score(frame))


def score(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per method (`TABLE_COLUMNS`).

    `mae` is over all rows, `mae_clean` / `mae_incident` over the rows of races
    without / with a safety car or red flag (NaN when there are none);
    `hit_rate` (share of actual totals inside p10-p90) and `width` (mean
    p90 - p10) are the model's only (NaN for benchmarks); `n` counts all rows.
    """
    clean = rows["incident"] == 0
    table = []
    for method in METHODS:
        error = (rows[method] - rows["actual"]).abs()
        is_model = method == "model"
        table.append({
            "method": method,
            "mae": float(error.mean()),
            "mae_clean": float(error[clean].mean()),
            "mae_incident": float(error[~clean].mean()),
            "hit_rate": float(rows["model_hit"].mean()) if is_model else np.nan,
            "width": float((rows["model_p90"] - rows["model_p10"]).mean()) if is_model else np.nan,
            "n": len(rows),
        })
    return pd.DataFrame(table, columns=TABLE_COLUMNS)
