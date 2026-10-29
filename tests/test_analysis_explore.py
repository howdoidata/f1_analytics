"""Tests for analysis.explore: profile, compare and violations."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from f1_analytics.analysis.explore import compare, profile, violations


def _stops() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stops": [1, 2, 3, np.nan, 0],
            "incident": [True, False, True, None, False],
            "team": ["williams", "williams", "ferrari", "ferrari", "mclaren"],
        },
        index=[10, 11, 12, 13, 14],
    )


def test_profile_gives_one_row_per_named_column_in_order():
    table = profile(_stops(), ["team", "stops"])
    assert list(table["column"]) == ["team", "stops"]
    assert list(table.columns) == ["column", "dtype", "rows", "missing", "missing_share", "distinct", "min", "max"]
    stops = table.iloc[1]
    assert stops["dtype"] == "float64"
    assert (stops["rows"], stops["missing"], stops["distinct"]) == (5, 1, 4)
    assert stops["missing_share"] == pytest.approx(0.2)
    assert (stops["min"], stops["max"]) == (0, 3)
    team = table.iloc[0]
    assert (team["missing"], team["distinct"], team["min"], team["max"]) == (0, 3, "ferrari", "williams")


def test_profile_names_an_unknown_column():
    with pytest.raises(KeyError, match="nope"):
        profile(_stops(), ["stops", "nope"])


def test_profile_of_an_empty_frame():
    table = profile(_stops().iloc[0:0], ["stops", "team"])
    assert list(table["rows"]) == [0, 0]
    assert list(table["missing"]) == [0, 0]
    assert all(math.isnan(v) for v in table["min"]) and all(math.isnan(v) for v in table["max"])
    assert all(math.isnan(v) for v in table["missing_share"])


def test_profile_of_mixed_types_leaves_min_and_max_empty():
    table = profile(pd.DataFrame({"x": [1, "a"]}), ["x"])
    assert math.isnan(table["min"].iloc[0]) and math.isnan(table["max"].iloc[0])


def test_compare_gives_stats_per_group_with_nan_as_its_own_group():
    table = compare(_stops(), "stops", "incident")
    assert list(table.columns) == ["incident", "n", "mean", "min", "median", "max"]
    assert len(table) == 3
    yes = table[table["incident"] == True].iloc[0]  # noqa: E712
    assert (yes["n"], yes["mean"], yes["min"], yes["median"], yes["max"]) == (2, 2.0, 1, 2.0, 3)
    missing = table[table["incident"].isna()].iloc[0]
    assert missing["n"] == 0 and math.isnan(missing["mean"])


def test_compare_by_a_list_of_columns():
    table = compare(_stops(), "stops", ["team", "incident"])
    assert list(table.columns[:2]) == ["team", "incident"]
    assert len(table) == 5
    row = table[(table["team"] == "williams") & (table["incident"] == False)].iloc[0]  # noqa: E712
    assert row["n"] == 1 and row["mean"] == 2.0


@pytest.mark.parametrize("value, by", [("nope", "team"), ("stops", "nope"), ("stops", ["team", "nope"])])
def test_compare_names_an_unknown_column(value, by):
    with pytest.raises(KeyError, match="nope"):
        compare(_stops(), value, by)


def test_violations_keeps_the_rows_breaking_the_rule_with_their_index():
    found = violations(_stops(), lambda d: d.stops >= 1)
    assert list(found.index) == [13, 14]
    assert list(found.columns) == ["stops", "incident", "team"]


def test_violations_of_a_rule_every_row_keeps_is_empty():
    assert violations(_stops(), lambda d: d.team != "").empty


@pytest.mark.parametrize("rule", [
    lambda d: True,
    lambda d: d.stops,
    lambda d: (d.stops >= 1).iloc[:2],
    lambda d: (d.stops >= 1).reset_index(drop=True),
    lambda d: list(d.stops >= 1),
])
def test_violations_rejects_a_rule_that_is_not_a_boolean_series_of_the_frame(rule):
    with pytest.raises(ValueError):
        violations(_stops(), rule)
