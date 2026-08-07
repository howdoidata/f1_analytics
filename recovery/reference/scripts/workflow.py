#!/usr/bin/env python3
"""Report workflow status and route common project intents."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from fitness_check import (
    CheckResult,
    check_completed_handoffs_not_approved,
    check_decision_entries,
    check_handoff_statuses,
    check_handoff_status_enum_consistent,
    check_prompt_layout,
    check_prompts_point_to_role_docs,
    check_required_docs,
    check_required_docs_matches_protocol_list,
    check_role_docs_have_required_inputs,
    check_supersede_references,
    check_terminal_names_consistent,
    check_terminal_protocol_sections_stay_pointers,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_RE = re.compile(r"^[ \t]*Status:\s*(.+)$", re.MULTILINE)
NUMBERED_FILE_RE = re.compile(r"^(\d+)-.*\.md$")

INTENT_ROUTES = {
    "architecture": "Planning terminal -- see docs/terminal_roles/planning.md.",
    "analysis": "Planning terminal -- see docs/terminal_roles/planning.md.",
    "execution": "Execution terminal -- see docs/terminal_roles/execution.md.",
    "command": "Command terminal -- see docs/terminal_roles/command.md.",
    "revise": "Workflow procedure -- see docs/terminal_protocol.md.",
}


def run_fitness_checks() -> list[CheckResult]:
    return [
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
    ]


def read_section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else "Not found."


def handoffs_with_status(folder: Path, statuses: set[str]) -> list[str]:
    matches = []
    for path in sorted(folder.glob("*.md")):
        status_match = STATUS_RE.search(path.read_text(encoding="utf-8"))
        status = status_match.group(1).strip() if status_match else "Missing"
        if status in statuses:
            matches.append(f"{path.name} [{status}]")
    return matches


def latest_implementation_note() -> str:
    candidates = []
    notes_dir = PROJECT_ROOT / "docs" / "implementation_notes"
    for path in notes_dir.glob("*.md"):
        match = NUMBERED_FILE_RE.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path.name))
    return max(candidates)[1] if candidates else "None"


def print_list(title: str, values: list[str]) -> None:
    print(f"\n{title}:")
    if values:
        for value in values:
            print(f"- {value}")
    else:
        print("- None")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", choices=sorted(INTENT_ROUTES))
    args = parser.parse_args()

    checks = run_fitness_checks()
    failed = sum(not result.passed for result in checks)
    print(f"Fitness: {len(checks)} run, {failed} failed")
    for result in checks:
        if not result.passed:
            print(f"- FAIL {result.name}: {result.detail}")

    active_context = PROJECT_ROOT / "docs" / "active_context.md"
    print("\nCurrent Focus:")
    print(read_section(active_context, "Current Focus"))
    print("\nNext Action:")
    print(read_section(active_context, "Next Action"))

    handoff_root = PROJECT_ROOT / "docs" / "handoffs"
    print_list(
        "Draft handoffs awaiting review",
        handoffs_with_status(handoff_root / "drafts", {"Draft", "Needs Revision"}),
    )
    print_list(
        "Approved handoffs awaiting completion",
        handoffs_with_status(handoff_root / "approved", {"Approved"}),
    )
    print(f"\nLatest implementation note:\n- {latest_implementation_note()}")

    if args.intent:
        print(f"\nIntent route ({args.intent}):\n{INTENT_ROUTES[args.intent]}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
