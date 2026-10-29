"""The mart check: conventions rules 1-7 over a dbt manifest and the repo tree.

`breaches(manifest, repo_root)` returns one line per breach, each naming the
mart, column or file at fault; an empty list means the repo passes. Every
helper is a pure function of the manifest (a parsed `manifest.json`), the
files under `repo_root` and, for rule 3, the tables each `analysis/data.py`
loader declares with `@reads`. `tests/test_mart_check.py` runs it on a fresh
`dbt parse`.

Reports live in topic folders (`reports/<topic>/recurring/`,
`reports/<topic>/editions/<name>/`). Rules 2 and 3 work per topic folder: a
`one_off` mart's `meta.question` names one, and every `.qmd` and `.py` at any
depth under it is that topic's report code.

The stray-SQL part of rule 3 skips files named `explore.qmd`: a report's
exploration may query raw and staging tables directly (conventions,
"Exploration done-criteria"); `report.qmd`, `data.py` loaders and analysis
modules stay strict.

Rule 3 follows imports at module level, so it can fail wrongly but never pass
wrongly: a report reaches every `f1_analytics` module its `{python}` cells
(and inline `{python}` expressions) import, and every module those import in turn; it reads the union of
`fn.reads` of every loader named anywhere in a reached module.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, Mapping

CORE = "core"
ONE_OFF = "one_off"
MART_TAGS = frozenset({CORE, ONE_OFF})

ROOT_PACKAGE = "f1_analytics"
ANALYSIS_PACKAGE = f"{ROOT_PACKAGE}.analysis"
DATA_MODULE = f"{ANALYSIS_PACKAGE}.data"
DATA_FILE = Path("src/f1_analytics/analysis/data.py")
ANALYSIS_DIR = Path("src/f1_analytics/analysis")
REPORTS_DIR = Path("reports")
EXPLORE_FILE = "explore.qmd"  # exempt from the stray-SQL part of rule 3

# SQL outside data.py: a DuckDB or pandas SQL call, or a SELECT ... FROM
# (any case, across lines).
SQL_PATTERNS = (
    re.compile(r"\.(?:execute|sql|query|table|view)\("),
    re.compile(r"\bread_sql"),
    re.compile(r"\bselect\b[\s\S]{0,500}?\bfrom\b", re.IGNORECASE),
)
PYTHON_CELL = re.compile(r"^```\{python\}[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
INLINE_PYTHON = re.compile(r"(?<!`)`\{python\}[ \t]+([^`\n]+)`")


# --------------------------------------------------------------------------
# manifest helpers
# --------------------------------------------------------------------------


def marts(manifest: Mapping) -> dict[str, dict]:
    """Every model under `models/marts/`, by name."""
    return {
        node["name"]: node
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model"
        and Path(node.get("original_file_path", "")).parts[:2] == ("models", "marts")
    }


def _meta(entry: Mapping) -> dict:
    return {**(entry.get("meta") or {}), **((entry.get("config") or {}).get("meta") or {})}


def _all_tags(node: Mapping) -> set[str]:
    return set(node.get("tags") or []) | set((node.get("config") or {}).get("tags") or [])


def _mart_tags(node: Mapping) -> set[str]:
    return _all_tags(node) & MART_TAGS


def _tag(node: Mapping) -> str | None:
    """`core` or `one_off` when that is the mart's only tag, else None."""
    tags = _all_tags(node)
    return next(iter(tags)) if len(tags) == 1 and tags <= MART_TAGS else None


def _core(all_marts: Mapping[str, dict]) -> dict[str, dict]:
    return {name: node for name, node in all_marts.items() if CORE in _mart_tags(node)}


def _tests_by_model(manifest: Mapping) -> dict[str, list[dict]]:
    """Generic tests by the unique_id of the model they test."""
    tests: dict[str, list[dict]] = {}
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "test" or not node.get("test_metadata"):
            continue
        attached = node.get("attached_node") or next(iter(node.get("depends_on", {}).get("nodes", [])), None)
        if attached:
            tests.setdefault(attached, []).append(node)
    return tests


def _column_tests(tests: Iterable[Mapping], test_name: str) -> set[str]:
    """Lower-cased columns that carry the generic test `test_name`."""
    return {
        str(test.get("column_name") or test["test_metadata"].get("kwargs", {}).get("column_name")).lower()
        for test in tests
        if test["test_metadata"].get("name") == test_name
        and (test.get("column_name") or test["test_metadata"].get("kwargs", {}).get("column_name"))
    }


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------


def rule_1_one_tag(all_marts: Mapping[str, dict]) -> list[str]:
    """Every mart carries exactly one tag, `core` or `one_off`, and no other."""
    return [
        f"rule 1: mart `{name}` has tags {sorted(_all_tags(node))}; it needs exactly one tag, core or one_off"
        for name, node in sorted(all_marts.items())
        if _tag(node) is None
    ]


def rule_2_question_exists(all_marts: Mapping[str, dict], repo_root: Path) -> list[str]:
    """A `one_off` mart's `meta.question` names an existing `reports/` topic folder."""
    reports = {path.name for path in _report_dirs(repo_root)}
    found = []
    for name, node in sorted(all_marts.items()):
        if ONE_OFF not in _mart_tags(node):
            continue
        question = _meta(node).get("question")
        if not question:
            found.append(f"rule 2: one_off mart `{name}` has no meta.question")
        elif question not in reports:
            found.append(
                f"rule 2: one_off mart `{name}` names meta.question `{question}`, which is not a reports/ topic folder with a .qmd"
            )
    return found


def stray_sql(repo_root: Path) -> list[str]:
    """Rule 3: SQL in a report or in an analysis module other than data.py.

    Files named `explore.qmd` are exempt: exploration may query raw and
    staging tables directly. `report.qmd`, `data.py` and analysis modules stay strict.
    """
    files = sorted((repo_root / ANALYSIS_DIR).rglob("*.py")) if (repo_root / ANALYSIS_DIR).is_dir() else []
    files = [path for path in files if path != repo_root / DATA_FILE]
    for pattern in ("*.qmd", "*.py"):
        files += sorted((repo_root / REPORTS_DIR).rglob(pattern))
    files = [path for path in files if path.name != EXPLORE_FILE]
    found = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in SQL_PATTERNS):
            found.append(f"rule 3: {path.relative_to(repo_root)} holds SQL; all SQL lives in {DATA_FILE}")
    return found


def loader_declarations(
    loaders: Mapping[str, frozenset[str] | None], all_marts: Mapping[str, dict]
) -> list[str]:
    """Rule 3: every loader declares its tables, and each is a mart."""
    found = []
    for loader, tables in sorted(loaders.items()):
        if tables is None:
            found.append(f"rule 3: loader `{loader}` in {DATA_FILE} declares no tables (`@reads`)")
            continue
        for table in sorted(tables):
            if table not in all_marts:
                found.append(f"rule 3: loader `{loader}` reads `{table}`, which is not a mart (models/marts/)")
    return found


def _module_file(repo_root: Path, module: str) -> Path | None:
    base = repo_root / "src" / Path(*module.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return path
    return None


def _in_project(module: str) -> bool:
    return module == ROOT_PACKAGE or module.startswith(ROOT_PACKAGE + ".")


def _imported_modules(tree: ast.AST, current: str | None, is_package: bool) -> set[str]:
    """Every module name an import in `tree` could load (submodules of `from x import y` included)."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if current is None:
                    continue
                parts = current.split(".") if is_package else current.split(".")[:-1]
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            found.add(base)
            found |= {f"{base}.{alias.name}" for alias in node.names}
    # Importing a.b.c runs a/__init__ and a/b/__init__ too.
    with_parents = set(found)
    for module in found:
        parts = module.split(".")
        with_parents |= {".".join(parts[:i]) for i in range(1, len(parts))}
    return with_parents


def _names(tree: ast.AST) -> set[str]:
    """Every identifier `tree` names: variables, attributes and imported names."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
            if node.asname:
                names.add(node.asname)
    return names


def _report_code(path: Path) -> list[str]:
    """The Python sources of a report file: the whole .py, or each .qmd cell and inline expression."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return [text]
    return ["\n".join(PYTHON_CELL.findall(text))] + [f"({expr.strip()})" for expr in INLINE_PYTHON.findall(text)]


def report_reads(repo_root: Path, report_dir: Path, loaders: Mapping[str, frozenset[str] | None]) -> tuple[set[str], list[str]]:
    """The tables a topic folder's reports read (every .qmd and .py at any depth), and any file the check could not parse."""
    problems: list[str] = []
    trees: list[ast.AST] = []
    for path in sorted(report_dir.rglob("*.qmd")) + sorted(report_dir.rglob("*.py")):
        for code in _report_code(path):
            try:
                trees.append(ast.parse(code))
            except SyntaxError as error:
                problems.append(
                    f"rule 3: {path.relative_to(repo_root)} has python the check cannot parse ({error.msg})"
                )
    named: set[str] = set()
    seen: set[str] = set()
    queue: list[tuple[ast.AST, str | None, bool]] = [(tree, None, False) for tree in trees]
    while queue:
        tree, current, is_package = queue.pop()
        if current != DATA_MODULE:
            # data.py defines every loader; naming them there is not reading them.
            named |= _names(tree)
        for module in sorted(_imported_modules(tree, current, is_package)):
            if module in seen or not _in_project(module):
                continue
            seen.add(module)
            path = _module_file(repo_root, module)
            if path is None:
                continue
            try:
                queue.append((ast.parse(path.read_text(encoding="utf-8")), module, path.name == "__init__.py"))
            except SyntaxError as error:
                problems.append(f"rule 3: {path.relative_to(repo_root)} cannot be parsed ({error.msg})")
    tables = {table for loader, declared in loaders.items() if loader in named for table in (declared or ())}
    return tables, problems


def _report_dirs(repo_root: Path) -> list[Path]:
    """The topic folders: each directory directly under `reports/` with a `.qmd` at any depth."""
    root = repo_root / REPORTS_DIR
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and any(path.rglob("*.qmd")))


def rule_3_reads(
    all_marts: Mapping[str, dict], repo_root: Path, loaders: Mapping[str, frozenset[str] | None]
) -> list[str]:
    """A topic's reports read only `core` marts or the topic's own `one_off` marts, through data.py loaders only."""
    found = stray_sql(repo_root) + loader_declarations(loaders, all_marts)
    for report_dir in _report_dirs(repo_root):
        folder = report_dir.name
        tables, problems = report_reads(repo_root, report_dir, loaders)
        found += problems
        for table in sorted(tables):
            node = all_marts.get(table)
            if node is None:
                found.append(f"rule 3: topic `{folder}` reads `{table}`, which is not a mart")
                continue
            tag = _tag(node)
            if tag == CORE:
                continue
            if tag == ONE_OFF and _meta(node).get("question") == folder:
                continue
            owner = f"a one_off mart of `{_meta(node).get('question')}`" if tag == ONE_OFF else "not tagged core"
            found.append(f"rule 3: topic `{folder}` reads `{table}`, {owner}")
    return found


def rule_4_documented(
    core_marts: Mapping[str, dict], columns: Mapping[str, Iterable[str]] | None = None
) -> list[str]:
    """A core mart and every column have descriptions.

    `columns` (actual columns by mart, e.g. from the built DuckDB file) also
    catches a column the yml does not list at all.
    """
    found = []
    for name, node in sorted(core_marts.items()):
        if not (node.get("description") or "").strip():
            found.append(f"rule 4: core mart `{name}` has no description")
        documented = {}
        for column_name, column in (node.get("columns") or {}).items():
            documented[column_name.lower()] = bool((column.get("description") or "").strip())
            if not documented[column_name.lower()]:
                found.append(f"rule 4: core mart `{name}` column `{column_name}` has no description")
        for column_name in (columns or {}).get(name, ()):
            if column_name.lower() not in documented:
                found.append(f"rule 4: core mart `{name}` column `{column_name}` is not in the yml (no description)")
    return found


def rule_5_grain(core_marts: Mapping[str, dict], tests: Mapping[str, list[dict]]) -> list[str]:
    """A core mart's grain is tested: `unique` (or `unique_combination`) plus `not_null` on the key."""
    found = []
    for name, node in sorted(core_marts.items()):
        model_tests = tests.get(node["unique_id"], [])
        not_null = _column_tests(model_tests, "not_null")
        single = _column_tests(model_tests, "unique") & not_null
        combined = [
            [str(column).lower() for column in test["test_metadata"].get("kwargs", {}).get("columns") or []]
            for test in model_tests
            if test["test_metadata"].get("name") == "unique_combination"
        ]
        if single or any(key and set(key) <= not_null for key in combined):
            continue
        if combined:
            missing = sorted(set().union(*map(set, combined)) - not_null)
            found.append(f"rule 5: core mart `{name}` key columns {missing} have no not_null test")
        else:
            found.append(f"rule 5: core mart `{name}` has no grain test (unique or unique_combination plus not_null)")
    return found


def rule_6_categories(core_marts: Mapping[str, dict], tests: Mapping[str, list[dict]]) -> list[str]:
    """A core column flagged `meta: {category: true}` has `accepted_values`."""
    found = []
    for name, node in sorted(core_marts.items()):
        accepted = _column_tests(tests.get(node["unique_id"], []), "accepted_values")
        for column_name, column in sorted((node.get("columns") or {}).items()):
            if _meta(column).get("category") is True and column_name.lower() not in accepted:
                found.append(f"rule 6: core mart `{name}` category column `{column_name}` has no accepted_values test")
    return found


def rule_7_no_one_off_dependency(core_marts: Mapping[str, dict], all_marts: Mapping[str, dict]) -> list[str]:
    """A core mart depends on no `one_off` mart."""
    one_off_ids = {node["unique_id"]: name for name, node in all_marts.items() if ONE_OFF in _mart_tags(node)}
    return [
        f"rule 7: core mart `{name}` depends on one_off mart `{one_off_ids[parent]}`"
        for name, node in sorted(core_marts.items())
        for parent in sorted(node.get("depends_on", {}).get("nodes", []))
        if parent in one_off_ids and parent != node["unique_id"]
    ]


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def data_loaders() -> dict[str, frozenset[str] | None]:
    """`fn.reads` of every public `load_*` function in analysis/data.py (None when undeclared)."""
    import inspect

    from f1_analytics.analysis import data

    return {
        name: getattr(fn, "reads", None)
        for name, fn in inspect.getmembers(data, inspect.isfunction)
        if name.startswith("load_") and fn.__module__ == data.__name__
    }


def breaches(
    manifest: dict,
    repo_root: Path,
    loaders: Mapping[str, frozenset[str] | None] | None = None,
    columns: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    """Every breach of conventions rules 1-7; empty when the repo passes.

    `loaders` defaults to the real `analysis/data.py` loaders; `columns`
    (optional) lists each mart's actual columns for rule 4.
    """
    repo_root = Path(repo_root)
    all_marts = marts(manifest)
    core_marts = _core(all_marts)
    tests = _tests_by_model(manifest)
    return [
        *rule_1_one_tag(all_marts),
        *rule_2_question_exists(all_marts, repo_root),
        *rule_3_reads(all_marts, repo_root, data_loaders() if loaders is None else loaders),
        *rule_4_documented(core_marts, columns),
        *rule_5_grain(core_marts, tests),
        *rule_6_categories(core_marts, tests),
        *rule_7_no_one_off_dependency(core_marts, all_marts),
    ]
