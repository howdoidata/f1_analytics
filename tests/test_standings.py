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
