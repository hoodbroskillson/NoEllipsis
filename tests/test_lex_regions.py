from __future__ import annotations

from pathlib import Path

from noellipsis.cli import main
from noellipsis.config import Config
from noellipsis.lex import Kind, comment_spans, offset_to_linecol, region_at, regions_for
from noellipsis.rules.placeholders import comment_start, find_placeholder_hits
from noellipsis.scanner import Scanner


def _ids(tmp_path: Path, name: str, text: str) -> list[str]:
    return [f.rule_id for f in Scanner(Config()).scan_text(tmp_path / name, text)]


def test_js_template_placeholder_not_ne001(tmp_path: Path) -> None:
    text = "const documentation = `\n// Rest of code unchanged\n`;\n"
    assert "NE001" not in _ids(tmp_path, "doc.js", text)
    assert "NE002" not in _ids(tmp_path, "doc.js", text)


def test_js_template_lone_ellipsis_not_ne002(tmp_path: Path) -> None:
    text = "const documentation = `\n...\n`;\n"
    assert "NE002" not in _ids(tmp_path, "doc.js", text)


def test_go_raw_string_not_ne001(tmp_path: Path) -> None:
    text = "package main\nvar documentation = `\n// Rest of code unchanged\n`\n"
    assert "NE001" not in _ids(tmp_path, "doc.go", text)


def test_rust_raw_string_not_flagged(tmp_path: Path) -> None:
    text = 'fn main() {\n    let documentation = r#"\n// Rest of code unchanged\n...\n"#;\n}\n'
    ids = _ids(tmp_path, "doc.rs", text)
    assert "NE001" not in ids
    assert "NE002" not in ids


def test_shell_heredoc_quoted_and_unquoted(tmp_path: Path) -> None:
    quoted = "cat <<'EOF'\n# TODO: implement later\nEOF\n"
    unquoted = "cat <<EOF\n# TODO: implement later\nEOF\n"
    dash = "cat <<-EOF\n# TODO: implement later\nEOF\n"
    assert "NE001" not in _ids(tmp_path, "a.sh", quoted)
    assert "NE001" not in _ids(tmp_path, "b.sh", unquoted)
    assert "NE001" not in _ids(tmp_path, "c.sh", dash)


def test_python_docstring_not_ne001(tmp_path: Path) -> None:
    text = (
        "def documentation():\n"
        '    """\n'
        "    # TODO: implement later\n"
        "    // Rest of code unchanged\n"
        '    """\n'
        "    return 1\n"
    )
    assert "NE001" not in _ids(tmp_path, "doc.py", text)


def test_docstring_ignore_file_does_not_suppress(tmp_path: Path) -> None:
    text = '""" # noellipsis: ignore-file """\n\ndef unfinished():\n    ...\n'
    assert "NE002" in _ids(tmp_path, "x.py", text)


def test_string_suppression_never_suppresses(tmp_path: Path) -> None:
    text = 'msg = "# noellipsis: ignore[NE002]"\ndef unfinished():\n    ...\n'
    assert "NE002" in _ids(tmp_path, "x.py", text)


def test_real_comment_still_ne001(tmp_path: Path) -> None:
    assert "NE001" in _ids(tmp_path, "x.py", "def f():\n    # TODO: implement later\n    return 1\n")
    assert "NE001" in _ids(tmp_path, "x.js", "function f() {\n  // Rest of code unchanged\n}\n")


def test_real_suppression_still_works(tmp_path: Path) -> None:
    text = "def experimental():\n    ...  # noellipsis: ignore[NE002]\n"
    assert _ids(tmp_path, "x.py", text) == []


def test_js_comment_inside_template_expr(tmp_path: Path) -> None:
    text = "const x = `${\n  // Rest of authentication code unchanged\n  1\n}`;\n"
    assert "NE001" in _ids(tmp_path, "x.js", text)


def test_js_spread_still_ok(tmp_path: Path) -> None:
    text = "const copy = [...items];\nfunction collect(...args) { return args; }\n"
    assert "NE002" not in _ids(tmp_path, "ok.js", text)


def test_regions_cover_python_comment() -> None:
    text = "x = 1  # hi\n"
    kinds = [r.kind for r in regions_for(text, "python")]
    assert Kind.COMMENT in kinds
    assert Kind.CODE in kinds


def test_comment_start_and_spans() -> None:
    assert comment_start("x = 1  # hi", "python") is not None
    assert comment_start("x = \"# not\"", "python") is None
    text = "a = 1  # c\n"
    assert list(comment_spans(text, "python"))


def test_region_at_and_offsets() -> None:
    regs = regions_for("abc", "python")
    assert region_at(regs, 99) is None
    assert offset_to_linecol("a\nb", 3)[0] >= 1


def test_incomplete_python_fallback_still_comments() -> None:
    text = "def broken(:\n    # TODO: implement later\n"
    kinds = {r.kind for r in regions_for(text, "python")}
    assert Kind.COMMENT in kinds


def test_html_markdown_comment() -> None:
    text = "Hello <!-- Rest of code unchanged -->\n"
    assert find_placeholder_hits(text, language="markdown")


def test_js_regex_and_nested_template() -> None:
    text = "const re = /\\(/;\nconst x = `${`n` + 1}`;\n"
    assert regions_for(text, "javascript")


def test_php_hash_and_slash() -> None:
    text = "<?php\n# TODO: implement later\n// Rest of code unchanged\n$x = 1;\n"
    hits = find_placeholder_hits(text, language="php")
    assert hits


def test_rust_byte_raw() -> None:
    text = "let s = br#\"(\n#\" ;\n"
    regs = regions_for(text, "rust")
    assert any(r.kind == Kind.STRING for r in regs)


def test_cli_equals_form(tmp_path, capsys) -> None:
    path = tmp_path / "x.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert main(["check", str(path), "--format=json"]) == 0
    assert capsys.readouterr().out.startswith("{")


def test_js_template_expr_line_and_block_comments() -> None:
    text = """const x = `${
  /* Rest of code unchanged */
  // Rest of authentication code unchanged
  foo}
`;
"""
    hits = find_placeholder_hits(text, language="javascript")
    assert hits


def test_shell_heredoc_double_quoted() -> None:
    text = """cat <<"EOF"
# TODO: implement later
EOF
echo hi
"""
    assert not find_placeholder_hits(text, language="shell")


def test_empty_text_regions() -> None:
    assert regions_for("", "python") == []
    assert regions_for("plain", "")


def test_python_triple_fallback_unclosed() -> None:
    text = 's = """\n# TODO: implement later\n'
    # force fallback by using tokenize-unfriendly mix is hard; unclosed triple is still STRING
    kinds = {r.kind for r in regions_for(text.replace("\\n", chr(10)), "python")}
    assert Kind.STRING in kinds or Kind.COMMENT in kinds


def test_nested_js_template() -> None:
    text = "const x = `${`${1}` + /* Rest of code unchanged */ 2}`;"
    assert find_placeholder_hits(text, language="javascript")
