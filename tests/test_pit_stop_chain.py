"""The pit-stop chain test: from a DuckDB built from the chain fixture world to model inputs.

Story 5 extends it to the count model's forecast and the backtest table; story 6
adds the scenario table. The
chain follows `CHAIN_TEAM` (not Williams) at non-COTA circuits, and checks that
every input comes from races before the target round.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pandas as pd
import pytest

from chain_world import CHAIN_CIRCUIT, CHAIN_EARLIER_SEASON, CHAIN_SEASON, CHAIN_TEAM, make_chain_world
from f1_analytics import cli
from f1_analytics.analysis.data import PitStopTables, load_pit_stop_tables
from f1_analytics.analysis.pit_stops import (
    SCENARIO_COLUMNS, backtest, fit_count_model, forecast, incident_chance, model_inputs, practice_wear_vs_history,
    scenario_grid,
)


@pytest.fixture(scope="module")
def chain_tables(tmp_path_factory) -> PitStopTables:
    root = tmp_path_factory.mktemp("chain")
    raw = make_chain_world(root / "raw")
    db_path = root / "chain.duckdb"
    assert cli.build(["--raw-dir", str(raw), "--db", str(db_path)]) == 0
    return load_pit_stop_tables(db_path)


def test_chain_is_off_williams_and_cota():
    assert CHAIN_TEAM != "williams" and CHAIN_CIRCUIT != "americas"


def test_bahrain_round_1_uses_only_the_earlier_season(chain_tables):
    inputs = model_inputs(chain_tables, CHAIN_TEAM, CHAIN_CIRCUIT, CHAIN_SEASON, 1)
    # 2022 R1: 8 stops over 6 cars (mercedes 3 of them over its 2 cars), 2 under the VSC.
    assert inputs.circuit_history.to_dict("records") == [{
        "season": CHAIN_EARLIER_SEASON, "round": 1, "cars": 6, "stops": 8,
        "normal": 6, "sc_vsc": 2, "red_flag": 0, "unknown": 0}]
    assert inputs.circuit_stops_per_car == pytest.approx(8 / 6)
    assert inputs.circuit_stops_per_car_no_red_flags == pytest.approx(8 / 6)
    assert inputs.team_form.empty and inputs.start_compounds.empty
    assert math.isnan(inputs.team_stops_per_car) and math.isnan(inputs.team_stops_per_car_no_red_flags)
    assert inputs.race_conditions.values.tolist() == [[CHAIN_EARLIER_SEASON, 1, CHAIN_CIRCUIT, 24.5, "dry"]]

    wear = practice_wear_vs_history(chain_tables, CHAIN_TEAM, CHAIN_CIRCUIT, CHAIN_SEASON, 1)
    assert wear.practice["session"].tolist() == ["FP2"]
    fp2 = (6 * 0.0812 + 14 * -0.0124) / 20
    assert wear.practice.loc[0, "team_deg_s_per_lap"] == pytest.approx(fp2)
    assert wear.practice.loc[0, "field_deg_s_per_lap"] == pytest.approx(fp2)
    assert wear.practice.loc[0, ["team_laps", "field_laps"]].tolist() == [40, 120]
    # russell has no race value in 2022 R1, so the team's is hamilton's.
    assert wear.history.values.tolist() == [[CHAIN_EARLIER_SEASON, 1, 0.0412, 0.0412]]


def test_albert_park_round_3_uses_the_seasons_first_two_rounds(chain_tables):
    inputs = model_inputs(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3)
    assert inputs.circuit_history.empty and math.isnan(inputs.circuit_stops_per_car)
    # R1: 1 + 1 stops; R2: hamilton 2 (one under the red flag) + russell 1.
    assert inputs.team_form[["season", "round", "cars", "stops", "red_flag"]].values.tolist() == [
        [CHAIN_SEASON, 1, 2, 2, 0], [CHAIN_SEASON, 2, 2, 3, 1]]
    assert inputs.team_stops_per_car == 1.25
    assert inputs.team_stops_per_car_no_red_flags == 1.0
    assert inputs.start_compounds.values.tolist() == [
        [CHAIN_SEASON, r, d, "MEDIUM"] for r in (1, 2) for d in ("hamilton", "russell")]
    assert inputs.race_conditions.values.tolist() == [
        [CHAIN_SEASON, 1, "bahrain", 24.5, "dry"], [CHAIN_SEASON, 2, "jeddah", 24.5, "dry"]]
    wear = practice_wear_vs_history(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3)
    assert wear.practice.empty and wear.history.empty


def _as_of(tables: PitStopTables, season: int, round_: int) -> PitStopTables:
    """The tables with every row at or after the target dropped (`race_incidents` too).

    `races` keeps the target's own schedule row (it is known in advance and the
    inputs check needs it); `practice_stints` keeps the target's practice,
    which runs before the race.
    """
    def drop(frame: pd.DataFrame, keep_target: bool = False) -> pd.DataFrame:
        later = (frame["season"] > season) | ((frame["season"] == season) & (frame["round"] >= round_))
        if keep_target:
            later &= ~((frame["season"] == season) & (frame["round"] == round_))
        return frame[~later]

    return replace(
        tables, races=drop(tables.races, keep_target=True), results=drop(tables.results),
        pit_stops=drop(tables.pit_stops), car_races=drop(tables.car_races),
        race_incidents=drop(tables.race_incidents),
        practice_stints=drop(tables.practice_stints, keep_target=True),
    )


def _assert_same(left, right) -> None:
    for name in left.__dataclass_fields__:
        a, b = getattr(left, name), getattr(right, name)
        if isinstance(a, pd.DataFrame):
            pd.testing.assert_frame_equal(a, b, obj=name)
        elif isinstance(a, float) and math.isnan(a):
            assert math.isnan(b), name
        else:
            assert a == b, name


def test_every_chain_round_ignores_the_target_race_and_later(chain_tables):
    races = chain_tables.races[["season", "round", "circuit_id"]].itertuples(index=False)
    checked = 0
    for season, round_, circuit in races:
        trimmed = _as_of(chain_tables, season, round_)
        for team in sorted(set(chain_tables.constructors["constructor_id"])):
            args = (team, circuit, season, round_)
            _assert_same(model_inputs(chain_tables, *args), model_inputs(trimmed, *args))
            _assert_same(practice_wear_vs_history(chain_tables, *args), practice_wear_vs_history(trimmed, *args))
            checked += 1
    assert checked == 4 * 3


# --- story 5: count model and backtest ----------------------------------------------------------

CHAIN_DRY_MEDIUM = {"start_compounds": ["MEDIUM", "MEDIUM"], "air_temp": 24.5, "weather": "dry"}


def test_round_3_forecast_reaches_a_total_and_range(chain_tables):
    model = fit_count_model(chain_tables, CHAIN_SEASON, 3)
    # 2022 R1 has no earlier fit race, so the fit is 2023 R1-R2: 12 cars, whose targets count
    # every stop (2023 R2's 4 red-flag stops included). Every car is dry, on MEDIUM, at 24.5 °C.
    assert (model.n_rows, model.n_races) == (12, 2)
    assert model.fit_rows["stops"].sum() == chain_tables.pit_stops.query(
        f"season == {CHAIN_SEASON} and round in (1, 2)").shape[0]
    assert {"air_temp"} <= set(model.dropped) and model.weather_levels == ("dry",)
    assert model.car_out_rate == 0.0

    result = forecast(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3, **CHAIN_DRY_MEDIUM, model=model)
    assert result == forecast(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3, **CHAIN_DRY_MEDIUM)
    band = result.total
    assert 0 <= band.p10 <= band.mean <= band.p90
    # albert_park has no earlier race: the field mean of the fit races (2023 R1-R2, all stops).
    assert result.circuit_rate == pytest.approx(model.field_rate)
    # R1: 1 + 1 stops; R2: hamilton 2 (one under the red flag) + russell 1; all stops over 4 cars.
    assert result.team_rate == 1.25


def test_chain_race_incidents_mart(chain_tables):
    incidents = chain_tables.race_incidents.sort_values(["season", "round"])
    # 2022 R1 has only a VSC; 2023 R1 an SC; 2023 R2 a VSC, an SC and a red flag; 2023 R3 no period.
    assert [(int(s), int(r), bool(i)) for s, r, i in incidents[["season", "round", "incident"]].itertuples(index=False)] == [
        (CHAIN_EARLIER_SEASON, 1, False), (CHAIN_SEASON, 1, True), (CHAIN_SEASON, 2, True), (CHAIN_SEASON, 3, False)]


def test_chain_incident_chance(chain_tables):
    # albert_park has no earlier race; the season's R1 and R2 both had an incident.
    assert incident_chance(chain_tables, "albert_park", CHAIN_SEASON, 3) == 1.0
    # bahrain 2023 R1: no earlier round this season; bahrain 2022 R1 had only a VSC.
    assert incident_chance(chain_tables, CHAIN_CIRCUIT, CHAIN_SEASON, 1) == 0.0
    result = forecast(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3, **CHAIN_DRY_MEDIUM)
    assert result.incident_chance == 1.0


def test_chain_backtest_table(chain_tables):
    result = backtest(chain_tables, CHAIN_SEASON, [2, 3])
    assert result.table["method"].tolist() == ["model", "circuit_history", "season_form"]
    assert result.table["n"].tolist() == [6, 6, 6]
    assert result.table["hit_rate"].isna().tolist() == [False, True, True]
    assert result.table["width"].isna().tolist() == [False, True, True]
    assert result.table.columns.tolist() == ["method", "mae", "mae_clean", "mae_incident", "hit_rate", "width", "n"]
    # R2 had an incident and R3 none, so both splits have rows.
    assert result.table[["mae", "mae_clean", "mae_incident"]].notna().all().all()
    assert result.rows.groupby("round")["incident"].first().to_dict() == {2: 1, 3: 0}
    team = result.rows[result.rows["constructor_id"] == CHAIN_TEAM]
    # R2: hamilton 2 (one under the red flag) + russell 1; R3: hamilton 2 + russell 1.
    assert team[["round", "actual"]].values.tolist() == [[2, 3], [3, 3]]
    with pytest.raises(ValueError, match=f"^no fit races before {CHAIN_SEASON} round 1$"):
        backtest(chain_tables, CHAIN_SEASON, [1])


def test_chain_forecast_ignores_the_target_race_and_later(chain_tables):
    for round_, circuit in ((2, "jeddah"), (3, "albert_park")):
        trimmed = _as_of(chain_tables, CHAIN_SEASON, round_)
        for team in sorted(set(chain_tables.constructors["constructor_id"])):
            args = (team, circuit, CHAIN_SEASON, round_)
            assert forecast(chain_tables, *args, **CHAIN_DRY_MEDIUM) == forecast(trimmed, *args, **CHAIN_DRY_MEDIUM)


# --- story 6: scenario grid ---------------------------------------------------------------------

def test_round_3_scenario_grid_reaches_the_scenario_table(chain_tables):
    grid = scenario_grid(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3)
    assert grid.columns.tolist() == SCENARIO_COLUMNS
    # R1 and R2 are dry, both cars on MEDIUM: one option; mixed and wet fall back to dry.
    # The live forecast's p is 0.4 (05:00 5 %, 06:00 40 %).
    assert grid[["weather", "start_tyres", "probability", "preset"]].values.tolist() == [
        ["dry", "MEDIUM|MEDIUM", pytest.approx(0.6), True],
        ["mixed", "MEDIUM|MEDIUM", pytest.approx(0.2), False],
        ["wet", "MEDIUM|MEDIUM", pytest.approx(0.2), False]]
    dry = forecast(chain_tables, CHAIN_TEAM, "albert_park", CHAIN_SEASON, 3, **CHAIN_DRY_MEDIUM, incident=None)
    assert grid.loc[0, ["mean", "p10", "p90"]].tolist() == [dry.total.mean, dry.total.p10, dry.total.p90]
