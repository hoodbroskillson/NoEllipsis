from __future__ import annotations

from pathlib import Path

from noellipsis.config import Config, apply_cli_overrides, load_pyproject
from noellipsis.scanner import Scanner


def test_inline_suppression(tmp_path: Path) -> None:
    text = "def experimental():\n    ...  # noellipsis: ignore[NE002]\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert findings == []


def test_previous_line_suppression(tmp_path: Path) -> None:
    text = "# noellipsis: ignore[NE002]\ndef experimental():\n    ...\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert findings == []


def test_file_suppression(tmp_path: Path) -> None:
    text = "# noellipsis: ignore-file\ndef experimental():\n    ...\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.py", text)
    assert findings == []


def test_js_comment_suppression(tmp_path: Path) -> None:
    text = "function f() {\n  ... // noellipsis: ignore[NE002]\n}\n"
    findings = Scanner(Config()).scan_text(tmp_path / "x.js", text)
    assert not any(f.rule_id == "NE002" for f in findings)


def test_disable_rule_via_config(tmp_path: Path) -> None:
    cfg = Config(disable=["NE002"])
    findings = Scanner(cfg).scan_text(tmp_path / "x.py", "def f():\n    ...\n")
    assert not any(f.rule_id == "NE002" for f in findings)


def test_load_pyproject(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.noellipsis]\nshrink-threshold = 25\nfail-on = \"warning\"\n"
        'exclude = ["vendor/**"]\ndisable = ["NE103"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_pyproject(tmp_path)
    assert cfg.shrink_threshold == 25
    assert cfg.fail_on == "warning"
    assert "NE103" in cfg.disable
    assert any(p.startswith("vendor") for p in cfg.exclude)


def test_cli_overrides() -> None:
    cfg = apply_cli_overrides(
        Config(),
        output_format="json",
        fail_on="warning",
        exclude=["tmp/**"],
        disable=["NE001"],
        shrink_threshold=10,
        verbose=True,
    )
    assert cfg.output_format == "json"
    assert cfg.fail_on == "warning"
    assert "tmp/**" in cfg.exclude
    assert cfg.shrink_threshold == 10
    assert cfg.verbose is True


def test_exclude_skips_vendor(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "bad.py").write_text("def f():\n    ...\n", encoding="utf-8")
    good = tmp_path / "app.py"
    good.write_text("def f():\n    return 1\n", encoding="utf-8")
    result = Scanner(Config()).scan_path(tmp_path)
    assert all("vendor" not in f.path for f in result.findings)
