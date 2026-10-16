"""Validation helpers the build runs after writing its tables."""

from __future__ import annotations

import pandas as pd


def load_present_tables(conn, table_names: list[str]) -> dict[str, pd.DataFrame]:
    """Load every table in `table_names` that currently exists in `conn`.

    A table not yet landed this run or ever (e.g. `raw_fastf1_weather`
    before this run wrote it) is silently absent from the returned dict --
    `checks.run_validations` already skips any registry entry naming an
    absent table, never raising.
    """
    existing = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    return {
        table_name: conn.execute(f"SELECT * FROM {table_name}").fetch_df()
        for table_name in table_names
        if table_name in existing
    }


def print_validation_findings(label: str, frame: pd.DataFrame) -> None:
    """Print every failing validation row (AD-8: advisory, never halts the build)."""
    if frame.empty:
        print(f"[{label}] validation: no checks ran (no target tables present)")
        return

    failing = frame[~frame["passed"]]
    if failing.empty:
        print(f"[{label}] validation: {len(frame)} check(s), all passed")
        return

    print(f"[{label}] validation: {len(failing)}/{len(frame)} check(s) FAILED")
    for _, row in failing.iterrows():
        if row["check_type"] == "null_rate":
            print(
                f"  null_rate {row['table_name']}.{row['column_name']}: "
                f"{row['null_count']}/{row['row_count']} null"
            )
        else:
            print(
                f"  referential_integrity {row['table_name']}.{row['column_name']} -> "
                f"{row['ref_table_name']}: {row['orphan_count']}/{row['row_count']} orphan(s)"
            )
