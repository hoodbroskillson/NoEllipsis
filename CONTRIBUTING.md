# Contributing

Thanks for helping keep NoEllipsis small, local, and deterministic.

## Principles

1. **No network at runtime.** The installed package must work offline with the standard library only.
2. **Never execute scanned code.** Parse it or read it as text.
3. **Never modify scanned files or Git state.**
4. **Prefer misses over false positives.** Add a regression test for every “do not flag” case.
5. **Stable rule IDs.** Do not reuse `NE00x` / `NE10x` for a different meaning.

## Setup

```bash
python -m pip install -e ".[dev]"
ruff check
pytest -q
```

Python 3.11+ is required for development that matches CI (3.11, 3.12, 3.13).

## Adding a rule

- Give it a stable id and a default severity.
- Implement it in `src/noellipsis/rules/`.
- Document it in the README table.
- Add a positive test and at least one false-positive test.

## Pull requests

- Keep changes focused.
- Do not add runtime dependencies.
- Run ruff and pytest before you push.
