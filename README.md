# NoEllipsis

A fast, **local** CLI that detects incomplete or dangerously truncated LLM-generated code **before** you paste, commit, or deploy it.

NoEllipsis is a deterministic static checker. It does **not** call a model, does **not** need an API key, and **never** uploads your source. It never executes the files it scans and never changes Git state.

It is **not** an AI-content detector, a full compiler, a vulnerability scanner, a rewriter, or a hosted service.

## Why it exists

LLMs often emit:

- `def calculate_total(): ...`
- `// Rest of authentication code unchanged`
- A 40-line snippet in place of a 400-line module
- An unclosed Markdown fence
- A file that drops half the imports and two public functions

Those failures are cheap to catch with an AST walk and a few conservative heuristics. They are expensive if they land in `main`.

## Install

Requires Python 3.11+.

```bash
python -m pip install .
```

Then:

```bash
noellipsis --help
python -m noellipsis --help
```

Development:

```bash
python -m pip install -e ".[dev]"
ruff check
pytest -q
```

## Commands

### `noellipsis check FILE_OR_DIRECTORY`

Scan a file or a tree. Default excludes include `.git`, virtualenvs, `node_modules`, `vendor`, `dist`, `build`, coverage output, `__pycache__`, minified JS, and common binaries.

```bash
noellipsis check src/
noellipsis check examples/incomplete.py --format text
```

### `noellipsis compare GENERATED --against ORIGINAL`

Compare a model’s candidate against the file it was supposed to edit. Reports percent size reduction, removed top-level functions/classes/methods, removed imports, snippet-as-replacement, and any placeholders the candidate introduced.

```bash
noellipsis compare generated.py --against original.py
```

### `noellipsis git-diff` / `noellipsis git-diff --staged`

Inspect **added** lines in the working-tree (or staged) diff. Requires a Git repository. Uses `subprocess.run` with an argument list and `shell=False`. Does not stage, commit, reset, restore, or checkout anything.

```bash
noellipsis git-diff
noellipsis git-diff --staged --format github
```

Outside a repository the command exits `2` with a clear error.

## Options

| Option | Meaning |
| --- | --- |
| `--format text\|json\|github` | Human text, stable JSON, or GitHub Actions annotations |
| `--fail-on error\|warning` | Minimum severity that yields exit code `1` |
| `--exclude PATTERN` | Extra glob (repeatable) |
| `--disable RULE_ID` | Turn off a rule (repeatable) |
| `--shrink-threshold 40` | Percent shrinkage that triggers NE101 |
| `--verbose` | Progress on stderr |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Nothing at or above `--fail-on` |
| `1` | One or more findings at or above the threshold |
| `2` | Invalid arguments, unreadable path, not a git repo, or internal error |

## Rules

| ID | Default | What it catches |
| --- | --- | --- |
| **NE001** | error | Placeholder phrases (`Rest of code unchanged`, `Insert your code here`, stub-like `TODO`/`FIXME`) |
| **NE002** | error | Bare ellipsis / incomplete body. A Python function whose **entire** body is `...` is an error |
| **NE003** | warning | `pass`-only (or `raise NotImplementedError`-only) function, unless abstract or clearly intentional |
| **NE004** | error | Unclosed Markdown code fence |
| **NE005** | error | Unbalanced `()`, `[]`, `{}` via a state machine that skips strings and comments |
| **NE006** | error | Python syntax error / truncated statement (`ast.parse`) |
| **NE007** | error | Unresolved merge-conflict markers |
| **NE101** | error | Candidate dramatically shorter than the original (default 40% smaller) |
| **NE102** | error | Top-level function, class, or method removed |
| **NE103** | warning | Imports unexpectedly removed |
| **NE104** | error | Probable full-file replacement with a partial snippet |

Each finding includes: rule id, severity, file, line (when known), a short explanation, and a suggested next action.

## What NoEllipsis deliberately does **not** flag

These are regression-tested:

- `print("...")`
- `const copy = [...items];` and `function collect(...args) {}`
- Prose such as `Wait... what happened?`
- URLs and quoted documentation
- Intentional Python `@abstractmethod` / `Protocol` stubs
- `.pyi` stub files
- Empty constructors (`def __init__(self): pass`)
- JavaScript spread / rest (`...args`)

Language support: **strong AST for Python**. Conservative heuristics for JS/TS/JSX/TSX, Java, Go, Rust, C/C++, C#, Ruby, PHP, Shell, and Markdown. Prefer a miss over a false positive.

## Configuration

`pyproject.toml`:

```toml
[tool.noellipsis]
shrink-threshold = 40
fail-on = "error"
exclude = ["vendor/**", "generated/**"]
disable = ["NE103"]
```

CLI flags override the file.

## Suppressions

Works in `#`, `//`, `/* */`, `<!-- -->`, and other comment styles:

```python
def experimental():
    ...  # noellipsis: ignore[NE002]
```

```python
# noellipsis: ignore-file
```

Multiple ids: `noellipsis: ignore[NE002,NE003]`.

## Output

Text:

```
src/example.py:84:5 ERROR NE002 Bare ellipsis used as function body
  Replace the placeholder with an implementation or suppress NE002 if intentional.
```

GitHub Actions:

```
::error file=src/example.py,line=84,col=5::NE002 Bare ellipsis used as function body
```

JSON is stable (sorted keys, findings ordered by file / line / rule).

## Safety

- No network requests
- No evaluation or `exec` of scanned files
- Scanned files are never modified
- Git is read-only (`git rev-parse`, `git diff`)

## License

MIT © 2026 hoodbroskillson
