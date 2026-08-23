"""Text, JSON, GitHub Actions, and SARIF 2.1.0 formatters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from noellipsis import __version__
from noellipsis.models import Finding, ScanResult, Severity
from noellipsis.rules.catalog import RULES_BY_ID, all_rules

_GH = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
}

_SARIF_LEVEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}

SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/sarif-2.1/schema/sarif-schema-2.1.0.json"
INFORMATION_URI = "https://github.com/hoodbroskillson/NoEllipsis"


def format_result(result: ScanResult, fmt: str) -> str:
    findings = result.sorted_findings()
    if fmt == "json":
        return _json(findings, result)
    if fmt == "github":
        return _github(findings)
    if fmt == "sarif":
        return format_sarif(result)
    return _text(findings)


def format_rules(fmt: str) -> str:
    if fmt == "json":
        payload = {
            "rules": [
                {
                    "description": rule.short_description,
                    "id": rule.rule_id,
                    "severity": rule.severity.value,
                }
                for rule in all_rules()
            ]
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    lines = []
    for rule in all_rules():
        lines.append(f"{rule.rule_id}  {rule.severity.value:<7}  {rule.short_description}")
    return "\n".join(lines) + "\n"


def artifact_uri(path: str, *, cwd: Path | None = None) -> str:
    """Repo-relative POSIX URI; never an absolute filesystem path."""
    raw = (path or "").replace("\\", "/")
    if not raw:
        return ""
    candidate = Path(path)
    bases: list[Path] = []
    if cwd is not None:
        bases.append(cwd)
    try:
        bases.append(Path.cwd())
    except OSError:
        pass
    for base in bases:
        try:
            return candidate.resolve().relative_to(base.resolve()).as_posix()
        except (ValueError, OSError):
            continue
    if candidate.is_absolute():
        return candidate.name or raw.lstrip("/")
    return raw.lstrip("./")


def _count_phrase(n: int, singular: str) -> str:
    return f"{n} {singular}" if n == 1 else f"{n} {singular}s"


def _summary_line(findings: list[Finding]) -> str:
    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    infos = sum(1 for f in findings if f.severity == Severity.INFO)
    bits: list[str] = []
    if errors:
        bits.append(_count_phrase(errors, "error"))
    if warnings:
        bits.append(_count_phrase(warnings, "warning"))
    if infos:
        bits.append(_count_phrase(infos, "info"))
    head = _count_phrase(len(findings), "finding")
    return f"{head}: {', '.join(bits)}" if bits else f"{head}"


def _text(findings: list[Finding]) -> str:
    if not findings:
        return "No issues found.\n"
    parts: list[str] = []
    for f in findings:
        loc = artifact_uri(f.path)
        if f.line is not None:
            loc += f":{f.line}"
            if f.column is not None:
                loc += f":{f.column}"
        parts.append(f"{loc} {f.severity.value.upper()} {f.rule_id} {f.message}")
        parts.append(f"  {f.suggestion}")
    parts.append(_summary_line(findings))
    return "\n".join(parts) + "\n"


def _json(findings: list[Finding], result: ScanResult) -> str:
    payload = {
        "count": len(findings),
        "files_scanned": result.files_scanned,
        "findings": [
            {
                "column": f.column,
                "file": artifact_uri(f.path),
                "line": f.line,
                "message": f.message,
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "suggestion": f.suggestion,
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_prop(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def _github(findings: list[Finding]) -> str:
    if not findings:
        return ""
    lines: list[str] = []
    for f in findings:
        bits = [f"file={_escape_prop(artifact_uri(f.path))}"]
        if f.line is not None:
            bits.append(f"line={f.line}")
        if f.column is not None:
            bits.append(f"col={f.column}")
        level = _GH[f.severity]
        message = _escape_data(f"{f.rule_id} {f.message}")
        lines.append(f"::{level} {','.join(bits)}::{message}")
    return "\n".join(lines) + "\n"


def _partial_fingerprint(finding: Finding, uri: str) -> str:
    line = finding.line if finding.line is not None else 0
    column = finding.column if finding.column is not None else 0
    material = f"{finding.rule_id}|{uri}|{line}|{column}|{finding.message}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _sarif_rules() -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for rule in all_rules():
        out.append(
            {
                "defaultConfiguration": {"level": _SARIF_LEVEL[rule.severity]},
                "fullDescription": {"text": rule.full_description},
                "helpUri": rule.help_uri,
                "id": rule.rule_id,
                "shortDescription": {"text": rule.short_description},
            }
        )
    return out


def format_sarif(result: ScanResult, *, cwd: Path | None = None) -> str:
    findings = result.sorted_findings()
    results: list[dict[str, object]] = []
    for finding in findings:
        uri = artifact_uri(finding.path, cwd=cwd)
        loc: dict[str, object] = {
            "physicalLocation": {
                "artifactLocation": {"uri": uri},
            }
        }
        region: dict[str, int] = {}
        if finding.line is not None:
            region["startLine"] = finding.line
        if finding.column is not None:
            region["startColumn"] = finding.column
        if region:
            loc["physicalLocation"]["region"] = region  # type: ignore[index]
        spec = RULES_BY_ID.get(finding.rule_id)
        level = _SARIF_LEVEL.get(finding.severity, "warning")
        if spec is not None:
            level = _SARIF_LEVEL[spec.severity] if finding.severity == spec.severity else level
        results.append(
            {
                "level": level,
                "locations": [loc],
                "message": {"text": finding.message},
                "partialFingerprints": {"primaryLocationLineHash": _partial_fingerprint(finding, uri)},
                "ruleId": finding.rule_id,
            }
        )
    notifications: list[dict[str, object]] = []
    for err in result.errors:
        notifications.append(
            {
                "descriptor": {"id": "NE-IO"},
                "level": "error",
                "message": {"text": err},
            }
        )
    invocation: dict[str, object] = {
        "executionSuccessful": not result.errors,
    }
    if notifications:
        invocation["toolExecutionNotifications"] = notifications
    payload = {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "invocations": [invocation],
                "results": results,
                "tool": {
                    "driver": {
                        "informationUri": INFORMATION_URI,
                        "name": "NoEllipsis",
                        "rules": _sarif_rules(),
                        "semanticVersion": __version__,
                        "version": __version__,
                    }
                },
            }
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
