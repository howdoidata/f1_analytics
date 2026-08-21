"""Tests for the one shared cumulative-standings function (AC 2 — no parallel implementation)."""

from __future__ import annotations

import pandas as pd

from f1_analytics.data_sources.standings import compute_cumulative_standings


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
    # first race weekend of a season, through both `build_f1_dataset.py` and
    # `build_combined_dataset.py`, after the latter had already written
    # `combined_results` — the partial-write-then-crash class the build's
    # fail-fast discipline exists to prevent.
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
