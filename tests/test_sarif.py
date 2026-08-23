from __future__ import annotations

import json
from pathlib import Path

from noellipsis import __version__
from noellipsis.cli import main
from noellipsis.formatters import artifact_uri, format_result, format_sarif
from noellipsis.models import Finding, ScanResult, Severity
from noellipsis.rules.catalog import RULES


def _finding(path: str = "src/example.py") -> Finding:
    return Finding(
        rule_id="NE002",
        severity=Severity.ERROR,
        path=path,
        message="Bare ellipsis used as function body",
        suggestion="Replace the placeholder.",
        line=84,
        column=5,
    )


def test_sarif_schema_and_rules() -> None:
    doc = json.loads(format_result(ScanResult(findings=[_finding()], files_scanned=1), "sarif"))
    assert doc["version"] == "2.1.0"
    assert "sarif" in doc["$schema"].lower()
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "NoEllipsis"
    assert driver["version"] == __version__
    ids = [r["id"] for r in driver["rules"]]
    assert ids == [r.rule_id for r in RULES]
    for rule in driver["rules"]:
        assert rule["shortDescription"]["text"]
        assert rule["fullDescription"]["text"]
        assert rule["defaultConfiguration"]["level"] in {"error", "warning", "note"}
        assert rule["helpUri"].startswith("https://")
    result = doc["runs"][0]["results"][0]
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 84
    assert result["locations"][0]["physicalLocation"]["region"]["startColumn"] == 5
    uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert not uri.startswith("/")
    assert ":" not in uri.split("/")[0] or uri.startswith("src/")
    assert result["partialFingerprints"]["primaryLocationLineHash"]


def test_sarif_severity_map() -> None:
    findings = [
        Finding("NE002", Severity.ERROR, "a.py", "e", "s", 1, 1),
        Finding("NE003", Severity.WARNING, "b.py", "w", "s", 2, 1),
        Finding("NE001", Severity.INFO, "c.py", "i", "s", 3, 1),
    ]
    doc = json.loads(format_sarif(ScanResult(findings=findings)))
    levels = [r["level"] for r in doc["runs"][0]["results"]]
    assert levels == ["error", "warning", "note"]


def test_sarif_absolute_path_stripped(tmp_path: Path) -> None:
    abs_path = str(tmp_path / "nested" / "x.py")
    finding = _finding(abs_path)
    doc = json.loads(format_sarif(ScanResult(findings=[finding]), cwd=tmp_path))
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert not uri.startswith("/")
    assert "nested" in uri or uri.endswith("x.py")


def test_sarif_notifications() -> None:
    result = ScanResult(errors=["Unreadable file: secret.py: Permission denied"])
    doc = json.loads(format_sarif(result))
    notes = doc["runs"][0]["invocations"][0]["toolExecutionNotifications"]
    assert notes[0]["level"] == "error"
    assert "Unreadable" in notes[0]["message"]["text"]
    assert doc["runs"][0]["invocations"][0]["executionSuccessful"] is False


def test_sarif_determinism() -> None:
    result = ScanResult(findings=[_finding("b.py"), _finding("a.py")], files_scanned=2)
    first = format_sarif(result)
    second = format_sarif(result)
    assert first == second
    json.loads(first)


def test_sarif_cli_stdout_only_json(tmp_path: Path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    ...\n", encoding="utf-8")
    code = main(["--format", "sarif", "check", str(path)])
    assert code == 1
    out = capsys.readouterr().out
    doc = json.loads(out)
    assert doc["version"] == "2.1.0"


def test_sarif_unicode_path(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "unicodé"
    folder.mkdir()
    path = folder / "名前.py"
    path.write_text("def leftover():\n    ...\n", encoding="utf-8")
    assert main(["check", str(path), "--format", "sarif"]) == 1
    doc = json.loads(capsys.readouterr().out)
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert "/" not in uri or "名前" in uri or "unicod" in uri
    assert not uri.startswith("/")


def test_artifact_uri_never_absolute() -> None:
    assert not artifact_uri("/tmp/abs/path.py").startswith("/")
    assert artifact_uri("rel/path.py") == "rel/path.py"


def test_sarif_snapshot() -> None:
    snap = Path(__file__).parent / "snapshots" / "sarif_example.json"
    doc = json.loads(format_result(ScanResult(findings=[_finding()], files_scanned=1), "sarif"))
    if not snap.exists():
        snap.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    expected = json.loads(snap.read_text(encoding="utf-8"))
    # version string may change; compare structure besides tool version
    expected["runs"][0]["tool"]["driver"]["version"] = doc["runs"][0]["tool"]["driver"]["version"]
    expected["runs"][0]["tool"]["driver"]["semanticVersion"] = doc["runs"][0]["tool"]["driver"]["semanticVersion"]
    assert doc == expected
