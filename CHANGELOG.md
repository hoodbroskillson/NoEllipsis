# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-08-23

### Fixed
- Release-notes renderer failed on v1.1.1 because the notes mentioned `{{SHA256SUMS}}` twice (once in prose). The marker now appears exactly once. Tag `v1.1.1` is left in place (no GitHub/PyPI artifacts).

[1.1.2]: https://github.com/hoodbroskillson/NoEllipsis/releases/tag/v1.1.2

## [1.1.1] - 2026-08-23

### Added
- GitHub Action writes validated SARIF 2.1.0 bytes to `sarif-file` (default `noellipsis.sarif`) and exposes `sarif-file` / `exit-code` outputs.
- Real `--config PATH` (before or after the subcommand). Explicit file wins over `pyproject.toml`; CLI flags still win over the file. Missing, unreadable, malformed, or invalid config exits `2` with no silent fallback.
- Version-aware release-notes renderer (`scripts/render_release_notes.py`) that injects `SHA256SUMS` into `docs/release-notes-<version>.md`.
- Curated (not real-world) regression corpus under `evals/` with committed TP/FP/TN/FN expectations.

### Fixed
- Action `command` / `mode` alias: empty defaults, prefer nonempty `command`, then `mode`, then `check`. Conflicting values fail clearly.
- Historical `docs/release-notes-1.1.0.md` now records that 1.1.0 is on PyPI, with real checksums and `gh attestation verify`.
- CI pre-commit job actually runs `validate-manifest` and `try-repo` (no `|| true` / string-only checks) and a throwaway consumer repo whose installed hook fails on a staged incomplete file.

### Changed
- Action and README examples pin `hoodbroskillson/NoEllipsis@v1.1.1`.
- Release workflow attests with `actions/attest-build-provenance@v4` and fails if versioned notes are missing.

[1.1.1]: https://github.com/hoodbroskillson/NoEllipsis/releases/tag/v1.1.1

## [1.1.0] - 2026-08-23

### Added
- SARIF 2.1.0 output (`--format sarif`) with driver rules, repo-relative URIs, 1-based locations, stable partial fingerprints, and invocation notifications for unreadable files.
- `noellipsis rules` lists every rule id, default severity, and short description (`--format text|json`).
- Reusable GitHub Action `hoodbroskillson/NoEllipsis@v1.1.0` (composite + Python argv runner; Linux/macOS/Windows).
- Example workflow that generates SARIF and uploads it with `github/codeql-action/upload-sarif@v4` even when the scanner exits 1.
- Hypothesis property tests (dev extra) and golden fixtures under `tests/fixtures/`.
- CI on Python 3.14; wheel/sdist smoke; Dependabot for github-actions and pip; CodeQL workflow.
- Release workflow builds artifacts once, writes SHA256SUMS, attests provenance, attaches the same bytes to the GitHub Release, and publishes via Trusted Publisher (`environment: pypi`, `pypa/gh-action-pypi-publish@release/v1`). No PyPI token secret.

### Changed
- Documentation landing page, architecture, SARIF, and releasing guides. Install remains git-tag until the first PyPI upload.
- Third-party Actions pinned to current majors (`actions/checkout@v7`, `actions/setup-python@v7`, `actions/upload-artifact@v7`, `actions/download-artifact@v8`, `actions/attest-build-provenance@v3`, CodeQL `@v4`).

[1.1.0]: https://github.com/hoodbroskillson/NoEllipsis/releases/tag/v1.1.0

## [1.0.0] - 2026-08-23

### Added
- Shared lexical-region scanner so comments, strings, templates, raw strings, and heredocs are classified once and reused by rules and suppressions.
- CLI shared options (`--format`, `--fail-on`, `--exclude`, `--disable`, `--shrink-threshold`, `--verbose`) work before or after the subcommand.
- Text output ends with a concise finding count (`2 findings: 1 error, 1 warning`).
- GitHub Actions annotations escape `%`, CR, newlines, commas, and colons.
- Official pre-commit hook (`id: noellipsis`) that runs `noellipsis git-diff --staged`.
- CI on Python 3.11–3.13 (Ubuntu) plus Windows and macOS on 3.12; release workflow for `v*.*.*` tags that builds artifacts and creates a GitHub release (not PyPI).
- Project URLs, optional `dev`/`release` extras for `build` and `twine`, and a Keep a Changelog file.

### Fixed
- Placeholder phrases and suppressions inside strings, docstrings, JS/TS templates, Go raw strings, Rust raw strings, and shell heredocs are no longer treated as comments.
- `--shrink-threshold` is validated as an integer from 0 to 100; invalid CLI flags or `[tool.noellipsis]` values exit `2`.
- Git C-quoted paths with non-UTF-8 bytes no longer crash `git-diff`.

### Changed
- Documentation rewritten for a v1.0.0 git-tag install; no PyPI claim.

[1.0.0]: https://github.com/hoodbroskillson/NoEllipsis/releases/tag/v1.0.0
