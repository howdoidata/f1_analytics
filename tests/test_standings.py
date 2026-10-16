"""Tests for the one shared cumulative-standings function (AC 2 — no parallel implementation)."""

from __future__ import annotations

import pandas as pd

from f1_analytics.data_sources.standings import add_standing_rank, compute_cumulative_standings


def _race_results_enriched_fixture() -> pd.DataFrame:
    # Shaped like race_results_enriched (results merged with races): season,
    # round, race_name, date, id_column, name_column, points, position.
    # 2024 rounds 1-2: driver "a" and "b" swap positions between rounds, so
    # both end round 2 tied on cumulative points (43) and wins (1) — proves
    # tie handling. 2025 round 1: proves cumulative totals reset per season.
    rows = [
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="a", driver_name="Driver A", points=18, position=2),
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="b", driver_name="Driver B", points=25, position=1),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="a", driver_name="Driver A", points=25, position=1),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="b", driver_name="Driver B", points=18, position=2),
        dict(season=2025, round=1, race_name="Bahrain Grand Prix", date="2025-03-01", driver_id="a", driver_name="Driver A", points=25, position=1),
        dict(season=2025, round=1, race_name="Bahrain Grand Prix", date="2025-03-01", driver_id="b", driver_name="Driver B", points=18, position=2),
    ]
    return pd.DataFrame(rows)


def test_cumulative_points_and_wins_accumulate_within_a_season():
    standings = compute_cumulative_standings(_race_results_enriched_fixture(), "driver_id", "driver_name")

    round1 = standings[(standings["season"] == 2024) & (standings["round"] == 1)].set_index("driver_id")
    assert round1.loc["a", "cumulative_points"] == 18
    assert round1.loc["b", "cumulative_points"] == 25

    round2 = standings[(standings["season"] == 2024) & (standings["round"] == 2)].set_index("driver_id")
    assert round2.loc["a", "cumulative_points"] == 43
    assert round2.loc["b", "cumulative_points"] == 43
    assert round2.loc["a", "cumulative_wins"] == 1
    assert round2.loc["b", "cumulative_wins"] == 1


def test_cumulative_totals_reset_per_season():
    standings = compute_cumulative_standings(_race_results_enriched_fixture(), "driver_id", "driver_name")

    season_2025 = standings[standings["season"] == 2025].set_index("driver_id")
    assert season_2025.loc["a", "cumulative_points"] == 25
    assert season_2025.loc["b", "cumulative_points"] == 18


def test_tied_cumulative_points_and_wins_receive_the_same_standing_rank():
    standings = compute_cumulative_standings(_race_results_enriched_fixture(), "driver_id", "driver_name")

    round2 = standings[(standings["season"] == 2024) & (standings["round"] == 2)].set_index("driver_id")
    assert round2.loc["a", "standing_rank"] == round2.loc["b", "standing_rank"] == 1


def _tie_with_a_driver_below_fixture() -> pd.DataFrame:
    # Three drivers, because dense (1,2,2,3) and standard competition (1,2,2,4)
    # ranking differ ONLY in the rank given to the row *after* a tie. The
    # two-driver fixture above puts the tie in both rows of its group, so it
    # has no such row and cannot tell the two conventions apart.
    #
    # 2024 round 2 standings: "a" leads on 43, "b" and "c" tie on 25 (each won
    # one race worth 25 and scored 0 in the other), "d" trails on 12. The tie
    # sits mid-table with a driver both above and below it, so the rank "d"
    # receives is what pins the convention.
    rows = [
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="a", driver_name="Driver A", points=18, position=2),
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="b", driver_name="Driver B", points=25, position=1),
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="c", driver_name="Driver C", points=0, position=11),
        dict(season=2024, round=1, race_name="Bahrain Grand Prix", date="2024-03-02", driver_id="d", driver_name="Driver D", points=12, position=3),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="a", driver_name="Driver A", points=25, position=1),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="b", driver_name="Driver B", points=0, position=12),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="c", driver_name="Driver C", points=25, position=1),
        dict(season=2024, round=2, race_name="Saudi Arabian Grand Prix", date="2024-03-09", driver_id="d", driver_name="Driver D", points=0, position=13),
    ]
    return pd.DataFrame(rows)


def test_the_rank_after_a_tie_skips_the_consumed_position():
    # Standard competition ranking (DW-8): two drivers tied for 2nd consume
    # positions 2 and 3, so the next driver is 4th, not 3rd. Dense ranking —
    # what the cumsum-over-tie-breaks construction produces — would give "d"
    # rank 3 and silently claim a driver finished 3rd when nobody did.
    standings = compute_cumulative_standings(_tie_with_a_driver_below_fixture(), "driver_id", "driver_name")

    round2 = standings[(standings["season"] == 2024) & (standings["round"] == 2)].set_index("driver_id")
    assert round2.loc["a", "standing_rank"] == 1
    assert round2.loc["b", "standing_rank"] == 2
    assert round2.loc["c", "standing_rank"] == 2
    assert round2.loc["d", "standing_rank"] == 4


def test_drivers_tied_on_missing_cumulative_points_share_a_rank():
    # DW-9: `totals.ne(totals.shift())` answers True for consecutive NaN rows
    # because NaN != NaN, handing two equally-placed drivers different ranks.
    #
    # Calls `add_standing_rank` directly rather than going through
    # `compute_cumulative_standings`: that function's `race_points=("points",
    # "sum")` aggregation turns an all-NaN group into 0.0, so a NaN can never
    # reach `cumulative_points` by that route and a fixture built from raw
    # `points` would pass without exercising the defect at all. NaN totals are
    # reachable here because `add_standing_rank` is a shared public function
    # that ranks whatever cumulative columns it is handed.
    df = pd.DataFrame(
        [
            dict(season=2024, round=1, driver_id="c", cumulative_points=25.0, cumulative_wins=1),
            dict(season=2024, round=1, driver_id="a", cumulative_points=float("nan"), cumulative_wins=0),
            dict(season=2024, round=1, driver_id="b", cumulative_points=float("nan"), cumulative_wins=0),
        ]
    )

    ranked = add_standing_rank(df, ["season", "round"], ["driver_id"]).set_index("driver_id")

    assert ranked.loc["c", "standing_rank"] == 1
    assert ranked.loc["a", "standing_rank"] == ranked.loc["b", "standing_rank"] == 2


def test_more_points_outranks_more_wins():
    # Regression: an implementation that ranks `cumulative_points` and
    # `cumulative_wins` independently and combines the two results is not
    # ordering on the pair. Ranking each column separately gave "a" (40 pts,
    # 3 wins) and "b" (50 pts, 1 win) the SAME rank of 2 and left rank 1
    # unassigned, because "a" leads on wins while "b" leads on points.
    # Points are the primary key; wins break ties only.
    df = pd.DataFrame(
        [
            dict(season=2024, round=1, driver_id="a", cumulative_points=40.0, cumulative_wins=3),
            dict(season=2024, round=1, driver_id="b", cumulative_points=50.0, cumulative_wins=1),
            dict(season=2024, round=1, driver_id="c", cumulative_points=30.0, cumulative_wins=0),
        ]
    )

    ranked = add_standing_rank(df, ["season", "round"], ["driver_id"]).set_index("driver_id")

    assert ranked.loc["b", "standing_rank"] == 1
    assert ranked.loc["a", "standing_rank"] == 2
    assert ranked.loc["c", "standing_rank"] == 3


def test_wins_break_a_tie_on_equal_points():
    # The companion to the test above: on equal points the driver with more
    # wins ranks ahead, and the two are NOT tied.
    df = pd.DataFrame(
        [
            dict(season=2024, round=1, driver_id="a", cumulative_points=50.0, cumulative_wins=1),
            dict(season=2024, round=1, driver_id="b", cumulative_points=50.0, cumulative_wins=2),
        ]
    )

    ranked = add_standing_rank(df, ["season", "round"], ["driver_id"]).set_index("driver_id")

    assert ranked.loc["b", "standing_rank"] == 1
    assert ranked.loc["a", "standing_rank"] == 2


def _single_round_fixture() -> pd.DataFrame:
    # Exactly one (season, round) group — the first race weekend of a new
    # season, before any second round exists. This is one `groupby` group,
    # which is the boundary `add_standing_rank` gets wrong (see the test
    # below); every other fixture here has three or more groups.
    rows = [
        dict(season=2026, round=1, race_name="Australian Grand Prix", date="2026-03-08", driver_id="a", driver_name="Driver A", points=25, position=1),
        dict(season=2026, round=1, race_name="Australian Grand Prix", date="2026-03-08", driver_id="b", driver_name="Driver B", points=18, position=2),
    ]
    return pd.DataFrame(rows)


def test_a_season_with_one_round_ranks_without_raising():
    # Regression: `groupby(...).apply(...)` returns a DataFrame rather than a
    # Series when there is exactly ONE group, so assigning it to the single
    # `standing_rank` column raised `ValueError: Cannot set a DataFrame with
    # multiple columns to the single column standing_rank`. Reachable on the
    # first race weekend of a season.
    standings = compute_cumulative_standings(_single_round_fixture(), "driver_id", "driver_name")

    assert len(standings) == 2
    ranked = standings.set_index("driver_id")
    assert ranked.loc["a", "standing_rank"] == 1
    assert ranked.loc["b", "standing_rank"] == 2
    assert ranked.loc["a", "cumulative_points"] == 25
    assert ranked.loc["b", "cumulative_points"] == 18


def test_the_very_first_row_of_the_frame_ranks_from_one():
    # Regression: rank is derived from a row differing from the row above it,
    # so the frame's first row has no predecessor. Deriving "first row of a
    # group" from `group_columns.shift()` made that row compare against NaN
    # and start no rank, leaving the earliest group 0-based while every later
    # group was 1-based — reproduced live as 1950 round 1 (the first race in
    # the dataset) ranking its leader 0 while all 1,159 other rounds ranked
    # theirs 1.
    standings = compute_cumulative_standings(_race_results_enriched_fixture(), "driver_id", "driver_name")

    assert standings["standing_rank"].min() == 1
    first_round = standings[(standings["season"] == 2024) & (standings["round"] == 1)]
    assert first_round["standing_rank"].min() == 1


def test_sprint_points_join_their_round_and_date_comes_from_races():
    results = pd.DataFrame(
        {
            "season": [2025, 2025],
            "round": [1, 1],
            "race_name": ["X Grand Prix", "X Grand Prix"],
            "driver_id": ["a", "b"],
            "driver_name": ["A", "B"],
            "points": [18.0, 25.0],
            "position": [2, 1],
        }
    )
    sprint = results.assign(points=[8.0, 0.0], position=[1, 9])
    races = pd.DataFrame({"season": [2025], "round": [1], "date": [pd.Timestamp("2025-03-01").date()]})

    standings = compute_cumulative_standings(
        results, "driver_id", "driver_name", races=races, sprint_results=sprint
    ).set_index("driver_id")

    assert standings.loc["a", "race_points"] == 26
    assert standings.loc["a", "race_wins"] == 0  # a sprint win is not a race win
    assert standings.loc["a", "standing_rank"] == 1
    assert standings.loc["b", "race_wins"] == 1
    assert str(standings.loc["a", "date"]) == "2025-03-01"
