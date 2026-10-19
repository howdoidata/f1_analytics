"""Plotly figures for the reports. One function per figure; each returns a `go.Figure`.

Every function takes frames produced elsewhere in `analysis/` and does no
computation beyond laying them out. `use_report_renderer` picks how Quarto
shows them: interactive (plotly.js from the CDN) in HTML, static PNG via
kaleido in PDF.
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from f1_analytics.analysis.formatting import signed

# Two categorical slots, in fixed order (validated light-mode palette): finishes, then retirements.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e6e5e0"
BAND = "#f2f1ec"

WIDTH = 720


def _layout(fig: go.Figure, height: int, **kwargs) -> go.Figure:
    fig.update_layout(
        width=WIDTH,
        height=height,
        margin={"l": 56, "r": 16, "t": 40, "b": 48},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Helvetica, Arial, sans-serif", "size": 12, "color": MUTED},
        legend={"orientation": "h", "x": 0, "y": 1.12, "traceorder": "normal", "font": {"color": MUTED}},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": GRID, "font": {"color": INK}},
        **kwargs,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#b8b7b0")
    return fig


def _quarto_target() -> str | None:
    """The pandoc target of the current Quarto render ('html', 'latex', ...), if any."""
    path = os.environ.get("QUARTO_EXECUTE_INFO")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        info = json.load(handle)
    return info.get("format", {}).get("pandoc", {}).get("to")


def use_report_renderer() -> str:
    """Show figures as PNG (kaleido) when Quarto renders a PDF; leave Quarto's interactive default otherwise."""
    target = _quarto_target()
    if target in ("latex", "pdf", "beamer"):
        pio.renderers.default = "png"
        pio.renderers["png"].width = WIDTH
        pio.renderers["png"].scale = 2
        return "png"
    return pio.renderers.default


# --------------------------------------------------------------------------
# Singapore
# --------------------------------------------------------------------------


def singapore_change_by_round(rounds: pd.DataFrame) -> go.Figure:
    """Bars of places gained or lost each round, finishes vs retirements (`singapore.driver_rounds`)."""
    labels = [f"R{r}" for r in rounds["round"]]
    fig = go.Figure()
    for finished, name, color in ((True, "Finished the race", BLUE), (False, "Retired or did not start", ORANGE)):
        part = rounds[rounds["finished"] == finished]
        fig.add_bar(
            name=name,
            x=[f"R{r}" for r in part["round"]],
            y=part["change"],
            marker={"color": color, "cornerradius": 4, "line": {"color": "#ffffff", "width": 2}},
            text=[signed(int(v)) for v in part["change"]],
            textposition="outside",
            textfont={"color": INK},
            cliponaxis=False,
            customdata=np.stack([part["race_name"], part["grid"], part["finish"], part["status"]], axis=-1)
            if len(part)
            else None,
            hovertemplate="%{customdata[0]}<br>Grid %{customdata[1]} → P%{customdata[2]}<br>"
            "Change %{y:+d} · %{customdata[3]}<extra></extra>",
        )
    _layout(fig, 320, bargap=0.18)
    fig.update_xaxes(categoryorder="array", categoryarray=labels)
    fig.update_yaxes(title_text="Places gained (+) or lost (−)", zeroline=True, dtick=2)
    return fig


def singapore_outcome_histogram(histogram: pd.DataFrame, pooled: dict[str, object]) -> go.Figure:
    """Stacked share of simulated races at each change, finishes vs retirements (`simulation.outcome_histogram`)."""
    fig = go.Figure()
    for column, color in (("Finishes the race", BLUE), ("Retires", ORANGE)):
        fig.add_bar(
            name=column,
            x=histogram["change"],
            y=histogram[column],
            marker={"color": color, "line": {"color": "#ffffff", "width": 1}},
            hovertemplate="Change %{x:+d}<br>%{y:.1f}% of simulated races<extra>%{fullData.name}</extra>",
        )
    low, high = pooled["middle_half"]
    fig.add_vrect(x0=low - 0.5, x1=high + 0.5, fillcolor=BAND, line_width=0, layer="below")
    fig.add_annotation(
        xref="paper", yref="paper", x=1, y=1.12, xanchor="right", yanchor="bottom", showarrow=False,
        text=f"shaded = middle half ({signed(low)} to {signed(high)})", font={"size": 11},
    )
    _layout(fig, 340, barmode="stack", bargap=0.12)
    fig.update_xaxes(title_text="Places gained (+) or lost (−) versus grid slot", dtick=1)
    fig.update_yaxes(title_text="% of simulated races", ticksuffix="%")
    return fig


def singapore_running_mean(running: pd.DataFrame, pooled_mean: float) -> go.Figure:
    """Running mean change of each run against races completed (`simulation.running_means`)."""
    fig = go.Figure()
    for run, part in running.groupby("run"):
        fig.add_scatter(
            x=part["races"], y=part["mean"], mode="lines", showlegend=False, opacity=0.45,
            line={"color": BLUE, "width": 1.5},
            hovertemplate=f"Run {run}<br>after %{{x:,}} races: mean %{{y:+.2f}}<extra></extra>",
        )
    fig.add_hline(y=pooled_mean, line={"color": INK, "width": 1, "dash": "dot"})
    fig.add_annotation(
        xref="paper", x=0.99, y=pooled_mean, yshift=12, xanchor="right", showarrow=False,
        text=f"all {running['run'].nunique()} runs settle at {signed(pooled_mean)}", font={"color": INK},
    )
    _layout(fig, 300)
    ticks = [t for t in (50, 100, 300, 1_000, 3_000, 10_000, 20_000) if t <= running["races"].max()]
    fig.update_xaxes(
        type="log",
        title_text="Simulated races completed within a run (log scale)",
        tickvals=ticks,
        ticktext=[f"{t:,}" for t in ticks],
    )
    fig.update_yaxes(title_text="Running mean change")
    return fig


def singapore_grid_slot(grid_slots: pd.DataFrame) -> go.Figure:
    """Median change (dot) and middle 80% (bar) for each fixed grid slot (`simulation.grid_slot_table`)."""
    fig = go.Figure()
    fig.add_scatter(
        x=grid_slots["slot"], y=grid_slots["median"], mode="markers+text", showlegend=False,
        text=[signed(int(v)) for v in grid_slots["median"]], textposition="middle right",
        textfont={"color": INK},
        marker={"color": BLUE, "size": 11, "line": {"color": "#ffffff", "width": 2}},
        error_y={
            "type": "data", "symmetric": False,
            "array": grid_slots["middle_80_high"] - grid_slots["median"],
            "arrayminus": grid_slots["median"] - grid_slots["middle_80_low"],
            "color": BLUE, "thickness": 2, "width": 0,
        },
        customdata=np.stack(
            [grid_slots["middle_80_low"], grid_slots["middle_80_high"], grid_slots["gains"], grid_slots["loses"]], axis=-1
        ),
        hovertemplate="Starts P%{x}<br>Median %{y:+d}<br>Middle 80%: %{customdata[0]:+d} to %{customdata[1]:+d}"
        "<br>Gains %{customdata[2]:.0f}% · loses %{customdata[3]:.0f}%<extra></extra>",
    )
    _layout(fig, 320)
    fig.update_xaxes(title_text="Grid slot at Singapore", dtick=1)
    fig.update_yaxes(title_text="Places gained (+) or lost (−)", zeroline=True, dtick=2)
    return fig


# --------------------------------------------------------------------------
# Zandvoort
# --------------------------------------------------------------------------


def zandvoort_combined_by_round(rounds: pd.DataFrame, estimate: dict[str, object], actual: dict[str, object]) -> go.Figure:
    """Combined total each round, the season mean, the estimate (with range) and the actual R12 total."""
    labels = [f"R{r}" for r in rounds["round"]]
    best = rounds["combined"].min()
    fig = go.Figure()
    fig.add_bar(
        name="Combined total", x=labels, y=rounds["combined"],
        marker={"color": [ORANGE if v == best else BLUE for v in rounds["combined"]], "cornerradius": 4,
                "line": {"color": "#ffffff", "width": 2}},
        text=rounds["combined"], textposition="outside", textfont={"color": INK}, cliponaxis=False,
        customdata=np.stack([rounds["race"], rounds["result"]], axis=-1),
        hovertemplate="%{customdata[0]}: %{customdata[1]} = %{y}<extra></extra>",
    )
    low, high = estimate["range"]
    fig.add_scatter(
        name=f"Estimate (judgement) {estimate['text']}", x=["R12 est."], y=[estimate["estimate"]], mode="markers",
        marker={"color": INK, "size": 10, "symbol": "diamond"},
        error_y={"type": "data", "symmetric": False, "array": [high - estimate["estimate"]],
                 "arrayminus": [estimate["estimate"] - low], "color": INK, "width": 6},
        hovertemplate=f"Estimate {estimate['text']}<extra></extra>",
    )
    if actual.get("raced"):
        fig.add_bar(
            name=f"Actual R12: {actual['combined']}", x=["R12 actual"], y=[actual["combined"]],
            marker={"color": MUTED, "cornerradius": 4}, text=[actual["combined"]], textposition="outside",
            textfont={"color": INK}, cliponaxis=False,
            hovertemplate=f"Actual: {actual['result']} = {actual['combined']}<extra></extra>",
        )
    mean = float(rounds["combined"].mean())
    fig.add_hline(y=mean, line={"color": MUTED, "width": 1, "dash": "dash"},
                  annotation_text=f"mean {mean:.1f}", annotation_position="top left")
    _layout(fig, 340, bargap=0.2)
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(title_text="Combined total (lower is better)", rangemode="tozero")
    return fig


def zandvoort_history(history: pd.DataFrame, band: tuple[int, int] = (28, 33)) -> go.Figure:
    """Williams' combined total at Zandvoort each season, with the band most seasons land in."""
    seasons = history["season"].astype(str)
    lowest = history["combined"].min()
    fig = go.Figure()
    fig.add_hrect(y0=band[0], y1=band[1], fillcolor=BAND, line_width=0, layer="below")
    fig.add_annotation(
        xref="paper", yref="paper", x=1, y=1.08, xanchor="right", yanchor="bottom", showarrow=False,
        text=f"shaded = {band[0]}–{band[1]} band", font={"size": 11},
    )
    fig.add_bar(
        x=seasons, y=history["combined"], showlegend=False,
        marker={"color": [ORANGE if v == lowest else BLUE for v in history["combined"]], "cornerradius": 4},
        text=history["combined"], textposition="outside", textfont={"color": INK}, cliponaxis=False,
        customdata=np.stack([history["grid"], history["result"]], axis=-1),
        hovertemplate="%{x}: grid %{customdata[0]}, %{customdata[1]} = %{y}<extra></extra>",
    )
    _layout(fig, 300, bargap=0.35)
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="Combined total at Zandvoort", rangemode="tozero")
    return fig


def zandvoort_grid_vs_result(rounds: pd.DataFrame) -> go.Figure:
    """Each round's grid sum against its combined total."""
    fig = go.Figure()
    fig.add_scatter(
        x=rounds["grid_sum"], y=rounds["combined"], mode="markers+text", showlegend=False,
        text=[f"R{r}" for r in rounds["round"]], textposition="top center", textfont={"size": 10},
        marker={"color": BLUE, "size": 10, "line": {"color": "#ffffff", "width": 2}},
        customdata=np.stack([rounds["race"], rounds["result"]], axis=-1),
        hovertemplate="%{customdata[0]}<br>Grid sum %{x} → %{customdata[1]} = %{y}<extra></extra>",
    )
    _layout(fig, 320)
    fig.update_xaxes(title_text="Grid sum (both cars)")
    fig.update_yaxes(title_text="Combined total")
    return fig


def zandvoort_constructor_standings(standings: pd.DataFrame, team: str = "williams") -> go.Figure:
    """Horizontal bars of constructor points (`zandvoort.standings_after`), the team highlighted."""
    rows = standings.sort_values("standing_rank", ascending=False)
    is_team = rows["constructor_id"].str.contains(team, case=False, na=False)
    fig = go.Figure()
    fig.add_bar(
        x=rows["cumulative_points"], y=rows["constructor"], orientation="h", showlegend=False,
        marker={"color": [ORANGE if t else BLUE for t in is_team], "cornerradius": 4},
        text=[f"{p:g}" for p in rows["cumulative_points"]], textposition="outside", textfont={"color": INK},
        cliponaxis=False, hovertemplate="%{y}: %{x:g} pts<extra></extra>",
    )
    _layout(fig, 360, bargap=0.25)
    fig.update_layout(margin={"l": 130})
    fig.update_xaxes(title_text="Constructors' points")
    return fig
