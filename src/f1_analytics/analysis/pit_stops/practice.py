"""The target round's practice tyre wear next to the circuit's earlier race tyre wear.

A displayed check, not a model input. Practice of the target round happens
before its race, so it may be used; race history uses only earlier races.
`deg_s_per_lap` is passed through unchanged: raw slopes, not fuel-corrected
(the count model does not use tyre wear; see `MODEL_NOTES`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from f1_analytics.analysis.pit_stops.history import HISTORY_START_SEASON, _before, check_inputs

if TYPE_CHECKING:
    from f1_analytics.analysis.data import PitStopTables


PRACTICE_COLUMNS = ["session", "team_deg_s_per_lap", "field_deg_s_per_lap", "team_laps", "field_laps"]
HISTORY_COLUMNS = ["season", "round", "team_deg_s_per_lap", "field_deg_s_per_lap"]


@dataclass(frozen=True)
class PracticeWear:
    """`practice`: one row per session of the target round; `history`: one row per earlier race at the circuit."""

    practice: pd.DataFrame
    history: pd.DataFrame


def _lap_weighted(stints: pd.DataFrame) -> tuple[float, int]:
    """Lap-weighted mean `deg_s_per_lap` of the stints that have one, and their laps."""
    rated = stints[stints["deg_s_per_lap"].notna() & (stints["laps"] > 0)]
    laps = int(rated["laps"].sum())
    if laps == 0:
        return float("nan"), 0
    return float((rated["deg_s_per_lap"] * rated["laps"]).sum() / laps), laps


def practice_wear_vs_history(
    tables: PitStopTables, constructor_id: str, circuit_id: str, season: int, round: int
) -> PracticeWear:
    """Practice wear of the target round (team and field, per session) and earlier race wear at the circuit.

    Practice values are lap-weighted over stints. A race's value is the mean of
    its cars' `deg_s_per_lap` (each already a lap-weighted mean of its stints);
    cars with none are skipped. Either side is empty when it has no rows.
    """
    check_inputs(tables, constructor_id, circuit_id, season, round)

    stints = tables.practice_stints
    stints = stints[(stints["season"] == season) & (stints["round"] == round)]
    rows = []
    for session, group in stints.groupby("session", sort=True):
        team_deg, team_laps = _lap_weighted(group[group["constructor_id"] == constructor_id])
        field_deg, field_laps = _lap_weighted(group)
        rows.append([session, team_deg, field_deg, team_laps, field_laps])
    practice = pd.DataFrame(rows, columns=PRACTICE_COLUMNS).astype(
        {"session": "object", "team_deg_s_per_lap": "float64", "field_deg_s_per_lap": "float64",
         "team_laps": "int64", "field_laps": "int64"}
    )

    cars = tables.car_races
    cars = cars[(cars["circuit_id"] == circuit_id) & (cars["season"] >= HISTORY_START_SEASON) & _before(cars, season, round)]
    rows = []
    for (s, r), group in cars.groupby(["season", "round"], sort=True):
        team = group.loc[group["constructor_id"] == constructor_id, "deg_s_per_lap"].dropna()
        field = group["deg_s_per_lap"].dropna()
        rows.append([s, r, float(team.mean()) if len(team) else np.nan, float(field.mean()) if len(field) else np.nan])
    history = pd.DataFrame(rows, columns=HISTORY_COLUMNS).astype(
        {"season": "int64", "round": "int64", "team_deg_s_per_lap": "float64", "field_deg_s_per_lap": "float64"}
    )
    return PracticeWear(practice=practice, history=history)
