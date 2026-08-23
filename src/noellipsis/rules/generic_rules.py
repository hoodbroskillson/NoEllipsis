"""Language-agnostic heuristics: NE001, NE002 (lone line), NE005, NE007."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from noellipsis.models import Finding, Severity
from noellipsis.rules.placeholders import find_placeholder_hits

_CONFLICT_START = re.compile(r"^<{7}( |$)")
_CONFLICT_END = re.compile(r"^>{7}( |$)")
_CONFLICT_MID = re.compile(r"^={7}\s*$")
_LONE_ELLIPSIS = re.compile(r"^\s*\.\.\.\s*;?\s*$")


class GenericRules:
    def check(self, path: Path, text: str, language: str) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._placeholders(path, text))
        findings.extend(self._lone_ellipsis(path, text, language))
        findings.extend(self._conflicts(path, text))
        if not looks_minified(text):
            findings.extend(self._unbalanced(path, text, language))
        return findings

    def _placeholders(self, path: Path, text: str) -> list[Finding]:
        out: list[Finding] = []
        for hit in find_placeholder_hits(text):
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
        if language == "python":
            return []
        findings: list[Finding] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _LONE_ELLIPSIS.match(line):
                findings.append(
                    Finding(
                        rule_id="NE002",
                        severity=Severity.ERROR,
                        path=str(path),
                        message="Bare ellipsis used as a standalone statement",
                        suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
                        line=lineno,
                        column=line.find("...") + 1,
                    )
                )
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


@dataclass(frozen=True)
class _Style:
    line: str | None = None
    block_open: str | None = None
    block_close: str | None = None


def _comment_style(language: str) -> _Style:
    if language in {"python", "ruby", "shell"}:
        return _Style(line="#")
    if language in {
        "javascript",
        "typescript",
        "java",
        "go",
        "rust",
        "c",
        "cpp",
        "csharp",
        "php",
    }:
        return _Style(line="//", block_open="/*", block_close="*/")
    return _Style()


def scan_delimiters(text: str, language: str) -> tuple[str, int, int] | None:
    """State machine for (), [], {} that ignores strings and comments."""
    style = _comment_style(language)
    stack: list[tuple[str, int, int]] = []
    i = 0
    n = len(text)
    line = 1
    col = 1
    state = "code"

    def bump(count: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if i >= n:
                return
            ch = text[i]
            i += 1
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1

    while i < n:
        ch = text[i]
        if state == "code":
            if style.line and text.startswith(style.line, i):
                state = "line_comment"
                bump(len(style.line))
                continue
            if style.block_open and text.startswith(style.block_open, i):
                state = "block_comment"
                bump(len(style.block_open))
                continue
            if language == "python" and text.startswith("'''", i):
                state = "py_sq3"
                bump(3)
                continue
            if language == "python" and text.startswith('"""', i):
                state = "py_dq3"
                bump(3)
                continue
            if ch in "'\"`":
                if ch == "'":
                    state = "sq"
                elif ch == "`" and language in {"javascript", "typescript"}:
                    state = "template"
                else:
                    state = "dq"
                bump()
                continue
            if ch in _PAIRS:
                stack.append((ch, line, col))
                bump()
                continue
            if ch in _CLOSERS:
                if not stack or stack[-1][0] != _CLOSERS[ch]:
                    return (f"Unbalanced delimiter: unexpected {ch!r}", line, col)
                stack.pop()
                bump()
                continue
            bump()
            continue

        if state == "line_comment":
            if ch == "\n":
                state = "code"
            bump()
            continue

        if state == "block_comment":
            if style.block_close and text.startswith(style.block_close, i):
                bump(len(style.block_close))
                state = "code"
                continue
            bump()
            continue

        # string-like states
        closer = {
            "sq": "'",
            "dq": '"',
            "template": "`",
            "py_sq3": "'''",
            "py_dq3": '"""',
        }[state]
        if state in {"sq", "dq", "template"} and ch == "\\":
            bump(2)
            continue
        if text.startswith(closer, i):
            bump(len(closer))
            state = "code"
            continue
        bump()

    if stack:
        opener, ol, oc = stack[-1]
        return (f"Unbalanced delimiter: unclosed {opener!r}", ol, oc)
    return None
