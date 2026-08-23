# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
