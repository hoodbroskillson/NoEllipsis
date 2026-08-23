from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("noellipsis_action_run", ROOT / "action" / "run.py")
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
build_argv = _MOD.build_argv
ALLOWED_COMMANDS = _MOD.ALLOWED_COMMANDS


def test_build_argv_check() -> None:
    argv = build_argv(
        command="check",
        path="src",
        fail_on="error",
        fmt="sarif",
        exclude="vendor/**\ngenerated/**",
        config="",
        against="",
        staged="",
    )
    assert argv[-2:] == ["check", "src"]
    assert argv.count("--exclude") == 2
    assert "sarif" in argv
    assert all(isinstance(part, str) for part in argv)


def test_build_argv_rejects_injection() -> None:
    with pytest.raises(SystemExit):
        build_argv(
            command="check; rm -rf /",
            path=".",
            fail_on="error",
            fmt="text",
            exclude="",
            config="",
            against="",
            staged="",
        )
    with pytest.raises(SystemExit):
        build_argv(
            command="check",
            path=".",
            fail_on="error",
            fmt="xml;true",
            exclude="",
            config="",
            against="",
            staged="",
        )


def test_allowed_commands() -> None:
    assert ALLOWED_COMMANDS == {"check", "git-diff", "compare"}


def test_action_yml_pins() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    readme = (ROOT / "action/README.md").read_text(encoding="utf-8")
    assert "v1.1.0" in readme
    assert "GITHUB_ACTION_PATH" in action
    assert "action/run.py" in action
    assert "actions/setup-python@v7" in action
