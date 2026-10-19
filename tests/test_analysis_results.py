"""Tests for analysis.results on tiny in-memory frames."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis_frames import results_frame
from f1_analytics.analysis import results as r


def test_with_change_is_grid_minus_position_and_flags_finishers():
    out = r.with_change(
        results_frame(
            [
                (2026, 1, "X", "a", "x", 18, 19, "Lapped"),
                (2026, 1, "X", "b", "x", 10, 4, "Finished"),
                (2026, 1, "X", "c", "x", 3, 20, "Retired"),
                (2026, 1, "X", "d", "x", 22, 22, "Did not start"),
            ]
        )
    )
    assert out["change"].tolist() == [-1, 6, -17, 0]
    assert out["finished"].tolist() == [True, True, False, False]


def test_season_rows_filters_season_and_last_round():
    rows = results_frame(
        [(2025, 1, "X", "a", "x", 1, 1, "Finished"), (2026, 1, "X", "a", "x", 1, 1, "Finished"), (2026, 2, "X", "a", "x", 2, 1, "Finished")]
    )
    out = r.season_rows(rows, 2026, last_round=1)
    assert out[["season", "round"]].values.tolist() == [[2026, 1]]
    assert "change" in out


def test_change_summary_splits_finishes_and_non_finishes():
    rows = r.with_change(
        results_frame(
            [
                (2026, 1, "X", "albon", "w", 15, 12, "Lapped"),
                (2026, 2, "X", "albon", "w", 22, 22, "Did not start"),
                (2026, 3, "X", "albon", "w", 17, 20, "Lapped"),
                (2026, 4, "X", "albon", "w", 18, 21, "Retired"),
            ]
        )
    )
    s = r.change_summary(rows)
    assert (s["starts"], s["finishes"], s["non_finishes"]) == (4, 2, 2)
    assert s["mean_change_finished"] == pytest.approx(0.0)
    assert s["mean_change_non_finished"] == pytest.approx(-1.5)
    assert s["mean_change_all"] == pytest.approx(-0.75)
    assert s["mean_grid"] == pytest.approx(18.0)


def test_combined_by_round_sums_both_classified_positions_without_exclusion():
    rows = results_frame(
        [
            (2026, 1, "X", "albon", "williams", 15, 9, "Finished"),
            (2026, 1, "X", "sainz", "williams", 13, 22, "Did not start"),
            (2026, 2, "X", "albon", "williams", 18, 10, "Finished"),
            (2026, 2, "X", "sainz", "williams", 10, 9, "Finished"),
        ]
    )
    out = r.combined_by_round(rows)
    assert out["combined"].tolist() == [31, 19]
    assert out["grid_sum"].tolist() == [28, 28]
    assert out["best"].tolist() == [9, 9]
    assert out["any_non_finish"].tolist() == [True, False]


def test_season_summary_uses_sample_stdev():
    s = r.season_summary(pd.Series([19, 27, 31, 35, 38]))
    assert (s["n"], s["min"], s["max"]) == (5, 19, 38)
    assert s["mean"] == pytest.approx(30.0)
    assert s["median"] == pytest.approx(31.0)
    assert s["stdev"] == pytest.approx(np.std([19, 27, 31, 35, 38], ddof=1))


def test_field_non_finish_rate_counts_every_car():
    rows = r.with_change(
        results_frame([(2026, 1, "X", d, "x", 1, 1, s) for d, s in zip("abcd", ["Finished", "Retired", "Lapped", "Retired"])])
    )
    assert r.field_non_finish_rate(rows) == pytest.approx(0.5)


def test_race_label_and_masks():
    assert r.race_label("Australian Grand Prix") == "Australian"
    assert r.race_label("Bahrain Grand Prix in Malaysia") == "Bahrain in Malaysia"
    ids = pd.Series(["williams", "Williams_B", "ferrari", None])
    assert r.team_mask(ids, "williams").tolist() == [True, True, False, False]
    assert r.race_mask(pd.Series(["Dutch Grand Prix", "Singapore Grand Prix"]), "dutch").tolist() == [True, False]


def test_non_finish_note_lists_distinct_non_finish_statuses():
    assert r.non_finish_note(pd.Series(["Finished", "Lapped"])) == ""
    assert r.non_finish_note(pd.Series(["Retired", "Finished", "Retired"])) == "Retired"
    assert r.non_finish_note(pd.Series(["Did not start", "Retired"])) == "Did not start, Retired"
