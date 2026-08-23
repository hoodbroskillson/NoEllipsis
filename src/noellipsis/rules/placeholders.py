"""NE001 placeholder-phrase detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

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


def _comment_start(line: str) -> int | None:
    """Index where a comment begins, or None. Strings are not comments."""
    i = 0
    n = len(line)
    quote: str | None = None
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\" and quote in {"'", '"', "`"}:
                i += 2
                continue
            if line.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            i += 1
            continue
        if line.startswith(('"""', "'''"), i):
            quote = line[i : i + 3]
            i += 3
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            i += 1
            continue
        if ch == "#":
            return i
        if line.startswith("//", i) or line.startswith("/*", i):
            return i
        if line.startswith("<!--", i):
            return i
        i += 1
    return None


def find_placeholder_hits(text: str, *, language: str = "") -> list[PhraseHit]:
    """Flag placeholder phrases only in comments, not quoted documentation."""
    del language  # reserved: comment detection is language-agnostic enough
    hits: list[PhraseHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        cstart = _comment_start(line)
        if cstart is None:
            continue
        region = line[cstart:]
        for pat in _PHRASE_RES:
            match = pat.search(region)
            if match:
                hits.append(
                    PhraseHit(
                        line=lineno,
                        column=cstart + match.start() + 1,
                        snippet=match.group(0),
                    )
                )
                break
    return hits


PLACEHOLDER_PATTERNS = _PHRASE_RES
