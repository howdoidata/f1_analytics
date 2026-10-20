"""Unit tests for analysis.pit_stops on small synthetic PitStopTables (no DuckDB)."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1_analytics.analysis.data import MissingDatabaseError, PitStopTables, load_pit_stop_tables
from f1_analytics.analysis.pit_stops import (
    UnknownInputError, check_inputs, circuit_stop_history, model_inputs, practice_wear_vs_history,
    race_conditions, team_start_compounds, team_stop_form,
)
from f1_analytics.analysis.pit_stops.history import _weather_category

TEAM, OTHER = "aa", "bb"
CARS = [("a1", TEAM), ("a2", TEAM), ("b1", OTHER), ("b2", OTHER)]
# (season, round, circuit_id); 2021 R4 is scheduled but not yet raced (no results).
RACES = [(2010, 1, "c1"), (2020, 1, "c1"), (2021, 1, "c2"), (2021, 2, "c1"), (2021, 3, "c3"),
         (2021, 4, "c2"), (2022, 1, "c1")]
HELD = [race for race in RACES if race[:2] != (2021, 4)]
# (season, round, driver_id, stop_type): one stop per row.
STOPS = [
    (2010, 1, "a1", "unknown"),
    (2020, 1, "a1", "normal"), (2020, 1, "a2", "normal"), (2020, 1, "b1", "sc_vsc"),
    (2020, 1, "b1", "red_flag"), (2020, 1, "b2", "normal"),
    (2021, 1, "a1", "normal"), (2021, 1, "a1", "red_flag"), (2021, 1, "b1", "normal"),
    (2021, 2, "a1", "normal"), (2021, 2, "a2", "sc_vsc"), (2021, 2, "a2", "normal"),
    (2021, 3, "a1", "normal"), (2021, 3, "a2", "normal"), (2021, 3, "b1", "normal"),
    (2022, 1, "a1", "normal"), (2022, 1, "a2", "normal"),
]


def make_tables(car_races: pd.DataFrame | None = None, practice: pd.DataFrame | None = None) -> PitStopTables:
    team_of = dict(CARS)
    races = pd.DataFrame(
        [(s, r, f"GP {s}-{r}", c) for s, r, c in RACES], columns=["season", "round", "race_name", "circuit_id"])
    results = pd.DataFrame(
        [(s, r, d, t) for s, r, _ in HELD for d, t in CARS],
        columns=["season", "round", "driver_id", "constructor_id"])
    pit_stops = pd.DataFrame(
        [(s, r, d, team_of[d], n, st) for n, (s, r, d, st) in enumerate(STOPS)],
        columns=["season", "round", "driver_id", "constructor_id", "stop", "stop_type"])
    if car_races is None:
        car_races = pd.DataFrame(
            [(s, r, c, d, t, 50, "MEDIUM" if d.endswith("1") else "SOFT", 0, 20.0 + s - 2020 + r, 0.05)
             for s, r, c in HELD if s >= 2020 for d, t in CARS],
            columns=["season", "round", "circuit_id", "driver_id", "constructor_id", "laps_completed",
                     "start_compound", "wet_laps", "air_temp_mean", "deg_s_per_lap"])
    if practice is None:
        practice = pd.DataFrame(
            [(2021, 2, "FP2", "a1", TEAM, 1, "SOFT", 10, 0.1), (2021, 2, "FP2", "a2", TEAM, 1, "SOFT", 30, 0.2),
             (2021, 2, "FP2", "b1", OTHER, 1, "SOFT", 20, 0.4), (2021, 2, "FP2", "b2", OTHER, 1, "SOFT", 5, None),
             (2021, 2, "FP1", "b1", OTHER, 1, "HARD", 10, 0.3),
             (2021, 3, "FP2", "a1", TEAM, 1, "SOFT", 10, 9.9)],
            columns=["season", "round", "session", "driver_id", "constructor_id", "stint", "compound", "laps",
                     "deg_s_per_lap"])
    return PitStopTables(
        races=races, results=results,
        constructors=pd.DataFrame({"constructor_id": [TEAM, OTHER]}),
        circuits=pd.DataFrame({"circuit_id": ["c1", "c2", "c3", "c9"]}),
        pit_stops=pit_stops, car_races=car_races, practice_stints=practice,
    )


TABLES = make_tables()


# --- errors -------------------------------------------------------------------------------------

@pytest.mark.parametrize("args, message", [
    (("nope", "c1", 2021, 2), "unknown constructor_id 'nope'"),
    ((TEAM, "nope", 2021, 2), "unknown circuit_id 'nope'"),
    ((TEAM, "c1", 2030, 1), "no races in season 2030"),
    ((TEAM, "c1", 2021, 9), "no round 9 in season 2021"),
    # Checked in order: constructor, circuit, season, round.
    (("nope", "nope", 2030, 9), "unknown constructor_id 'nope'"),
    ((TEAM, "nope", 2030, 9), "unknown circuit_id 'nope'"),
    ((TEAM, "c1", 2030, 9), "no races in season 2030"),
])
@pytest.mark.parametrize("function", [
    check_inputs, circuit_stop_history, team_stop_form, team_start_compounds, race_conditions, model_inputs,
    practice_wear_vs_history,
])
def test_unknown_inputs_raise_the_epic_messages(function, args, message):
    with pytest.raises(UnknownInputError) as info:
        function(TABLES, *args)
    assert str(info.value) == message
    assert isinstance(info.value, ValueError)


# --- stop history ---------------------------------------------------------------------------------

def test_circuit_history_is_earlier_races_from_2011_with_every_car():
    history = circuit_stop_history(TABLES, TEAM, "c1", 2021, 3)
    assert history.to_dict("records") == [
        {"season": 2020, "round": 1, "cars": 4, "stops": 5, "normal": 3, "sc_vsc": 1, "red_flag": 1, "unknown": 0},
        {"season": 2021, "round": 2, "cars": 4, "stops": 3, "normal": 2, "sc_vsc": 1, "red_flag": 0, "unknown": 0},
    ]


def test_team_form_is_the_teams_earlier_rounds_this_season():
    form = team_stop_form(TABLES, TEAM, "c3", 2021, 3)
    assert form[["season", "round", "cars", "stops", "red_flag"]].values.tolist() == [
        [2021, 1, 2, 2, 1], [2021, 2, 2, 3, 0]]
    inputs = model_inputs(TABLES, TEAM, "c3", 2021, 3)
    assert inputs.team_stops_per_car == 5 / 4
    assert inputs.team_stops_per_car_no_red_flags == 4 / 4
    # c3 has no earlier race.
    assert inputs.circuit_history.empty and math.isnan(inputs.circuit_stops_per_car)
    assert math.isnan(inputs.circuit_stops_per_car_no_red_flags)


def test_model_inputs_rates_pool_stops_over_cars():
    inputs = model_inputs(TABLES, TEAM, "c1", 2021, 3)
    assert inputs.circuit_stops_per_car == 8 / 8
    assert inputs.circuit_stops_per_car_no_red_flags == 7 / 8
    assert inputs.start_compounds.values.tolist() == [
        [2021, 1, "a1", "MEDIUM"], [2021, 1, "a2", "SOFT"], [2021, 2, "a1", "MEDIUM"], [2021, 2, "a2", "SOFT"]]


def test_round_1_has_empty_team_form_and_start_compounds_and_nan_rates():
    inputs = model_inputs(TABLES, TEAM, "c2", 2021, 1)
    assert inputs.team_form.empty and list(inputs.team_form.columns) == list(inputs.circuit_history.columns)
    assert inputs.start_compounds.empty
    assert list(inputs.start_compounds.columns) == ["season", "round", "driver_id", "start_compound"]
    assert math.isnan(inputs.team_stops_per_car) and math.isnan(inputs.team_stops_per_car_no_red_flags)
    # c2's first race is this one, so circuit history is empty too.
    assert inputs.circuit_history.empty and math.isnan(inputs.circuit_stops_per_car)


def test_new_circuit_has_empty_history_and_nan_rate():
    inputs = model_inputs(TABLES, TEAM, "c9", 2021, 3)
    assert inputs.circuit_history.empty
    assert math.isnan(inputs.circuit_stops_per_car)
    assert not inputs.team_form.empty


def _drop_from(tables: PitStopTables, season: int, round_: int) -> PitStopTables:
    """Every row at or after the target dropped (races keeps the target's own schedule row)."""
    def keep(frame, include_target=False):
        later = (frame["season"] > season) | ((frame["season"] == season) & (frame["round"] >= round_))
        if include_target:
            later &= ~((frame["season"] == season) & (frame["round"] == round_))
        return frame[~later]
    return replace(
        tables, races=keep(tables.races, include_target=True), results=keep(tables.results),
        pit_stops=keep(tables.pit_stops), car_races=keep(tables.car_races),
        practice_stints=keep(tables.practice_stints, include_target=True),
    )


def assert_inputs_equal(left, right):
    for name in left.__dataclass_fields__:
        a, b = getattr(left, name), getattr(right, name)
        if isinstance(a, pd.DataFrame):
            pd.testing.assert_frame_equal(a, b, obj=name)
        elif isinstance(a, float) and math.isnan(a):
            assert math.isnan(b), name
        else:
            assert a == b, name


@pytest.mark.parametrize("season, round_, circuit", [(s, r, c) for s, r, c in HELD])
def test_later_rows_do_not_change_the_output(season, round_, circuit):
    trimmed = _drop_from(TABLES, season, round_)
    for team in (TEAM, OTHER):
        args = (team, circuit, season, round_)
        assert_inputs_equal(model_inputs(TABLES, *args), model_inputs(trimmed, *args))
        assert_inputs_equal(practice_wear_vs_history(TABLES, *args), practice_wear_vs_history(trimmed, *args))


# --- weather and conditions ---------------------------------------------------------------------

def _cars(wet_and_laps):
    return pd.DataFrame(wet_and_laps, columns=["wet_laps", "laps_completed"])


@pytest.mark.parametrize("rows, expected", [
    ([(0, 50), (0, 50)], "dry"),
    ([(1, 50), (0, 50)], "mixed"),
    ([(49, 50), (0, 50)], "mixed"),
    ([(50, 50), (0, 50)], "wet"),  # exactly half of all laps
    ([(50, 50), (10, 50)], "wet"),
])
def test_weather_category_thresholds(rows, expected):
    assert _weather_category(_cars(rows)) == expected


def test_weather_category_is_none_without_car_rows():
    assert _weather_category(_cars([])) is None


def test_race_conditions_cover_circuit_history_and_earlier_rounds():
    cars = make_tables().car_races
    cars.loc[(cars["season"] == 2021) & (cars["round"] == 1), "wet_laps"] = 25  # 100 of 200 laps: wet
    cars.loc[(cars["season"] == 2020) & (cars["round"] == 1) & (cars["driver_id"] == "a1"), "wet_laps"] = 3
    cars = cars[~((cars["season"] == 2021) & (cars["round"] == 2))]  # no car_races rows: nulls
    conditions = race_conditions(make_tables(car_races=cars), TEAM, "c1", 2021, 3)
    assert conditions[["season", "round", "circuit_id", "weather"]].values.tolist() == [
        [2020, 1, "c1", "mixed"], [2021, 1, "c2", "wet"], [2021, 2, "c1", None]]
    assert conditions["air_temp_mean"].tolist()[:2] == [21.0, 22.0]
    assert math.isnan(conditions["air_temp_mean"].iloc[2])


# --- practice -----------------------------------------------------------------------------------

def test_practice_wear_is_lap_weighted_per_session_next_to_race_history():
    wear = practice_wear_vs_history(TABLES, TEAM, "c1", 2021, 2)
    practice = wear.practice.set_index("session")
    assert list(practice.index) == ["FP1", "FP2"]
    assert practice.loc["FP2", "team_deg_s_per_lap"] == pytest.approx((10 * 0.1 + 30 * 0.2) / 40)
    assert practice.loc["FP2", "field_deg_s_per_lap"] == pytest.approx((10 * 0.1 + 30 * 0.2 + 20 * 0.4) / 60)
    assert practice.loc["FP2", "field_laps"] == 60
    assert math.isnan(practice.loc["FP1", "team_deg_s_per_lap"]) and practice.loc["FP1", "team_laps"] == 0
    assert wear.history.values.tolist() == [[2020, 1, 0.05, 0.05]]


def test_no_practice_gives_an_empty_practice_side_and_keeps_history():
    wear = practice_wear_vs_history(TABLES, TEAM, "c1", 2022, 1)
    assert wear.practice.empty
    assert list(wear.practice.columns) == ["session", "team_deg_s_per_lap", "field_deg_s_per_lap", "team_laps",
                                           "field_laps"]
    assert wear.history[["season", "round"]].values.tolist() == [[2020, 1], [2021, 2]]


# --- loader -------------------------------------------------------------------------------------

def test_load_pit_stop_tables_reads_the_seven_marts(tmp_path: Path):
    db_path = tmp_path / "tiny.duckdb"
    with duckdb.connect(str(db_path)) as con:
        for name, frame in vars(TABLES).items():
            con.register("frame", frame)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
            con.unregister("frame")
    loaded = load_pit_stop_tables(db_path)
    assert {name: len(frame) for name, frame in vars(loaded).items()} == {
        name: len(frame) for name, frame in vars(TABLES).items()}
    with pytest.raises(MissingDatabaseError):
        load_pit_stop_tables(tmp_path / "nope.duckdb")
