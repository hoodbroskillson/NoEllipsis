# SARIF 2.1.0

```bash
noellipsis check src --format sarif
```

stdout is a single deterministic JSON document:

- `$schema` points at the OASIS SARIF 2.1.0 schema
- `version` is `2.1.0`
- `runs[0].tool.driver.rules` lists every built-in rule
- `artifactLocation.uri` is repo-relative (never an absolute checkout path)
- `startLine` / `startColumn` are 1-based when known
- severity mapping: error→`error`, warning→`warning`, info→`note`
- `partialFingerprints.primaryLocationLineHash` is stable across machines
- unreadable files become `invocations[0].toolExecutionNotifications`

There is **no** `jsonschema` runtime dependency. Validity is covered by unit, snapshot, unicode-path, and determinism tests.

## GitHub code scanning

See `.github/workflows/noellipsis-sarif.yml`:

1. `permissions: contents: read` and `security-events: write`
2. `noellipsis check . --format sarif > noellipsis.sarif` with `continue-on-error: true` so an exit of `1` still uploads
3. `github/codeql-action/upload-sarif@v4`
4. fail the job if the scanner exit was not `0`

Reusable action pin: `hoodbroskillson/NoEllipsis@v1.1.1` (no floating `v1`).
