# NoEllipsis GitHub Action

Pin the exact tag. Do **not** use a floating `v1` tag.

```yaml
- uses: hoodbroskillson/NoEllipsis@v1.1.0
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
| `command` / `mode` | `check` | `check`, `git-diff`, or `compare` |
| `fail-on` | `error` | `error` or `warning` |
| `format` | `text` | `text`, `json`, `github`, `sarif` |
| `exclude` | _(empty)_ | Extra globs, one per line |
| `config` | _(empty)_ | Reserved; `[tool.noellipsis]` is still auto-discovered |
| `against` | _(empty)_ | Required when `command` is `compare` |
| `staged` | `false` | When `command` is `git-diff`, scan the index |

The composite action installs this repository from `GITHUB_ACTION_PATH` and runs a checked-in Python runner that builds an argv **list**. Consumer repository paths are never interpolated into a shell command.

## Permissions and exit codes

The action itself needs `contents: read` to see the checkout. SARIF upload (see `docs/sarif.md`) additionally needs `security-events: write`.

| Exit | Meaning |
| --- | --- |
| `0` | Nothing at or above `--fail-on` |
| `1` | One or more findings at or above the threshold |
| `2` | Invalid arguments, unreadable path, not a git repo, or internal error |

## SARIF

```yaml
- uses: hoodbroskillson/NoEllipsis@v1.1.0
  id: scan
  continue-on-error: true
  with:
    command: check
    path: .
    format: sarif
- uses: github/codeql-action/upload-sarif@v4
  if: always()
  with:
    sarif_file: noellipsis.sarif
```

Redirect stdout to a file in a wrapping step if you need a path for `upload-sarif`. The example workflow in this repository writes the file, uploads it even when the scanner exits `1`, then fails the job if findings exist.

## Platforms

Linux, macOS, and Windows GitHub-hosted runners (composite + Python runner).
