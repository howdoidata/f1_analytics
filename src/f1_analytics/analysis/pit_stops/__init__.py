"""Pit-stop forecast analysis: stop history, model inputs, practice wear, the count model, its backtest
and the scenario grid.

Pure functions over the `PitStopTables` that `analysis.data.load_pit_stop_tables`
returns. Each history function takes `(tables, constructor_id, circuit_id, season,
round)`, raises `UnknownInputError` for unknown inputs and uses only races
before `(season, round)`; so do the count model's fit and forecast.
"""

from f1_analytics.analysis.pit_stops.history import (
    ModelInputs,
    UnknownInputError,
    check_inputs,
    circuit_stop_history,
    model_inputs,
    race_conditions,
    team_start_compounds,
    team_stop_form,
)
from f1_analytics.analysis.pit_stops.backtest import Backtest, backtest
from f1_analytics.analysis.pit_stops.model import (
    MODEL_NOTES,
    CountModel,
    Forecast,
    StopRange,
    car_out_rate,
    fit_count_model,
    forecast,
    incident_chance,
    team_split_check,
)
from f1_analytics.analysis.pit_stops.practice import PracticeWear, practice_wear_vs_history
from f1_analytics.analysis.pit_stops.scenarios import SCENARIO_COLUMNS, scenario_grid, start_tyre_weights
from f1_analytics.analysis.pit_stops.weather import race_weather, weather_weights

__all__ = [
    "MODEL_NOTES",
    "SCENARIO_COLUMNS",
    "Backtest",
    "CountModel",
    "Forecast",
    "ModelInputs",
    "PracticeWear",
    "StopRange",
    "UnknownInputError",
    "backtest",
    "car_out_rate",
    "check_inputs",
    "circuit_stop_history",
    "fit_count_model",
    "forecast",
    "incident_chance",
    "model_inputs",
    "practice_wear_vs_history",
    "race_conditions",
    "race_weather",
    "scenario_grid",
    "start_tyre_weights",
    "team_start_compounds",
    "team_split_check",
    "team_stop_form",
    "weather_weights",
]
