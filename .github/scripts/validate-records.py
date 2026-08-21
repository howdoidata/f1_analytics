# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate the machine-readable planning records.

Three artifacts in this repo have a schema that something actually parses; the rest
is prose. This checks exactly those three, so drift is caught by CI instead of by a
human noticing weeks later:

  1. sprint-status.yaml  -- delegated to sprint_plan.py's own validator
  2. deferred-work.md    -- the DW entry format `bmad-loop sweep` partitions on
  3. spec-*.md frontmatter -- the `status:` field bmad-build routes on

Read-only, stdlib-only. Exit 0 clean, 1 on any error. Warnings never fail the run.

Ported from howdoidata/manalink's .github/scripts/validate-records.py, reduced to the
artifacts this repo actually keeps (no sprint-status-r1.yaml sibling tracker, no
record-authority classification layer, no issue-sprint-map traceability -- this repo
has no GitHub-issue backward link to enforce).

The companion check is tools/artifact-status-assertions.sh, which is the *cross*-artifact
half: this script validates each record against its own schema, that one validates a
completed spec's status against its board entry. Both are needed -- a board and a spec
can each be individually well-formed and still contradict each other.

Run locally the same way CI does:
    uv run .github/scripts/validate-records.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# `RECORDS_ROOT` exists so the regression harness can point the whole validator at a
# fixture tree and prove each check goes RED. Unset in CI and in normal local runs.
ROOT = Path(os.environ.get("RECORDS_ROOT") or Path(__file__).resolve().parents[2]).resolve()
IMPL = ROOT / "_bmad-output" / "implementation-artifacts"
SPRINT_PLAN = ROOT / ".claude" / "skills" / "bmad-sprint-planning" / "scripts" / "sprint_plan.py"

# The status vocabulary bmad-build routes on. `awaiting-operator` is this repo's own
# addition (spec-1-2-fastf1-adoption-spike parked pending a human-run spike) and is
# routable here even though it is absent from the upstream BMad set.
SPEC_STATUSES = {"draft", "ready-for-dev", "in-progress", "in-review", "awaiting-operator", "done"}
# The ledger's triage label. `bmad-loop sweep` buckets on it, so a value outside the
# vocabulary sorts into no bucket at all.
SEVERITIES = {"low", "medium", "high"}

ERRORS: list[str] = []
WARNINGS: list[str] = []


def error(artifact: str, msg: str) -> None:
    ERRORS.append(f"{artifact}: {msg}")


def warn(artifact: str, msg: str) -> None:
    WARNINGS.append(f"{artifact}: {msg}")


def check_sprint_status() -> None:
    """Delegate to the generator's own validator -- it owns this file's schema."""
    path = IMPL / "sprint-status.yaml"
    name = "sprint-status.yaml"
    if not path.exists():
        error(name, "missing")
        return
    if not SPRINT_PLAN.exists():
        warn(name, f"{SPRINT_PLAN} not found -- skipped")
        return
    # `uv run`, not `sys.executable`: sprint_plan.py carries a PEP 723 header declaring
    # `ruamel.yaml`, which the ambient interpreter is not guaranteed to have importable.
    # Invoking it bare raises ImportError before it can emit its JSON contract.
    proc = subprocess.run(
        ["uv", "run", str(SPRINT_PLAN), "validate", "--status-file", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        error(name, f"validator produced no JSON (exit {proc.returncode}): {proc.stderr.strip()[:200]}")
        return
    if not report.get("valid"):
        for problem in report.get("problems", []) or ["invalid, no detail given"]:
            error(name, problem)
    for legacy in report.get("legacy_mapped", []):
        warn(name, f"legacy status name: {legacy}")


def check_deferred_work() -> None:
    """The DW entry format `bmad-loop sweep` partitions on."""
    path = IMPL / "deferred-work.md"
    name = "deferred-work.md"
    if not path.exists():
        warn(name, "missing -- skipped")
        return

    text = path.read_text(encoding="utf-8")
    blocks = [b for b in re.split(r"\n(?=### DW-)", text) if b.startswith("### DW-")]
    if not blocks:
        warn(name, "no DW entries found")
        return

    status_re = re.compile(r"^status: (open|done \d{4}-\d{2}-\d{2})\s*$", re.M)
    numbers: list[int] = []

    for block in blocks:
        header = block.splitlines()[0]
        match = re.match(r"### DW-(\d+):", header)
        if not match:
            error(name, f"malformed entry header: {header[:70]}")
            continue
        num = int(match.group(1))
        numbers.append(num)
        tag = f"DW-{num}"

        for field in ("origin", "location", "reason", "status"):
            if not re.search(rf"^{field}:", block, re.M):
                error(name, f"{tag} is missing required field `{field}:`")

        # Only 2 of 28 entries carried `severity:` when this validator landed
        # (2026-08-20), so an absent one warns rather than fails -- the sweep treats a
        # missing severity as untriaged, which is recoverable, unlike a value outside
        # the vocabulary, which buckets into nothing at all.
        severity = re.search(r"^severity:\s*(\S+)\s*$", block, re.M)
        if severity and severity.group(1) not in SEVERITIES:
            error(
                name,
                f"{tag} has severity `{severity.group(1)}` -- allowed: {sorted(SEVERITIES)}. "
                f"A value outside the vocabulary buckets into nothing when the sweep triages.",
            )

        if not status_re.search(block):
            actual = re.search(r"^status:.*$", block, re.M)
            shown = actual.group(0)[:80] if actual else "(none)"
            error(
                name,
                f"{tag} status is not canonical -- must be `open` or `done YYYY-MM-DD`, "
                f"with any prose on a separate `resolution:` line. Found: {shown}",
            )
        elif "status: done" in block and not re.search(r"^resolution:", block, re.M):
            # The forward link: a done entry with no resolution ends the chain in silence.
            error(name, f"{tag} is done but has no `resolution:` line recording how it ended")

    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        error(name, f"duplicate entry numbers: {duplicates}")
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers)) if numbers else []
    if gaps:
        warn(name, f"gaps in entry numbering: {gaps} (entries are never deleted, so this is unusual)")


def check_spec_frontmatter() -> None:
    """`status:` is what bmad-build routes on -- a typo silently misroutes the workflow."""
    name = "spec frontmatter"
    specs = sorted(IMPL.glob("spec-*.md"))
    if not specs:
        warn(name, "no spec files found -- skipped")
        return
    for spec in specs:
        head = spec.read_text(encoding="utf-8")[:1500]
        if not head.startswith("---"):
            warn(name, f"{spec.name} has no frontmatter block")
            continue
        match = re.search(r"^status:\s*'?\"?([a-z-]+)'?\"?\s*$", head, re.M)
        if not match:
            error(name, f"{spec.name} has no `status:` field in frontmatter")
        elif match.group(1) not in SPEC_STATUSES:
            error(
                name,
                f"{spec.name} status `{match.group(1)}` is not a routable value -- "
                f"allowed: {sorted(SPEC_STATUSES)}",
            )


def main() -> int:
    if not IMPL.is_dir():
        print(f"FATAL: {IMPL} not found", file=sys.stderr)
        return 1

    check_sprint_status()
    check_deferred_work()
    check_spec_frontmatter()

    for w in WARNINGS:
        print(f"WARN  {w}")
    for e in ERRORS:
        print(f"ERROR {e}", file=sys.stderr)

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s), {len(WARNINGS)} warning(s).", file=sys.stderr)
        return 1
    print(f"\nRecords valid. {len(WARNINGS)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
