"""The explore toolkit: three DataFrame functions for a report's `explore.qmd`.

- `profile(df, columns)`: dtype, rows, missing values, distinct values and
  range of each named column (the columns the model uses, not every column).
- `compare(df, value, by)`: count, mean, min, median and max of one column
  per group of one or more others.
- `violations(df, rule)`: the rows breaking a rule, given as a callable that
  takes the frame and returns a boolean Series.

Frames in, frames out: the toolkit holds no SQL and reads no database. An
`explore.qmd` loads its staging tables itself and passes the frames in;
the question-specific part is only the arguments.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import pandas as pd

PROFILE_COLUMNS = ["column", "dtype", "rows", "missing", "missing_share", "distinct", "min", "max"]
COMPARE_STATS = ["n", "mean", "min", "median", "max"]


def _require(df: pd.DataFrame, columns: Sequence[str]) -> None:
    unknown = [column for column in columns if column not in df.columns]
    if unknown:
        raise KeyError(f"unknown column(s) {unknown}; the frame has {list(df.columns)}")


def _bound(values: pd.Series, which: str) -> object:
    """min or max of the non-missing values; NaN when empty or not comparable."""
    present = values.dropna()
    if present.empty:
        return math.nan
    try:
        return getattr(present, which)()
    except TypeError:
        return math.nan


def profile(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """One row per named column, in the order given.

    `missing_share` is NaN for an empty frame; `min` and `max` are NaN when
    there are no values or they cannot be ordered (mixed types).
    """
    columns = list(columns)
    _require(df, columns)
    rows = []
    for column in columns:
        values = df[column]
        missing = int(values.isna().sum())
        rows.append({
            "column": column,
            "dtype": str(values.dtype),
            "rows": len(values),
            "missing": missing,
            "missing_share": missing / len(values) if len(values) else math.nan,
            "distinct": int(values.nunique(dropna=True)),
            "min": _bound(values, "min"),
            "max": _bound(values, "max"),
        })
    return pd.DataFrame(rows, columns=PROFILE_COLUMNS)


def compare(df: pd.DataFrame, value: str, by: str | Sequence[str]) -> pd.DataFrame:
    """Count, mean, min, median and max of `value` per group of `by`.

    `by` is a column name or a list of them; a missing key is its own group.
    `n` counts the non-missing values of `value` in the group.
    """
    keys = [by] if isinstance(by, str) else list(by)
    _require(df, [value, *keys])
    grouped = df.groupby(keys, dropna=False, sort=True)[value]
    table = grouped.agg(["count", "mean", "min", "median", "max"]).rename(columns={"count": "n"})
    return table.reset_index()[[*keys, *COMPARE_STATS]]


def violations(df: pd.DataFrame, rule: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
    """The rows of `df` where `rule(df)` is False, with their index kept.

    `rule` must return a boolean Series on `df`'s index; anything else raises
    `ValueError`.
    """
    kept = rule(df)
    if not isinstance(kept, pd.Series) or not pd.api.types.is_bool_dtype(kept.dtype):
        raise ValueError(f"rule must return a boolean Series, got {type(kept).__name__}"
                         + (f" of {kept.dtype}" if isinstance(kept, pd.Series) else ""))
    if len(kept) != len(df) or not kept.index.equals(df.index):
        raise ValueError(f"rule returned {len(kept)} values on another index; the frame has {len(df)} rows")
    return df[~kept]
