"""Pit-stop forecast analysis: stop history, model inputs and practice wear.

Pure functions over the `PitStopTables` that `analysis.data.load_pit_stop_tables`
returns. Each public function takes `(tables, constructor_id, circuit_id, season,
round)`, raises `UnknownInputError` for unknown inputs and uses only races
before `(season, round)`.
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
from f1_analytics.analysis.pit_stops.practice import PracticeWear, practice_wear_vs_history

__all__ = [
    "ModelInputs",
    "PracticeWear",
    "UnknownInputError",
    "check_inputs",
    "circuit_stop_history",
    "model_inputs",
    "practice_wear_vs_history",
    "race_conditions",
    "team_start_compounds",
    "team_stop_form",
]
