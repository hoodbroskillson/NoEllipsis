from __future__ import annotations

import json
from pathlib import Path

from noellipsis.cli import main


def test_format_before_and_after(tmp_path: Path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    pass\n", encoding="utf-8")
    assert main(["--format", "json", "check", str(path)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["check", str(path), "--format", "json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first == second
    assert first["findings"][0]["rule_id"] == "NE003"


def test_fail_on_before_and_after_compare(examples: Path) -> None:
    gen = examples / "generated_snippet.py"
    orig = examples / "original_module.py"
    assert main(["--fail-on", "warning", "compare", str(gen), "--against", str(orig)]) == 1
    assert main(["compare", str(gen), "--against", str(orig), "--fail-on", "warning"]) == 1


def test_git_diff_format_positions_help() -> None:
    assert main(["--help"]) == 0
    assert main(["check", "--help"]) == 0
    assert main(["--version"]) == 0


def test_repeated_exclude_disable(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def calculate_total():\n    ...\n", encoding="utf-8")
    assert main(["--disable", "NE002", "--disable", "NE003", "check", str(path)]) == 0
    assert main(["check", str(path), "--disable", "NE002", "--disable", "NE003"]) == 0


def test_verbose_after_command(tmp_path: Path, capsys) -> None:
    path = tmp_path / "ok.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert main(["check", str(path), "--verbose"]) == 0
    assert "scanning" in capsys.readouterr().err


def test_invalid_threshold_positions(tmp_path: Path) -> None:
    path = tmp_path / "ok.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert main(["--shrink-threshold", "101", "check", str(path)]) == 2
    assert main(["check", str(path), "--shrink-threshold", "-1"]) == 2
    assert main(["check", str(path), "--shrink-threshold", "nope"]) == 2


def test_invalid_toml_exits_2(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.noellipsis]\nshrink-threshold = 200\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["check", "ok.py"]) == 2
