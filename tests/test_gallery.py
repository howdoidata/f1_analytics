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
    _report(tmp_path, "2026-01-01-one", 'title: "One"\ndate: 2026-01-01\n')
    gallery.write_gallery(tmp_path)
    _assert_gallery_current(tmp_path)

    _report(tmp_path, "2026-02-01-two", 'title: "Two"\ndate: 2026-02-01\n')

    with pytest.raises(AssertionError, match="uv run gallery"):
        _assert_gallery_current(tmp_path)


def test_committed_gallery_lists_every_report():
    folders = sorted(p.parent.name for p in gallery.REPORTS_DIR.glob("*/report.qmd"))
    assert len(folders) >= 3
    markdown = (gallery.REPORTS_DIR / "README.md").read_text(encoding="utf-8")
    index = (gallery.REPORTS_DIR / "index.html").read_text(encoding="utf-8")
    for folder in folders:
        assert f"{folder}/report.html" in markdown
        assert f"{folder}/report.qmd" in markdown
        assert f'href="{folder}/report.html"' in index
        assert (gallery.REPORTS_DIR / folder / "report.html").exists(), f"reports/{folder} has no report.html"


def test_entries_newest_first_with_title_date_and_subtitle(tmp_path):
    _report(tmp_path, "2026-01-01-old", 'title: "Old one"\nsubtitle: "Why old?"\ndate: 2026-01-01\n')
    _report(tmp_path, "2026-03-01-new", "title: 'It''s new'\ndate: 2026-03-01\ndate-format: iso\n")
    (tmp_path / "golden").mkdir()  # not a report: no report.qmd

    reports = gallery.find_reports(tmp_path)

    assert [r.folder for r in reports] == ["2026-03-01-new", "2026-01-01-old"]
    assert reports[0].title == "It's new"
    assert reports[1].subtitle == "Why old?"
    markdown = gallery.render_markdown(reports)
    assert markdown.index("It's new") < markdown.index("Old one")
    assert "**2026-01-01**" in markdown and "Why old?" in markdown
    assert "It&#x27;s new" in gallery.render_html(reports)


def test_new_report_makes_committed_gallery_stale(tmp_path):
    _report(tmp_path, "2026-01-01-one", 'title: "One"\ndate: 2026-01-01\n')
    gallery.write_gallery(tmp_path)
    before = (tmp_path / "README.md").read_text(encoding="utf-8")

    _report(tmp_path, "2026-02-01-two", 'title: "Two"\ndate: 2026-02-01\n')
    regenerated = gallery.render_markdown(gallery.find_reports(tmp_path))

    assert regenerated != before
    assert regenerated.index("Two") < regenerated.index("One")


@pytest.mark.parametrize("missing", ["title", "date"])
def test_missing_field_names_file_and_field(tmp_path, missing):
    fields = {"title": 'title: "T"\n', "date": "date: 2026-01-01\n"}
    del fields[missing]
    _report(tmp_path, "2026-01-01-x", "".join(fields.values()))

    with pytest.raises(gallery.GalleryError) as excinfo:
        gallery.find_reports(tmp_path)

    message = str(excinfo.value)
    assert "2026-01-01-x/report.qmd" in message
    assert f"'{missing}'" in message


def test_missing_field_exits_nonzero_without_writing(tmp_path, capsys):
    _report(tmp_path, "2026-01-01-x", 'title: "T"\n')

    assert gallery.main(tmp_path) == 1
    assert "'date'" in capsys.readouterr().err
    assert not (tmp_path / "README.md").exists()


def test_bad_date_is_reported(tmp_path):
    _report(tmp_path, "2026-01-01-x", 'title: "T"\ndate: soon\n')
    with pytest.raises(gallery.GalleryError, match="ISO date"):
        gallery.find_reports(tmp_path)
