"""The report gallery: generated from frontmatter, committed copies up to date."""

from __future__ import annotations

from pathlib import Path

import pytest

from f1_analytics import gallery


def _report(root: Path, folder: str, frontmatter: str) -> None:
    (root / folder).mkdir(parents=True)
    (root / folder / "report.qmd").write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")


def _stale_gallery_files(reports_dir: Path) -> list[str]:
    """The gallery files in `reports_dir` that differ from what the generator produces."""
    reports = gallery.find_reports(reports_dir)
    expected = {
        "README.md": gallery.render_markdown(reports),
        "index.html": gallery.render_html(reports),
    }
    return [
        name
        for name, text in expected.items()
        if not (reports_dir / name).exists() or (reports_dir / name).read_text(encoding="utf-8") != text
    ]


def _assert_gallery_current(reports_dir: Path) -> None:
    stale = _stale_gallery_files(reports_dir)
    assert not stale, (
        f"{', '.join(stale)} out of date with the reports' frontmatter; "
        f"run `{gallery.REGENERATE_COMMAND}` and commit the result"
    )


def test_committed_gallery_matches_generated():
    _assert_gallery_current(gallery.REPORTS_DIR)


def test_new_report_fails_check_naming_regenerate_command(tmp_path):
    _report(tmp_path, "t/editions/2026-01-01-one", 'title: "One"\ndate: 2026-01-01\n')
    gallery.write_gallery(tmp_path)
    _assert_gallery_current(tmp_path)

    _report(tmp_path, "t/editions/2026-02-01-two", 'title: "Two"\ndate: 2026-02-01\n')

    with pytest.raises(AssertionError, match="uv run gallery"):
        _assert_gallery_current(tmp_path)


def test_committed_gallery_lists_every_report():
    root = gallery.REPORTS_DIR
    qmds = [*root.glob("*/recurring/report.qmd"), *root.glob("*/editions/*/report.qmd")]
    folders = sorted(qmd.parent.relative_to(root).as_posix() for qmd in qmds)
    assert len(folders) >= 5
    markdown = (gallery.REPORTS_DIR / "README.md").read_text(encoding="utf-8")
    index = (gallery.REPORTS_DIR / "index.html").read_text(encoding="utf-8")
    for folder in folders:
        assert f"{folder}/report.html" in markdown
        assert f"{folder}/report.qmd" in markdown
        assert f'href="{folder}/report.html"' in index
        assert (gallery.REPORTS_DIR / folder / "report.html").exists(), f"reports/{folder} has no report.html"


def test_entries_newest_first_with_title_date_and_subtitle(tmp_path):
    _report(tmp_path, "t/editions/2026-01-01-old", 'title: "Old one"\nsubtitle: "Why old?"\ndate: 2026-01-01\n')
    _report(tmp_path, "t/editions/2026-03-01-new", "title: 'It''s new'\ndate: 2026-03-01\ndate-format: iso\n")
    (tmp_path / "golden").mkdir()  # not a report: no report.qmd

    reports = gallery.find_reports(tmp_path)

    assert [r.folder for r in reports] == ["t/editions/2026-03-01-new", "t/editions/2026-01-01-old"]
    assert reports[0].title == "It's new"
    assert reports[1].subtitle == "Why old?"
    markdown = gallery.render_markdown(reports)
    assert markdown.index("It's new") < markdown.index("Old one")
    assert "**2026-01-01**" in markdown and "Why old?" in markdown
    assert "It&#x27;s new" in gallery.render_html(reports)


def test_new_report_makes_committed_gallery_stale(tmp_path):
    _report(tmp_path, "t/editions/2026-01-01-one", 'title: "One"\ndate: 2026-01-01\n')
    gallery.write_gallery(tmp_path)
    before = (tmp_path / "README.md").read_text(encoding="utf-8")

    _report(tmp_path, "t/editions/2026-02-01-two", 'title: "Two"\ndate: 2026-02-01\n')
    regenerated = gallery.render_markdown(gallery.find_reports(tmp_path))

    assert regenerated != before
    assert regenerated.index("Two") < regenerated.index("One")


@pytest.mark.parametrize("missing", ["title", "date"])
def test_missing_field_names_file_and_field(tmp_path, missing):
    fields = {"title": 'title: "T"\n', "date": "date: 2026-01-01\n"}
    del fields[missing]
    _report(tmp_path, "t/editions/2026-01-01-x", "".join(fields.values()))

    with pytest.raises(gallery.GalleryError) as excinfo:
        gallery.find_reports(tmp_path)

    message = str(excinfo.value)
    assert "t/editions/2026-01-01-x/report.qmd" in message
    assert f"'{missing}'" in message


def test_missing_field_exits_nonzero_without_writing(tmp_path, capsys):
    _report(tmp_path, "t/editions/2026-01-01-x", 'title: "T"\n')

    assert gallery.main(tmp_path) == 1
    assert "'date'" in capsys.readouterr().err
    assert not (tmp_path / "README.md").exists()


def test_bad_date_is_reported(tmp_path):
    _report(tmp_path, "t/editions/2026-01-01-x", 'title: "T"\ndate: soon\n')
    with pytest.raises(gallery.GalleryError, match="ISO date"):
        gallery.find_reports(tmp_path)


_STATUS_AND_GAPS = (
    'title: "Q"\n'
    "date: 2026-01-01\n"
    "status: provisional\n"
    "gaps:\n"
    "  - Small sample <n=11>\n"
    '  - "Round 16 label: unresolved"\n'
)


def test_status_and_gaps_show_on_both_cards(tmp_path):
    """Matrix row: `status: provisional` and a two-item `gaps` block list."""
    _report(tmp_path, "t/editions/2026-01-01-q", _STATUS_AND_GAPS)

    [report] = gallery.find_reports(tmp_path)

    assert report.status == "provisional"
    assert report.gaps == ("Small sample <n=11>", "Round 16 label: unresolved")
    markdown = gallery.render_markdown([report])
    assert "Status: **provisional**" in markdown
    assert "- Small sample <n=11>\n- Round 16 label: unresolved" in markdown
    index = gallery.render_html([report])
    assert "Status: <strong>provisional</strong>" in index
    assert "<li>Small sample &lt;n=11&gt;</li>" in index
    assert "<li>Round 16 label: unresolved</li>" in index


def test_report_without_status_or_gaps_renders_as_before(tmp_path):
    """Matrix row: only title and date, so the card has no status or gaps."""
    _report(tmp_path, "t/editions/2026-01-01-q", 'title: "Q"\ndate: 2026-01-01\n')

    [report] = gallery.find_reports(tmp_path)

    assert (report.status, report.gaps) == ("", ())
    assert gallery.render_markdown([report]).endswith(
        "## Q\n\n**2026-01-01** · Edition\n\n"
        "[Report (HTML)](t/editions/2026-01-01-q/report.html) · [Source (`report.qmd`)](t/editions/2026-01-01-q/report.qmd)\n"
    )
    index = gallery.render_html([report])
    assert (
        '<p class="date">2026-01-01 · <span class="kind">Edition</span></p>\n'
        '    <p><a href="t/editions/2026-01-01-q/report.html">Report</a>' in index
    )


def test_bad_status_names_file_and_allowed_values(tmp_path):
    """Matrix row: `status: done` is not an allowed value."""
    _report(tmp_path, "t/editions/2026-01-01-x", 'title: "T"\ndate: 2026-01-01\nstatus: done\n')

    with pytest.raises(gallery.GalleryError) as excinfo:
        gallery.find_reports(tmp_path)

    message = str(excinfo.value)
    assert "t/editions/2026-01-01-x/report.qmd" in message
    assert "provisional" in message and "validated" in message and "'done'" in message


def test_status_without_gaps_shows_no_gaps_list(tmp_path):
    """Matrix row: `status: validated` and no gaps."""
    _report(tmp_path, "t/editions/2026-01-01-q", 'title: "Q"\ndate: 2026-01-01\nstatus: validated\n')

    [report] = gallery.find_reports(tmp_path)

    assert (report.status, report.gaps) == ("validated", ())
    markdown = gallery.render_markdown([report])
    assert "Status: **validated**" in markdown and "Known gaps" not in markdown
    index = gallery.render_html([report])
    assert "Status: <strong>validated</strong>" in index and "Known gaps" not in index


def test_nested_mapping_is_not_read_as_a_list(tmp_path):
    """`format:` with a nested mapping (the COTA page) stays out of the fields."""
    _report(tmp_path, "t/editions/2026-01-01-q", 'title: "Q"\ndate: 2026-01-01\nformat:\n  html:\n    embed-resources: true\n')

    fields = gallery.read_frontmatter(tmp_path / "t/editions/2026-01-01-q" / "report.qmd")

    assert "format" not in fields and "html" not in fields


def test_date_as_a_list_is_a_gallery_error(tmp_path):
    _report(tmp_path, "t/editions/2026-01-01-x", 'title: "T"\ndate:\n  - 2026-01-01\n')
    with pytest.raises(gallery.GalleryError, match="'date' must be one line of text"):
        gallery.find_reports(tmp_path)


def test_recurring_page_first_with_its_label_then_editions_newest_first(tmp_path):
    """A recurring page leads whatever its date; a topic with only explore.qmd is not a report."""
    _report(tmp_path, "t/editions/2026-01-01-old", 'title: "Old edition"\ndate: 2026-01-01\n')
    _report(tmp_path, "t/recurring", 'title: "Every race"\ndate: 2025-06-01\n')
    _report(tmp_path, "u/editions/2026-03-01-new", 'title: "New edition"\ndate: 2026-03-01\n')
    (tmp_path / "v" / "recurring").mkdir(parents=True)
    (tmp_path / "v" / "recurring" / "explore.qmd").write_text('---\ntitle: "E"\ndate: 2026-04-01\n---\n')
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / "explore.qmd").write_text('---\ntitle: "E"\ndate: 2026-04-01\n---\n')

    reports = gallery.find_reports(tmp_path)

    assert [(r.folder, r.kind) for r in reports] == [
        ("t/recurring", "Recurring"),
        ("u/editions/2026-03-01-new", "Edition"),
        ("t/editions/2026-01-01-old", "Edition"),
    ]
    markdown = gallery.render_markdown(reports)
    assert "**2025-06-01** · Recurring" in markdown
    assert markdown.index("Every race") < markdown.index("New edition") < markdown.index("Old edition")
    assert "[Report (HTML)](t/recurring/report.html)" in markdown
    index = gallery.render_html(reports)
    assert '<span class="kind">Recurring</span>' in index
    assert 'href="u/editions/2026-03-01-new/report.html"' in index


def test_quarto_project_renders_only_recurring_pages():
    """Matrix row: `uv run quarto render reports` renders the recurring pages and leaves editions frozen."""
    text = (gallery.REPORTS_DIR / "_quarto.yml").read_text(encoding="utf-8")
    after_render = text.split("\n  render:\n", 1)[1].splitlines()
    render = []
    for line in after_render:
        if not line.strip().startswith("- "):
            break
        render.append(line.strip()[2:].strip('"'))
    assert render == ["*/recurring/report.qmd"]
    rendered = {p.relative_to(gallery.REPORTS_DIR).as_posix() for p in gallery.REPORTS_DIR.glob(render[0])}
    assert "team_stops/recurring/report.qmd" in rendered
    assert not [path for path in rendered if "editions/" in path]
