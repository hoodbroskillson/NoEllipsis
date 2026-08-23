# Architecture

NoEllipsis is a local static checker. The installed wheel has **zero** runtime dependencies.

```
CLI (check | compare | git-diff | rules)
        │
        ▼
   Config (defaults + pyproject + flags)
        │
        ▼
   Scanner ──► lex.py regions (code / string / comment)
        │
        ▼
   Rules NE001–NE007, NE101–NE104
        │
        ▼
   Formatters (text | json | github | sarif)
```

## Principles

1. Never execute scanned text.
2. Never mutate files or Git state.
3. Prefer a miss over a false positive.
4. Shared lexer: comments, strings, templates, raw strings, and heredocs are classified once.
5. stdout for a machine format is *only* that format. Progress and I/O errors go to stderr (or SARIF notifications).

## Lex

`regions_for(text, language)` returns ordered, non-overlapping `Region` spans covering the file. Python uses `tokenize` and falls back to the generic state machine. JS/TS, Go, Rust, and shell have extra string forms (templates, raw strings, heredocs).

## Compare / git-diff

`compare` reads two files and adds NE101–NE104. `git-diff` runs `git` with an argument list (`shell=False`) and scans added lines only.
