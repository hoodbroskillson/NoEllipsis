"""Shared lexical regions: code vs string vs comment. Never executes scanned text."""

from __future__ import annotations

import io
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

STRING_TOKENS = {tokenize.STRING}
COMMENT_TOKENS = {tokenize.COMMENT}
if hasattr(tokenize, "FSTRING_START"):
    STRING_TOKENS.update(
        {
            tokenize.FSTRING_START,
            tokenize.FSTRING_MIDDLE,
            tokenize.FSTRING_END,
        }
    )


class Kind(StrEnum):
    CODE = "code"
    STRING = "string"
    COMMENT = "comment"


@dataclass(frozen=True)
class Region:
    kind: Kind
    start: int
    end: int


def line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def offset_to_linecol(text: str, offset: int) -> tuple[int, int]:
    offset = max(0, min(offset, len(text)))
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    col = offset + 1 if last_nl < 0 else offset - last_nl
    return line, col


def _pos_to_offset(starts: list[int], line: int, col: int, n: int) -> int:
    if line < 1:
        return 0
    if line > len(starts):
        return n
    return min(n, starts[line - 1] + col)


def regions_for(text: str, language: str = "") -> list[Region]:
    """Return non-overlapping regions covering *text* (possibly empty)."""
    lang = (language or "").lower()
    if not text:
        return []
    if lang == "python":
        return _python_regions(text)
    return _machine_regions(text, lang)


def region_at(regions: list[Region], offset: int) -> Region | None:
    for region in regions:
        if region.start <= offset < region.end:
            return region
    return None


def comment_spans(text: str, language: str = "") -> Iterable[Region]:
    for region in regions_for(text, language):
        if region.kind == Kind.COMMENT:
            yield region


def _coalesce(raw: list[Region], n: int) -> list[Region]:
    raw.sort(key=lambda r: r.start)
    filled: list[Region] = []
    cursor = 0
    for region in raw:
        start = max(region.start, cursor)
        end = min(region.end, n)
        if start > cursor:
            filled.append(Region(Kind.CODE, cursor, start))
        if end > start:
            if filled and filled[-1].kind == region.kind and filled[-1].end == start:
                filled[-1] = Region(region.kind, filled[-1].start, end)
            else:
                filled.append(Region(region.kind, start, end))
            cursor = end
    if cursor < n:
        filled.append(Region(Kind.CODE, cursor, n))
    return filled


def _python_regions(text: str) -> list[Region]:
    starts = line_starts(text)
    n = len(text)
    raw: list[Region] = []
    try:
        reader = io.BytesIO(text.encode("utf-8")).readline
        for tok in tokenize.tokenize(reader):
            skip = {
                tokenize.ENCODING,
                tokenize.ENDMARKER,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
            }
            if tok.type in skip:
                continue
            start = _pos_to_offset(starts, tok.start[0], tok.start[1], n)
            end = _pos_to_offset(starts, tok.end[0], tok.end[1], n)
            if tok.type in COMMENT_TOKENS:
                raw.append(Region(Kind.COMMENT, start, end))
            elif tok.type in STRING_TOKENS:
                raw.append(Region(Kind.STRING, start, end))
    except (tokenize.TokenError, SyntaxError, UnicodeError):
        return _machine_regions(text, "python")
    return _coalesce(raw, n)


def _js_slash_starts_regex(text: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and text[j] in " \t":
        j -= 1
    if j < 0:
        return True
    ch = text[j]
    if ch in "=(:,[{!&|?~^;+-*%\n":
        return True
    k = j
    while k >= 0 and (text[k].isalnum() or text[k] == "_"):
        k -= 1
    word = text[k + 1 : j + 1]
    return word in {
        "return",
        "case",
        "throw",
        "new",
        "typeof",
        "delete",
        "void",
        "await",
        "yield",
        "in",
        "of",
    }


def _rust_raw_header(text: str, i: int) -> tuple[int, int] | None:
    idx = i
    if idx < len(text) and text[idx] in {"b", "c"}:
        idx += 1
    if idx >= len(text) or text[idx] != "r":
        return None
    idx += 1
    hashes = 0
    while idx < len(text) and text[idx] == "#":
        hashes += 1
        idx += 1
    if idx < len(text) and text[idx] == '"':
        return idx - i + 1, hashes
    return None


def _heredoc_opener(text: str, i: int) -> tuple[int, str, bool] | None:
    if not text.startswith("<<", i):
        return None
    j = i + 2
    strip_tabs = False
    if j < len(text) and text[j] == "-":
        strip_tabs = True
        j += 1
    while j < len(text) and text[j] in " \t":
        j += 1
    quote = None
    if j < len(text) and text[j] in ("'", '"'):
        quote = text[j]
        j += 1
    start = j
    while j < len(text) and (text[j].isalnum() or text[j] in "_-"):
        j += 1
    word = text[start:j]
    if not word:
        return None
    if quote:
        if j >= len(text) or text[j] != quote:
            return None
        j += 1
    return j, word, strip_tabs


def _machine_regions(text: str, language: str) -> list[Region]:
    n = len(text)
    raw: list[Region] = []
    i = 0
    state = "code"
    rust_hashes = 0
    template_stack: list[tuple[str, int]] = []
    heredoc_word = ""
    py_close = ""
    heredoc_strip = False

    hash_langs = {"python", "ruby", "shell", "php"}
    slash_langs = {
        "javascript",
        "typescript",
        "java",
        "go",
        "rust",
        "c",
        "cpp",
        "csharp",
        "php",
    }
    allow_hash = language in hash_langs or language == ""
    allow_slash = language in slash_langs or language == ""
    allow_html = language in {"markdown", ""} or language not in hash_langs
    if language == "markdown":
        allow_hash = False
        allow_slash = False
        allow_html = True
    js = language in {"javascript", "typescript"}
    go = language == "go"
    rust = language == "rust"
    py = language == "python"
    shell = language == "shell"

    def emit(kind: Kind, start: int, end: int) -> None:
        if end > start:
            raw.append(Region(kind, start, end))

    mark = 0
    kind = Kind.CODE

    def switch(new_kind: Kind, at: int) -> None:
        nonlocal mark, kind
        emit(kind, mark, at)
        mark = at
        kind = new_kind

    while i < n:
        ch = text[i]
        if state == "code":
            if py and text.startswith(('"""', "'''"), i):
                py_close = text[i : i + 3]
                switch(Kind.STRING, i)
                state = "py3"
                i += 3
                continue
            if allow_hash and ch == "#":
                switch(Kind.COMMENT, i)
                state = "line_comment"
                i += 1
                continue
            if allow_slash and text.startswith("//", i):
                switch(Kind.COMMENT, i)
                state = "line_comment"
                i += 2
                continue
            if allow_slash and text.startswith("/*", i):
                switch(Kind.COMMENT, i)
                state = "block_comment"
                i += 2
                continue
            if allow_html and text.startswith("<!--", i):
                switch(Kind.COMMENT, i)
                state = "html_comment"
                i += 4
                continue
            if rust:
                header = _rust_raw_header(text, i)
                if header is not None:
                    prefix, rust_hashes = header
                    switch(Kind.STRING, i)
                    i += prefix
                    state = "rust_raw"
                    continue
            if shell:
                hd = _heredoc_opener(text, i)
                if hd is not None:
                    end_op, heredoc_word, heredoc_strip = hd
                    i = end_op
                    continue
            if js and ch == "/" and not text.startswith("//", i) and not text.startswith("/*", i):
                if _js_slash_starts_regex(text, i):
                    switch(Kind.STRING, i)
                    state = "js_regex"
                    i += 1
                    continue
            if ch == "`":
                if js:
                    switch(Kind.STRING, i)
                    state = "template"
                    i += 1
                    continue
                if go:
                    switch(Kind.STRING, i)
                    state = "go_raw"
                    i += 1
                    continue
            if ch in {"'", '"'}:
                switch(Kind.STRING, i)
                state = "sq" if ch == "'" else "dq"
                i += 1
                continue
            if ch == "\n" and heredoc_word:
                switch(Kind.STRING, i + 1)
                state = "heredoc"
                i += 1
                continue
            i += 1
            continue

        if state == "line_comment":
            if ch == "\n":
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "block_comment":
            if text.startswith("*/", i):
                i += 2
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "html_comment":
            if text.startswith("-->", i):
                i += 3
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "js_regex":
            if ch == "\\":
                i += 2
                continue
            if ch == "[":
                state = "js_regex_class"
                i += 1
                continue
            if ch == "/":
                i += 1
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "js_regex_class":
            if ch == "\\":
                i += 2
                continue
            if ch == "]":
                state = "js_regex"
                i += 1
                continue
            i += 1
            continue

        if state == "go_raw":
            if ch == "`":
                i += 1
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "rust_raw":
            if ch == '"' and text[i + 1 : i + 1 + rust_hashes] == ("#" * rust_hashes):
                i += 1 + rust_hashes
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "py3":
            if py_close and text.startswith(py_close, i):
                i += 3
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "template":
            if ch == "\\":
                i += 2
                continue
            if text.startswith("${", i):
                i += 2
                switch(Kind.CODE, i)
                template_stack.append(("template", 0))
                state = "template_expr"
                continue
            if ch == "`":
                i += 1
                switch(Kind.CODE, i)
                state = "code"
                continue
            i += 1
            continue

        if state == "template_expr":
            if allow_slash and text.startswith("//", i):
                switch(Kind.COMMENT, i)
                state = "tpl_line_comment"
                i += 2
                continue
            if allow_slash and text.startswith("/*", i):
                switch(Kind.COMMENT, i)
                state = "tpl_block_comment"
                i += 2
                continue
            if ch == "`":
                switch(Kind.STRING, i)
                state = "nested_template"
                i += 1
                continue
            if ch in {"'", '"'}:
                switch(Kind.STRING, i)
                state = "tpl_sq" if ch == "'" else "tpl_dq"
                i += 1
                continue
            if ch == "{":
                ret, depth = template_stack[-1]
                template_stack[-1] = (ret, depth + 1)
                i += 1
                continue
            if ch == "}":
                ret, depth = template_stack[-1]
                if depth == 0:
                    template_stack.pop()
                    switch(Kind.STRING, i)
                    i += 1
                    state = ret
                    continue
                template_stack[-1] = (ret, depth - 1)
                i += 1
                continue
            i += 1
            continue

        if state == "nested_template":
            if ch == "\\":
                i += 2
                continue
            if text.startswith("${", i):
                i += 2
                switch(Kind.CODE, i)
                template_stack.append(("nested_template", 0))
                state = "template_expr"
                continue
            if ch == "`":
                i += 1
                switch(Kind.CODE, i)
                state = "template_expr"
                continue
            i += 1
            continue

        if state == "tpl_line_comment":
            if ch == "\n":
                switch(Kind.CODE, i)
                state = "template_expr"
                continue
            i += 1
            continue

        if state == "tpl_block_comment":
            if text.startswith("*/", i):
                i += 2
                switch(Kind.CODE, i)
                state = "template_expr"
                continue
            i += 1
            continue

        if state in {"tpl_sq", "tpl_dq"}:
            closer = "'" if state == "tpl_sq" else '"'
            if ch == "\\":
                i += 2
                continue
            if ch == closer:
                i += 1
                switch(Kind.CODE, i)
                state = "template_expr"
                continue
            i += 1
            continue

        if state == "heredoc":
            if ch == "\n" or i == 0:
                line_start = i + 1 if ch == "\n" else i
                rest = text[line_start:]
                line = rest.split("\n", 1)[0]
                candidate = line.lstrip("\t") if heredoc_strip else line
                if candidate == heredoc_word:
                    end = line_start + len(line)
                    switch(Kind.CODE, end)
                    heredoc_word = ""
                    state = "code"
                    i = end
                    continue
            i += 1
            continue

        # sq / dq
        closer = "'" if state == "sq" else '"'
        if ch == "\\":
            i += 2
            continue
        if ch == closer:
            i += 1
            switch(Kind.CODE, i)
            state = "code"
            continue
        i += 1

    emit(kind, mark, n)
    return _coalesce(raw, n)
