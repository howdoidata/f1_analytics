"""Stop history and model inputs for one team at one circuit, as of one round.

Every public function takes `(tables, constructor_id, circuit_id, season, round)`,
checks those inputs and uses only races before `(season, round)`: an earlier
season, or the same season with a lower round. Nothing from the target race or
later reaches the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


# Jolpica pit-stop data starts in 2011, so circuit history does too.
HISTORY_START_SEASON = 2011
STOP_TYPES = ("normal", "sc_vsc", "red_flag", "unknown")
STOP_COLUMNS = ["season", "round", "cars", "stops", *STOP_TYPES]


class UnknownInputError(ValueError):
    """A constructor, circuit, season or round the database does not know."""


def check_inputs(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> None:
    """Raise `UnknownInputError` for the first unknown input: constructor, circuit, season, round."""
    if constructor_id not in set(tables.constructors["constructor_id"]):
        raise UnknownInputError(f"unknown constructor_id '{constructor_id}'")
    if circuit_id not in set(tables.circuits["circuit_id"]):
        raise UnknownInputError(f"unknown circuit_id '{circuit_id}'")
    season_rounds = tables.races.loc[tables.races["season"] == season, "round"]
    if season_rounds.empty:
        raise UnknownInputError(f"no races in season {season}")
    if round not in set(season_rounds):
        raise UnknownInputError(f"no round {round} in season {season}")


def _before(frame: pd.DataFrame, season: int, round: int) -> pd.Series:
    """Rows of `frame` from races before `(season, round)`."""
    return (frame["season"] < season) | ((frame["season"] == season) & (frame["round"] < round))


def _earlier_circuit_races(tables: PitStopTables, circuit_id: str, season: int, round: int) -> pd.DataFrame:
    """season, round of the circuit's races from 2011 that are before the target and have results."""
    races = tables.races
    keep = (races["circuit_id"] == circuit_id) & (races["season"] >= HISTORY_START_SEASON) & _before(races, season, round)
    return _with_results(tables, races.loc[keep, ["season", "round"]])


def _earlier_season_rounds(tables: PitStopTables, season: int, round: int) -> pd.DataFrame:
    """season, round of the season's earlier rounds that have results."""
    races = tables.races
    keep = (races["season"] == season) & (races["round"] < round)
    return _with_results(tables, races.loc[keep, ["season", "round"]])


def _with_results(tables: PitStopTables, keys: pd.DataFrame) -> pd.DataFrame:
    held = tables.results[["season", "round"]].drop_duplicates()
    return (
        keys.merge(held, on=["season", "round"])
        .astype({"season": "int64", "round": "int64"})
        .sort_values(["season", "round"])
        .reset_index(drop=True)
    )


def _stop_counts(keys: pd.DataFrame, results: pd.DataFrame, pit_stops: pd.DataFrame) -> pd.DataFrame:
    """One row per race in `keys`: cars (results rows), stops, and stops per stop_type."""
    cars = results.groupby(["season", "round"]).size().rename("cars").reset_index()
    by_type = (
        pd.crosstab([pit_stops["season"], pit_stops["round"]], pit_stops["stop_type"])
        .reindex(columns=list(STOP_TYPES), fill_value=0).reset_index()
        if not pit_stops.empty
        else pd.DataFrame({c: pd.Series(dtype="int64") for c in ["season", "round", *STOP_TYPES]})
    )
    out = keys.merge(cars, on=["season", "round"], how="left").merge(by_type, on=["season", "round"], how="left")
    out[["cars", *STOP_TYPES]] = out[["cars", *STOP_TYPES]].fillna(0)
    out["stops"] = out[list(STOP_TYPES)].sum(axis=1)
    return out[STOP_COLUMNS].astype({c: "int64" for c in STOP_COLUMNS}).reset_index(drop=True)


def circuit_stop_history(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """One row per earlier race at the circuit from 2011: season, round, cars, stops, stops per stop_type.

    `cars` counts the race's results rows, so cars that never stopped count.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)
    keys = _earlier_circuit_races(tables, circuit_id, season, round)
    return _stop_counts(keys, tables.results, tables.pit_stops)


def team_stop_form(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """The circuit-history columns for the team's own cars in the season's earlier rounds."""
    check_inputs(tables, constructor_id, circuit_id, season, round)
    keys = _earlier_season_rounds(tables, season, round)
    results = tables.results[tables.results["constructor_id"] == constructor_id]
    keys = keys.merge(results[["season", "round"]].drop_duplicates(), on=["season", "round"])
    pit_stops = tables.pit_stops[tables.pit_stops["constructor_id"] == constructor_id]
    return _stop_counts(keys, results, pit_stops)


def team_start_compounds(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """The team's per-car start compounds in the season's earlier rounds: season, round, driver_id, start_compound."""
    check_inputs(tables, constructor_id, circuit_id, season, round)
    cars = tables.car_races
    keep = (cars["constructor_id"] == constructor_id) & (cars["season"] == season) & (cars["round"] < round)
    return (
        cars.loc[keep, ["season", "round", "driver_id", "start_compound"]]
        .astype({"season": "int64", "round": "int64"})
        .sort_values(["season", "round", "driver_id"])
        .reset_index(drop=True)
    )


def _weather_category(car_rows: pd.DataFrame) -> str | None:
    """`wet` when at least half of all cars' laps are wet, `mixed` when some are, `dry` when none are.

    None when the race has no `car_races` rows.
    """
    if car_rows.empty:
        return None
    wet = car_rows["wet_laps"].fillna(0).sum()
    laps = car_rows["laps_completed"].fillna(0).sum()
    if wet <= 0:
        return "dry"
    return "wet" if 2 * wet >= laps else "mixed"


def race_conditions(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> pd.DataFrame:
    """Per earlier race at the circuit (from 2011) and earlier round this season: air_temp_mean, weather.

    `air_temp_mean` is the mean over the race's cars; it and `weather` are null
    for a race with no `car_races` rows.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)
    keys = (
        pd.concat([_earlier_circuit_races(tables, circuit_id, season, round), _earlier_season_rounds(tables, season, round)])
        .drop_duplicates().sort_values(["season", "round"]).reset_index(drop=True)
    )
    races = tables.races[["season", "round", "circuit_id"]]
    keys = keys.merge(races, on=["season", "round"], how="left")
    by_race = dict(tuple(tables.car_races.groupby(["season", "round"])))
    empty = tables.car_races.iloc[0:0]
    rows = []
    for s, r, c in keys.itertuples(index=False):
        cars = by_race.get((s, r), empty)
        rows.append({
            "season": s, "round": r, "circuit_id": c,
            "air_temp_mean": float(cars["air_temp_mean"].mean()) if not cars.empty else np.nan,
            "weather": _weather_category(cars),
        })
    out = pd.DataFrame(rows, columns=["season", "round", "circuit_id", "air_temp_mean", "weather"])
    return out.astype({"season": "int64", "round": "int64", "air_temp_mean": "float64", "weather": "object"})


def _stops_per_car(counts: pd.DataFrame, *, red_flags: bool = True) -> float:
    """Pooled stops per car of a stop-count frame; NaN when it has no cars."""
    cars = counts["cars"].sum()
    if cars == 0:
        return float("nan")
    stops = counts["stops"].sum() - (0 if red_flags else counts["red_flag"].sum())
    return float(stops / cars)


@dataclass(frozen=True)
class ModelInputs:
    """Everything the count model needs, known before the target race."""

    constructor_id: str
    circuit_id: str
    season: int
    round: int
    circuit_history: pd.DataFrame
    team_form: pd.DataFrame
    start_compounds: pd.DataFrame
    race_conditions: pd.DataFrame
    circuit_stops_per_car: float
    team_stops_per_car: float
    circuit_stops_per_car_no_red_flags: float
    team_stops_per_car_no_red_flags: float


def model_inputs(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> ModelInputs:
    """The circuit history, team form, start compounds, past conditions and the pooled stop rates."""
    args = (tables, constructor_id, circuit_id, season, round)
    history = circuit_stop_history(*args)
    form = team_stop_form(*args)
    return ModelInputs(
        constructor_id=constructor_id,
        circuit_id=circuit_id,
        season=season,
        round=round,
        circuit_history=history,
        team_form=form,
        start_compounds=team_start_compounds(*args),
        race_conditions=race_conditions(*args),
        circuit_stops_per_car=_stops_per_car(history),
        team_stops_per_car=_stops_per_car(form),
        circuit_stops_per_car_no_red_flags=_stops_per_car(history, red_flags=False),
        team_stops_per_car_no_red_flags=_stops_per_car(form, red_flags=False),
    )
