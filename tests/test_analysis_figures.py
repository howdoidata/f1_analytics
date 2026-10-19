"""Tests for the Plotly figure functions in analysis.figures (synthetic frames, no rendering)."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pytest

from analysis_frames import results_frame, synthetic_season
from f1_analytics.analysis import figures, simulation as sim, singapore as sg, zandvoort as zv
from f1_analytics.analysis.results import with_change


@pytest.fixture(scope="module")
def sim_report():
    season = with_change(synthetic_season(rounds=16))
    return sg.simulation_report(season, seeds=(0, 1), n=200)


def test_singapore_change_by_round_splits_finishes_and_retirements():
    rounds = sg.driver_rounds(with_change(synthetic_season(rounds=8)))
    fig = figures.singapore_change_by_round(rounds)
    assert isinstance(fig, go.Figure)
    assert [t.name for t in fig.data] == ["Finished the race", "Retired or did not start"]
    assert sum(len(t.y) for t in fig.data) == len(rounds)


def test_singapore_simulation_figures(sim_report):
    hist = figures.singapore_outcome_histogram(sim_report.histogram, sim_report.pooled)
    assert [t.name for t in hist.data] == ["Finishes the race", "Retires"]
    assert hist.layout.barmode == "stack"

    running = figures.singapore_running_mean(sim_report.running_means, sim_report.pooled["mean"])
    assert len(running.data) == sim_report.runs
    assert running.layout.xaxis.type == "log"

    grid = figures.singapore_grid_slot(sim_report.grid_slots)
    assert list(grid.data[0].x) == list(sim.GRID_SLOTS)


def _zandvoort_rounds() -> pd.DataFrame:
    return pd.DataFrame(
        {"round": [1, 2, 3], "race": ["A", "B", "C"], "result": ["P1 + P2"] * 3, "combined": [27, 19, 31], "grid_sum": [36, 28, 39]}
    )


def test_zandvoort_combined_by_round_shows_estimate_and_actual():
    estimate = {"estimate": 31, "range": (29, 33), "text": "31 (29–33)"}
    raced = {"raced": True, "combined": 33, "result": "P16 + P17"}
    fig = figures.zandvoort_combined_by_round(_zandvoort_rounds(), estimate, raced)
    names = [t.name for t in fig.data]
    assert names[1].startswith("Estimate (judgement)")
    assert names[2] == "Actual R12: 33"
    not_raced = figures.zandvoort_combined_by_round(_zandvoort_rounds(), estimate, {"raced": False, "text": "not yet raced"})
    assert len(not_raced.data) == 2


def test_zandvoort_other_figures():
    history = pd.DataFrame({"season": [2024, 2025], "grid": ["1+2", "3+4"], "result": ["P1 + P2"] * 2, "combined": [30, 18]})
    assert list(figures.zandvoort_history(history).data[0].y) == [30, 18]
    assert len(figures.zandvoort_grid_vs_result(_zandvoort_rounds()).data[0].x) == 3
    standings = pd.DataFrame(
        {"standing_rank": [1, 2], "constructor_id": ["mercedes", "williams"], "constructor": ["Mercedes", "Williams"], "cumulative_points": [10.0, 1.0]}
    )
    fig = figures.zandvoort_constructor_standings(standings)
    assert fig.data[0].marker.color == (figures.ORANGE, figures.BLUE)  # Williams first: rows run bottom-up


def test_use_report_renderer_switches_to_png_only_for_pdf(tmp_path, monkeypatch):
    before = pio.renderers.default
    info = tmp_path / "info.json"
    try:
        info.write_text(json.dumps({"format": {"pandoc": {"to": "html"}}}))
        monkeypatch.setenv("QUARTO_EXECUTE_INFO", str(info))
        assert figures.use_report_renderer() == before
        info.write_text(json.dumps({"format": {"pandoc": {"to": "latex"}}}))
        assert figures.use_report_renderer() == "png"
        assert pio.renderers.default == "png"
    finally:
        pio.renderers.default = before
