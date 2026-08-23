from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

import pytest

from noellipsis.cli import main
from noellipsis.compare import compare_files
from noellipsis.config import Config, apply_cli_overrides, load_pyproject
from noellipsis.formatters import format_result
from noellipsis.git import GitError, parse_diff, run_git, scan_git_diff
from noellipsis.models import Finding, ScanResult, Severity
from noellipsis.rules.generic_rules import looks_minified, scan_delimiters
from noellipsis.scanner import Scanner


def test_not_implemented_only(tmp_path: Path) -> None:
    text = "def f():\n    raise NotImplementedError()\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert any(f.rule_id == "NE003" for f in findings)


def test_class_ellipsis_body(tmp_path: Path) -> None:
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", "class Foo:\n    ...\n")
    assert any(f.rule_id == "NE002" for f in findings)


def test_decorator_call_and_attribute(tmp_path: Path) -> None:
    text = (
        "import abc\n"
        "class W(abc.ABC):\n"
        "    @abc.abstractmethod\n"
        "    def run(self):\n"
        "        pass\n"
        "\n"
        "def deco(fn):\n"
        "    return fn\n"
        "\n"
        "@deco()\n"
        "def real():\n"
        "    return 1\n"
    )
    ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "x.py", text)]
    assert "NE003" not in ids


def test_unexpected_closer() -> None:
    result = scan_delimiters("foo)\n", "javascript")
    assert result is not None
    assert "unexpected" in result[0]


def test_js_template_and_block_comment() -> None:
    text = "const x = `function(){`;\n/* leftover { */\nfunction ok() { return 1; }\n"
    assert scan_delimiters(text, "javascript") is None


def test_python_triple_quotes() -> None:
    text = 'def ok():\n    s = """ { ( [ """\n    return 1\n'
    assert scan_delimiters(text, "python") is None


def test_looks_minified() -> None:
    assert looks_minified("x" * 5001 + "\n")
    assert looks_minified(("a" * 450 + "\n") * 3)


def test_scan_path_missing(tmp_path: Path) -> None:
    result = Scanner(Config()).scan_path(tmp_path / "nope")
    assert result.errors


def test_compare_missing_original(tmp_path: Path) -> None:
    g = tmp_path / "g.py"
    g.write_text("x = 1\n", encoding="utf-8")
    result = compare_files(g, tmp_path / "missing.py", Config())
    assert result.errors


def test_cli_compare_missing(tmp_path: Path) -> None:
    g = tmp_path / "g.py"
    g.write_text("x = 1\n", encoding="utf-8")
    assert main(["compare", str(g), "--against", str(tmp_path / "no.py")]) == 2
    assert main(["compare", str(tmp_path / "no.py"), "--against", str(g)]) == 2


def test_cli_git_diff_outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["git-diff"]) == 2


def test_cli_check_unreadable_dir_ok(tmp_path: Path) -> None:
    # empty dir of unknown files
    (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")
    assert main(["check", str(tmp_path)]) == 0


def test_finding_without_line() -> None:
    f = Finding("NE104", Severity.INFO, "a.py", "m", "s")
    text = format_result(ScanResult(findings=[f]), "text")
    assert "A.py" not in text
    assert "a.py INFO NE104" in text
    gh = format_result(ScanResult(findings=[f]), "github")
    assert "file=a.py" in gh
    assert "line=" not in gh
    assert format_result(ScanResult(), "github") == ""


def test_load_pyproject_invalid_and_no_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text("not = [toml\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = load_pyproject(tmp_path)
    assert cfg.shrink_threshold == 40
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    cfg = load_pyproject(tmp_path / "pyproject.toml")
    assert cfg.fail_on == "error"
    (tmp_path / "pyproject.toml").write_text(
        '[tool.noellipsis]\nshrink-threshold = "nope"\nfail-on = "bogus"\nexclude = "one"\n',
        encoding="utf-8",
    )
    cfg = load_pyproject(tmp_path)
    assert cfg.shrink_threshold == 40
    assert cfg.fail_on == "error"


def test_apply_cli_none_exclude() -> None:
    cfg = apply_cli_overrides(Config(), exclude=None, disable=None)
    assert cfg.disable == []


def test_parse_diff_deleted() -> None:
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"
    assert parse_diff(diff) == {}


def test_run_git_and_scan_empty(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "i"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert result.files_scanned == 0
    proc = run_git(["status"], cwd=tmp_path)
    assert proc.returncode == 0


def test_git_error_on_bad_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    def fake(args, cwd=None):
        class P:
            returncode = 1
            stdout = ""
            stderr = "boom"

        if args[:1] == ["rev-parse"]:
            class Q:
                returncode = 0
                stdout = str(tmp_path) + "\n"
                stderr = ""

            return Q()
        return P()

    monkeypatch.setattr("noellipsis.git.run_git", fake)
    with pytest.raises(GitError):
        scan_git_diff(Config(), cwd=tmp_path)


def test_main_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["noellipsis", "--help"])
    with pytest.raises(SystemExit):
        runpy.run_module("noellipsis", run_name="__main__")


def test_html_ignore(tmp_path: Path) -> None:
    text = "<!-- noellipsis: ignore-file -->\n```python\n"
    assert Scanner(Config()).scan_text(tmp_path / "x.md", text) == []


def test_disable_via_cli_ne103_compare(tmp_path: Path) -> None:
    o = tmp_path / "o.py"
    g = tmp_path / "g.py"
    o.write_text("import os\n\ndef a():\n    return 1\n\ndef b():\n    return 2\n", encoding="utf-8")
    g.write_text("def a():\n    return 1\n", encoding="utf-8")
    args = ["--disable", "NE103", "--disable", "NE101", "--disable", "NE102", "--disable", "NE104"]
    code = main([*args, "compare", str(g), "--against", str(o)])
    assert code == 0


def test_todo_implement(tmp_path: Path) -> None:
    src = "def f():\n    # TODO: implement\n    return 1\n"
    ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "x.py", src)]
    assert "NE001" in ids


def test_existing_code_goes_here(tmp_path: Path) -> None:
    ids = [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / "x.rb", "# existing implementation goes here\n")]
    assert "NE001" in ids


def test_scan_unknown_extension(tmp_path: Path) -> None:
    assert Scanner(Config()).scan_text(tmp_path / "x.bin", "...") == []


def test_null_bytes(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_bytes(b"def f():\n    ...\n\x00")
    assert Scanner(Config()).scan_file(path) == []


def test_json_sort(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def a():\n    ...\n", encoding="utf-8")
    assert main(["--format", "json", "check", str(path)]) == 1


def test_as_str_list_via_config_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.noellipsis]\ndisable = ["NE001", "NE103"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_pyproject(tmp_path)
    assert cfg.disable == ["NE001", "NE103"]


def test_snippet_fence_replacement(tmp_path: Path) -> None:
    o = tmp_path / "o.py"
    g = tmp_path / "g.py"
    o.write_text("def a():\n    return 1\n\ndef b():\n    return 2\n", encoding="utf-8")
    g.write_text("```python\ndef a():\n    return 1\n```\n", encoding="utf-8")
    ids = {f.rule_id for f in compare_files(g, o, Config()).findings}
    assert "NE104" in ids


def test_indented_snippet(tmp_path: Path) -> None:
    o = tmp_path / "o.py"
    g = tmp_path / "g.py"
    src = "class A:\n    def x(self):\n        return 1\n\nclass B:\n    def y(self):\n        return 2\n"
    o.write_text(src, encoding="utf-8")
    g.write_text("    def x(self):\n        return 1\n", encoding="utf-8")
    ids = {f.rule_id for f in compare_files(g, o, Config()).findings}
    assert "NE101" in ids
    assert "NE104" in ids


def test_git_c_unquote_and_octal() -> None:
    from noellipsis.git import _c_unquote, _decode_git_path, parse_diff_details

    assert _c_unquote('"foo\\tbar"') == "foo\tbar"
    assert _c_unquote('"oct\\141"') == "octa"
    assert _c_unquote('"x\\q"') == "xq"
    assert _decode_git_path("b/plain.py") == "plain.py"
    assert _c_unquote('"caf\\303\\251.js"') == "café.js"
    assert _decode_git_path('"b/caf\\303\\251.js"') == "café.js"
    diff = (
        'diff --git a/x.py b/x.py\n'
        '--- a/x.py\n'
        '+++ b/x.py\n'
        '@@ -1,0 +1,1 @@\n'
        '+ok\n'
        '\\ No newline at end of file\n'
        '@@ -10,0 +11,1 @@\n'
        '+more\n'
    )
    details = parse_diff_details(diff)
    assert details[0].path == "x.py"
    assert len(details[0].hunks) == 2


def test_rust_raw_and_js_regex_class() -> None:
    rust = 'fn main() { let s = r#" ( { [ "#; let t = r"brace {"; let u = [1, 2]; }\n'
    assert scan_delimiters(rust, "rust") is None
    js = "const re = /[a(]/; function ok() { return 1; }\n"
    assert scan_delimiters(js, "javascript") is None
    js2 = "const re = /\\(/; const x = 1;\n"
    assert scan_delimiters(js2, "javascript") is None


def test_scan_text_minified_and_null(tmp_path: Path) -> None:
    assert Scanner(Config()).scan_text(tmp_path / "x.min.js", "function f(){...}") == []
    assert Scanner(Config()).scan_text(tmp_path / "x.js", "x" * 5001 + "\n") == []
    assert Scanner(Config()).scan_text(tmp_path / "x.py", "def f():\n    ...\n\x00") == []


def test_scan_file_unreadable(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")

    def boom(self):
        raise OSError("nope")

    monkeypatch.setattr(Path, "read_bytes", boom)
    result = Scanner(Config()).scan_path(path)
    assert result.errors


def test_cli_internal_and_oserror(tmp_path: Path, monkeypatch) -> None:
    from noellipsis import cli as cli_mod

    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("disk")

    monkeypatch.setattr(cli_mod, "Scanner", type("S", (), {"__init__": lambda self, cfg: None, "scan_path": boom}))
    assert main(["check", str(path)]) == 2

    def boom2(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_mod, "Scanner", type("S", (), {"__init__": lambda self, cfg: None, "scan_path": boom2}))
    assert main(["check", str(path)]) == 2


def test_cli_errors_nothing_scannable(tmp_path: Path) -> None:
    result_code = main(["check", str(tmp_path / "missing-dir")])
    assert result_code == 2


def test_python_attr_notimplemented_and_bases(tmp_path: Path) -> None:
    text = (
        "class E(Exception):\n"
        "    pass\n"
        "class C(foo.Bar):\n"
        "    def run(self):\n"
        "        raise builtins.NotImplementedError\n"
        "    @foo.deco\n"
        "    def other(self):\n"
        "        return 1\n"
    )
    Scanner(Config()).scan_text(tmp_path / "x.py", text)


def test_placeholders_escape_in_string() -> None:
    from noellipsis.rules.placeholders import find_placeholder_hits

    assert find_placeholder_hits('x = "Insert your code here"\\n') == []


def test_git_scan_missing_on_disk(tmp_path: Path) -> None:
    from noellipsis.git import DiffFile, _ellipsis_only_hunks

    patch = DiffFile(path="gone.py", added_text="    ...\\n", added_lines={3}, hunks=[[(3, "    ...")]])
    extra = _ellipsis_only_hunks(tmp_path / "gone.py", patch, [])
    assert extra and extra[0].rule_id == "NE002"
    extra2 = _ellipsis_only_hunks(tmp_path / "gone.py", patch, extra)
    assert extra2 == []
    empty = _ellipsis_only_hunks(tmp_path / "gone.py", DiffFile("x.py", "", hunks=[[(1, "   ")]]), [])
    assert empty == []
