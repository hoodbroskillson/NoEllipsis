# NoEllipsis 1.1.0

Local static checker for incomplete or truncated LLM-generated code. Still zero runtime dependencies. Still no network, telemetry, or rewrite.

NoEllipsis 1.1.0 **is on PyPI**: https://pypi.org/project/noellipsis/

## Highlights

- **SARIF 2.1.0** (`--format sarif`) for GitHub code scanning
- **`noellipsis rules`** lists every rule id and default severity
- **Reusable GitHub Action** `hoodbroskillson/NoEllipsis@v1.1.0` (exact tag; no floating `v1`)
- Hypothesis property tests (dev extra) and golden fixtures
- CI on Python 3.11–3.14 (Ubuntu) plus Windows and macOS
- Trusted Publishing workflow: one build, checksums, attestations, `environment: pypi`

## Install

```bash
pipx install noellipsis
python -m pip install noellipsis
```

From the git tag (same version):

```bash
python -m pip install "noellipsis @ git+https://github.com/hoodbroskillson/NoEllipsis.git@v1.1.0"
```

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

Release assets include the wheel, sdist, and `SHA256SUMS`. GitHub artifact attestations were produced on the 1.1.0 release workflow.

```
06d10994dabc7658247a07fbf362f743f5a242577c7ba69ef5d7a13d35926a84  noellipsis-1.1.0-py3-none-any.whl
154ec70778eed56725118c768cab0d5bed00c8b69264306d928ab546aa6b96b3  noellipsis-1.1.0.tar.gz
```

Verify a downloaded wheel:

```bash
gh attestation verify noellipsis-1.1.0-py3-none-any.whl --repo hoodbroskillson/NoEllipsis
```

## Upgrade

```bash
python -m pip install --upgrade noellipsis
```

pre-commit consumers should set `rev: v1.1.0`.

## Limitations

Unchanged: not a compiler, type checker, or AI-content detector. Non-Python languages stay conservative. Compare shrink is byte-size based.
