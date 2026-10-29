"""The mart check (conventions rules 1-7): the repo passes, and each breach is named.

The repo case parses the dbt project into a temp target path (offline, no
stale dbt/target/), so an edit to a yml file is judged as it stands. When the
built DuckDB file is there it also lists each mart's actual columns, so a
column the yml leaves out fails rule 4; locally that part skips without the
file, in CI (`CI` set) a missing file fails it.
"""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import duckdb
import pytest

from f1_analytics import config
from f1_analytics.mart_check import breaches, marts
from test_real_db import require_real_db


COTA = "2026-10-24-williams-cota-pit-stop-forecast"
ONE_OFF_MARTS = {"pit_stops", "car_races", "practice_stints", "weather_forecasts", "race_incidents", "stop_rules"}


def _no_network(*args, **kwargs):
    raise RuntimeError("Network access is blocked in tests (AD-11)")


@pytest.fixture(scope="module")
def repo_manifest(tmp_path_factory) -> dict:
    """The manifest `dbt parse` writes for the repo's dbt project, into a temp target path."""
    from dbt.cli.main import dbtRunner

    target = tmp_path_factory.mktemp("dbt_target")
    args = [
        "parse", "--project-dir", str(config.DBT_DIR), "--profiles-dir", str(config.DBT_DIR),
        "--target-path", str(target), "--log-path", str(target), "--no-partial-parse", "--quiet",
    ]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", _no_network)
        patch.setattr(socket.socket, "connect_ex", _no_network)
        result = dbtRunner().invoke(args)
    assert result.success, f"dbt parse failed: {result.exception}"
    return json.loads((target / "manifest.json").read_text())


def test_the_repo_passes_the_mart_check(repo_manifest):
    assert breaches(repo_manifest, config.PROJECT_ROOT) == []


def test_every_mart_has_one_tag_and_every_one_off_names_the_cota_report(repo_manifest):
    found = marts(repo_manifest)
    assert len(found) == 21
    tags = {name: node["tags"] for name, node in found.items()}
    assert {name for name, t in tags.items() if t == ["one_off"]} == ONE_OFF_MARTS
    assert {name for name, t in tags.items() if t == ["core"]} == set(found) - ONE_OFF_MARTS
    for name in ONE_OFF_MARTS:
        assert found[name]["config"]["meta"]["question"] == COTA


def test_every_built_core_column_is_documented(repo_manifest):
    db_path = require_real_db(config.DUCKDB_PATH)
    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'main'"
        ).fetchall()
    columns: dict[str, list[str]] = {}
    for table, column in rows:
        columns.setdefault(table, []).append(column)
    assert breaches(repo_manifest, config.PROJECT_ROOT, columns=columns) == []


# --------------------------------------------------------------------------
# synthetic manifests and trees, one case per matrix row
# --------------------------------------------------------------------------

PACKAGE = "f1_analytics"


def _model(name: str, tags: list[str], question: str | None = None, path: str = "marts",
           columns: dict | None = None, depends: list[str] = ()) -> dict:
    meta = {"question": question} if question else {}
    return {
        "unique_id": f"model.{PACKAGE}.{name}",
        "resource_type": "model",
        "name": name,
        "original_file_path": f"models/{path}/{name}.sql",
        "description": f"The {name} mart.",
        "tags": tags,
        "meta": meta,
        "config": {"tags": tags, "meta": meta},
        "columns": columns if columns is not None else {
            "id": {"name": "id", "description": "Key.", "meta": {}, "config": {"meta": {}}},
            "kind": {"name": "kind", "description": "A category.", "meta": {"category": True},
                     "config": {"meta": {"category": True}}},
        },
        "depends_on": {"nodes": [f"model.{PACKAGE}.{parent}" for parent in depends]},
    }


def _test(model: str, name: str, column: str | None = None, columns: list[str] | None = None) -> dict:
    kwargs = {"columns": columns} if columns else {"column_name": column}
    return {
        "unique_id": f"test.{PACKAGE}.{name}_{model}_{column or '_'.join(columns or [])}",
        "resource_type": "test",
        "name": f"{name}_{model}",
        "attached_node": f"model.{PACKAGE}.{model}",
        "column_name": column,
        "test_metadata": {"name": name, "kwargs": kwargs},
        "depends_on": {"nodes": [f"model.{PACKAGE}.{model}"]},
    }


def _manifest() -> dict:
    """A passing manifest: core `lib`, one_offs `a_table` (report a) and `b_table` (report b), staging `stg_x`."""
    nodes = [
        _model("lib", ["core"]),
        _model("a_table", ["one_off"], question="a"),
        _model("b_table", ["one_off"], question="b"),
        _model("stg_x", [], path="staging"),
        _test("lib", "unique", "id"),
        _test("lib", "not_null", "id"),
        _test("lib", "accepted_values", "kind"),
    ]
    return {"nodes": {node["unique_id"]: node for node in nodes}}


LOADERS = {
    "load_lib": frozenset({"lib"}),
    "load_a": frozenset({"a_table"}),
    "load_b": frozenset({"b_table"}),
}


def _report(root: Path, folder: str, code: str) -> None:
    path = root / "reports" / folder / "report.qmd"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {folder}\n---\n\n```{{python}}\n#| echo: false\n{code}\n```\n\nText `{{python}} 1`.\n")


def _module(root: Path, dotted: str, code: str) -> None:
    path = root / "src" / Path(*dotted.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.relative_to(root / "src").parents:
        if str(parent) != ".":
            (root / "src" / parent / "__init__.py").touch()
    path.write_text(code)


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    """Reports a and b, each reading its own one_off through an analysis module, plus `lib`."""
    _module(tmp_path, "f1_analytics.analysis.data", "def load_lib(): ...\ndef load_a(): ...\ndef load_b(): ...\n")
    _module(tmp_path, "f1_analytics.analysis.a_logic", "from f1_analytics.analysis.data import load_a\n")
    _module(tmp_path, "f1_analytics.analysis.b_logic", "from f1_analytics.analysis import data\nx = data.load_b\n")
    _report(tmp_path, "a", "from f1_analytics.analysis import a_logic\nfrom f1_analytics.analysis.data import load_lib")
    _report(tmp_path, "b", "from f1_analytics.analysis import b_logic")
    return tmp_path


def _check(manifest: dict, root: Path, loaders=LOADERS) -> list[str]:
    return breaches(manifest, root, loaders=loaders)


def test_synthetic_tree_passes(tree):
    assert _check(_manifest(), tree) == []


@pytest.mark.parametrize("tags", [[], ["core", "one_off"], ["core", "nightly"]])
def test_a_mart_without_exactly_one_tag_fails_rule_1(tree, tags):
    manifest = _manifest()
    node = manifest["nodes"]["model.f1_analytics.lib"]
    node["tags"] = node["config"]["tags"] = tags
    found = [line for line in _check(manifest, tree) if line.startswith("rule 1")]
    assert len(found) == 1 and "`lib`" in found[0]


def test_an_orphan_one_off_fails_rule_2(tree):
    manifest = _manifest()
    node = manifest["nodes"]["model.f1_analytics.a_table"]
    node["meta"] = node["config"]["meta"] = {"question": "no-such-folder"}
    found = _check(manifest, tree)
    assert any(line.startswith("rule 2") and "`a_table`" in line and "no-such-folder" in line for line in found)


def test_a_report_reading_another_questions_one_off_fails_rule_3(tree):
    _module(tree, "f1_analytics.analysis.a_logic", "from f1_analytics.analysis.data import load_a, load_b\n")
    found = _check(_manifest(), tree)
    assert found == ["rule 3: report `a` reads `b_table`, a one_off mart of `b`"]


def test_reads_are_followed_through_nested_and_relative_imports(tree):
    _module(tree, "f1_analytics.analysis.pkg.inner", "from ..data import load_b\n")
    _module(tree, "f1_analytics.analysis.a_logic", "from f1_analytics.analysis.pkg import inner\n")
    assert _check(_manifest(), tree) == ["rule 3: report `a` reads `b_table`, a one_off mart of `b`"]


@pytest.mark.parametrize("where", ["report", "module"])
@pytest.mark.parametrize("sql", [
    "con.execute('x')", "q = \'\'\'SELECT *\\n  FROM lib\'\'\'", "q = \'\'\'select *\\n  from lib\'\'\'",
    "con.query('x')", "con.table('lib')", "con.view('lib')", "pd.read_sql('x', con)",
])
def test_stray_sql_outside_data_py_fails_rule_3(tree, where, sql):
    if where == "report":
        _report(tree, "b", f"from f1_analytics.analysis import b_logic\n{sql}")
        culprit = "reports/b/report.qmd"
    else:
        _module(tree, "f1_analytics.analysis.b_logic", f"from f1_analytics.analysis import data\nx = data.load_b\n{sql}\n")
        culprit = "src/f1_analytics/analysis/b_logic.py"
    found = _check(_manifest(), tree)
    assert any(line.startswith("rule 3") and culprit in line for line in found), found


@pytest.mark.parametrize("sql", ["con.execute('x')", "q = \'\'\'SELECT *\\n  FROM staging.stg_x\'\'\'"])
def test_sql_in_explore_qmd_is_exempt_but_not_in_report_qmd(tree, sql):
    explore = tree / "reports" / "b" / "explore.qmd"
    explore.write_text(f"---\ntitle: explore\n---\n\n```{{python}}\n{sql}\n```\n")
    assert _check(_manifest(), tree) == []
    _report(tree, "b", f"from f1_analytics.analysis import b_logic\n{sql}")
    found = _check(_manifest(), tree)
    assert found == ["rule 3: reports/b/report.qmd holds SQL; all SQL lives in src/f1_analytics/analysis/data.py"]


def test_sql_in_data_py_is_allowed(tree):
    _module(tree, "f1_analytics.analysis.data", "def load_lib(con): return con.execute('SELECT * FROM lib')\n")
    assert _check(_manifest(), tree) == []


def test_a_loader_declaring_a_staging_model_fails_rule_3(tree):
    loaders = {**LOADERS, "load_lib": frozenset({"lib", "stg_x"})}
    found = _check(_manifest(), tree, loaders)
    assert any(line.startswith("rule 3") and "`load_lib`" in line and "`stg_x`" in line for line in found)
    assert any(line.startswith("rule 3") and "report `a`" in line and "`stg_x`" in line for line in found)


def test_a_loader_without_reads_fails_rule_3(tree):
    found = _check(_manifest(), tree, {**LOADERS, "load_lib": None})
    assert any(line.startswith("rule 3") and "`load_lib`" in line for line in found)


def test_an_undocumented_core_mart_or_column_fails_rule_4(tree):
    manifest = _manifest()
    node = manifest["nodes"]["model.f1_analytics.lib"]
    node["description"] = " "
    node["columns"]["kind"]["description"] = ""
    found = [line for line in _check(manifest, tree) if line.startswith("rule 4")]
    assert found == [
        "rule 4: core mart `lib` has no description",
        "rule 4: core mart `lib` column `kind` has no description",
    ]


def test_a_built_column_missing_from_the_yml_fails_rule_4(tree):
    found = breaches(_manifest(), tree, loaders=LOADERS, columns={"lib": ["id", "kind", "extra"]})
    assert found == ["rule 4: core mart `lib` column `extra` is not in the yml (no description)"]


def test_one_off_marts_need_no_docs_grain_or_values(tree):
    manifest = _manifest()
    node = manifest["nodes"]["model.f1_analytics.a_table"]
    node["description"] = ""
    node["columns"]["id"]["description"] = ""
    assert _check(manifest, tree) == []


@pytest.mark.parametrize("drop", ["unique", "not_null", "both"])
def test_a_core_mart_without_a_grain_test_fails_rule_5(tree, drop):
    manifest = _manifest()
    for name in (["unique", "not_null"] if drop == "both" else [drop]):
        del manifest["nodes"][f"test.f1_analytics.{name}_lib_id"]
    found = [line for line in _check(manifest, tree) if line.startswith("rule 5")]
    assert len(found) == 1 and "`lib`" in found[0]


def test_unique_combination_with_not_null_key_passes_rule_5(tree):
    manifest = _manifest()
    del manifest["nodes"]["test.f1_analytics.unique_lib_id"]
    combo = _test("lib", "unique_combination", columns=["id", "kind"])
    manifest["nodes"][combo["unique_id"]] = combo
    assert [line for line in _check(manifest, tree) if line.startswith("rule 5")] == [
        "rule 5: core mart `lib` key columns ['kind'] have no not_null test"
    ]
    not_null = _test("lib", "not_null", "kind")
    manifest["nodes"][not_null["unique_id"]] = not_null
    assert _check(manifest, tree) == []


def test_a_category_column_without_accepted_values_fails_rule_6(tree):
    manifest = _manifest()
    del manifest["nodes"]["test.f1_analytics.accepted_values_lib_kind"]
    assert [line for line in _check(manifest, tree) if line.startswith("rule 6")] == [
        "rule 6: core mart `lib` category column `kind` has no accepted_values test"
    ]


def test_a_core_mart_on_a_one_off_fails_rule_7(tree):
    manifest = _manifest()
    manifest["nodes"]["model.f1_analytics.lib"]["depends_on"]["nodes"] = [
        "model.f1_analytics.stg_x", "model.f1_analytics.a_table",
    ]
    assert [line for line in _check(manifest, tree) if line.startswith("rule 7")] == [
        "rule 7: core mart `lib` depends on one_off mart `a_table`"
    ]


def test_the_real_loaders_are_used_by_default(repo_manifest):
    """With no loaders passed, a report reaching load_pit_stop_tables is judged on its ten tables."""
    manifest = copy.deepcopy(repo_manifest)
    node = manifest["nodes"]["model.f1_analytics.pit_stops"]
    node["meta"] = node["config"]["meta"] = {"question": "2026-10-11-championship-leader-conversion"}
    found = breaches(manifest, config.PROJECT_ROOT)
    assert found == [
        f"rule 3: report `{COTA}` reads `pit_stops`, a one_off mart of `2026-10-11-championship-leader-conversion`"
    ]


def test_a_one_off_naming_a_folder_without_a_report_fails_rule_2(tree):
    (tree / "reports" / "golden").mkdir()
    (tree / "reports" / "golden" / "old.pdf").write_bytes(b"%PDF")
    manifest = _manifest()
    node = manifest["nodes"]["model.f1_analytics.a_table"]
    node["meta"] = node["config"]["meta"] = {"question": "golden"}
    found = _check(manifest, tree)
    assert any(line.startswith("rule 2") and "`a_table`" in line and "golden" in line for line in found)


def test_imports_outside_the_analysis_package_are_followed(tree):
    _module(tree, "f1_analytics.scenarios", "from f1_analytics.analysis.data import load_b\n")
    _report(tree, "a", "from f1_analytics import scenarios")
    assert _check(_manifest(), tree) == ["rule 3: report `a` reads `b_table`, a one_off mart of `b`"]


def test_a_loader_named_only_in_an_inline_expression_is_read(tree):
    path = tree / "reports" / "a" / "report.qmd"
    path.write_text(path.read_text() + "\nRows: `{python} data.load_b()`.\n")
    assert _check(_manifest(), tree) == ["rule 3: report `a` reads `b_table`, a one_off mart of `b`"]


def test_sql_in_a_nested_report_file_fails_rule_3(tree):
    nested = tree / "reports" / "b" / "parts" / "extra.qmd"
    nested.parent.mkdir(parents=True)
    nested.write_text("```{python}\nx = con.execute('x')\n```\n")
    found = _check(_manifest(), tree)
    assert any(line.startswith("rule 3") and "reports/b/parts/extra.qmd" in line for line in found), found
