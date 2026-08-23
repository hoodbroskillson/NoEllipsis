"""Text, JSON, and GitHub Actions formatters."""

from __future__ import annotations

import json

from noellipsis.models import Finding, ScanResult, Severity

_GH = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
}


def format_result(result: ScanResult, fmt: str) -> str:
    findings = result.sorted_findings()
    if fmt == "json":
        return _json(findings, result)
    if fmt == "github":
        return _github(findings)
    return _text(findings)


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
        loc = f.path
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
                "file": f.path,
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
        bits = [f"file={_escape_prop(f.path)}"]
        if f.line is not None:
            bits.append(f"line={f.line}")
        if f.column is not None:
            bits.append(f"col={f.column}")
        level = _GH[f.severity]
        message = _escape_data(f"{f.rule_id} {f.message}")
        lines.append(f"::{level} {','.join(bits)}::{message}")
    return "\n".join(lines) + "\n"
