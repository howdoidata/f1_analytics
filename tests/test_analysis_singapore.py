"""Tests for analysis.singapore on synthetic frames."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis_frames import results_frame, synthetic_season
from f1_analytics.analysis import singapore as sg


@pytest.fixture
def results() -> pd.DataFrame:
    history = results_frame(
        [
            (2019, 15, "Singapore Grand Prix", "albon", "red_bull", 6, 6, "Finished"),
            (2024, 18, "Singapore Grand Prix", "albon", "williams", 11, 20, "Retired"),
            (2024, 18, "Singapore Grand Prix", "sainz", "ferrari", 3, 2, "Finished"),
            (2026, 17, "Singapore Grand Prix", "albon", "williams", 16, 18, "Retired"),
        ]
    )
    return pd.concat([synthetic_season(rounds=16), history], ignore_index=True)


def test_driver_rounds_lists_grid_finish_change_and_note(results):
    rounds = sg.driver_rounds(sg.season_data(results))
    assert rounds["round"].tolist() == list(range(1, 17))
    assert (rounds["change"] == rounds["grid"] - rounds["finish"]).all()
    assert (rounds.loc[rounds["finished"], "note"] == "").all()
    assert (rounds.loc[~rounds["finished"], "note"] == "Retired").all()
    shown = sg.rounds_display(rounds)
    assert shown.loc[15, "Race"].endswith("*")
    assert shown["Finish"].str.startswith("P").all()


def test_season_data_stops_at_the_last_pre_race_round(results):
    assert sg.season_data(results)["round"].max() == sg.LAST_ROUND


def test_driver_summary_adds_field_rate_in_percent(results):
    s = sg.driver_summary(sg.season_data(results))
    assert s["starts"] == 16
    assert 0 < s["field_non_finish_pct"] < 100


def test_driver_at_race_keeps_seasons_before_the_target(results):
    history = sg.driver_at_race(results)
    assert history["season"].tolist() == [2019, 2024]
    assert history["note"].tolist() == ["", "Retired"]
    assert history["change"].tolist() == [0, -9]
    assert sg.history_display(history)["Change"].tolist() == ["0", "−9"]


def test_actual_result_when_raced(results):
    actual = sg.actual_result(results)
    assert actual["raced"] and (actual["grid"], actual["finish"], actual["change"]) == (16, 18, -2)
    assert sg.actual_text(actual) == "Grid 16 → P18, change −2 (Retired)"


def test_actual_result_when_not_yet_raced(results):
    actual = sg.actual_result(results[results["round"] != 17])
    assert actual == {"raced": False, "text": "not yet raced"}
    assert sg.actual_text(actual) == "not yet raced"


def test_simulation_report_small_run_and_displays(results):
    report = sg.simulation_report(sg.season_data(results), seeds=(0, 1), n=200)
    assert (report.runs, report.races_per_run, report.total_races) == (2, 200, 400)
    assert report.scenario("Base case")["mean"] == pytest.approx(report.pooled["mean"])
    with pytest.raises(KeyError):
        report.scenario("nope")
    assert len(sg.run_table_display(report.run_table)) == 5
    assert sg.sensitivity_display(report.sensitivity)["Retire"].str.endswith("%").all()
    assert sg.grid_slots_display(report.grid_slots)["If he starts"].tolist()[0] == "P11"
    assert len(sg.revise_display(report.revise)) == 3


def test_top_outcomes_and_seeds_text():
    pooled = {"share_of": {-3: 9.0, 0: 11.1, 1: 13.2, 3: 14.5}}
    assert sg.top_outcomes(pooled) == [(3, 14.5), (1, 13.2), (0, 11.1)]
    assert sg.top_outcomes_text(pooled) == "+3 (14.5%), +1 (13.2%) and 0 (11.1%)"
    assert sg.top_outcomes_text(pooled, k=1) == "+3 (14.5%)"
    assert sg.seeds_text() == "0–24"
