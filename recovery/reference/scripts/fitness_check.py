#!/usr/bin/env python3
"""Mechanically check the project's process/documentation invariants.

This is the documentation-layer equivalent of
src/f1_analytics/validation/checks.py: instead of null-rate and
referential-integrity checks against DuckDB tables, it runs required-file,
status-enum, supersede-reference, and layout checks against docs/ so the
"standing fitness check" in docs/terminal_protocol.md is run, not just read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "AGENTS.md",
    "PROJECT.md",
    "docs/project_profile.md",
    "docs/active_context.md",
    "docs/decisions.md",
    "docs/questions.md",
    "docs/backlog.md",
    "docs/run_log.md",
    "docs/inbox/README.md",
    "docs/asset_inventory.md",
    "docs/architecture_operating_model.md",
    "docs/architecture_principles.md",
    "docs/analysis_output_standards.md",
    "docs/terminal_protocol.md",
    "docs/terminal_roles/planning.md",
    "docs/terminal_roles/execution.md",
    "docs/terminal_roles/command.md",
    "docs/handoffs/drafts",
    "docs/handoffs/approved",
    "docs/implementation_notes",
]

HANDOFF_STATUSES = {"Draft", "Needs Revision", "Approved", "Completed", "Rejected", "Superseded"}
DRAFT_FOLDER_STATUSES = {"Draft", "Needs Revision"}
APPROVED_FOLDER_STATUSES = {"Approved", "Completed", "Rejected", "Superseded"}

STATUS_LINE_RE = re.compile(r"^[ \t]*Status:\s*(.+)$", re.MULTILINE)
SUPERSEDE_RE = re.compile(r"^[ \t]*(?:Supersedes|Superseded by):\s*(.+)$", re.MULTILINE)
REVISION_NOTE_RE = re.compile(r"^##\s*Revision Note", re.MULTILINE)
DECISION_REQUIRED_FIELDS = ["Decision:", "Rationale:", "Tradeoffs:", "Status:"]
ROLE_DOC_ORDER = ["planning", "execution", "command"]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check_required_docs() -> CheckResult:
    missing = [p for p in REQUIRED_DOCS if not (PROJECT_ROOT / p).exists()]
    if missing:
        return CheckResult("required_docs_exist", False, f"missing: {', '.join(missing)}")
    return CheckResult("required_docs_exist", True)


def _read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _protocol_section(heading: str) -> str:
    text = _read_text("docs/terminal_protocol.md")
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _role_doc_name(role_slug: str) -> str:
    text = _read_text(f"docs/terminal_roles/{role_slug}.md")
    match = re.search(r"^# (.+)$", text, flags=re.MULTILINE)
    heading = match.group(1).strip() if match else role_slug.title()
    return re.sub(r"(?: Terminal)? Role$", "", heading).strip()


def check_required_docs_matches_protocol_list() -> CheckResult:
    section = _protocol_section("Source of Truth / Standing Fitness Check")
    listed_paths = re.findall(r"`([^`]+)`", section)

    missing: list[str] = []
    for required in REQUIRED_DOCS:
        covered = False
        for listed in listed_paths:
            normalized = listed.rstrip("/")
            if listed.endswith("/"):
                covered = required == normalized or required.startswith(f"{normalized}/")
            else:
                covered = required == listed
            if covered:
                break
        if not covered:
            missing.append(required)

    if missing:
        return CheckResult(
            "required_docs_match_protocol_list",
            False,
            f"protocol list does not cover: {', '.join(missing)}",
        )
    return CheckResult("required_docs_match_protocol_list", True)


def _iter_handoff_files():
    handoff_dir = PROJECT_ROOT / "docs" / "handoffs"
    for sub in ("drafts", "approved"):
        folder = handoff_dir / sub
        if folder.exists():
            yield from sorted(folder.glob("*.md"))


def check_terminal_names_consistent() -> CheckResult:
    canonical_names = [_role_doc_name(role) for role in ROLE_DOC_ORDER]
    protocol = _read_text("docs/terminal_protocol.md")
    active_context = _read_text("docs/active_context.md")

    problems: list[str] = []

    protocol_names = re.findall(r"^### Terminal \d+: (.+)$", protocol, flags=re.MULTILINE)
    if protocol_names != canonical_names:
        problems.append(f"protocol headings={protocol_names}, expected={canonical_names}")

    current_model = re.search(
        r"^## Current Operating Model\s*$\n(.*?)(?=^## |\Z)",
        active_context,
        flags=re.MULTILINE | re.DOTALL,
    )
    operating_names = []
    if current_model:
        operating_names = re.findall(r"^\d+\.\s+([A-Za-z ]+?) terminal\b", current_model.group(1), flags=re.MULTILINE)
    if operating_names != canonical_names:
        problems.append(f"active_context names={operating_names}, expected={canonical_names}")

    if problems:
        return CheckResult("terminal_names_consistent", False, "; ".join(problems))
    return CheckResult("terminal_names_consistent", True)


def check_handoff_status_enum_consistent() -> CheckResult:
    readme = _read_text("docs/handoffs/README.md")
    protocol = _read_text("docs/terminal_protocol.md")

    status_section = re.search(
        r"^## Status\s*$\n(.*?)(?=^## |\Z)",
        readme,
        flags=re.MULTILINE | re.DOTALL,
    )
    readme_statuses = set(re.findall(r"^\* `([^`]+)`", status_section.group(1), flags=re.MULTILINE)) if status_section else set()

    problems: list[str] = []
    if readme_statuses != HANDOFF_STATUSES:
        problems.append(
            f"README statuses={sorted(readme_statuses)}, expected={sorted(HANDOFF_STATUSES)}"
        )

    if re.search(r"^\* `(?:Draft|Needs Revision|Approved|Completed|Rejected|Superseded)`", protocol, flags=re.MULTILINE):
        problems.append("docs/terminal_protocol.md still itemizes handoff statuses")

    if problems:
        return CheckResult("handoff_status_enum_consistent", False, "; ".join(problems))
    return CheckResult("handoff_status_enum_consistent", True)


def check_role_docs_have_required_inputs() -> CheckResult:
    required_refs = {"AGENTS.md", "PROJECT.md", "docs/active_context.md"}
    problems: list[str] = []

    for role in ROLE_DOC_ORDER:
        text = _read_text(f"docs/terminal_roles/{role}.md")
        match = re.search(
            r"^## (?:Required Inputs|Source of Truth)\s*$\n(.*?)(?=^## |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            problems.append(f"{role}.md: missing Required Inputs/Source of Truth section")
            continue
        section = match.group(1)
        missing = sorted(ref for ref in required_refs if ref not in section)
        if missing:
            problems.append(f"{role}.md: missing {', '.join(missing)}")

    if problems:
        return CheckResult("role_docs_have_required_inputs", False, "; ".join(problems))
    return CheckResult("role_docs_have_required_inputs", True)


def check_prompts_point_to_role_docs() -> CheckResult:
    expected = {
        "docs/prompts/planning/session_prompt.txt": "docs/terminal_roles/planning.md",
        "docs/prompts/execution_prompt.txt": "docs/terminal_roles/execution.md",
        "docs/prompts/command_prompt.txt": "docs/terminal_roles/command.md",
    }
    problems: list[str] = []
    for prompt_path, role_path in expected.items():
        if role_path not in _read_text(prompt_path):
            problems.append(f"{prompt_path}: missing pointer to {role_path}")

    if problems:
        return CheckResult("prompts_point_to_role_docs", False, "; ".join(problems))
    return CheckResult("prompts_point_to_role_docs", True)


def check_terminal_protocol_sections_stay_pointers() -> CheckResult:
    protocol = _read_text("docs/terminal_protocol.md")
    problems: list[str] = []

    if "Use this terminal for:" in protocol:
        problems.append("docs/terminal_protocol.md regrew a 'Use this terminal for:' heading")

    for idx, role in enumerate(ROLE_DOC_ORDER, start=1):
        match = re.search(
            rf"^### Terminal {idx}: [^\n]*\n(.*?)(?=^### Terminal {idx + 1}:|^## |\Z)",
            protocol,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            problems.append(f"Terminal {idx} section missing")
            continue
        expected_pointer = f"docs/terminal_roles/{role}.md"
        if expected_pointer not in match.group(1):
            problems.append(f"Terminal {idx} section missing pointer to {expected_pointer}")

    if problems:
        return CheckResult("terminal_protocol_sections_are_pointers", False, "; ".join(problems))
    return CheckResult("terminal_protocol_sections_are_pointers", True)


def check_handoff_statuses() -> CheckResult:
    problems: list[str] = []
    for folder_name, expected_statuses in (
        ("drafts", DRAFT_FOLDER_STATUSES),
        ("approved", APPROVED_FOLDER_STATUSES),
    ):
        folder = PROJECT_ROOT / "docs" / "handoffs" / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            match = STATUS_LINE_RE.search(text)
            rel = path.relative_to(PROJECT_ROOT)
            if not match:
                problems.append(f"{rel}: missing Status: line")
                continue
            status = match.group(1).strip()
            if status not in HANDOFF_STATUSES:
                problems.append(f"{rel}: invalid status '{status}'")
            elif status not in expected_statuses:
                problems.append(f"{rel}: status '{status}' does not belong in {folder_name}/")
            if status == "Needs Revision" and not REVISION_NOTE_RE.search(text):
                problems.append(f"{rel}: status 'Needs Revision' but no Revision Note section found")

    if problems:
        return CheckResult("handoff_status_validity", False, "; ".join(problems))
    return CheckResult("handoff_status_validity", True)


def check_supersede_references() -> CheckResult:
    known_handoff_names = {p.name for p in _iter_handoff_files()}
    problems: list[str] = []

    for path in _iter_handoff_files():
        text = path.read_text(encoding="utf-8")
        for target in SUPERSEDE_RE.findall(text):
            filename = target.strip().strip("`").split()[0] if target.strip() else ""
            if filename and filename not in known_handoff_names:
                problems.append(f"{path.relative_to(PROJECT_ROOT)}: references missing handoff '{filename}'")

    decisions_path = PROJECT_ROOT / "docs" / "decisions.md"
    if decisions_path.exists():
        text = decisions_path.read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
        for target in SUPERSEDE_RE.findall(text):
            target = target.strip().strip("`")
            if target and not any(target in heading for heading in headings):
                problems.append(f"docs/decisions.md: references missing decision '{target}'")

    if problems:
        return CheckResult("supersede_references_valid", False, "; ".join(problems))
    return CheckResult("supersede_references_valid", True)


def check_prompt_layout() -> CheckResult:
    problems: list[str] = []
    docs_dir = PROJECT_ROOT / "docs"

    stray = sorted(p.name for p in docs_dir.glob("*prompt*") if p.is_file())
    if stray:
        problems.append(f"prompt-like file(s) outside docs/prompts/: {', '.join(stray)}")

    planning_dir = docs_dir / "prompts" / "planning"
    if planning_dir.exists():
        active = [p for p in planning_dir.glob("*.txt") if p.is_file()]
        if len(active) != 1:
            names = ", ".join(p.name for p in active) or "none"
            problems.append(f"expected exactly 1 active planning prompt template, found {len(active)}: {names}")

    if problems:
        return CheckResult("no_stray_prompt_files", False, "; ".join(problems))
    return CheckResult("no_stray_prompt_files", True)


def check_decision_entries() -> CheckResult:
    decisions_path = PROJECT_ROOT / "docs" / "decisions.md"
    if not decisions_path.exists():
        return CheckResult("decision_entries_well_formed", False, "docs/decisions.md missing")

    text = decisions_path.read_text(encoding="utf-8")
    entries = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    problems = []
    for entry in entries:
        title = entry.splitlines()[0].strip()
        missing = [field for field in DECISION_REQUIRED_FIELDS if field not in entry]
        if missing:
            problems.append(f"'{title}': missing {', '.join(missing)}")

    if problems:
        return CheckResult("decision_entries_well_formed", False, "; ".join(problems))
    return CheckResult("decision_entries_well_formed", True)


def check_completed_handoffs_not_approved() -> CheckResult:
    """Flag approved handoffs that already have implementation evidence."""
    notes_dir = PROJECT_ROOT / "docs" / "implementation_notes"
    note_ids = {
        match.group(1)
        for path in notes_dir.glob("*.md")
        if (match := re.match(r"^(\d+)-", path.name))
    }
    problems: list[str] = []

    approved_dir = PROJECT_ROOT / "docs" / "handoffs" / "approved"
    for path in sorted(approved_dir.glob("*.md")):
        id_match = re.match(r"^(\d+)-", path.name)
        if not id_match or id_match.group(1) not in note_ids:
            continue
        status_match = STATUS_LINE_RE.search(path.read_text(encoding="utf-8"))
        if status_match and status_match.group(1).strip() == "Approved":
            problems.append(str(path.relative_to(PROJECT_ROOT)))

    if problems:
        return CheckResult(
            "completed_handoffs_not_approved",
            False,
            f"implementation note exists but status is Approved: {', '.join(problems)}",
        )
    return CheckResult("completed_handoffs_not_approved", True)


def check_inbox_items_triaged() -> CheckResult:
    inbox_dir = PROJECT_ROOT / "docs" / "inbox"
    if not inbox_dir.exists():
        return CheckResult("inbox_items_triaged", False, "docs/inbox missing")

    allowed_names = {"README.md", "processed"}
    untriaged = sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in inbox_dir.iterdir()
        if path.name not in allowed_names
    )
    if untriaged:
        return CheckResult(
            "inbox_items_triaged",
            False,
            f"untriaged item(s): {', '.join(untriaged)}",
        )
    return CheckResult("inbox_items_triaged", True)


def record_run_log(summary: str, failed: int, results: list[CheckResult]) -> None:
    run_log_path = PROJECT_ROOT / "docs" / "run_log.md"
    if not run_log_path.exists():
        return

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    date_title = now.strftime("%Y-%m-%d")
    issues = [result for result in results if not result.passed]
    issue_line = "None." if not issues else "; ".join(
        f"{result.name}: {result.detail}" for result in issues
    )
    entry = (
        f"## {date_title} — Automatic Fitness Check\n\n"
        "Purpose:\n"
        "Record the standing process fitness check result.\n\n"
        "Command:\n\n"
        "```bash\n"
        "python3 scripts/fitness_check.py\n"
        "```\n\n"
        "Result:\n"
        f"* Timestamp: {timestamp}\n"
        f"* {summary}\n"
        f"* Issues: {issue_line}\n\n"
    )

    text = run_log_path.read_text(encoding="utf-8")
    marker = "# Run Log\n"
    if text.startswith(marker):
        insert_at = len(marker)
        if text[insert_at:insert_at + 1] == "\n":
            insert_at += 1
        updated = text[:insert_at] + entry + text[insert_at:]
    else:
        updated = entry + text
    run_log_path.write_text(updated, encoding="utf-8")


def main() -> int:
    checks = [
        check_required_docs(),
        check_required_docs_matches_protocol_list(),
        check_handoff_statuses(),
        check_supersede_references(),
        check_terminal_names_consistent(),
        check_handoff_status_enum_consistent(),
        check_role_docs_have_required_inputs(),
        check_prompts_point_to_role_docs(),
        check_terminal_protocol_sections_stay_pointers(),
        check_prompt_layout(),
        check_decision_entries(),
        check_completed_handoffs_not_approved(),
        check_inbox_items_triaged(),
    ]

    failed = 0
    for result in checks:
        status = "PASS" if result.passed else "FAIL"
        line = f"[{status}] {result.name}"
        if not result.passed:
            failed += 1
            line += f" -- {result.detail}"
        print(line)

    summary = f"Fitness checks: {len(checks)} run, {failed} failed"
    print(summary)
    record_run_log(summary, failed, checks)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
