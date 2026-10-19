"""Text formatting for the reports: signed changes, percentages and Markdown tables.

The reports print through these so a `.qmd` never formats or computes values itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def signed(value, decimals: int | None = None) -> str:
    """+3 / −3 / 0, using a real minus sign. Integers print whole; floats with `decimals` places (default 2)."""
    if isinstance(value, (float, np.floating)):
        text = f"{abs(value):.{2 if decimals is None else decimals}f}"
    else:
        text = f"{abs(int(value))}"
    if text.strip("0.") == "":
        return text
    return ("+" if value > 0 else "−") + text


def signed1(value) -> str:
    return signed(value, 1)


def pct(value, decimals: int = 1) -> str:
    """A percentage already on the 0-100 scale."""
    return f"{value:.{decimals}f}%"


def pct0(value) -> str:
    return pct(value, 0)


def num(value, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"


def g(value) -> str:
    """A number without trailing zeros: 31.0 -> '31', 11.5 -> '11.5'."""
    return f"{float(value):g}"


def count(value) -> str:
    """An integer with thousands separators: 500,000."""
    return f"{int(value):,}"


def span(low, high) -> str:
    """'−2 to +3'."""
    return f"{signed(low)} to {signed(high)}"


def estimate_text(value) -> str:
    """A revise-on-qualifying estimate: one signed value, or a tuple of them."""
    if isinstance(value, tuple):
        return " / ".join(signed(v) for v in value)
    return signed(value)


def _cell(value) -> str:
    text = "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def markdown_table(frame: pd.DataFrame, align: str | None = None) -> str:
    """A pipe table for Quarto (renders natively in HTML and PDF). `align` is one of l/r/c per column."""
    columns = [str(c) for c in frame.columns]
    align = align or "l" * len(columns)
    if len(align) != len(columns):
        raise ValueError("align needs one character per column")
    rule = {"l": ":---", "r": "---:", "c": ":---:"}
    lines = [
        "| " + " | ".join(_cell(c) for c in columns) + " |",
        "|" + "|".join(rule[a] for a in align) + "|",
    ]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(lines) + "\n"
