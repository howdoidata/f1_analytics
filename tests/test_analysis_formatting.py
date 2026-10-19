"""Tests for analysis.formatting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from f1_analytics.analysis import formatting as fmt


def test_signed_uses_minus_sign_and_no_sign_for_zero():
    assert fmt.signed(3) == "+3"
    assert fmt.signed(-3) == "−3"
    assert fmt.signed(0) == "0"
    assert fmt.signed(np.int64(2)) == "+2"
    assert fmt.signed(0.734) == "+0.73"
    assert fmt.signed1(-3.3) == "−3.3"


def test_numbers():
    assert fmt.pct(54.44) == "54.4%"
    assert fmt.pct0(21.02) == "21%"
    assert fmt.share(0.5) == "50%"
    assert fmt.num(16.4545) == "16.5"
    assert fmt.g(31.0) == "31" and fmt.g(11.5) == "11.5"
    assert fmt.count(500000) == "500,000"
    assert fmt.span(-2, 3) == "−2 to +3"
    assert fmt.estimate_text(1) == "+1"
    assert fmt.estimate_text((0, 1)) == "0 / +1"


def test_markdown_table_escapes_pipes_and_aligns():
    table = fmt.markdown_table(pd.DataFrame({"a": ["x|y", None], "b": [1, 2]}), "lr")
    lines = table.splitlines()
    assert lines[0] == "| a | b |"
    assert lines[1] == "|:---|---:|"
    assert lines[2] == "| x\\|y | 1 |"
    assert lines[3] == "|  | 2 |"
    with pytest.raises(ValueError):
        fmt.markdown_table(pd.DataFrame({"a": [1]}), "lr")
