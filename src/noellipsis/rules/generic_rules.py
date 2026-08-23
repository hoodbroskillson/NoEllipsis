"""Language-agnostic heuristics: NE001, NE002 (lone line), NE005, NE007."""

from __future__ import annotations

import re
from pathlib import Path

from noellipsis.lex import Kind, offset_to_linecol, region_at, regions_for
from noellipsis.models import Finding, Severity
from noellipsis.rules.placeholders import find_placeholder_hits

_CONFLICT_START = re.compile(r"^<{7}")
_CONFLICT_END = re.compile(r"^>{7}")
_CONFLICT_MID = re.compile(r"^={7}\s*$")
_LONE_ELLIPSIS = re.compile(r"^\s*\.\.\.\s*;?\s*$")


class GenericRules:
    def check(self, path: Path, text: str, language: str) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._placeholders(path, text, language))
        findings.extend(self._lone_ellipsis(path, text, language))
        findings.extend(self._conflicts(path, text))
        if not looks_minified(text):
            findings.extend(self._unbalanced(path, text, language))
        return findings

    def _placeholders(self, path: Path, text: str, language: str) -> list[Finding]:
        out: list[Finding] = []
        for hit in find_placeholder_hits(text, language=language):
            out.append(
                Finding(
                    rule_id="NE001",
                    severity=Severity.ERROR,
                    path=str(path),
                    message=f"Placeholder phrase: {hit.snippet!r}",
                    suggestion="Replace the placeholder with a real implementation before commit or deploy.",
                    line=hit.line,
                    column=hit.column,
                )
            )
        return out

    def _lone_ellipsis(self, path: Path, text: str, language: str) -> list[Finding]:
        if language == "python" or language == "markdown":
            return []
        findings: list[Finding] = []
        regions = regions_for(text, language)
        offset = 0
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _LONE_ELLIPSIS.match(line):
                dots = line.find("...")
                abs_off = offset + dots
                region = region_at(regions, abs_off)
                if region is not None and region.kind == Kind.STRING:
                    offset += len(line) + 1
                    continue
                findings.append(
                    Finding(
                        rule_id="NE002",
                        severity=Severity.ERROR,
                        path=str(path),
                        message="Bare ellipsis used as a standalone statement",
                        suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
                        line=lineno,
                        column=dots + 1,
                    )
                )
            offset += len(line) + 1
        return findings

    def _conflicts(self, path: Path, text: str) -> list[Finding]:
        lines = text.splitlines()
        has_start = any(_CONFLICT_START.match(line) for line in lines)
        has_end = any(_CONFLICT_END.match(line) for line in lines)
        if not (has_start or has_end):
            return []
        findings: list[Finding] = []
        for lineno, line in enumerate(lines, start=1):
            if (
                _CONFLICT_START.match(line)
                or _CONFLICT_END.match(line)
                or (has_start and _CONFLICT_MID.match(line))
            ):
                findings.append(
                    Finding(
                        rule_id="NE007",
                        severity=Severity.ERROR,
                        path=str(path),
                        message="Unresolved merge-conflict marker",
                        suggestion="Resolve the conflict and remove <<<<<<< / ======= / >>>>>>> markers.",
                        line=lineno,
                        column=1,
                    )
                )
        return findings

    def _unbalanced(self, path: Path, text: str, language: str) -> list[Finding]:
        result = scan_delimiters(text, language)
        if result is None:
            return []
        kind, line, col = result
        return [
            Finding(
                rule_id="NE005",
                severity=Severity.ERROR,
                path=str(path),
                message=kind,
                suggestion="Restore the missing delimiter; the file may have been truncated.",
                line=line,
                column=col,
            )
        ]


def looks_minified(text: str) -> bool:
    lines = text.splitlines() or [""]
    if any(len(line) > 4000 for line in lines):
        return True
    nonempty = [ln for ln in lines if ln.strip()]
    if nonempty and (sum(len(ln) for ln in nonempty) / len(nonempty)) > 400:
        return True
    return False


_PAIRS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {")": "(", "]": "[", "}": "{"}


def scan_delimiters(text: str, language: str) -> tuple[str, int, int] | None:
    """Scan (), [], {} in code regions only (strings and comments ignored)."""
    stack: list[tuple[str, int]] = []
    for region in regions_for(text, language):
        if region.kind != Kind.CODE:
            continue
        i = region.start
        while i < region.end:
            ch = text[i]
            if ch in _PAIRS:
                stack.append((ch, i))
            elif ch in _CLOSERS:
                if not stack or stack[-1][0] != _CLOSERS[ch]:
                    line, col = offset_to_linecol(text, i)
                    return (f"Unbalanced delimiter: unexpected {ch!r}", line, col)
                stack.pop()
            i += 1
    if stack:
        opener, off = stack[-1]
        line, col = offset_to_linecol(text, off)
        return (f"Unbalanced delimiter: unclosed {opener!r}", line, col)
    return None
