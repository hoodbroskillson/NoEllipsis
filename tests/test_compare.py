from __future__ import annotations

from pathlib import Path

from noellipsis.compare import compare_files
from noellipsis.config import Config


def test_shrink_removed_function_imports_and_snippet(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    generated = tmp_path / "generated.py"
    original.write_text(
        "import os\nimport sys\nfrom pathlib import Path\n\n"
        "def alpha():\n    return os.name\n\n"
        "def beta():\n    return sys.version\n\n"
        "class Service:\n    def start(self):\n        return Path('.')\n"
        "    def stop(self):\n        return 'ok'\n",
        encoding="utf-8",
    )
    generated.write_text("def alpha():\n    ...\n", encoding="utf-8")
    result = compare_files(generated, original, Config())
    ids = {f.rule_id for f in result.findings}
    assert "NE101" in ids
    assert "NE102" in ids
    assert "NE103" in ids
    assert "NE104" in ids
    assert "NE002" in ids


def test_js_removed_function(tmp_path: Path) -> None:
    original = tmp_path / "a.js"
    generated = tmp_path / "b.js"
    original.write_text(
        "function alpha() { return 1; }\nfunction beta() { return 2; }\nfunction gamma() { return 3; }\n",
        encoding="utf-8",
    )
    generated.write_text("function alpha() { return 1; }\n", encoding="utf-8")
    result = compare_files(generated, original, Config())
    assert any(f.rule_id == "NE102" for f in result.findings)
    assert any(f.rule_id == "NE101" for f in result.findings)


def test_disable_ne103(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text("import os\n\ndef a():\n    return os.name\n\ndef b():\n    return 2\n", encoding="utf-8")
    generated.write_text("def a():\n    return 1\n", encoding="utf-8")
    result = compare_files(generated, original, Config(disable=["NE103"]))
    assert not any(f.rule_id == "NE103" for f in result.findings)


def test_unreadable_compare(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    original.write_text("x = 1\n", encoding="utf-8")
    result = compare_files(tmp_path / "missing.py", original, Config())
    assert result.errors



def test_compare_latin1_generated_is_error_not_crash(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    original.write_text("x = 1\n", encoding="utf-8")
    generated.write_bytes(b"x = '\xe9'\n")
    result = compare_files(generated, original, Config())
    assert result.errors
    assert not result.findings


def test_compare_latin1_original_is_error_not_crash(tmp_path: Path) -> None:
    original = tmp_path / "o.py"
    generated = tmp_path / "g.py"
    generated.write_text("x = 1\n", encoding="utf-8")
    original.write_bytes(b"x = '\xe9'\n")
    result = compare_files(generated, original, Config())
    assert result.errors
    assert not result.findings
