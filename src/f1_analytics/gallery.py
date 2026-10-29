"""`uv run gallery`: the report gallery, generated from each report's frontmatter.

Reports live in topic folders: `reports/<topic>/recurring/report.qmd` is the
page that is re-rendered for each race, `reports/<topic>/editions/<name>/report.qmd`
a frozen one. Each contributes one entry (a "Recurring" or "Edition" label from its
path, title, date, subtitle, the optional `status` and `gaps`, links to its
`report.html` and `report.qmd`): recurring pages first, then editions newest first.
The gallery is written twice:

- `reports/README.md`, which GitHub shows when a reader opens `reports/`;
- `reports/index.html`, the home page of the GitHub Pages site.

Both files are generated, never hand-edited; `tests/test_gallery.py` fails
when the committed copies differ from what this module produces.
"""

from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from f1_analytics.config import PROJECT_ROOT


REPORTS_DIR = PROJECT_ROOT / "reports"
REGENERATE_COMMAND = "uv run gallery"
REQUIRED_FIELDS = ("title", "date")
STATUSES = ("provisional", "validated")
REPORT_GLOBS = ("*/recurring/report.qmd", "*/editions/*/report.qmd")
RECURRING = "Recurring"
EDITION = "Edition"
ORDER_NOTE = "Recurring pages first, then editions newest first."


class GalleryError(Exception):
    """A report's frontmatter is missing or unreadable."""


@dataclass(frozen=True)
class Report:
    folder: str
    title: str
    date: date
    subtitle: str
    status: str = ""
    gaps: tuple[str, ...] = ()

    @property
    def kind(self) -> str:
        """'Recurring' for `<topic>/recurring/`, 'Edition' for `<topic>/editions/<name>/`."""
        return RECURRING if self.folder.split("/")[1:2] == ["recurring"] else EDITION


def _scalar(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        # A YAML double-quoted scalar on one line reads the same as a JSON string.
        return json.loads(value)
    if value.startswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def read_frontmatter(path: Path) -> dict[str, str | list[str]]:
    """The top-level fields of a `.qmd`'s YAML frontmatter.

    Reports use one-line scalar fields plus block lists (`gaps:` followed by
    indented `- item` lines), so this reads them without a YAML library. A
    key with no value collects the `- item` lines under it as a list; other
    nested or multi-line values are skipped.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise GalleryError(f"{path}: no YAML frontmatter (the file must start with '---')")
    fields: dict[str, str | list[str]] = {}
    list_key: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0].isspace():
            if list_key is not None and stripped.startswith("- "):
                items = fields.get(list_key)
                if not isinstance(items, list):
                    items = fields[list_key] = []
                items.append(_scalar(stripped[2:]))
            continue
        list_key = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if value.strip():
            fields[key.strip()] = _scalar(value)
        else:
            list_key = key.strip()
    raise GalleryError(f"{path}: frontmatter is not closed with '---'")


def load_report(qmd: Path, reports_dir: Path = REPORTS_DIR) -> Report:
    fields = read_frontmatter(qmd)
    for field in REQUIRED_FIELDS:
        if not fields.get(field):
            raise GalleryError(f"{qmd}: frontmatter has no '{field}' field")
    raw_date = _text(qmd, fields, "date")
    try:
        report_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise GalleryError(f"{qmd}: 'date' is not an ISO date (YYYY-MM-DD): {raw_date!r}") from exc
    status = _text(qmd, fields, "status")
    if status and status not in STATUSES:
        raise GalleryError(f"{qmd}: 'status' must be one of {', '.join(STATUSES)}, not {status!r}")
    gaps = fields.get("gaps", [])
    if isinstance(gaps, str):
        gaps = [gaps]
    return Report(
        folder=qmd.parent.relative_to(reports_dir).as_posix(),
        title=_text(qmd, fields, "title"),
        date=report_date,
        subtitle=_text(qmd, fields, "subtitle"),
        status=status,
        gaps=tuple(gaps),
    )


def _text(qmd: Path, fields: dict[str, str | list[str]], name: str) -> str:
    value = fields.get(name, "")
    if not isinstance(value, str):
        raise GalleryError(f"{qmd}: '{name}' must be one line of text, not a list")
    return value


def find_reports(reports_dir: Path = REPORTS_DIR) -> list[Report]:
    """Every recurring and edition `report.qmd` under `reports_dir`: recurring first, then newest first."""
    qmds = sorted(qmd for pattern in REPORT_GLOBS for qmd in reports_dir.glob(pattern))
    reports = sorted((load_report(qmd, reports_dir) for qmd in qmds), key=lambda r: (r.date, r.folder), reverse=True)
    return sorted(reports, key=lambda r: r.kind != RECURRING)


def render_markdown(reports: Sequence[Report]) -> str:
    lines = [
        "# Report gallery",
        "",
        f"<!-- Generated by `{REGENERATE_COMMAND}` from each report's frontmatter. Do not edit. -->",
        "",
        f"Each report answers one question about Formula 1 results. {ORDER_NOTE}",
        "",
    ]
    for r in reports:
        lines += [f"## {r.title}", "", f"**{r.date.isoformat()}** · {r.kind}"]
        if r.subtitle:
            lines += ["", r.subtitle]
        if r.status:
            lines += ["", f"Status: **{r.status}**"]
        if r.gaps:
            lines += ["", "Known gaps:", ""] + [f"- {gap}" for gap in r.gaps]
        lines += [
            "",
            f"[Report (HTML)]({r.folder}/report.html) · [Source (`report.qmd`)]({r.folder}/report.qmd)",
            "",
        ]
    return "\n".join(lines)


def render_html(reports: Sequence[Report]) -> str:
    esc = html.escape
    items = []
    for r in reports:
        subtitle = f'\n    <p class="subtitle">{esc(r.subtitle)}</p>' if r.subtitle else ""
        status = f'\n    <p class="status">Status: <strong>{esc(r.status)}</strong></p>' if r.status else ""
        gaps = (
            '\n    <p class="gaps">Known gaps:</p>\n    <ul class="gaps">\n'
            + "\n".join(f"      <li>{esc(gap)}</li>" for gap in r.gaps)
            + "\n    </ul>"
            if r.gaps
            else ""
        )
        items.append(
            "  <li>\n"
            f'    <h2><a href="{esc(r.folder)}/report.html">{esc(r.title)}</a></h2>\n'
            f'    <p class="date">{r.date.isoformat()} · <span class="kind">{r.kind}</span></p>{subtitle}{status}{gaps}\n'
            f'    <p><a href="{esc(r.folder)}/report.html">Report</a> · '
            f'<a href="{esc(r.folder)}/report.qmd">Source (<code>report.qmd</code>)</a></p>\n'
            "  </li>"
        )
    body = "\n".join(items)
    return f"""<!DOCTYPE html>
<!-- Generated by `{REGENERATE_COMMAND}` from each report's frontmatter. Do not edit. -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F1 Analytics reports</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
         color: #0b0b0b; max-width: 780px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ border-bottom: 1px solid #e6e5e0; padding: 0.6rem 0; }}
  h2 {{ font-size: 1.2rem; margin: 0.2rem 0; }}
  p {{ margin: 0.2rem 0; }}
  .date, .subtitle {{ color: #52514e; }}
  ul.gaps {{ list-style: disc; padding-left: 1.4rem; margin: 0.2rem 0; }}
  ul.gaps li {{ border-bottom: none; padding: 0; }}
</style>
</head>
<body>
<h1>F1 Analytics reports</h1>
<p>Each report answers one question about Formula 1 results. {ORDER_NOTE}</p>
<ul>
{body}
</ul>
</body>
</html>
"""


def write_gallery(reports_dir: Path = REPORTS_DIR) -> list[Path]:
    reports = find_reports(reports_dir)
    outputs = {
        reports_dir / "README.md": render_markdown(reports),
        reports_dir / "index.html": render_html(reports),
    }
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    return list(outputs)


def main(reports_dir: Path = REPORTS_DIR) -> int:
    try:
        written = write_gallery(reports_dir)
    except GalleryError as exc:
        print(f"gallery: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    return 0


def cli() -> None:
    sys.exit(main())
