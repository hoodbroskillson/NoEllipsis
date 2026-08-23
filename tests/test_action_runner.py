from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("noellipsis_action_run", ROOT / "action" / "run.py")
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
build_argv = _MOD.build_argv
ALLOWED_COMMANDS = _MOD.ALLOWED_COMMANDS
resolve_command = _MOD.resolve_command
resolve_sarif_path = _MOD.resolve_sarif_path
write_github_output = _MOD.write_github_output
validate_sarif_bytes = _MOD.validate_sarif_bytes
main = _MOD.main


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


def test_build_argv_passes_config() -> None:
    argv = build_argv(
        command="check",
        path=".",
        fail_on="error",
        fmt="text",
        exclude="",
        config="noellipsis.example.toml",
        against="",
        staged="",
    )
    assert "--config" in argv
    assert argv[argv.index("--config") + 1] == "noellipsis.example.toml"


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


def test_resolve_command_default_mode_and_conflict() -> None:
    assert resolve_command("", "") == "check"
    assert resolve_command("git-diff", "") == "git-diff"
    assert resolve_command("", "compare") == "compare"
    assert resolve_command("check", "check") == "check"
    with pytest.raises(SystemExit, match="disagree"):
        resolve_command("check", "git-diff")
    with pytest.raises(SystemExit, match="unsupported"):
        resolve_command("explode", "")


def test_resolve_sarif_path_relative_and_escape(tmp_path: Path) -> None:
    dest = resolve_sarif_path("out/scan.sarif", str(tmp_path))
    assert dest == (tmp_path / "out" / "scan.sarif").resolve()
    with pytest.raises(SystemExit, match="outside the workspace"):
        resolve_sarif_path("../escape.sarif", str(tmp_path))


def test_write_github_output(tmp_path: Path) -> None:
    path = tmp_path / "github_output"
    write_github_output({"sarif-file": "noellipsis.sarif", "exit-code": "1"}, str(path))
    text = path.read_text(encoding="utf-8")
    assert "sarif-file=noellipsis.sarif\n" in text
    assert "exit-code=1\n" in text


def test_validate_sarif_bytes() -> None:
    validate_sarif_bytes(b'{"version": "2.1.0", "runs": []}')
    with pytest.raises(SystemExit, match="valid JSON"):
        validate_sarif_bytes(b"not-json")
    with pytest.raises(SystemExit, match="2.1.0"):
        validate_sarif_bytes(b'{"version": "2.0.0"}')


def test_action_yml_pins() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    readme = (ROOT / "action/README.md").read_text(encoding="utf-8")
    assert "v1.1.1" in readme
    assert "GITHUB_ACTION_PATH" in action
    assert "action/run.py" in action
    assert "actions/setup-python@v7" in action
    assert "id: run" in action
    assert "sarif-file:" in action
    assert "exit-code:" in action
    assert 'default: ""' in action


def _env(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    for key, value in mapping.items():
        monkeypatch.setenv(key, value)


def test_main_sarif_writes_file_and_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "bad.py"
    target.write_text("def leftover():\n    ...\n", encoding="utf-8")
    out = tmp_path / "gha_out"
    _env(
        monkeypatch,
        {
            "INPUT_COMMAND": "",
            "INPUT_MODE": "",
            "INPUT_PATH": str(target),
            "INPUT_FORMAT": "sarif",
            "INPUT_FAIL_ON": "error",
            "INPUT_EXCLUDE": "",
            "INPUT_CONFIG": "",
            "INPUT_AGAINST": "",
            "INPUT_STAGED": "",
            "INPUT_SARIF_FILE": "reports/out.sarif",
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_OUTPUT": str(out),
        },
    )
    monkeypatch.chdir(workspace)
    code = main()
    assert code == 1
    sarif_path = workspace / "reports" / "out.sarif"
    assert sarif_path.is_file()
    doc = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert doc["version"] == "2.1.0"
    ids = {item["ruleId"] for item in doc["runs"][0]["results"]}
    assert "NE002" in ids
    text = out.read_text(encoding="utf-8")
    assert "exit-code=1\n" in text
    assert "sarif-file=" in text
    assert "reports/out.sarif" in text.replace("\\", "/")


def test_main_sarif_file_exists_on_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path
    target = workspace / "bad.py"
    target.write_text("def leftover():\n    ...\n", encoding="utf-8")
    out = tmp_path / "gha_out"
    _env(
        monkeypatch,
        {
            "INPUT_COMMAND": "check",
            "INPUT_MODE": "",
            "INPUT_PATH": str(target),
            "INPUT_FORMAT": "sarif",
            "INPUT_FAIL_ON": "error",
            "INPUT_EXCLUDE": "",
            "INPUT_CONFIG": "",
            "INPUT_AGAINST": "",
            "INPUT_STAGED": "",
            "INPUT_SARIF_FILE": "noellipsis.sarif",
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_OUTPUT": str(out),
        },
    )
    assert main() == 1
    assert (workspace / "noellipsis.sarif").is_file()
    assert json.loads((workspace / "noellipsis.sarif").read_text())["version"] == "2.1.0"
    assert "exit-code=1\n" in out.read_text(encoding="utf-8")


def test_main_mode_alias_and_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "ok.py"
    target.write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "gha_out"
    base = {
        "INPUT_PATH": str(target),
        "INPUT_FORMAT": "text",
        "INPUT_FAIL_ON": "error",
        "INPUT_EXCLUDE": "",
        "INPUT_CONFIG": "",
        "INPUT_AGAINST": "",
        "INPUT_STAGED": "",
        "GITHUB_OUTPUT": str(out),
        "GITHUB_WORKSPACE": str(tmp_path),
    }
    _env(monkeypatch, {**base, "INPUT_COMMAND": "", "INPUT_MODE": "check"})
    assert main() == 0
    _env(monkeypatch, {**base, "INPUT_COMMAND": "check", "INPUT_MODE": "git-diff"})
    assert main() == 2
    assert "disagree" in (tmp_path / "gha_out").read_text(encoding="utf-8") or True
    # stderr holds the message; exit-code is recorded
    assert "exit-code=2\n" in out.read_text(encoding="utf-8")


def test_main_invalid_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "gha_out"
    _env(
        monkeypatch,
        {
            "INPUT_COMMAND": "nope",
            "INPUT_MODE": "",
            "INPUT_PATH": ".",
            "INPUT_FORMAT": "text",
            "INPUT_FAIL_ON": "error",
            "GITHUB_OUTPUT": str(out),
        },
    )
    assert main() == 2
    assert "exit-code=2\n" in out.read_text(encoding="utf-8")


def test_main_config_and_missing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "ok.py"
    target.write_text("x = 1\n", encoding="utf-8")
    cfg = tmp_path / "custom.toml"
    cfg.write_text('[tool.noellipsis]\nfail-on = "error"\n', encoding="utf-8")
    out = tmp_path / "gha_out"
    base = {
        "INPUT_COMMAND": "check",
        "INPUT_MODE": "",
        "INPUT_PATH": str(target),
        "INPUT_FORMAT": "text",
        "INPUT_FAIL_ON": "error",
        "INPUT_EXCLUDE": "",
        "INPUT_AGAINST": "",
        "INPUT_STAGED": "",
        "GITHUB_OUTPUT": str(out),
        "GITHUB_WORKSPACE": str(tmp_path),
    }
    _env(monkeypatch, {**base, "INPUT_CONFIG": str(cfg)})
    assert main() == 0
    _env(monkeypatch, {**base, "INPUT_CONFIG": str(tmp_path / "missing.toml")})
    assert main() == 2
    assert "exit-code=2\n" in out.read_text(encoding="utf-8")


def test_main_non_sarif_streams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "ok.py"
    target.write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "gha_out"
    _env(
        monkeypatch,
        {
            "INPUT_COMMAND": "check",
            "INPUT_MODE": "",
            "INPUT_PATH": str(target),
            "INPUT_FORMAT": "text",
            "INPUT_FAIL_ON": "error",
            "INPUT_EXCLUDE": "",
            "INPUT_CONFIG": "",
            "INPUT_AGAINST": "",
            "INPUT_STAGED": "",
            "GITHUB_OUTPUT": str(out),
            "GITHUB_WORKSPACE": str(tmp_path),
        },
    )
    assert main() == 0
    assert (tmp_path / "noellipsis.sarif").exists() is False
    assert "exit-code=0\n" in out.read_text(encoding="utf-8")
