"""The pit-stop chain test: from a DuckDB built from the chain fixture world to model inputs.

Stories 5 and 6 extend this file (count model, backtest, scenario table). The
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
from f1_analytics.analysis.pit_stops import model_inputs, practice_wear_vs_history


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
    """The tables with every row at or after the target dropped.

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
