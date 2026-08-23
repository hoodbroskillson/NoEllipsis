from __future__ import annotations

from pathlib import Path

from noellipsis.config import Config
from noellipsis.scanner import Scanner, language_for


def test_examples_incomplete(examples: Path) -> None:
    findings = Scanner(Config()).scan_file(examples / "incomplete.py")
    assert any(f.rule_id == "NE002" for f in findings)


def test_examples_auth_js(examples: Path) -> None:
    findings = Scanner(Config()).scan_file(examples / "auth.js")
    assert any(f.rule_id == "NE001" for f in findings)


def test_examples_ok_python(examples: Path) -> None:
    findings = Scanner(Config()).scan_file(examples / "ok_examples.py")
    assert findings == []


def test_examples_ok_js(examples: Path) -> None:
    findings = Scanner(Config()).scan_file(examples / "ok_spread.js")
    assert findings == []


def test_examples_pyi(examples: Path) -> None:
    findings = Scanner(Config()).scan_file(examples / "stub_sample.pyi")
    assert findings == []


def test_path_with_spaces(examples: Path) -> None:
    target = examples / "path with spaces" / "note.py"
    findings = Scanner(Config()).scan_file(target)
    assert any(f.rule_id == "NE003" for f in findings)


def test_language_for() -> None:
    assert language_for(Path("a.ts")) == "typescript"
    assert language_for(Path("a.unknown")) is None


def test_skip_binary(tmp_path: Path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(b"\x89PNG\x00\x00")
    assert Scanner(Config()).scan_file(path) == []


def test_directory_scan_counts(examples: Path) -> None:
    result = Scanner(Config()).scan_path(examples)
    assert result.files_scanned >= 8
    assert result.findings
