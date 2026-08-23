# Contributing

Thanks for helping keep NoEllipsis small, local, and deterministic.

## Principles

1. **No network at runtime.** The installed package must work offline with the standard library only.
2. **Never execute scanned code.** Parse it or read it as text.
3. **Never modify scanned files or Git state.**
4. **Prefer misses over false positives.** Add a regression test for every “do not flag” case.
5. **Stable rule IDs.** Do not reuse `NE00x` / `NE10x` for a different meaning.
6. **Shared lexer.** New comment/string-aware logic belongs in `noellipsis.lex`, not a one-off regex.

## Setup

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
```

Python 3.11+ is required. CI runs 3.11–3.14 on Ubuntu, plus Windows and macOS on 3.12.

## Adding a rule

- Give it a stable id and a default severity.
- Implement it in `src/noellipsis/rules/`.
- Document it in the README table and CHANGELOG.
- Add a positive test and at least one false-positive test.

## Pull requests

- Keep changes focused.
- Do not add runtime dependencies.
- Run ruff and pytest before you push.

## Release checklist

1. Version is `1.1.0` (or the next semver) in `pyproject.toml` and `src/noellipsis/__init__.py`.
2. `CHANGELOG.md` has a dated section.
3. `ruff check .` and `pytest -q` pass; coverage stays at or above 90%.
4. `python -m build && python -m twine check dist/*` (from the `dev` or `release` extra).
5. A human tags `vX.Y.Z` on GitHub. See `docs/releasing.md`. Never publish to PyPI from your machine; never recreate `v1.0.0`.
