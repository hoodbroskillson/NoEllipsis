from __future__ import annotations

from pathlib import Path

from noellipsis.config import Config
from noellipsis.scanner import Scanner


def _scan(tmp_path: Path, name: str, text: str, cfg: Config | None = None) -> list[str]:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    findings = Scanner(cfg or Config()).scan_file(path)
    return [f.rule_id for f in findings]


def test_ne001_placeholder_phrase(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "auth.js", "function authenticate() {\n  // Rest of authentication code unchanged\n}\n")
    assert "NE001" in ids


def test_ne001_insert_your_code(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "x.py", "def foo():\n    # Insert your code here\n    return 1\n")
    assert "NE001" in ids


def test_ne002_python_ellipsis_body(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "calc.py", "def calculate_total():\n    ...\n")
    assert "NE002" in ids


def test_ne002_does_not_flag_print_ellipsis(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "ok.py", 'def show():\n    print("...")\n')
    assert "NE002" not in ids


def test_ne002_does_not_flag_prose(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "ok.py", 'def t():\n    return "Wait... what happened?"\n')
    assert "NE002" not in ids


def test_ne002_does_not_flag_url(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "ok.py", 'u = "https://example.com/a...z"\n')
    assert not ids


def test_ne002_js_spread_and_rest(tmp_path: Path) -> None:
    text = "const copy = [...items];\nfunction collect(...args) { return args; }\n"
    ids = _scan(tmp_path, "ok.js", text)
    assert "NE002" not in ids


def test_ne002_lone_js_ellipsis(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "x.js", "function f() {\n  ...\n}\n")
    assert "NE002" in ids


def test_ne003_pass_only_warning(tmp_path: Path) -> None:
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", "def leftover():\n    pass\n")
    assert any(f.rule_id == "NE003" and f.severity.value == "warning" for f in findings)


def test_ne003_skips_abstract_and_init(tmp_path: Path) -> None:
    text = """
from abc import ABC, abstractmethod
from typing import Protocol

class W(ABC):
    @abstractmethod
    def run(self):
        pass

class P(Protocol):
    def close(self) -> None: ...

class Box:
    def __init__(self):
        pass
"""
    ids = _scan(tmp_path, "ok.py", text)
    assert "NE002" not in ids
    assert "NE003" not in ids


def test_ne003_skips_pyi(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "mod.pyi", "def public_api(x: int) -> int: ...\n")
    assert "NE002" not in ids
    assert "NE003" not in ids


def test_ne004_unclosed_fence(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "n.md", "# t\n\n```python\ndef x():\n    return 1\n")
    assert "NE004" in ids


def test_ne004_closed_fence_ok(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "n.md", "```python\nx = 1\n```\n")
    assert "NE004" not in ids


def test_ne005_unbalanced(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "m.go", "package main\nfunc main() {\n    xs := []int{1, 2, 3\n}\n")
    assert "NE005" in ids


def test_ne005_ignores_braces_in_strings_and_comments(tmp_path: Path) -> None:
    text = 'def ok():\n    s = "function(){"\n    # leftover {\n    return 1\n'
    ids = _scan(tmp_path, "ok.py", text)
    assert "NE005" not in ids


def test_ne006_truncated_statement(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "t.py", "def broken():\n    value = 1 +\n")
    assert "NE006" in ids


def test_ne007_conflict_markers(tmp_path: Path) -> None:
    text = "def merged():\n<<<<<<< HEAD\n    return 1\n=======\n    return 2\n>>>>>>> other\n"
    ids = _scan(tmp_path, "c.py", text)
    assert "NE007" in ids


def test_heading_underline_not_conflict(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "t.md", "Title\n=======\n\nHello.\n")
    assert "NE007" not in ids


def test_todo_that_is_not_a_stub(tmp_path: Path) -> None:
    ids = _scan(tmp_path, "ok.py", "def f():\n    # TODO: rename this later\n    return 1\n")
    assert "NE001" not in ids
