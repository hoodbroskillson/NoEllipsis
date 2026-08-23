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
    return "\n".join(parts) + "\n"


def _json(findings: list[Finding], result: ScanResult) -> str:
    payload = {
        "files_scanned": result.files_scanned,
        "count": len(findings),
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "file": f.path,
                "line": f.line,
                "column": f.column,
                "message": f.message,
                "suggestion": f.suggestion,
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _github(findings: list[Finding]) -> str:
    if not findings:
        return ""
    lines: list[str] = []
    for f in findings:
        bits = [f"file={f.path}"]
        if f.line is not None:
            bits.append(f"line={f.line}")
        if f.column is not None:
            bits.append(f"col={f.column}")
        level = _GH[f.severity]
        lines.append(f"::{level} {','.join(bits)}::{f.rule_id} {f.message}")
    return "\n".join(lines) + "\n"
