"""`uv run build` and `uv run refresh`.

- `build` turns `data/raw/` into the DuckDB file by running `dbt build` (the
  project in `dbt/`) into a fresh temporary DuckDB file, then swapping it in.
  It is offline: it reads only the committed CSVs, needs no credentials, and
  never imports `fastf1`. A failing dbt model or test, or a build that would
  shrink a guarded table, leaves the previous DuckDB file untouched.
- `refresh` checks the F1TV token first, then appends newly published rounds
  from Jolpica, fetches the FastF1 extract of every completed round that lacks
  one, and finally runs `build`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Callable, Iterator, Sequence

import duckdb
import pandas as pd

from f1_analytics.config import DBT_DIR, DUCKDB_PATH, FASTF1_CACHE_DIR, RAW_DATA_DIR
from f1_analytics.database.duckdb_io import WriteRegressionError, existing_row_count


LOGIN_COMMAND = "uv run python -m fastf1 auth f1tv --authenticate"

# Tables fed by data that only ever grows; a build that would shrink one
# means a raw file was truncated or lost, so the swap is refused.
REGRESSION_GUARDED_TABLES = frozenset(
    {"results", "sprint_results", "qualifying", "raw_fastf1_laps", "raw_fastf1_stints", "raw_fastf1_weather"}
)
# Failing rows printed per failing dbt test.
FAILURE_SAMPLE_ROWS = 5


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------


class BuildError(Exception):
    """`dbt build` failed: a model errored or a test failed."""


@contextmanager
def _env(**values: str) -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _main_table_names(conn) -> list[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
    ).fetchall()
    return [name for (name,) in rows]


def _failure_sample(db_path: Path, compiled_sql: str | None) -> list[tuple]:
    """A few of a failed test's offending rows, read back from the temp build."""
    if not compiled_sql:
        return []
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            return conn.execute(f"SELECT * FROM ({compiled_sql}) LIMIT {FAILURE_SAMPLE_ROWS}").fetchall()
    except duckdb.Error:
        return []


def _close_dbt_duckdb() -> None:
    """Close the DuckDB handle dbt-duckdb keeps open after an in-process invocation.

    Until it is closed the temp file can't be reopened read-only, and its WAL
    may not be checkpointed before the swap.
    """
    from dbt.adapters.duckdb.connections import DuckDBConnectionManager

    env = DuckDBConnectionManager._ENV
    if env is not None:
        env.close()
    DuckDBConnectionManager.close_all_connections()


def _run_dbt(raw_dir: Path, db_path: Path) -> None:
    """`dbt build` from `raw_dir` into `db_path`; raises `BuildError` naming every failed node."""
    from dbt.cli.main import dbtRunner

    # No partial parsing: the sources read F1_RAW_DIR at parse time, and it changes between builds.
    args = ["build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR), "--no-partial-parse"]
    with _env(F1_DUCKDB_PATH=str(db_path), F1_RAW_DIR=str(raw_dir.resolve())):
        try:
            result = dbtRunner().invoke(args)
        finally:
            _close_dbt_duckdb()
    if result.success:
        return
    if result.exception is not None:
        raise BuildError(f"dbt build failed: {result.exception}")
    failures = []
    for node_result in getattr(result.result, "results", None) or []:
        status = str(getattr(node_result.status, "value", node_result.status))
        if status not in {"error", "fail"}:
            continue
        node = node_result.node
        line = f"{node.resource_type} {node.name} {status}: {node_result.message}"
        if status == "fail":
            for row in _failure_sample(db_path, getattr(node, "compiled_code", None)):
                line += f"\n    {row}"
        failures.append(line)
    raise BuildError("dbt build failed:\n  " + "\n  ".join(failures or ["(no failing node reported)"]))


def _check_regression(new_db: Path, current_db: Path) -> None:
    """Refuse a build whose guarded tables have fewer rows than the current DB's."""
    if not current_db.exists():
        return
    with duckdb.connect(str(new_db), read_only=True) as new, duckdb.connect(str(current_db), read_only=True) as old:
        for name in sorted(REGRESSION_GUARDED_TABLES):
            existing = existing_row_count(old, name)
            # A guarded table the new build lacks counts as 0 rows.
            new_count = existing_row_count(new, name) or 0
            if existing is not None and new_count < existing:
                raise WriteRegressionError(
                    f"{name}: this build has {new_count} row(s), fewer than the "
                    f"{existing} row(s) already landed -- refusing to replace"
                )


def run_build(raw_dir: Path = RAW_DATA_DIR, db_path: Path = DUCKDB_PATH, *, log: Callable[[str], None] = print) -> int:
    """Build into a temp DuckDB file next to `db_path`, guard it, then swap it in.

    Raises `BuildError` or `WriteRegressionError`; either way `db_path` is untouched.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f".{db_path.stem}-build-", dir=db_path.parent))
    try:
        tmp_db = tmp_dir / db_path.name
        _run_dbt(raw_dir, tmp_db)
        _check_regression(tmp_db, db_path)
        with duckdb.connect(str(tmp_db), read_only=True) as conn:
            counts = {name: conn.execute(f'SELECT COUNT(*) FROM main."{name}"').fetchone()[0] for name in _main_table_names(conn)}
        os.replace(tmp_db, db_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    log(f"[build] DuckDB built: {db_path}")
    for name, count in counts.items():
        log(f"[build]   {name}: {count} row(s)")
    log(f"[build] dbt test results: {DBT_DIR / 'target' / 'run_results.json'}")
    return 0


def build(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build", description="Build the DuckDB file from data/raw/ (offline).")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--db", type=Path, default=DUCKDB_PATH)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run_build(args.raw_dir, args.db)
    except (BuildError, duckdb.Error) as error:
        print(f"[build] {error}", file=sys.stderr)
        print(f"[build] {args.db} was left unchanged.", file=sys.stderr)
        return 1
    except WriteRegressionError as error:
        print(f"[build] {error}. If the raw data shrank on purpose, delete {args.db} and rebuild.", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------
# refresh
# --------------------------------------------------------------------------


class TokenError(RuntimeError):
    """The F1TV token is missing, unreadable, malformed, or expired."""


def default_token_path() -> Path:
    """FastF1's token file. Resolved without `ensure_exists`, so the check creates nothing."""
    import platformdirs

    return Path(platformdirs.user_data_dir("fastf1")) / "f1auth.json"


def check_token(token_path: Path | None = None, *, now: float | None = None) -> str:
    """Return the F1TV token if it decodes as a JWT whose `exp` is in the future.

    Offline only: the signature is not verified and
    `fastf1.internals.f1auth` (which creates directories and calls the
    network) is never imported. The file holds a raw JWT, not JSON.
    """
    import jwt

    path = token_path or default_token_path()
    try:
        token = path.read_text().strip()
    except OSError as error:
        raise TokenError(f"no readable F1TV token at {path} ({type(error).__name__})") from error
    if not token:
        raise TokenError(f"F1TV token file {path} is empty")
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as error:
        raise TokenError(f"F1TV token at {path} is not a valid JWT ({type(error).__name__})") from error
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        raise TokenError(f"F1TV token at {path} has no expiry")
    if exp <= (time.time() if now is None else now):
        raise TokenError(f"F1TV token at {path} expired")
    return token


def missing_extract_rounds(raw_dir: Path, season: int, today: date | None = None) -> list[tuple[int, str]]:
    """Completed rounds of `season` with results but no FastF1 extract: `[(round, dir_name)]`."""
    from f1_analytics.data_sources.fastf1_fetch import round_dir_name
    from f1_analytics.data_sources.jolpica_fetch import completed_rounds, read_raw_table

    races = read_raw_table(raw_dir / "jolpica", "races")
    names = {
        int(round_): race_name
        for season_, round_, race_name in zip(races["season"], races["round"], races["raceName"])
        if int(season_) == season
    }
    season_dir = raw_dir / "fastf1" / str(season)
    missing = []
    for round_ in completed_rounds(raw_dir / "jolpica", season, today):
        # Any `<RR>-*` folder with a counts.json counts, so a renamed race is not refetched.
        if not any(season_dir.glob(f"{round_:02d}-*/counts.json")):
            missing.append((round_, round_dir_name(round_, names[round_])))
    return missing


def refresh(
    argv: Sequence[str] | None = None,
    *,
    token_path: Path | None = None,
    raw_dir: Path = RAW_DATA_DIR,
    db_path: Path = DUCKDB_PATH,
    cache_dir: Path = FASTF1_CACHE_DIR,
    jolpica_client=None,
    fetch_race=None,
    today: date | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="refresh", description="Check the F1TV token, update Jolpica and FastF1 raw data, then build."
    )
    parser.parse_args(sys.argv[1:] if argv is None else argv)

    # 1. The token, before any request or write.
    try:
        token = check_token(token_path)
    except TokenError as error:
        print(f"[refresh] {error}.", file=sys.stderr)
        print(f"[refresh] Log in to F1TV, then rerun:\n\n    {LOGIN_COMMAND}\n", file=sys.stderr)
        return 1

    from f1_analytics.data_sources import fastf1_fetch, jolpica_fetch

    # 2. Jolpica: append newly published rounds.
    client = jolpica_client or jolpica_fetch.JolpicaClient()
    update = jolpica_fetch.update_raw_dir(raw_dir / "jolpica", client)
    appended = ", ".join(f"{s} R{r}" for s, r in update["appended"]) or "none"
    print(f"[refresh] Jolpica rounds appended: {appended}")

    # 3. FastF1: every completed round of the latest season lacking an extract.
    results = jolpica_fetch.read_raw_table(raw_dir / "jolpica", "results")
    season = int(pd.to_numeric(results["season"]).max())
    fetch_race = fetch_race or fastf1_fetch.fetch_race
    failed = []
    missing = missing_extract_rounds(raw_dir, season, today)
    if not missing:
        print(f"[refresh] FastF1: every completed {season} round has an extract")
    for round_, dir_name in missing:
        outcome = fetch_race(season, round_, cache_dir, raw_dir / "fastf1" / str(season) / dir_name, token)
        status = outcome.get("status")
        if status == "pass":
            print(
                f"[refresh] FastF1 {season} R{round_} ({dir_name}): {outcome.get('lap_count')} laps, "
                f"{outcome.get('weather_count')} weather rows"
            )
        else:
            failed.append(round_)
            detail = outcome.get("exception") or f"{outcome.get('lap_count', 0)} laps"
            print(f"[refresh] FastF1 {season} R{round_} ({dir_name}): FAILED ({status}) -- {detail}", file=sys.stderr)

    # 4. Build from the updated raw data.
    built = True
    try:
        run_build(raw_dir, db_path)
    except (BuildError, WriteRegressionError, duckdb.Error) as error:
        built = False
        print(f"[refresh] build failed, {db_path} left unchanged: {error}", file=sys.stderr)
    if failed:
        print(f"[refresh] {len(failed)} round(s) failed: {', '.join(f'R{r}' for r in failed)}", file=sys.stderr)
        return 1
    return 0 if built else 1
