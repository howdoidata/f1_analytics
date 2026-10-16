"""Unit tests for scripts/golden_check.py on tiny in-memory frames.

The golden comparison itself is not a test: it runs against the local DuckDB
and its output is pasted into each stage PR.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from f1_analytics.config import PROJECT_ROOT


_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "golden_check.py"
_spec = importlib.util.spec_from_file_location("golden_check", _SCRIPT_PATH)
golden_check = importlib.util.module_from_spec(_spec)
# dataclasses resolve string annotations through sys.modules.
sys.modules["golden_check"] = golden_check
_spec.loader.exec_module(golden_check)


def _rows(records):
    return pd.DataFrame(
        records, columns=["season", "round", "driver_id", "constructor_id", "grid", "position", "status"]
    )


@pytest.fixture
def tiny_season() -> pd.DataFrame:
    records = []
    statuses = ["Finished", "Lapped", "Retired", "Did not start"]
    for rnd in range(1, 5):
        for car in range(6):
            grid = car + 1
            status = statuses[(rnd + car) % 4] if car % 2 == 0 else "Finished"
            position = (grid + rnd) % 6 + 1
            driver = "albon" if car == 2 else f"d{car}"
            team = "williams" if car in (2, 3) else f"t{car}"
            records.append((2026, rnd, driver, team, grid, position, status))
    return golden_check.with_change(_rows(records))


def test_with_change_is_grid_minus_position_and_flags_finishers():
    out = golden_check.with_change(
        _rows(
            [
                (2026, 1, "a", "x", 18, 19, "Lapped"),
                (2026, 1, "b", "x", 10, 4, "Finished"),
                (2026, 1, "c", "x", 3, 20, "Retired"),
                (2026, 1, "d", "x", 22, 22, "Did not start"),
            ]
        )
    )
    assert out["change"].tolist() == [-1, 6, -17, 0]
    assert out["finished"].tolist() == [True, True, False, False]


def test_change_summary_splits_finishes_and_non_finishes():
    rows = golden_check.with_change(
        _rows(
            [
                (2026, 1, "albon", "w", 15, 12, "Lapped"),
                (2026, 2, "albon", "w", 22, 22, "Did not start"),
                (2026, 3, "albon", "w", 17, 20, "Lapped"),
                (2026, 4, "albon", "w", 18, 21, "Retired"),
            ]
        )
    )
    s = golden_check.change_summary(rows)
    assert (s["starts"], s["finishes"], s["non_finishes"]) == (4, 2, 2)
    assert s["mean_change_finished"] == pytest.approx(0.0)
    assert s["mean_change_non_finished"] == pytest.approx(-1.5)
    assert s["mean_change_all"] == pytest.approx(-0.75)
    assert s["mean_grid"] == pytest.approx(18.0)


def test_combined_by_round_sums_both_classified_positions_without_exclusion():
    rows = _rows(
        [
            (2026, 1, "albon", "williams", 15, 9, "Finished"),
            (2026, 1, "sainz", "williams", 13, 22, "Did not start"),
            (2026, 2, "albon", "williams", 18, 10, "Finished"),
            (2026, 2, "sainz", "williams", 10, 9, "Finished"),
        ]
    )
    out = golden_check.combined_by_round(rows)
    assert out["combined"].tolist() == [31, 19]
    assert out["grid_sum"].tolist() == [28, 28]
    assert out["best"].tolist() == [9, 9]
    assert out["any_non_finish"].tolist() == [True, False]


def test_season_summary_uses_sample_stdev():
    s = golden_check.season_summary(pd.Series([19, 27, 31, 35, 38]))
    assert (s["n"], s["min"], s["max"]) == (5, 19, 38)
    assert s["mean"] == pytest.approx(30.0)
    assert s["median"] == pytest.approx(31.0)
    assert s["stdev"] == pytest.approx(np.std([19, 27, 31, 35, 38], ddof=1))


@pytest.mark.parametrize(
    ("regenerated", "baseline", "tolerance", "expected"),
    [
        (1, 1, golden_check.EXACT, True),
        (2, 1, golden_check.EXACT, False),
        (30.6, 30.6, golden_check.EXACT, True),
        ("5 of 11", "5 of 11", golden_check.EXACT, True),
        (33.9, 32, golden_check.WITHIN_2PP, True),
        (34.1, 32, golden_check.WITHIN_2PP, False),
        (0.83, 0.73, golden_check.WITHIN_0_1, True),
        (0.84, 0.73, golden_check.WITHIN_0_1, False),
        ((-3, 6), (-2, 5), golden_check.ENDS_WITHIN_1, True),
        ((-4, 5), (-2, 5), golden_check.ENDS_WITHIN_1, False),
    ],
)
def test_within_tolerance(regenerated, baseline, tolerance, expected):
    assert golden_check.within_tolerance(regenerated, baseline, tolerance) is expected


def test_report_marks_deviation_and_counts_it(capsys):
    report = golden_check.Report()
    report.check("a", 1, 1)
    report.check("b", 40.0, 42, golden_check.WITHIN_2PP, golden_check.pct)
    report.check("c", 39.0, 42, golden_check.WITHIN_2PP, golden_check.pct)
    assert report.summary() == 1
    out = capsys.readouterr().out
    assert "a · 1 · 1 · exact · OK" in out
    assert "c · 39.0% · 42.0% · ±2 pp · DEVIATION" in out
    assert "3 values compared · 2 OK · 1 DEVIATION" in out


def test_signed_uses_minus_sign_and_no_sign_for_zero():
    assert golden_check.signed(3) == "+3"
    assert golden_check.signed(-3) == "−3"
    assert golden_check.signed(0) == "0"
    assert golden_check.signed(0.734) == "+0.73"
    assert golden_check.signed1(-3.3) == "−3.3"


def test_missing_db_exits_non_zero_with_the_path(tmp_path: Path, capsys):
    missing = tmp_path / "nope.duckdb"
    assert golden_check.main(db_path=missing) != 0
    err = capsys.readouterr().err
    assert str(missing) in err
    assert "Traceback" not in err
    assert not missing.exists()


def test_simulation_is_deterministic_per_seed(tiny_season):
    inputs = golden_check.build_sim_inputs(tiny_season)
    first = golden_check.simulate(inputs, 500, seed=3)
    again = golden_check.simulate(inputs, 500, seed=3)
    other = golden_check.simulate(inputs, 500, seed=4)
    np.testing.assert_array_equal(first[0], again[0])
    np.testing.assert_array_equal(first[1], again[1])
    assert not np.array_equal(first[0], other[0])


def test_sim_inputs_blend_albon_record_with_field_rate(tiny_season):
    inputs = golden_check.build_sim_inputs(tiny_season)
    albon = tiny_season[tiny_season["driver_id"] == "albon"]
    n_nf = int((~albon["finished"]).sum())
    f = golden_check.field_non_finish_rate(tiny_season)
    assert inputs.beta_a == pytest.approx(n_nf + 8 * f)
    assert inputs.beta_b == pytest.approx(len(albon) - n_nf + 8 * (1 - f))
    # Recency: the latest round carries weight 1 before normalising, 6 rounds back half.
    assert inputs.grid_weights.sum() == pytest.approx(1.0)
    assert inputs.grid_weights[-1] > inputs.grid_weights[0]


def test_fixed_slot_and_fixed_p_are_honoured(tiny_season):
    from dataclasses import replace

    inputs = replace(golden_check.build_sim_inputs(tiny_season), fixed_slot=3, fixed_p=0.0)
    change, retired = golden_check.simulate(inputs, 300, seed=0)
    assert not retired.any()
    # Every finishing change comes from Albon or a finisher within 2 of slot 3.
    peers = tiny_season[
        (tiny_season["driver_id"] != "albon") & tiny_season["finished"] & ((tiny_season["grid"] - 3).abs() <= 2)
    ]
    allowed = set(peers["change"]) | set(inputs.own_finish_changes)
    assert set(change) <= allowed


def test_happy_path_prints_rows_and_summary_and_exits_zero(tmp_path: Path, capsys, monkeypatch):
    import duckdb

    db_path = tmp_path / "empty.duckdb"
    duckdb.connect(str(db_path)).close()

    monkeypatch.setattr(golden_check, "_load", lambda conn: {})
    monkeypatch.setattr(golden_check, "check_zandvoort", lambda report, data: report.check("z", 1, 1))
    monkeypatch.setattr(
        golden_check, "check_singapore_exact", lambda report, data: report.check("s", 2, 2) and None
    )
    monkeypatch.setattr(golden_check, "check_singapore_simulation", lambda report, season: report.check("m", 3, 4))

    assert golden_check.main(db_path=db_path) == 0
    out = capsys.readouterr().out
    assert "Columns: name · regenerated · baseline · tolerance · OK/DEVIATION" in out
    assert "z · 1 · 1 · exact · OK" in out
    assert "m · 3 · 4 · exact · DEVIATION" in out
    assert "3 values compared · 2 OK · 1 DEVIATION" in out
