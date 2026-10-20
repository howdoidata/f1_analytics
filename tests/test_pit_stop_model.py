"""Unit tests for the count model, the weather inputs and the backtest on small synthetic PitStopTables."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from f1_analytics.analysis.data import PitStopTables
from f1_analytics.analysis.pit_stops import (
    MODEL_NOTES, UnknownInputError, backtest, car_out_rate, fit_count_model, forecast, race_weather,
    weather_weights,
)
from f1_analytics.analysis.pit_stops.model import DRAWS, SEED

TEAMS = {"aa": ("a1", "a2"), "bb": ("b1", "b2"), "cc": ("c1", "c2")}
DRIVERS = [d for cars in TEAMS.values() for d in cars]
TEAM_OF = {d: t for t, cars in TEAMS.items() for d in cars}
# (season, round, circuit_id); 2025 R5 is scheduled, not raced.
RACES = [(2024, 1, "c1"), (2024, 2, "c2"), (2024, 3, "c3"),
         (2025, 1, "c1"), (2025, 2, "c2"), (2025, 3, "c3"), (2025, 4, "c1"), (2025, 5, "c4")]
HELD = RACES[:-1]
COMPOUND_CYCLE = ("MEDIUM", "SOFT", "HARD", "MEDIUM", "INTERMEDIATE")
# 2025 R2 is mixed (some wet laps); 2025 R3 has a red flag (b1 and c2 stop under it).
MIXED = {(2025, 2)}
RED_FLAG_STOPS = [(2025, 3, "b1"), (2025, 3, "c2")]


def _stops_of(season: int, round_: int, i: int) -> int:
    return 1 + (i + round_ + season) % 3


def make_world() -> PitStopTables:
    races = pd.DataFrame([(s, r, f"GP {s}-{r}", c) for s, r, c in RACES],
                         columns=["season", "round", "race_name", "circuit_id"])
    results, pit_stops, car_races = [], [], []
    for s, r, c in HELD:
        for i, d in enumerate(DRIVERS):
            stops = _stops_of(s, r, i)
            status = "Finished"
            if (s, r, d) == (2024, 3, "c1"):
                stops, status = 0, "Retired"
            elif (s, r, d) == (2025, 1, "c1"):
                stops, status = 0, "Did not start"
            elif (s, r, d) == (2025, 2, "a2"):
                stops, status = 0, "+1 Lap"
            elif (s, r, d) == (2025, 2, "b2"):
                status = "Retired"  # out after a stop: not a car out before its first stop
            results.append((s, r, d, TEAM_OF[d], status))
            for n in range(1, stops + 1):
                pit_stops.append((s, r, d, TEAM_OF[d], n, 10 * n, "sc_vsc" if n == 2 else "normal"))
            compound = COMPOUND_CYCLE[(i + r) % len(COMPOUND_CYCLE)] if (s, r) in MIXED else \
                COMPOUND_CYCLE[(i + r) % 3]
            car_races.append((s, r, c, d, TEAM_OF[d], 50, compound, 10 if (s, r) in MIXED else 0,
                              18.0 + 2 * r + (s - 2024) + 0.5 * i))
        for d in [d for (s2, r2, d) in RED_FLAG_STOPS if (s2, r2) == (s, r)]:
            n = sum(1 for row in pit_stops if row[:3] == (s, r, d)) + 1
            pit_stops.append((s, r, d, TEAM_OF[d], n, 30, "red_flag"))
    return PitStopTables(
        races=races,
        results=pd.DataFrame(results, columns=["season", "round", "driver_id", "constructor_id", "status"]),
        constructors=pd.DataFrame({"constructor_id": [*TEAMS, "new_team"]}),
        circuits=pd.DataFrame({"circuit_id": ["c1", "c2", "c3", "c4"]}),
        pit_stops=pd.DataFrame(pit_stops, columns=["season", "round", "driver_id", "constructor_id", "stop", "lap",
                                                   "stop_type"]),
        car_races=pd.DataFrame(car_races, columns=["season", "round", "circuit_id", "driver_id", "constructor_id",
                                                   "laps_completed", "start_compound", "wet_laps", "air_temp_mean"]),
        practice_stints=pd.DataFrame(),
        weather_forecasts=weather_frame([(2025, r, 13, 0.0 if r != 3 else 0.5) for r in range(1, 6)]),
    )


def weather_frame(races) -> pd.DataFrame:
    """Forecast rows for (season, round, start hour, rain probability at the start hour), hours 10-17 UTC."""
    rows = []
    for s, r, start, rain in races:
        day = pd.Timestamp(f"{s}-06-{r:02d}")
        for h in range(10, 18):
            rows.append({
                "season": s, "round": r, "kind": "day_before", "hour_utc": day + pd.to_timedelta(h, unit="h"),
                "endpoint": "e", "fetched_at": day, "race_start_utc": day + pd.to_timedelta(start, unit="h"),
                "precipitation_probability": rain if h == start else 0.0, "precipitation_mm": 0.0,
                "air_temp": 20.0 + h,
            })
    return pd.DataFrame(rows)


WORLD = make_world()
ARGS = ("aa", "c1", 2025, 4)
DRY_MEDIUM = {"start_compounds": ["MEDIUM", "MEDIUM"], "air_temp": 25.0, "weather": "dry"}


def _later(frame: pd.DataFrame, season: int, round_: int) -> pd.DataFrame:
    return frame[(frame["season"] > season) | ((frame["season"] == season) & (frame["round"] >= round_))]


# --- weather --------------------------------------------------------------------------------------

@pytest.mark.parametrize("p, expected", [(0, (1, 0, 0)), (1, (0, 0.5, 0.5)), (0.4, (0.6, 0.2, 0.2))])
def test_weather_weights(p, expected):
    weights = weather_weights(p)
    assert list(weights) == ["dry", "mixed", "wet"]
    assert list(weights.values()) == pytest.approx(expected)


def test_weather_weights_reject_a_p_outside_0_1():
    with pytest.raises(ValueError):
        weather_weights(1.2)


def test_race_weather_reads_the_race_start_hour_and_the_next():
    # 2025 R3 starts at 13:00 with a 0.5 rain probability then and 0 at 14:00: p is the higher.
    # Air temp 33 and 34 °C.
    assert race_weather(WORLD, 2025, 3) == (0.5, 33.5)
    assert race_weather(WORLD, 2025, 1) == (0.0, 33.5)


def test_race_weather_floors_a_start_off_the_hour():
    frame = WORLD.weather_forecasts.copy()
    frame["race_start_utc"] = frame["race_start_utc"] + pd.to_timedelta(30, unit="min")
    assert race_weather(replace(WORLD, weather_forecasts=frame), 2025, 3) == (0.5, 33.5)


@pytest.mark.parametrize("frame", [
    lambda f: f[f["round"] != 2],
    lambda f: f[~((f["round"] == 2) & (f["hour_utc"].dt.hour == 14))],
    lambda f: f.assign(kind="live"),
    lambda f: f.assign(precipitation_probability=f["precipitation_probability"].where(
        ~((f["round"] == 2) & (f["hour_utc"].dt.hour == 14)))),
    lambda f: f.assign(air_temp=f["air_temp"].where(~((f["round"] == 2) & (f["hour_utc"].dt.hour == 13)))),
])
def test_a_round_without_both_day_before_hours_raises(frame):
    tables = replace(WORLD, weather_forecasts=frame(WORLD.weather_forecasts))
    with pytest.raises(ValueError, match="^no day-before forecast for 2025 round 2$"):
        race_weather(tables, 2025, 2)


# --- the fit --------------------------------------------------------------------------------------

def test_fit_rows_are_cars_of_earlier_races_and_exclude_red_flag_stops():
    model = fit_count_model(WORLD, 2025, 4)
    rows = model.fit_rows
    # 2024 R1 has no earlier fit race, so its rows (no circuit, team or field rate) are left out.
    assert sorted(set(zip(rows["season"], rows["round"]))) == [(2024, 2), (2024, 3), (2025, 1), (2025, 2), (2025, 3)]
    # c1 is out before its first stop in 2024 R3 and 2025 R1, so those two rows are left out.
    assert model.n_rows == 5 * 6 - 2 and model.n_races == 5
    b1 = rows[(rows["season"] == 2025) & (rows["round"] == 3) & (rows["driver_id"] == "b1")]
    assert b1["stops"].tolist() == [_stops_of(2025, 3, DRIVERS.index("b1"))]
    assert set(rows["weather"]) == {"dry", "mixed"}


def test_cars_out_before_their_first_stop_are_left_out_of_the_fit():
    keys = set(zip(*[fit_count_model(WORLD, 2025, 4).fit_rows[c] for c in ("season", "round", "driver_id")]))
    # Retired and Did not start with no stop: out, drawn by the car-out part instead.
    assert (2024, 3, "c1") not in keys and (2025, 1, "c1") not in keys
    # +1 Lap with no stop finished, and Retired after a stop was running: both stay in.
    assert (2025, 2, "a2") in keys and (2025, 2, "b2") in keys


def test_fit_row_rates_use_races_before_their_own_race():
    rows = fit_count_model(WORLD, 2025, 4).fit_rows.set_index(["season", "round", "driver_id"])
    # 2025 R3 at c3: 2024 R3 (one car with no stop) is its only earlier c3 race.
    c3_2024 = sum(_stops_of(2024, 3, i) for i, d in enumerate(DRIVERS) if d != "c1") / 6
    assert rows.loc[(2025, 3, "a1"), "circuit_rate"] == pytest.approx(c3_2024)
    # aa's 2025 R3 team rate: its R1 and R2 stops without red flags (a2 had none in R2).
    aa = (_stops_of(2025, 1, 0) + _stops_of(2025, 1, 1) + _stops_of(2025, 2, 0)) / 4
    assert rows.loc[(2025, 3, "a1"), "team_rate"] == pytest.approx(aa)
    # 2025 R1: the team rate is the previous season's.
    aa_2024 = sum(_stops_of(2024, r, i) for r in (1, 2, 3) for i in (0, 1)) / 6
    assert rows.loc[(2025, 1, "a1"), "team_rate"] == pytest.approx(aa_2024)
    # 2024 R2 at c2 (never raced before) takes the field mean of the fit races before it: 2024 R1.
    field = sum(_stops_of(2024, 1, i) for i in range(6)) / 6
    assert rows.loc[(2024, 2, "a1"), "circuit_rate"] == pytest.approx(field)


def test_red_flag_and_car_out_parts():
    model = fit_count_model(WORLD, 2025, 4)
    assert model.red_flag_race_rate == pytest.approx(1 / 5)
    assert model.red_flag_stops_per_car == pytest.approx(2 / 6)


def test_car_out_rate_counts_no_stop_non_finishers():
    # 2025 R1-R3: c1 did not start (out); a2 +1 Lap with no stop (finished); b2 retired after a stop.
    assert car_out_rate(WORLD, 2025, 4) == pytest.approx(1 / 18)
    # Round 1 uses the previous season: c1 retired with no stop in 2024 R3.
    assert car_out_rate(WORLD, 2025, 1) == pytest.approx(1 / 18)
    assert car_out_rate(WORLD, 2024, 1) == 0.0


def test_no_fit_rows_raises():
    with pytest.raises(ValueError, match="^no fit races before 2024 round 1$"):
        fit_count_model(WORLD, 2024, 1)


def test_a_constant_covariate_is_dropped_and_the_fit_succeeds():
    cars = WORLD.car_races.assign(start_compound="MEDIUM", wet_laps=0)
    model = fit_count_model(replace(WORLD, car_races=cars), 2025, 4)
    assert model.weather_levels == ("dry",) and model.compound_levels == ("MEDIUM",)
    assert not any(c.startswith(("weather:", "start_compound:")) for c in model.columns)
    assert np.isfinite(model.params).all()
    result = forecast(replace(WORLD, car_races=cars), *ARGS, start_compounds=["SOFT", "WET"], air_temp=25.0,
                      weather="wet", model=model)
    assert result.with_red_flags.mean > 0


def test_a_constant_numeric_covariate_is_dropped():
    cars = WORLD.car_races.assign(air_temp_mean=24.5)
    model = fit_count_model(replace(WORLD, car_races=cars), 2025, 4)
    assert "air_temp" in model.dropped and "air_temp" not in model.columns


# --- leakage --------------------------------------------------------------------------------------

def _with_sentinels(tables: PitStopTables, season: int, round_: int) -> PitStopTables:
    """Add a result, ten stops (some red-flag) and a wet car_races row at the target and in a later round."""
    results, stops, cars = [tables.results], [tables.pit_stops], [tables.car_races]
    for r in (round_, round_ + 1):
        results.append(pd.DataFrame([(season, r, "zz", "aa", "Retired")], columns=tables.results.columns))
        stops.append(pd.DataFrame(
            [(season, r, "zz", "aa", n, n, "red_flag" if n % 2 else "normal") for n in range(1, 11)],
            columns=tables.pit_stops.columns))
        cars.append(pd.DataFrame([(season, r, "c1", "zz", "aa", 50, "WET", 50, 5.0)], columns=tables.car_races.columns))
    races = tables.races
    if not ((races["season"] == season) & (races["round"] == round_ + 1)).any():
        races = pd.concat([races, pd.DataFrame([(season, round_ + 1, "GP", "c1")], columns=races.columns)])
    return replace(tables, races=races, results=pd.concat(results), pit_stops=pd.concat(stops),
                   car_races=pd.concat(cars))


@pytest.mark.parametrize("target", [(2025, 4), (2025, 2), (2025, 1)])
def test_sentinel_rows_at_or_after_the_target_change_nothing(target):
    season, round_ = target
    clean, dirty = fit_count_model(WORLD, *target), fit_count_model(_with_sentinels(WORLD, *target), *target)
    np.testing.assert_array_equal(clean.params, dirty.params)
    np.testing.assert_array_equal(clean.cov_params, dirty.cov_params)
    assert (clean.columns, clean.red_flag_race_rate, clean.red_flag_stops_per_car, clean.car_out_rate) == \
        (dirty.columns, dirty.red_flag_race_rate, dirty.red_flag_stops_per_car, dirty.car_out_rate)
    pd.testing.assert_frame_equal(clean.fit_rows, dirty.fit_rows)
    args = ("aa", "c1", season, round_)
    assert forecast(WORLD, *args, **DRY_MEDIUM) == forecast(_with_sentinels(WORLD, *target), *args, **DRY_MEDIUM)


# --- the forecast ---------------------------------------------------------------------------------

def test_forecast_is_deterministic_and_rounded():
    first, second = forecast(WORLD, *ARGS, **DRY_MEDIUM), forecast(WORLD, *ARGS, **DRY_MEDIUM)
    assert first == second
    for band in (first.with_red_flags, first.without_red_flags):
        assert band.mean == round(band.mean, 1)
        assert band.p10 <= band.mean <= band.p90
    assert first.with_red_flags.mean >= first.without_red_flags.mean
    assert (SEED, DRAWS) == (20261025, 10_000)


def test_a_reused_model_gives_the_same_forecast():
    model = fit_count_model(WORLD, 2025, 4)
    assert forecast(WORLD, *ARGS, **DRY_MEDIUM, model=model) == forecast(WORLD, *ARGS, **DRY_MEDIUM)
    with pytest.raises(ValueError, match="fitted for 2025 round 4, not 2025 round 3"):
        forecast(WORLD, "aa", "c3", 2025, 3, **DRY_MEDIUM, model=model)


@pytest.mark.parametrize("args, message", [
    (("nope", "c1", 2025, 4), "unknown constructor_id 'nope'"),
    (("aa", "nope", 2025, 4), "unknown circuit_id 'nope'"),
    (("aa", "c1", 2030, 1), "no races in season 2030"),
    (("aa", "c1", 2025, 9), "no round 9 in season 2025"),
])
def test_bad_ids_raise_story_4s_messages(args, message):
    with pytest.raises(UnknownInputError) as info:
        forecast(WORLD, *args, **DRY_MEDIUM)
    assert str(info.value) == message


@pytest.mark.parametrize("inputs", [
    {"weather": "snow"}, {"weather": {"dry": 0.5, "mixed": 0.2}}, {"weather": {"dry": 1.0, "hail": 0.0}},
    {"start_compounds": ["MEDIUM", "SUPERSOFT"]}, {"start_compounds": []},
])
def test_bad_weather_or_compounds_raise(inputs):
    with pytest.raises(ValueError):
        forecast(WORLD, *ARGS, **{**DRY_MEDIUM, **inputs})


def test_category_and_one_hot_weights_agree():
    weights = {"dry": 0.0, "mixed": 1.0, "wet": 0.0}
    assert forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": "mixed"}).with_red_flags == \
        forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": weights}).with_red_flags


def test_unseen_levels_use_the_nearest_seen_level():
    # The fit has no wet race and no WET start: wet -> mixed, WET -> INTERMEDIATE.
    model = fit_count_model(WORLD, 2025, 4)
    assert "wet" not in model.weather_levels and "WET" not in model.compound_levels
    assert "INTERMEDIATE" in model.compound_levels
    wet = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": "wet"}, model=model)
    mixed = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": "mixed"}, model=model)
    assert (wet.with_red_flags, wet.without_red_flags) == (mixed.with_red_flags, mixed.without_red_flags)
    on_wets = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "start_compounds": ["WET", "WET"]}, model=model)
    on_inters = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "start_compounds": ["INTERMEDIATE"] * 2}, model=model)
    assert on_wets.with_red_flags == on_inters.with_red_flags


def test_no_history_uses_the_field_mean_of_the_fit_races():
    model = fit_count_model(WORLD, 2025, 5)
    # c4 has never been raced and new_team has never raced.
    result = forecast(WORLD, "new_team", "c4", 2025, 5, **DRY_MEDIUM, model=model)
    assert result.circuit_rate == pytest.approx(model.field_rate)
    assert result.team_rate == pytest.approx(model.field_rate)
    non_red_flag = WORLD.pit_stops[WORLD.pit_stops["stop_type"] != "red_flag"]
    assert model.field_rate == pytest.approx(len(non_red_flag) / len(WORLD.results))


def test_no_red_flags_yet_gives_the_same_range_with_and_without():
    model = fit_count_model(WORLD, 2025, 3)
    assert model.red_flag_race_rate == 0.0
    result = forecast(WORLD, "aa", "c3", 2025, 3, **DRY_MEDIUM, model=model)
    assert result.with_red_flags == result.without_red_flags


def test_mixed_range_is_at_least_as_wide_as_dry():
    dry = forecast(WORLD, *ARGS, **DRY_MEDIUM)
    mixed = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": "mixed"})
    for d, m in ((dry.with_red_flags, mixed.with_red_flags), (dry.without_red_flags, mixed.without_red_flags)):
        assert m.p90 - m.p10 >= d.p90 - d.p10


def test_weights_with_p_zero_equal_dry():
    dry = forecast(WORLD, *ARGS, **DRY_MEDIUM)
    zero = forecast(WORLD, *ARGS, **{**DRY_MEDIUM, "weather": weather_weights(0.0)})
    assert dry.with_red_flags == zero.with_red_flags


def test_model_notes_say_what_story_7_shows():
    text = " ".join(MODEL_NOTES).lower()
    assert isinstance(MODEL_NOTES, list) and all(isinstance(note, str) for note in MODEL_NOTES)
    assert "penalty stops" in text and "counted as normal stops" in text
    assert "wet and mixed ranges rest on few races" in text and "wider" in text
    assert "start-tyre effect is a pattern" in text and "not cause and effect" in text
    assert "field mean" in text
    assert "an unseen weather or start-tyre level uses its nearest seen level (wet → mixed → dry; wet → intermediate)" in text
    assert "a car out before its first stop is drawn separately" in text
    assert "historical forecast api" in text and "previous runs api" in text
    assert "higher precipitation probability of the race-start hour and the next" in text
    assert "not the forecast made the day before" in text and "optimistic" in text
    assert "tyre wear is not a model input" in text


# --- the backtest ---------------------------------------------------------------------------------

def test_backtest_scores_the_model_and_both_benchmarks():
    result = backtest(WORLD, 2025, [2, 3, 4])
    assert result.table.columns.tolist() == ["method", "mae_with_red_flags", "mae_without_red_flags", "hit_rate", "n"]
    assert result.table["method"].tolist() == ["model", "circuit_history", "season_form"]
    assert result.table["n"].tolist() == [9, 9, 9]
    assert result.table["hit_rate"].isna().tolist() == [False, True, True]
    rows = result.rows.set_index(["round", "constructor_id"])
    # 2025 R3, bb: b1 has one red-flag stop.
    bb = _stops_of(2025, 3, 2) + _stops_of(2025, 3, 3)
    assert rows.loc[(3, "bb"), ["actual_with_red_flags", "actual_without_red_flags"]].tolist() == [bb + 1, bb]
    # Benchmarks use all stops: c3's only earlier race (2024 R3), and bb's 2025 R1-R2.
    c3 = sum(_stops_of(2024, 3, i) for i, d in enumerate(DRIVERS) if d != "c1") / 6
    assert rows.loc[(3, "bb"), "circuit_history"] == pytest.approx(2 * c3)
    form = sum(_stops_of(2025, r, i) for r in (1, 2) for i in (2, 3)) / 4
    assert rows.loc[(3, "bb"), "season_form"] == pytest.approx(2 * form)
    # The model row is the forecast with that round's weather and grid compounds.
    p, temp = race_weather(WORLD, 2025, 3)
    expected = forecast(WORLD, "bb", "c3", 2025, 3, start_compounds=["HARD", "MEDIUM"], air_temp=temp,
                        weather=weather_weights(p))
    # Scored on the unrounded mean.
    assert rows.loc[(3, "bb"), ["model_with_red_flags", "model_p10", "model_p90"]].tolist() == [
        expected.with_red_flags.raw_mean, expected.with_red_flags.p10, expected.with_red_flags.p90]
    assert expected.with_red_flags.mean == round(expected.with_red_flags.raw_mean, 1)
    # Each benchmark's one prediction is scored against both actual totals.
    bench = result.rows["circuit_history"]
    assert result.table.loc[1, "mae_with_red_flags"] == pytest.approx(
        (bench - result.rows["actual_with_red_flags"]).abs().mean())
    assert result.table.loc[1, "mae_without_red_flags"] == pytest.approx(
        (bench - result.rows["actual_without_red_flags"]).abs().mean())
    hits = (result.rows["model_p10"] <= result.rows["actual_with_red_flags"]) & \
        (result.rows["actual_with_red_flags"] <= result.rows["model_p90"])
    assert result.table.loc[0, "hit_rate"] == pytest.approx(hits.mean())


def test_backtest_round_1_benchmarks_use_the_previous_season_and_the_field_mean():
    rows = backtest(WORLD, 2025, [1]).rows.set_index("constructor_id")
    aa_2024 = sum(_stops_of(2024, r, i) for r in (1, 2, 3) for i in (0, 1)) / 6
    assert rows.loc["aa", "season_form"] == pytest.approx(2 * aa_2024)


def test_backtest_a_car_with_no_start_compound_takes_the_races_most_common():
    cars = WORLD.car_races.copy()
    cars.loc[(cars["season"] == 2025) & (cars["round"] == 3) & (cars["driver_id"] == "b2"), "start_compound"] = None
    tables = replace(WORLD, car_races=cars)
    rows = backtest(tables, 2025, [3]).rows.set_index("constructor_id")
    # b1 starts on HARD; b2's start is unknown, so it takes the race's most common start compound.
    starts = cars[(cars["season"] == 2025) & (cars["round"] == 3)]["start_compound"].dropna()
    common = sorted(starts.value_counts()[lambda c: c == c.max()].index)[0]
    p, temp = race_weather(WORLD, 2025, 3)
    expected = forecast(tables, "bb", "c3", 2025, 3, start_compounds=["HARD", common], air_temp=temp,
                        weather=weather_weights(p))
    assert rows.loc["bb", "model_with_red_flags"] == expected.with_red_flags.raw_mean


def test_backtest_an_unknown_round_raises_story_4s_error():
    with pytest.raises(UnknownInputError, match="^no round 9 in season 2025$"):
        backtest(WORLD, 2025, [9])


def test_backtest_without_a_day_before_forecast_raises():
    tables = replace(WORLD, weather_forecasts=WORLD.weather_forecasts.query("round != 4"))
    with pytest.raises(ValueError, match="^no day-before forecast for 2025 round 4$"):
        backtest(tables, 2025, [3, 4])


def test_no_history_never_yields_nan_rates():
    model = fit_count_model(WORLD, 2025, 2)
    assert not math.isnan(model.field_rate)
    assert not model.fit_rows[["circuit_rate", "team_rate"]].isna().any().any()
