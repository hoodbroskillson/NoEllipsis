# NoEllipsis 1.1.0

Local static checker for incomplete or truncated LLM-generated code. Still zero runtime dependencies. Still no network, telemetry, or rewrite.

## Highlights

- **SARIF 2.1.0** (`--format sarif`) for GitHub code scanning
- **`noellipsis rules`** lists every rule id and default severity
- **Reusable GitHub Action** `hoodbroskillson/NoEllipsis@v1.1.0` (exact tag; no floating `v1`)
- Hypothesis property tests (dev extra) and golden fixtures
- CI on Python 3.11–3.14 (Ubuntu) plus Windows and macOS
- Trusted Publishing workflow: one build, checksums, attestations, `environment: pypi`

## Install

Until the first PyPI upload, install from the git tag:

```bash
python -m pip install "noellipsis @ git+https://github.com/hoodbroskillson/NoEllipsis.git@v1.1.0"
```

After publish, `pipx install noellipsis` / `pip install noellipsis` will work. There is no PyPI badge yet.

## SARIF

```bash
noellipsis check src --format sarif > noellipsis.sarif
```

See `docs/sarif.md` and `.github/workflows/noellipsis-sarif.yml`.

## Action

```yaml
- uses: hoodbroskillson/NoEllipsis@v1.1.0
  with:
    command: check
    path: .
    format: github
```

## Python versions

Requires Python 3.11+. Tested on 3.11, 3.12, 3.13, and 3.14.

## Compatibility

- Breaking changes: **none**
- Existing `check` / `compare` / `git-diff` flags and option positions still work
- New format: `sarif`
- New command: `rules`

## Checksums and provenance

Release assets include the wheel, sdist, and `SHA256SUMS`. GitHub artifact attestations are produced by `actions/attest-build-provenance@v3` on the release workflow. Verify checksums after download; do not trust a wheel copied from an unattested machine.

Checksum placeholders (filled by `release.yml` at tag time):

```
<sha256>  noellipsis-1.1.0-py3-none-any.whl
<sha256>  noellipsis-1.1.0.tar.gz
```

## Upgrade

```bash
python -m pip install --upgrade "noellipsis @ git+https://github.com/hoodbroskillson/NoEllipsis.git@v1.1.0"
```

pre-commit consumers should set `rev: v1.1.0`.

## Limitations

Unchanged: not a compiler, type checker, or AI-content detector. Non-Python languages stay conservative. Compare shrink is byte-size based.
