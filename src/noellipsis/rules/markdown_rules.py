"""Markdown-specific rules (NE004)."""

from __future__ import annotations

import re
from pathlib import Path

from noellipsis.models import Finding, Severity

_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})")


class MarkdownRules:
    def check(self, path: Path, text: str) -> list[Finding]:
        fence: str | None = None
        fence_line = 0
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = _FENCE.match(line)
            if not match:
                continue
            marker = match.group(2)[0] * len(match.group(2))
            if fence is None:
                fence = marker
                fence_line = lineno
            elif line.strip().startswith(fence[0] * len(fence)) and len(line.strip()) >= len(fence):
                # Closing fence: same character, at least as long, no info string required
                if line.strip()[0] == fence[0] and set(line.strip().split()[0]) == {fence[0]}:
                    fence = None
                    fence_line = 0
        if fence is not None:
            return [
                Finding(
                    rule_id="NE004",
                    severity=Severity.ERROR,
                    path=str(path),
                    message="Unclosed Markdown code fence",
                    suggestion="Close the fenced block with a matching ``` or ~~~ line.",
                    line=fence_line,
                    column=1,
                )
            ]
        return []
