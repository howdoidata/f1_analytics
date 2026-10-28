"""Tests for the championship leader conversion analysis."""

from __future__ import annotations

import pandas as pd
import pytest

from f1_analytics.analysis.championship_leaders import (
    build_constructor_comeback_cases,
    build_conversion_table,
    current_leaders,
    determine_cutoff_round,
    format_names,
    rate_range_text,
    summarize_conversion,
    wilson_interval,
)


def _standing(season, round_, driver_id, points, wins, rank):
    return dict(
        season=season,
        round=round_,
        race_name=f"Race {round_}",
        date=f"{season}-03-{round_:02d}",
        driver_id=driver_id,
        driver_name=f"Driver {driver_id.upper()}",
        cumulative_points=points,
        cumulative_wins=wins,
        standing_rank=rank,
    )


def _driver_standings_fixture() -> pd.DataFrame:
    # 2022: "a" leads after round 2 and wins the title (converted).
    # 2023: "a" leads after round 2 but "b" wins the title (not converted).
    # 2024: only one round, so it has no round-2 row and drops out (short season).
    # 2025: "a" and "b" are tied first after round 2; "b" wins the title.
    # 2026: target season, "b" leads after round 2.
    rows = [
        _standing(2022, 1, "a", 25, 1, 1),
        _standing(2022, 2, "a", 50, 2, 1),
        _standing(2022, 2, "b", 36, 0, 2),
        _standing(2023, 2, "a", 43, 1, 1),
        _standing(2023, 2, "b", 40, 1, 2),
        _standing(2024, 1, "a", 25, 1, 1),
        _standing(2025, 2, "a", 43, 1, 1),
        _standing(2025, 2, "b", 43, 1, 1),
        _standing(2025, 2, "c", 10, 0, 3),
        _standing(2026, 1, "b", 25, 1, 1),
        _standing(2026, 2, "b", 50, 2, 1),
        _standing(2026, 2, "a", 36, 0, 2),
    ]
    return pd.DataFrame(rows)


def _driver_final_fixture() -> pd.DataFrame:
    rows = [
        dict(season=2022, driver_id="a", driver_name="Driver A", position=1),
        dict(season=2022, driver_id="b", driver_name="Driver B", position=2),
        dict(season=2023, driver_id="b", driver_name="Driver B", position=1),
        dict(season=2024, driver_id="a", driver_name="Driver A", position=1),
        dict(season=2025, driver_id="b", driver_name="Driver B", position=1),
    ]
    return pd.DataFrame(rows)


def _conversion(**overrides) -> pd.DataFrame:
    kwargs = dict(
        standings=_driver_standings_fixture(),
        champions=_driver_final_fixture(),
        cutoff_round=2,
        target_season=2026,
        id_column="driver_id",
        name_column="driver_name",
    )
    kwargs.update(overrides)
    return build_conversion_table(**kwargs)


def test_conversion_has_one_row_per_past_season_with_leader_champion_and_flag():
    conversion = _conversion().set_index("season")

    assert list(conversion.index) == [2022, 2023, 2025]
    assert conversion.loc[2022, "leader_names"] == "Driver A"
    assert conversion.loc[2022, "champion_names"] == "Driver A"
    assert bool(conversion.loc[2022, "converted"]) is True
    assert conversion.loc[2023, "leader_names"] == "Driver A"
    assert conversion.loc[2023, "champion_names"] == "Driver B"
    assert bool(conversion.loc[2023, "converted"]) is False
    assert (conversion["cutoff_round"] == 2).all()


def test_conversion_excludes_target_season():
    conversion = _conversion()

    assert 2026 not in conversion["season"].tolist()


def test_season_shorter_than_cutoff_is_excluded():
    conversion = _conversion()

    assert 2024 not in conversion["season"].tolist()


def test_tied_leaders_are_both_named():
    row = _conversion().set_index("season").loc[2025]

    assert row["leader_ids"] == "a, b"
    assert row["leader_names"] == "Driver A, Driver B"
    assert row["leader_count"] == 2
    assert bool(row["converted"]) is True


def test_summary_counts_converted_seasons_and_rate():
    summary = summarize_conversion(_conversion())

    assert summary["converted"] == 2
    assert summary["total"] == 3
    assert summary["rate"] == pytest.approx(2 / 3)


def test_no_past_seasons_gives_zero_total_and_no_rate():
    standings = _driver_standings_fixture()
    only_target = standings[standings["season"] == 2026]

    conversion = _conversion(standings=only_target)
    summary = summarize_conversion(conversion)

    assert conversion.empty
    assert summary == {"converted": 0, "total": 0, "rate": None}


def test_format_names_skips_nulls():
    assert format_names(pd.Series(["Driver A", None, "Driver B"])) == "Driver A, Driver B"


def test_current_leaders_returns_target_season_leader_at_cutoff():
    leaders = current_leaders(_driver_standings_fixture(), 2026, 2, "driver_id", "driver_name", "driver")

    assert len(leaders) == 1
    row = leaders.iloc[0]
    assert row["entity_type"] == "driver"
    assert row["cutoff_round"] == 2
    assert row["leader_id"] == "b"
    assert row["leader_name"] == "Driver B"
    assert row["leader_points"] == 50
    assert row["leader_wins"] == 2


def test_determine_cutoff_round_returns_max_round_of_target_season():
    assert determine_cutoff_round(_driver_standings_fixture(), 2026) == 2
    assert determine_cutoff_round(_driver_standings_fixture(), 2024) == 1


def test_determine_cutoff_round_raises_when_season_missing():
    with pytest.raises(ValueError):
        determine_cutoff_round(_driver_standings_fixture(), 2030)


def _constructor_standings_fixture() -> pd.DataFrame:
    def row(season, constructor_id, points, rank):
        return dict(
            season=season,
            round=2,
            constructor_id=constructor_id,
            constructor=constructor_id.title(),
            cumulative_points=points,
            cumulative_wins=0,
            standing_rank=rank,
        )

    # 2022: "red" leads and wins (deficit 0). 2023: "blue" trails "red" by
    # 30 and wins (deficit 30). 2026 is the target season and is ignored.
    return pd.DataFrame(
        [
            row(2022, "red", 80, 1),
            row(2022, "blue", 60, 2),
            row(2023, "red", 90, 1),
            row(2023, "blue", 60, 2),
            row(2026, "blue", 100, 1),
        ]
    )


def _constructor_final_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(season=2022, constructor_id="red", constructor="Red", position=1, points=500.0, wins=10),
            dict(season=2023, constructor_id="blue", constructor="Blue", position=1, points=450.0, wins=8),
            # 2021 has a champion but no cutoff standings, so it is excluded.
            dict(season=2021, constructor_id="red", constructor="Red", position=1, points=400.0, wins=7),
        ]
    )


def test_constructor_comeback_cases_sorted_by_deficit_overcome():
    cases = build_constructor_comeback_cases(
        _constructor_standings_fixture(), _constructor_final_fixture(), cutoff_round=2, target_season=2026
    )

    assert cases["season"].tolist() == [2023, 2022]
    top = cases.iloc[0]
    assert top["champion_constructor_id"] == "blue"
    assert top["cutoff_points"] == 60
    assert top["cutoff_leader_points"] == 90
    assert top["points_deficit_overcome"] == 30
    assert top["cutoff_rank"] == 2
    assert top["final_points"] == 450
    assert top["final_wins"] == 8
    assert cases.iloc[1]["points_deficit_overcome"] == 0


def test_constructor_comeback_cases_empty_keeps_columns():
    cases = build_constructor_comeback_cases(
        _constructor_standings_fixture(), _constructor_final_fixture(), cutoff_round=5, target_season=2026
    )

    assert cases.empty
    assert "points_deficit_overcome" in cases.columns


def test_wilson_interval_matches_known_values():
    # 25 of 28 by hand: centre 0.8455, half-width 0.1174.
    low, high = wilson_interval(25, 28)
    assert low == pytest.approx(0.7281, abs=1e-4)
    assert high == pytest.approx(0.9629, abs=1e-4)
    assert low < 25 / 28 < high


def test_wilson_interval_stays_inside_zero_and_one():
    assert wilson_interval(0, 5)[0] == 0.0
    assert wilson_interval(5, 5)[1] == pytest.approx(1.0)
    assert 0 < wilson_interval(5, 5)[0] < 1


def test_wilson_interval_rejects_no_seasons():
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_rate_range_text():
    assert rate_range_text({"converted": 25, "total": 28, "rate": 25 / 28}) == "89% of 28 seasons (95% interval 73–96%)"
    assert rate_range_text({"converted": 1, "total": 1, "rate": 1.0}).startswith("100% of 1 season (95% interval ")
    assert rate_range_text({"converted": 0, "total": 0, "rate": None}) == "no seasons"
