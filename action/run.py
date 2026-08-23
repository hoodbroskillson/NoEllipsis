"""Build a safe argv list for the NoEllipsis GitHub Action. No shell interpolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ALLOWED_COMMANDS = {"check", "git-diff", "compare"}
ALLOWED_FORMATS = {"text", "json", "github", "sarif"}
ALLOWED_FAIL_ON = {"error", "warning"}


def _input(name: str, default: str = "") -> str:
    env = f"INPUT_{name.upper().replace('-', '_')}"
    return os.environ.get(env, default)


def resolve_command(command: str, mode: str) -> str:
    command = (command or "").strip()
    mode = (mode or "").strip()
    if command and mode and command != mode:
        raise SystemExit(
            f"error: inputs command={command!r} and mode={mode!r} disagree; set only one"
        )
    resolved = command or mode or "check"
    if resolved not in ALLOWED_COMMANDS:
        raise SystemExit(f"error: unsupported command {resolved!r} (use check, git-diff, or compare)")
    return resolved


def resolve_sarif_path(sarif_file: str, workspace: str | None) -> Path:
    raw = (sarif_file or "").strip() or "noellipsis.sarif"
    base = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    candidate = Path(raw)
    resolved = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise SystemExit(f"error: sarif-file {raw!r} is outside the workspace") from exc
    return resolved


def write_github_output(outputs: dict[str, str], output_path: str | None = None) -> None:
    path = output_path if output_path is not None else os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for name, value in outputs.items():
            handle.write(f"{name}={value}\n")


def validate_sarif_bytes(data: bytes) -> None:
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: SARIF output is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("version") != "2.1.0":
        raise SystemExit("error: SARIF output must be a JSON object with version 2.1.0")


def build_argv(
    *,
    command: str,
    path: str,
    fail_on: str,
    fmt: str,
    exclude: str,
    config: str,
    against: str,
    staged: str,
) -> list[str]:
    if command not in ALLOWED_COMMANDS:
        raise SystemExit(f"error: unsupported command {command!r} (use check, git-diff, or compare)")
    if fmt not in ALLOWED_FORMATS:
        raise SystemExit(f"error: unsupported format {fmt!r}")
    if fail_on not in ALLOWED_FAIL_ON:
        raise SystemExit(f"error: unsupported fail-on {fail_on!r}")

    argv: list[str] = [sys.executable, "-m", "noellipsis", "--fail-on", fail_on, "--format", fmt]
    if exclude.strip():
        for part in exclude.splitlines():
            part = part.strip()
            if part:
                argv.extend(["--exclude", part])
    if config.strip():
        argv.extend(["--config", config.strip()])

    if command == "check":
        argv.extend(["check", path or "."])
    elif command == "git-diff":
        argv.append("git-diff")
        if staged.strip().lower() in {"1", "true", "yes"}:
            argv.append("--staged")
    else:
        if not against.strip():
            raise SystemExit("error: compare requires the 'against' input")
        argv.extend(["compare", path, "--against", against.strip()])
    return argv


def _run_cli(argv: list[str], env: dict[str, str], *, capture_stdout: bool) -> subprocess.CompletedProcess[bytes]:
    if capture_stdout:
        return subprocess.run(argv, check=False, env=env, stdout=subprocess.PIPE)
    return subprocess.run(argv, check=False, env=env)


def main() -> int:
    outputs = {"sarif-file": "", "exit-code": "2"}
    try:
        command = resolve_command(_input("command"), _input("mode"))
        path = _input("path", ".")
        fail_on = (_input("fail-on") or _input("fail_on") or "error").strip()
        fmt = (_input("format") or "text").strip()
        exclude = _input("exclude")
        config = _input("config")
        against = _input("against")
        staged = _input("staged")
        sarif_file = _input("sarif-file", "noellipsis.sarif")
        argv = build_argv(
            command=command,
            path=path,
            fail_on=fail_on,
            fmt=fmt,
            exclude=exclude,
            config=config,
            against=against,
            staged=staged,
        )
        action_path = os.environ.get("GITHUB_ACTION_PATH")
        env = os.environ.copy()
        if action_path:
            src = Path(action_path) / "src"
            if src.is_dir():
                existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(src) if not existing else f"{src}{os.pathsep}{existing}"
        if fmt == "sarif":
            completed = _run_cli(argv, env, capture_stdout=True)
            data = completed.stdout or b""
            dest = resolve_sarif_path(sarif_file, os.environ.get("GITHUB_WORKSPACE"))
            if data:
                validate_sarif_bytes(data)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                outputs["sarif-file"] = str(dest)
            outputs["exit-code"] = str(int(completed.returncode))
            write_github_output(outputs)
            return int(completed.returncode)
        completed = _run_cli(argv, env, capture_stdout=False)
        outputs["exit-code"] = str(int(completed.returncode))
        write_github_output(outputs)
        return int(completed.returncode)
    except SystemExit as exc:
        code = exc.code
        message = None
        if code is None:
            code = 0
        elif isinstance(code, int):
            pass
        else:
            message = str(code)
            code = 2
        if message:
            print(message, file=sys.stderr)
        outputs["exit-code"] = str(int(code))
        write_github_output(outputs)
        return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
