"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def rank(self) -> int:
        return {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}[self]


SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    path: str
    message: str
    suggestion: str
    line: int | None = None
    column: int | None = None

    def at_or_above(self, threshold: str) -> bool:
        return self.severity.rank() >= SEVERITY_RANK.get(threshold, 2)


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    errors: list[str] = field(default_factory=list)

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (f.path, f.line or 0, f.column or 0, f.rule_id),
        )
