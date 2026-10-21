"""Unit tests for the start-tyre weights and the scenario grid on the count model's synthetic world."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from f1_analytics.analysis.pit_stops import (
    SCENARIO_COLUMNS, UnknownInputError, forecast, race_weather, scenario_grid, start_tyre_weights,
)
from f1_analytics.analysis.pit_stops.weather import LIVE
from test_pit_stop_model import ARGS, WORLD, weather_frame

# The world's team aa (a1, a2) in 2025: R1 dry SOFT + HARD, R2 mixed HARD + MEDIUM, R3 dry MEDIUM + SOFT.
OPTIONS = ["SOFT|MEDIUM", "SOFT|HARD", "MEDIUM|HARD"]


def with_live(tables, rain: float, round_: int = 4):
    """The tables plus a live forecast for 2025 `round_` (start 13:00 UTC, `rain` at the start hour)."""
    live = weather_frame([(2025, round_, 13, rain)]).assign(kind=LIVE)
    return replace(tables, weather_forecasts=pd.concat([tables.weather_forecasts, live], ignore_index=True))


def with_compound(tables, round_: int, driver: str, compound):
    cars = tables.car_races.copy()
    cars.loc[(cars["season"] == 2025) & (cars["round"] == round_) & (cars["driver_id"] == driver),
             "start_compound"] = compound
    return replace(tables, car_races=cars)


# --- start-tyre weights ---------------------------------------------------------------------------

def test_weights_are_the_teams_shares_per_weather_with_wet_falling_back_to_mixed():
    weights = start_tyre_weights(WORLD, *ARGS)
    assert list(weights) == ["dry", "mixed", "wet"]
    assert weights == {
        "dry": {"SOFT|MEDIUM": 0.5, "SOFT|HARD": 0.5, "MEDIUM|HARD": 0.0},
        "mixed": {"SOFT|MEDIUM": 0.0, "SOFT|HARD": 0.0, "MEDIUM|HARD": 1.0},
        "wet": {"SOFT|MEDIUM": 0.0, "SOFT|HARD": 0.0, "MEDIUM|HARD": 1.0},
    }
    # Options are in COMPOUNDS order, each pair's compounds too.
    assert all(list(w) == OPTIONS for w in weights.values())


@pytest.mark.parametrize("compound", [None, "UNKNOWN"])
def test_a_race_with_an_unknown_compound_is_skipped_and_weathers_fall_back_to_dry(compound):
    # 2025 R2 (the only mixed race) loses a2's compound: mixed and wet have no starts, so both use dry.
    tables = with_compound(WORLD, 2, "a2", compound)
    weights = start_tyre_weights(tables, *ARGS)
    dry = {"SOFT|MEDIUM": 0.5, "SOFT|HARD": 0.5}
    assert weights == {"dry": dry, "mixed": dry, "wet": dry}


def test_a_repeated_pair_counts_once_per_race():
    # R1 becomes SOFT + MEDIUM like R3: 2 of the 2 dry races.
    tables = with_compound(WORLD, 1, "a2", "MEDIUM")
    assert start_tyre_weights(tables, *ARGS)["dry"] == {"SOFT|MEDIUM": 1.0, "MEDIUM|HARD": 0.0}


def test_a_team_with_no_earlier_starts_raises():
    with pytest.raises(ValueError, match="^no start compounds for aa before 2025 round 1$"):
        start_tyre_weights(WORLD, "aa", "c1", 2025, 1)
    with pytest.raises(ValueError, match="^no start compounds for new_team before 2025 round 4$"):
        start_tyre_weights(WORLD, "new_team", "c1", 2025, 4)


# --- scenario grid --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def grid() -> pd.DataFrame:
    return scenario_grid(with_live(WORLD, 0.4), *ARGS)


def test_grid_columns_rows_and_probabilities(grid):
    assert grid.columns.tolist() == SCENARIO_COLUMNS == [
        "weather", "start_tyres", "probability", "mean", "p10", "p90", "preset"]
    assert grid[["weather", "start_tyres"]].values.tolist() == [[w, o] for w in ("dry", "mixed", "wet") for o in OPTIONS]
    # dry 0.6 × (0.5, 0.5, 0), mixed 0.2 × (0, 0, 1), wet 0.2 × (0, 0, 1).
    assert grid["probability"].tolist() == pytest.approx([0.3, 0.3, 0, 0, 0, 0.2, 0, 0, 0.2])
    assert grid["probability"].sum() == pytest.approx(1, abs=1e-9)
    assert not {"red_flags", "incident", "incident_chance"} & set(grid.columns)


def test_one_preset_and_a_tie_goes_to_the_earlier_option(grid):
    assert grid["preset"].sum() == 1
    assert grid.loc[grid["preset"], ["weather", "start_tyres"]].values.tolist() == [["dry", "SOFT|MEDIUM"]]


def test_a_tie_across_weathers_goes_to_the_earlier_weather():
    grid = scenario_grid(with_live(WORLD, 1.0), *ARGS)
    # mixed and wet MEDIUM|HARD are both 0.5.
    assert grid.loc[grid["preset"], ["weather", "start_tyres", "probability"]].values.tolist() == [
        ["mixed", "MEDIUM|HARD", 0.5]]


def test_p_0_leaves_mixed_and_wet_at_0_and_the_preset_dry():
    grid = scenario_grid(with_live(WORLD, 0.0), *ARGS)
    assert (grid.loc[grid["weather"] != "dry", "probability"] == 0).all()
    assert grid.loc[grid["preset"], "weather"].tolist() == ["dry"]
    assert grid["probability"].sum() == pytest.approx(1, abs=1e-9)


def test_totals_equal_a_direct_forecast_call(grid):
    tables = with_live(WORLD, 0.4)
    _, air_temp = race_weather(tables, 2025, 4, kind=LIVE)
    assert air_temp == 33.5
    for row in grid.itertuples(index=False):
        result = forecast(tables, *ARGS, start_compounds=row.start_tyres.split("|"), air_temp=air_temp,
                          weather=row.weather, incident=None)
        assert (row.mean, row.p10, row.p90) == (result.total.mean, result.total.p10, result.total.p90)


def test_the_grid_needs_a_live_forecast():
    # WORLD has only day-before forecasts.
    with pytest.raises(ValueError, match="^no live forecast for 2025 round 4$"):
        scenario_grid(WORLD, *ARGS)


@pytest.mark.parametrize("args, message", [
    (("nope", "c1", 2025, 4), "unknown constructor_id 'nope'"),
    (("aa", "c1", 2025, 40), "no round 40 in season 2025"),
])
def test_unknown_inputs_raise_story_4s_message(args, message):
    with pytest.raises(UnknownInputError, match=f"^{message}$"):
        scenario_grid(with_live(WORLD, 0.4), *args)
