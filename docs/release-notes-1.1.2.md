# NoEllipsis 1.1.2

Patch release. Still zero runtime dependencies. Still no network, telemetry, or rewrite. Published on PyPI: https://pypi.org/project/noellipsis/

## Highlights

- GitHub Action writes **validated SARIF 2.1.0** to `sarif-file` and exports `sarif-file` / `exit-code`
- `command` / `mode` alias resolves without a silent clash
- Real `--config PATH` (same `[tool.noellipsis]` schema; no silent fallback)
- CI runs real `pre-commit validate-manifest` and `try-repo`
- Version-aware release notes with SHA256SUMS injection
- Curated (not real-world) evals corpus with committed metrics

## Install

```bash
pipx install noellipsis
python -m pip install noellipsis
```

Pin the action and pre-commit hook to `v1.1.2`.

## Action SARIF upload

```yaml
- uses: actions/checkout@v7
- uses: hoodbroskillson/NoEllipsis@v1.1.2
  id: scan
  continue-on-error: true
  with:
    command: check
    path: src
    format: sarif
- uses: github/codeql-action/upload-sarif@v4
  if: always()
  with:
    sarif_file: ${{ steps.scan.outputs.sarif-file }}
- name: Fail if findings
  run: test "${{ steps.scan.outputs.exit-code }}" = "0"
```

## Checksums and provenance

Release assets include the wheel, sdist, and `SHA256SUMS`. Attestations use `actions/attest-build-provenance@v4`.

```
{{SHA256SUMS}}
```

Verify:

```bash
gh attestation verify noellipsis-1.1.2-py3-none-any.whl --repo hoodbroskillson/NoEllipsis
```

## Compatibility

- Breaking changes: **none**
- New CLI flag: `--config PATH`
- Action `command` default is empty (still becomes `check` when `mode` is also empty)

## Limitations

Unchanged: not a compiler, type checker, or AI-content detector.
