from __future__ import annotations

from pathlib import Path

import pytest
from scripts.render_release_notes import (
    MARKER,
    project_version,
    render_notes,
    render_release_notes,
    write_sha256sums,
)


def test_render_notes_once() -> None:
    text = render_notes("# v\n\n" + MARKER + "\n", "abc  wheel")
    assert "abc  wheel" in text
    assert MARKER not in text


def test_render_notes_missing_or_dup() -> None:
    with pytest.raises(SystemExit, match="exactly once"):
        render_notes("no marker", "x")
    with pytest.raises(SystemExit, match="exactly once"):
        render_notes(MARKER + MARKER, "x")


def test_render_notes_leftover() -> None:
    with pytest.raises(SystemExit, match="leftover"):
        render_notes(MARKER + "\n{{OTHER}}\n", "x")


def test_write_sha256sums_and_full_render(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    docs = root / "docs"
    dist = root / "dist"
    docs.mkdir(parents=True)
    dist.mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    (docs / "release-notes-9.9.9.md").write_text("# 9.9.9\n\n" + MARKER + "\n", encoding="utf-8")
    (dist / "noellipsis-9.9.9-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "noellipsis-9.9.9.tar.gz").write_bytes(b"sdist")
    out = tmp_path / "notes.md"
    render_release_notes(root, dist, out)
    sums = (dist / "SHA256SUMS").read_text(encoding="utf-8")
    assert "noellipsis-9.9.9-py3-none-any.whl" in sums
    rendered = out.read_text(encoding="utf-8")
    assert MARKER not in rendered
    first = sums.strip().splitlines()[0].split()[0]
    assert first in rendered
    assert project_version(root) == "9.9.9"


def test_missing_notes_file(tmp_path: Path) -> None:
    root = tmp_path
    (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    (root / "dist").mkdir()
    (root / "dist" / "a.whl").write_bytes(b"x")
    with pytest.raises(SystemExit, match="missing release notes"):
        render_release_notes(root, root / "dist", tmp_path / "out.md")


def test_write_sha256sums_empty(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no wheel"):
        write_sha256sums(tmp_path)


def test_github_actions_expressions_are_not_placeholders() -> None:
    text = render_notes("# v\n" + MARKER + "\n${{ steps.scan.outputs.sarif-file }}\n", "abc")
    assert "${{ steps.scan.outputs.sarif-file }}" in text
    assert MARKER not in text
