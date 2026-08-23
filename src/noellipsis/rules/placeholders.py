"""NE001 placeholder-phrase detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from noellipsis.lex import Kind, regions_for

# Stub-like phrases commonly emitted by LLMs when they skip an implementation.
_PHRASE_RES = [
    re.compile(r"rest of (?:the )?(?:code|implementation|authentication|function|method|logic).{0,40}unchanged", re.I),
    re.compile(r"existing (?:code|implementation) goes here", re.I),
    re.compile(r"insert your code here", re.I),
    re.compile(r"your code here", re.I),
    re.compile(r"implementation goes here", re.I),
    re.compile(r"code goes here", re.I),
    re.compile(r"\[\s*rest of code\s*\]", re.I),
    re.compile(r"\.\.\.\s*existing code\s*\.\.\.", re.I),
    re.compile(
        r"(?:TODO|FIXME)\s*:?\s*(?:implement|implementation|add (?:the )?implementation|fill in|complete|stub)\b",
        re.I,
    ),
    re.compile(r"not implemented(?: yet)?\s*[.!]?\s*$", re.I),
]


@dataclass(frozen=True)
class PhraseHit:
    line: int
    column: int
    snippet: str


def comment_start(line: str, language: str = "") -> int | None:
    """Index where a language-aware comment begins, or None. Strings are not comments."""
    for region in regions_for(line if line.endswith("\n") else line + "\n", language):
        if region.kind == Kind.COMMENT:
            return region.start
    return None


def find_placeholder_hits(text: str, *, language: str = "") -> list[PhraseHit]:
    """Flag placeholder phrases only in comments, not quoted documentation."""
    hits: list[PhraseHit] = []
    for region in regions_for(text, language):
        if region.kind != Kind.COMMENT:
            continue
        region_text = text[region.start : region.end]
        for pat in _PHRASE_RES:
            match = pat.search(region_text)
            if not match:
                continue
            abs_off = region.start + match.start()
            line = text.count("\n", 0, abs_off) + 1
            last_nl = text.rfind("\n", 0, abs_off)
            column = abs_off + 1 if last_nl < 0 else abs_off - last_nl
            hits.append(PhraseHit(line=line, column=column, snippet=match.group(0)))
            break
    return hits


PLACEHOLDER_PATTERNS = _PHRASE_RES
