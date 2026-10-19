"""Tests for the Monte Carlo in analysis.simulation, with small runs on synthetic seasons."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from analysis_frames import synthetic_season
from f1_analytics.analysis import simulation as sim
from f1_analytics.analysis.results import field_non_finish_rate, with_change


@pytest.fixture
def season() -> pd.DataFrame:
    return with_change(synthetic_season())


def test_method_constants_are_the_golden_method():
    assert sim.SEEDS == tuple(range(25))
    assert sim.RACES_PER_RUN == 20_000
    assert (sim.RECENCY_HALF_LIFE, sim.PRIOR_STRENGTH, sim.PEER_WINDOW, sim.OWN_FINISH_SHARE) == (6, 8, 2, 0.5)


def test_simulation_is_deterministic_per_seed(season):
    inputs = sim.build_sim_inputs(season)
    first = sim.simulate(inputs, 500, seed=3)
    again = sim.simulate(inputs, 500, seed=3)
    other = sim.simulate(inputs, 500, seed=4)
    np.testing.assert_array_equal(first[0], again[0])
    np.testing.assert_array_equal(first[1], again[1])
    assert not np.array_equal(first[0], other[0])


def test_same_inputs_and_seeds_give_identical_stats(season):
    inputs = sim.build_sim_inputs(season)
    pooled, per_run = sim.run_scenario(inputs, seeds=(0, 1, 2), n=300)
    pooled_again, per_run_again = sim.run_scenario(inputs, seeds=(0, 1, 2), n=300)
    assert pooled == pooled_again
    assert per_run == per_run_again


def test_sim_inputs_blend_driver_record_with_field_rate(season):
    inputs = sim.build_sim_inputs(season)
    albon = season[season["driver_id"] == "albon"]
    n_nf = int((~albon["finished"]).sum())
    f = field_non_finish_rate(season)
    assert inputs.beta_a == pytest.approx(n_nf + 8 * f)
    assert inputs.beta_b == pytest.approx(len(albon) - n_nf + 8 * (1 - f))
    assert inputs.grid_weights.sum() == pytest.approx(1.0)
    assert inputs.grid_weights[-1] > inputs.grid_weights[0]
    flat = sim.build_sim_inputs(season, recency=False)
    assert np.allclose(flat.grid_weights, 1 / len(albon))


def test_retirement_options_fix_p(season):
    albon = season[season["driver_id"] == "albon"]
    assert sim.build_sim_inputs(season).fixed_p is None
    assert sim.build_sim_inputs(season, retirement="field").fixed_p == pytest.approx(field_non_finish_rate(season))
    assert sim.build_sim_inputs(season, retirement="own").fixed_p == pytest.approx((~albon["finished"]).mean())


def test_exclude_rounds_drops_them(season):
    inputs = sim.build_sim_inputs(season, exclude_rounds=(6,))
    assert len(inputs.grids) == 5


def test_fixed_slot_and_fixed_p_are_honoured(season):
    inputs = replace(sim.build_sim_inputs(season), fixed_slot=3, fixed_p=0.0)
    change, retired = sim.simulate(inputs, 300, seed=0)
    assert not retired.any()
    peers = season[(season["driver_id"] != "albon") & season["finished"] & ((season["grid"] - 3).abs() <= 2)]
    assert set(change) <= set(peers["change"]) | set(inputs.own_finish_changes)


def test_draw_near_raises_without_rows_in_the_window():
    with pytest.raises(ValueError, match="grid slot 10"):
        sim._draw_near(np.random.default_rng(0), np.array([10]), np.array([1]), np.array([0]))


def test_outcome_stats_uses_inverted_cdf_quantiles():
    change = np.array([-3, -1, 0, 1, 1, 3, 3, 3])
    retired = np.array([True, False, False, False, False, False, False, True])
    stats = sim.outcome_stats(change, retired)
    assert stats["retire"] == pytest.approx(25.0)
    assert stats["median"] == 1
    assert stats["mode"] == 3
    assert stats["mean"] == pytest.approx(change.mean())
    assert (stats["gains"], stats["level"], stats["loses"]) == pytest.approx((62.5, 12.5, 25.0))
    assert stats["middle_half"] == (-1, 3)
    assert stats["share_of"][3] == pytest.approx(37.5)


def test_tables_from_a_small_run(season):
    inputs = sim.build_sim_inputs(season)
    result = sim.run_scenario_detail(inputs, seeds=(0, 1), n=200)

    runs = sim.run_table(result.per_run)
    assert runs["key"].tolist() == ["median", "mode", "mean", "gains", "loses"]
    assert (runs["lowest"] <= runs["highest"]).all()

    sens = sim.sensitivity_table(season, result.pooled, seeds=(0, 1), n=200)
    assert sens["assumption"].tolist() == [label for label, _ in sim.SENSITIVITY_SCENARIOS]
    assert sens.iloc[0]["mean"] == pytest.approx(result.pooled["mean"])

    slots = sim.grid_slot_table(inputs, slots=(11, 12, 16, 20), seeds=(0,), n=200)
    assert slots["slot"].tolist() == [11, 12, 16, 20]
    assert (slots["middle_80_low"] <= slots["median"]).all()
    assert (slots["median"] <= slots["middle_80_high"]).all()

    hist = sim.outcome_histogram(result)
    assert hist[["Finishes the race", "Retires"]].to_numpy().sum() == pytest.approx(100.0)

    running = sim.running_means(result, points=10, start=10)
    assert running["run"].nunique() == 2
    last = running[running["races"] == 200]
    assert last["mean"].tolist() == pytest.approx([run["mean"] for run in result.per_run])


def test_revise_on_qualifying_reads_the_grid_slot_medians():
    table = pd.DataFrame({"slot": list(range(11, 21)), "median": [0] * 5 + [1] * 4 + [2]})
    out = sim.revise_on_qualifying(table)
    assert out["estimate"].tolist() == [0, 1, 2]
    mixed = table.assign(median=[0, 0, 0, 0, 1, 1, 1, 1, 1, 2])
    assert sim.revise_on_qualifying(mixed)["estimate"].tolist()[0] == (0, 1)
