from __future__ import annotations

import subprocess
from pathlib import Path

from noellipsis.cli import main
from noellipsis.compare import compare_files
from noellipsis.config import Config
from noellipsis.git import parse_diff, scan_git_diff
from noellipsis.rules.generic_rules import scan_delimiters
from noellipsis.scanner import Scanner, path_is_excluded


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_git_diff_body_only_ellipsis_is_ne002(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.py"
    target.write_text("def calculate_total():\n    return 1 + 2\n", encoding="utf-8")
    _git(["add", "app.py"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("def calculate_total():\n    ...\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    ids = [f.rule_id for f in result.findings]
    assert "NE002" in ids
    assert "NE006" not in ids


def test_compare_parse_failure_falls_back_to_heuristic(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    generated = tmp_path / "generated.py"
    original.write_text(
        "def alpha():\n    return 1\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )
    generated.write_text("def alpha():\n    return 1 +\n", encoding="utf-8")
    result = compare_files(generated, original, Config())
    assert any(f.rule_id == "NE102" and "beta" in f.message for f in result.findings)


def test_ignore_file_in_string_does_not_suppress(tmp_path: Path) -> None:
    text = "x = \"noellipsis: ignore-file\"\ndef calculate_total():\n    ...\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert any(f.rule_id == "NE002" for f in findings)


def test_inline_ignore_in_string_does_not_suppress(tmp_path: Path) -> None:
    text = "s = \"noellipsis: ignore[NE002]\"\ndef calculate_total():\n    ...\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert any(f.rule_id == "NE002" for f in findings)


def test_compare_inline_ignore_ne101(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text("import os\n\ndef a():\n    return os.name\n\ndef b():\n    return 2\n", encoding="utf-8")
    generated.write_text(
        "# noellipsis: ignore[NE101,NE102,NE103,NE104]\ndef a():\n    return 1\n",
        encoding="utf-8",
    )
    result = compare_files(generated, original, Config())
    ids = {f.rule_id for f in result.findings}
    assert "NE101" not in ids
    assert "NE102" not in ids
    assert "NE103" not in ids
    assert "NE104" not in ids


def test_exclude_relative_to_scan_root(tmp_path: Path, monkeypatch) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    proj = tmp_path / "proj"
    (proj / "keep").mkdir(parents=True)
    (proj / "skipme").mkdir()
    (proj / "keep" / "ok.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (proj / "skipme" / "bad.py").write_text("def f():\n    ...\n", encoding="utf-8")
    cfg = Config(exclude=["skipme/**"])
    result = Scanner(cfg).scan_path(proj)
    assert all("skipme" not in f.path for f in result.findings)
    assert path_is_excluded(proj / "skipme" / "bad.py", cfg, root=proj)


def test_ne001_skips_string_literal_and_prose(tmp_path: Path) -> None:
    py = "def demo():\n    print(\"Insert your code here\")\n    return 1\n"
    assert "NE001" not in [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "x.py", py)]
    md = "Quoted docs say \"Insert your code here\" in the tutorial.\n"
    assert "NE001" not in [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "x.md", md)]
    comment = "def demo():\n    # Insert your code here\n    return 1\n"
    assert "NE001" in [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "y.py", comment)]


def test_parse_quoted_git_path() -> None:
    diff = """diff --git "a/foo bar.py" "b/foo bar.py"
--- "a/foo bar.py"
+++ "b/foo bar.py"
@@ -0,0 +1,2 @@
+def calculate_total():
+    ...
"""
    files = parse_diff(diff)
    assert "foo bar.py" in files
    assert "..." in files["foo bar.py"]


def test_js_regex_not_unbalanced() -> None:
    text = "const re = /\\(/;\nfunction ok() { return 1; }\n"
    assert scan_delimiters(text, "javascript") is None


def test_go_raw_string_backticks() -> None:
    text = "package main\nfunc main() {\n    s := `quote \" and ( brace`\n    xs := []int{1, 2, 3}\n}\n"
    assert scan_delimiters(text, "go") is None


def test_unknown_backtick_not_a_string() -> None:
    text = "int main() {\n    char *s = `not-a-string;\n    int xs[] = {1, 2, 3};\n}\n"
    assert scan_delimiters(text, "c") is None


def test_cli_errors_do_not_override_findings(tmp_path: Path, capsys) -> None:
    from noellipsis import cli as cli_mod

    path = tmp_path / "x.py"
    path.write_text("def calculate_total():\n    ...\n", encoding="utf-8")

    real_scan = cli_mod.Scanner.scan_path

    def wrapped(self, target):
        result = real_scan(self, target)
        result.errors.append("partial read on sibling")
        return result

    cli_mod.Scanner.scan_path = wrapped
    try:
        code = main(["check", str(path)])
    finally:
        cli_mod.Scanner.scan_path = real_scan
    assert code == 2
    assert "partial read" in capsys.readouterr().err


def test_git_diff_skips_vendor_and_minjs(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.min.js").write_text("function f(){return 1;}\n", encoding="utf-8")
    _git(["add", "vendor/lib.py", "app.min.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    (vendor / "lib.py").write_text("def f():\n    ...\n", encoding="utf-8")
    (tmp_path / "app.min.js").write_text("function f(){\n  ...\n}\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert result.findings == []
    assert result.files_scanned == 0


def test_lone_ellipsis_skipped_in_markdown(tmp_path: Path) -> None:
    text = "Then the story continued...\n\n...\n\nThe end.\n"
    findings = Scanner(Config()).scan_text(tmp_path / "note.md", text)
    assert not any(f.rule_id == "NE002" for f in findings)


def test_abstractmethod_vs_concrete_empty_on_abc(tmp_path: Path) -> None:
    abstract = """
from abc import ABC, abstractmethod

class W(ABC):
    @abstractmethod
    def run(self):
        pass
"""
    concrete = """
from abc import ABC

class W(ABC):
    def run(self):
        pass
"""
    abs_ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "a.py", abstract)]
    con_ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "b.py", concrete)]
    assert "NE003" not in abs_ids
    assert "NE003" in con_ids


def test_conflict_marker_without_space(tmp_path: Path) -> None:
    text = "def merged():\n<<<<<<<HEAD\n    return 1\n=======\n    return 2\n>>>>>>>other\n"
    ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "c.py", text)]
    assert "NE007" in ids


def test_relative_imports_count_for_ne103(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text(
        "from . import helper\nfrom .mod import util\n\ndef a():\n    return helper.x\n\ndef b():\n    return util.y\n",
        encoding="utf-8",
    )
    generated.write_text("def a():\n    return 1\n", encoding="utf-8")
    result = compare_files(generated, original, Config())
    ne103 = [f for f in result.findings if f.rule_id == "NE103"]
    assert ne103
    msg = ne103[0].message
    assert "." in msg or ".mod" in msg


def test_git_diff_keeps_ne005_on_added_lines(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.js"
    target.write_text("function f() {\n  return foo();\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function f() {\n  return foo(\n}\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert any(f.rule_id == "NE005" for f in result.findings)


def test_git_diff_drops_preexisting_ne005_on_unmodified_lines(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.js"
    target.write_text("function f() {\n  return foo(\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function f() {\n  return foo(\n}\n// note\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert not any(f.rule_id == "NE005" for f in result.findings)


def test_git_diff_staged_reads_index_not_workdir(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.js"
    target.write_text("function f() { return 1; }\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function f() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    target.write_text("function f() {\n  ...\n}\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert not any(f.rule_id == "NE002" for f in result.findings)

    target.write_text("function f() {\n  // Insert your code here\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    target.write_text("function f() { return 1; }\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert any(f.rule_id == "NE001" for f in result.findings)


def test_compare_ignore_file_skips_extras(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text(
        "import os\n\ndef a():\n    return os.name\n\ndef b():\n    return 2\n",
        encoding="utf-8",
    )
    generated.write_text("# noellipsis: ignore-file\ndef a():\n    return 1\n", encoding="utf-8")
    result = compare_files(generated, original, Config())
    ids = {f.rule_id for f in result.findings}
    assert ids == set()


def test_compare_header_ignore_not_on_line_one(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text(
        "import os\n\ndef a():\n    return os.name\n\ndef b():\n    return 2\n",
        encoding="utf-8",
    )
    generated.write_text(
        "#!/usr/bin/env python\n# noellipsis: ignore[NE101,NE102,NE103,NE104]\ndef a():\n    return 1\n",
        encoding="utf-8",
    )
    result = compare_files(generated, original, Config())
    ids = {f.rule_id for f in result.findings}
    assert "NE101" not in ids
    assert "NE102" not in ids
    assert "NE103" not in ids
    assert "NE104" not in ids


def test_cli_errors_exit_two_when_files_scanned(tmp_path: Path, capsys) -> None:
    good = tmp_path / "ok.py"
    good.write_text("x = 1\n", encoding="utf-8")
    from noellipsis import cli as cli_mod

    real_scan = cli_mod.Scanner.scan_path

    def wrapped(self, target):
        result = real_scan(self, target)
        result.errors.append("Unreadable file: sibling.py: Permission denied")
        return result

    cli_mod.Scanner.scan_path = wrapped
    try:
        code = main(["check", str(good)])
    finally:
        cli_mod.Scanner.scan_path = real_scan
    assert code == 2
    assert "Unreadable file" in capsys.readouterr().err


def test_markdown_atx_heading_is_not_ne001(tmp_path: Path) -> None:
    md = "# Insert your code here\n\nThen write the function.\n"
    findings = Scanner(Config()).scan_text(tmp_path / "guide.md", md)
    assert not any(f.rule_id == "NE001" for f in findings)
    html = "<!-- Insert your code here -->\n"
    findings = Scanner(Config()).scan_text(tmp_path / "guide.md", html)
    assert any(f.rule_id == "NE001" for f in findings)


def test_git_diff_delete_only_unbalanced_ne005(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.js"
    target.write_text("function ok() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function ok() {\n  return 1;\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert any(f.rule_id == "NE005" for f in result.findings)


def test_git_diff_delete_only_truncated_ne006(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.py"
    target.write_text("def leftover():\n    return (\n        1\n    )\n", encoding="utf-8")
    _git(["add", "app.py"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("def leftover():\n    return (\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert any(f.rule_id == "NE006" for f in result.findings)


def test_git_diff_staged_delete_only_ne005(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.js"
    target.write_text("function ok() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function ok() {\n  return 1;\n", encoding="utf-8")
    _git(["add", "app.js"], tmp_path)
    result = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert any(f.rule_id == "NE005" for f in result.findings)


def test_cli_unreadable_plus_findings_prints_then_exit_2(tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.py"
    good.write_text("def calculate_total():\n    ...\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("x = 1\n", encoding="utf-8")
    real = Path.read_bytes

    def boom(self):
        if self.name == "bad.py":
            raise OSError("nope")
        return real(self)

    Path.read_bytes = boom
    try:
        code = main(["check", str(tmp_path)])
    finally:
        Path.read_bytes = real
    captured = capsys.readouterr()
    assert code == 2
    assert "NE002" in captured.out
    assert "Unreadable" in captured.err


def test_compare_ignore_after_module_docstring(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text(
        "import os\n\ndef a():\n    return os.name\n\ndef b():\n    return 2\n",
        encoding="utf-8",
    )
    generated.write_text(
        '"""Module docs."""\n# noellipsis: ignore[NE101]\ndef a():\n    return 1\n',
        encoding="utf-8",
    )
    result = compare_files(generated, original, Config())
    ids = {f.rule_id for f in result.findings}
    assert "NE101" not in ids
