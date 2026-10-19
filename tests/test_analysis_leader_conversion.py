"""Tests for championship_leaders.conversion_report / leader_conversion (the leaders report)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from f1_analytics.analysis.championship_leaders import (
    conversion_display,
    conversion_report,
    leader_conversion,
    leaders_display,
    rate_text,
)
from f1_analytics.analysis.data import open_database


def _drivers() -> pd.DataFrame:
    rows = []

    def add(season, rnd, driver, points, rank):
        rows.append(
            dict(season=season, round=rnd, race_name=f"Race {rnd}", date=pd.Timestamp(f"{season}-05-{rnd:02d}"),
                 driver_id=driver, driver_name=driver.upper(), cumulative_points=points, cumulative_wins=1,
                 standing_rank=rank)
        )

    add(2024, 2, "a", 40, 1)  # a leads, b champion: not converted
    add(2024, 2, "b", 30, 2)
    add(2025, 2, "a", 43, 1)  # a and b tied first; b champion: converted (either wins)
    add(2025, 2, "b", 43, 1)
    add(2026, 1, "c", 25, 1)
    add(2026, 2, "c", 50, 1)  # the target season's latest round
    return pd.DataFrame(rows)


def _constructors() -> pd.DataFrame:
    return _drivers().rename(columns={"driver_id": "constructor_id", "driver_name": "constructor"})


def _tables() -> dict[str, pd.DataFrame]:
    final = pd.DataFrame(
        [dict(season=2024, driver_id="b", driver_name="B", position=1), dict(season=2025, driver_id="b", driver_name="B", position=1)]
    )
    return {
        "driver_standings": _drivers(),
        "constructor_standings": _constructors(),
        "driver_final": final,
        "constructor_final": final.rename(columns={"driver_id": "constructor_id", "driver_name": "constructor"}),
    }


def test_defaults_to_the_latest_round_of_the_latest_season():
    report = conversion_report(_tables())
    assert (report["target_season"], report["cutoff_round"]) == (2026, 2)
    assert report["cutoff_race"] == "Race 2"
    # The report prints this inline, so it must be the ISO text, not a date object.
    assert report["cutoff_date"] == "2026-05-02"


def test_tied_leaders_count_as_converted_if_either_wins():
    report = conversion_report(_tables())
    converted = report["drivers"].set_index("season")["converted"]
    assert converted.to_dict() == {2024: False, 2025: True}
    assert report["driver_summary"] == {"converted": 1, "total": 2, "rate": 0.5}
    assert report["constructor_summary"] == report["driver_summary"]


def test_current_leaders_cover_both_championships():
    leaders = conversion_report(_tables())["current_leaders"]
    assert leaders["entity_type"].tolist() == ["driver", "constructor"]
    assert leaders_display(leaders)["Leader"].tolist() == ["C", "C"]


def test_explicit_cutoff_and_unknown_cutoff():
    assert conversion_report(_tables(), cutoff_round=1)["drivers"].empty
    with pytest.raises(ValueError, match="round 9"):
        conversion_report(_tables(), cutoff_round=9)


def test_display_and_rate_text():
    report = conversion_report(_tables())
    shown = conversion_display(report["drivers"])
    assert shown["Converted"].tolist() == ["no", "yes"]
    assert rate_text(report["driver_summary"]) == "1 of 2 (50.0%)"
    assert rate_text({"converted": 0, "total": 0, "rate": None}) == "no seasons"


def test_leader_conversion_loads_the_four_marts_read_only(tmp_path: Path):
    db_path = tmp_path / "tiny.duckdb"
    with duckdb.connect(str(db_path)) as con:
        for name, frame in {
            "driver_standings_by_round": _tables()["driver_standings"],
            "constructor_standings_by_round": _tables()["constructor_standings"],
            "final_driver_standings": _tables()["driver_final"],
            "final_constructor_standings": _tables()["constructor_final"],
        }.items():
            con.register("frame", frame)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
            con.unregister("frame")
    with open_database(db_path) as con:
        report = leader_conversion(con)
        with pytest.raises(duckdb.Error):
            con.execute("CREATE TABLE nope (x INT)")
    assert report["driver_summary"]["total"] == 2
