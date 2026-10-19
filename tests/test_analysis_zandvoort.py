"""Tests for analysis.zandvoort on synthetic frames."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis_frames import results_frame, synthetic_season
from f1_analytics.analysis import zandvoort as zv


@pytest.fixture
def results() -> pd.DataFrame:
    dutch = []
    for season, (g1, p1, g2, p2) in zip(range(2021, 2026), [(0, 16, 11, 17), (15, 12, 20, 18), (4, 8, 10, 20), (19, 14, 18, 16), (15, 5, 9, 13)]):
        dutch += [
            (season, 13, "Dutch Grand Prix", "albon", "williams", g1, p1, "Finished"),
            (season, 13, "Dutch Grand Prix", "sainz", "williams", g2, p2, "Finished"),
            (season, 13, "Dutch Grand Prix", "other", "ferrari", 1, 7, "Finished"),
        ]
    actual = [
        (2026, 12, "Dutch Grand Prix", "albon", "williams", 16, 17, "Retired"),
        (2026, 12, "Dutch Grand Prix", "sainz", "williams", 17, 16, "Lapped"),
    ]
    return pd.concat([synthetic_season(rounds=11), results_frame(dutch + actual)], ignore_index=True)


@pytest.fixture
def standings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": 2026,
            "round": 11,
            "constructor_id": ["mercedes", "williams", "haas"],
            "constructor": ["Mercedes", "Williams", "Haas"],
            "standing_rank": [1, 2, 3],
            "cumulative_points": [100.0, 11.0, 0.0],
        }
    )


def test_round_table_sums_both_cars_per_round(results):
    table = zv.round_table(zv.team_rows(results))
    assert table["round"].tolist() == list(range(1, 12))
    first = zv.team_rows(results).query("round == 1")
    assert table.loc[0, "combined"] == first["position"].sum()
    assert table.loc[0, "result"].count("P") == 2
    assert zv.rounds_display(table).columns.tolist() == ["Round", "Race", "Grid sum", "Result", "Total", "Note"]


def test_window_means_cover_all_and_last_windows():
    table = pd.DataFrame({"round": range(1, 12), "combined": [27, 31, 35, 19, 30, 24, 30, 37, 38, 31, 35]})
    windows = zv.window_means(table)
    assert windows["window"].tolist() == ["All 11 rounds", "Last 6 (R6–R11)", "Last 4 (R8–R11)"]
    assert windows["mean"].tolist() == pytest.approx([30.636, 32.5, 35.25], abs=1e-3)
    assert zv.windows_display(windows)["Mean"].tolist() == ["30.6", "32.5", "35.2"]


def test_validation_answers(results):
    laps = pd.DataFrame(
        {
            "season": 2026,
            "round": [1, 1, 1, 2],
            "constructor_id": ["williams", "williams", "ferrari", "williams"],
            "driver_id": ["albon", "sainz", "leclerc", "sainz"],
            "LapTime": ["0 days 00:01:24.000000", "0 days 00:01:23.590000", "0 days 00:01:20.000000", "0 days 00:01:10.000000"],
        }
    )
    answers = zv.validation_answers(results, laps)
    assert answers["melbourne_fastest_lap"] == "1:23.590"
    assert answers["melbourne_fastest_driver"] == "sainz"
    assert answers["canada_best"].startswith("P")
    assert isinstance(answers["miami_combined"], int)


def test_race_history_and_volatility(results):
    history = zv.race_history(results)
    assert history["season"].tolist() == [2021, 2022, 2023, 2024, 2025]
    assert history["combined"].tolist() == [33, 30, 28, 30, 18]
    assert history.loc[0, "grid"] == "0+11"
    vol = zv.race_volatility(results)
    assert vol["starts"] == 14  # 15 starts, minus the grid-0 one
    assert vol["moved_5_plus"] == int(vol["moved_5_plus_pct"] * vol["starts"] / 100 + 0.5)


def test_standings_after_and_team_standing(standings):
    table = zv.standings_after(standings)
    assert zv.team_standing(table) == {"rank": 2, "of": 3, "points": 11.0}
    assert zv.standings_display(table)["Rank"].tolist() == ["P1", "P2", "P3"]


def test_estimate_is_the_stated_judgement_with_computed_inputs(results, standings):
    est = zv.estimate(results, standings)
    assert (est["estimate"], est["range"], est["label"]) == (31, (29, 33), "judgement")
    assert est["text"] == "31 (29–33)"
    inputs = est["inputs"]
    assert inputs["rounds"] == 11
    assert (inputs["standing_rank"], inputs["standing_of"], inputs["standing_points"]) == (2, 3, 11.0)
    assert inputs["last_race_combined"] == 18
    shown = zv.estimate_inputs_display(est)
    assert "P2 of 3, 11 pts" in shown["Value"].tolist()


def test_actual_result_when_raced(results):
    actual = zv.actual_result(results)
    assert actual["raced"] and actual["combined"] == 33
    assert actual["result"] == "P16 + P17"
    assert actual["in_range"] and actual["vs_estimate"] == 2
    assert zv.actual_text(actual) == "33 (P16 + P17; Retired)"


def test_actual_result_when_round_not_raced(results):
    actual = zv.actual_result(results[~((results["season"] == 2026) & (results["round"] == 12))])
    assert actual == {"raced": False, "text": "not yet raced"}
    assert zv.actual_text(actual) == "not yet raced"


def test_lap_text():
    assert zv.lap_text(pd.to_timedelta(pd.Series(["0 days 00:01:23.590000"])).iloc[0]) == "1:23.590"


def test_revise_display_is_labelled_a_judgement():
    assert "judgement" in zv.revise_display().columns[1]
