from __future__ import annotations

from pathlib import Path

import pytest

from noellipsis.cli import main
from noellipsis.config import ConfigError, load_config_file, load_pyproject


def test_explicit_config_wins_over_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.noellipsis]\nfail-on = "warning"\nshrink-threshold = 10\n',
        encoding="utf-8",
    )
    cfg_path = tmp_path / "extra.toml"
    cfg_path.write_text('[tool.noellipsis]\nfail-on = "error"\nshrink-threshold = 99\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = load_config_file(cfg_path)
    assert cfg.fail_on == "error"
    assert cfg.shrink_threshold == 99
    discovered = load_pyproject(tmp_path)
    assert discovered.fail_on == "warning"


def test_cli_flags_win_over_explicit_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ok.py").write_text("def leftover():\n    pass\n", encoding="utf-8")
    cfg_path = tmp_path / "cfg.toml"
    cfg_path.write_text('[tool.noellipsis]\nfail-on = "error"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # NE003 is a warning; fail-on error => 0; CLI --fail-on warning => 1
    assert main(["--config", str(cfg_path), "check", "ok.py"]) == 0
    assert main(["--config", str(cfg_path), "--fail-on", "warning", "check", "ok.py"]) == 1
    assert main(["check", "ok.py", "--config", str(cfg_path), "--fail-on", "warning"]) == 1


def test_missing_unreadable_malformed_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["--config", str(tmp_path / "nope.toml"), "check", "ok.py"]) == 2
    bad = tmp_path / "bad.toml"
    bad.write_text("not = [toml\n", encoding="utf-8")
    assert main(["--config", str(bad), "check", "ok.py"]) == 2
    empty = tmp_path / "empty.toml"
    empty.write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert main(["--config", str(empty), "check", "ok.py"]) == 2
    invalid = tmp_path / "invalid.toml"
    invalid.write_text('[tool.noellipsis]\nfail-on = "loud"\n', encoding="utf-8")
    assert main(["--config", str(invalid), "check", "ok.py"]) == 2
    with pytest.raises(ConfigError):
        load_config_file(tmp_path / "nope.toml")


def test_config_after_subcommand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    cfg = tmp_path / "cfg.toml"
    cfg.write_text('[tool.noellipsis]\nfail-on = "error"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["check", "ok.py", "--config", str(cfg)]) == 0


def test_config_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cfg.toml"
    path.write_text("[tool.noellipsis]\n", encoding="utf-8")

    def boom(self, *a, **k):
        raise OSError("denied")

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(ConfigError, match="cannot read"):
        load_config_file(path)
