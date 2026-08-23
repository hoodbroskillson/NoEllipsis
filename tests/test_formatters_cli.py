from __future__ import annotations

import json
from pathlib import Path

from noellipsis.cli import main
from noellipsis.formatters import format_result
from noellipsis.models import Finding, ScanResult, Severity


def _finding() -> Finding:
    return Finding(
        rule_id="NE002",
        severity=Severity.ERROR,
        path="src/example.py",
        message="Bare ellipsis used as function body",
        suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
        line=84,
        column=5,
    )


def test_text_format() -> None:
    text = format_result(ScanResult(findings=[_finding()]), "text")
    assert "src/example.py:84:5 ERROR NE002 Bare ellipsis used as function body" in text
    assert "Replace the placeholder" in text
    assert "1 finding: 1 error" in text


def test_json_stable() -> None:
    payload = json.loads(format_result(ScanResult(findings=[_finding()], files_scanned=1), "json"))
    assert payload["count"] == 1
    assert payload["findings"][0]["rule_id"] == "NE002"
    assert list(payload["findings"][0].keys()) == sorted(payload["findings"][0].keys())


def test_github_format() -> None:
    text = format_result(ScanResult(findings=[_finding()]), "github")
    assert text.strip() == "::error file=src/example.py,line=84,col=5::NE002 Bare ellipsis used as function body"


def test_text_clean() -> None:
    assert format_result(ScanResult(), "text") == "No issues found.\n"


def test_cli_help() -> None:
    assert main(["--help"]) == 0


def test_cli_check_examples_exit(examples: Path) -> None:
    code = main(["check", str(examples / "incomplete.py")])
    assert code == 1


def test_cli_check_missing() -> None:
    assert main(["check", "/no/such/path/noellipsis"]) == 2


def test_cli_json_and_fail_on_warning(tmp_path: Path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    pass\n", encoding="utf-8")
    assert main(["--format", "json", "--fail-on", "warning", "check", str(path)]) == 1
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["findings"][0]["rule_id"] == "NE003"


def test_cli_fail_on_error_ignores_warning(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    pass\n", encoding="utf-8")
    assert main(["--fail-on", "error", "check", str(path)]) == 0


def test_cli_spaces_in_path(tmp_path: Path) -> None:
    folder = tmp_path / "path with spaces"
    folder.mkdir()
    target = folder / "note.py"
    target.write_text("def leftover():\n    pass\n", encoding="utf-8")
    assert main(["--fail-on", "warning", "check", str(target)]) == 1


def test_cli_compare(examples: Path) -> None:
    code = main(
        [
            "compare",
            str(examples / "generated_snippet.py"),
            "--against",
            str(examples / "original_module.py"),
        ]
    )
    assert code == 1


def test_cli_disable(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def calculate_total():\n    ...\n", encoding="utf-8")
    assert main(["--disable", "NE002", "check", str(path)]) == 0


def test_cli_github(tmp_path: Path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("def calculate_total():\n    ...\n", encoding="utf-8")
    main(["--format", "github", "check", str(path)])
    assert "::error file=" in capsys.readouterr().out


def test_cli_no_command_help(capsys) -> None:
    assert main([]) == 0
    assert "check" in capsys.readouterr().out


def test_cli_invalid_threshold(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert main(["--shrink-threshold", "-1", "check", str(path)]) == 2


def test_cli_verbose(tmp_path: Path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert main(["--verbose", "check", str(path)]) == 0
    err = capsys.readouterr().err
    assert "scanning" in err


def test_github_escapes_specials() -> None:
    finding = Finding(
        rule_id="NE001",
        severity=Severity.ERROR,
        path="path,with:percent%.py",
        message="line1\nline2,colon:",
        suggestion="fix",
        line=1,
        column=1,
    )
    text = format_result(ScanResult(findings=[finding]), "github")
    assert "file=path%2Cwith%3Apercent%25.py" in text
    assert "%0A" in text
    assert "%3A" in text or "colon" in text


def test_text_mixed_summary() -> None:
    findings = [
        Finding("NE002", Severity.ERROR, "a.py", "e", "s", 1, 1),
        Finding("NE003", Severity.WARNING, "b.py", "w", "s", 2, 1),
    ]
    text = format_result(ScanResult(findings=findings), "text")
    assert text.endswith("2 findings: 1 error, 1 warning\n")
