# NoEllipsis GitHub Action

Pin the exact tag. Do **not** use a floating `v1` tag.

```yaml
- uses: hoodbroskillson/NoEllipsis@v1.1.2
  with:
    path: .
    command: check
    fail-on: error
    format: github
```

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `path` | `.` | File or directory (`check` / `compare`) |
| `command` | _(empty)_ | `check`, `git-diff`, or `compare`. Empty falls back to `mode`, then `check`. |
| `mode` | _(empty)_ | Alias for `command`. If both are nonempty and disagree, the step fails. |
| `fail-on` | `error` | `error` or `warning` |
| `format` | `text` | `text`, `json`, `github`, `sarif` |
| `exclude` | _(empty)_ | Extra globs, one per line |
| `config` | _(empty)_ | Path passed as `--config PATH` |
| `against` | _(empty)_ | Required when `command` is `compare` |
| `staged` | `false` | When `command` is `git-diff`, scan the index |
| `sarif-file` | `noellipsis.sarif` | Destination when `format` is `sarif` (created, parents included) |

## Outputs

| Output | Meaning |
| --- | --- |
| `sarif-file` | Absolute path written when `format` is `sarif` |
| `exit-code` | Process exit code (`0` / `1` / `2`) |

The composite action installs this repository from `GITHUB_ACTION_PATH` and runs a checked-in Python runner that builds an argv **list**. Consumer repository paths are never interpolated into a shell command. Relative `sarif-file` paths resolve against `GITHUB_WORKSPACE` and must stay inside it.

## Permissions and exit codes

The action itself needs `contents: read` to see the checkout. SARIF upload (see `docs/sarif.md`) additionally needs `security-events: write`.

| Exit | Meaning |
| --- | --- |
| `0` | Nothing at or above `--fail-on` |
| `1` | One or more findings at or above the threshold |
| `2` | Invalid arguments, unreadable path, not a git repo, or internal error |

## SARIF

When `format` is `sarif`, stdout is captured, validated as JSON with `version` `2.1.0`, and written as the exact bytes to `sarif-file`. stderr is left on the job log. The process exit code is preserved and also written to the `exit-code` output.

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

## Platforms

Linux, macOS, and Windows GitHub-hosted runners (composite + Python runner).
