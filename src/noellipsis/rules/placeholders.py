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


def find_placeholder_hits(text: str) -> list[PhraseHit]:
    hits: list[PhraseHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat in _PHRASE_RES:
            match = pat.search(line)
            if match:
                hits.append(PhraseHit(line=lineno, column=match.start() + 1, snippet=match.group(0)))
                break
    return hits


PLACEHOLDER_PATTERNS = _PHRASE_RES
