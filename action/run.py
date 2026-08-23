"""Build a safe argv list for the NoEllipsis GitHub Action. No shell interpolation."""

from __future__ import annotations

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
        # Config is discovered from the scanned path / cwd; extra excludes only here.
        # A dedicated config file path is treated as an extra scan root hint via env.
        os.environ["NOELLIPSIS_CONFIG"] = config.strip()

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


def main() -> int:
    command = (_input("command") or _input("mode") or "check").strip()
    path = _input("path", ".")
    fail_on = (_input("fail-on") or _input("fail_on") or "error").strip()
    fmt = (_input("format") or "text").strip()
    exclude = _input("exclude")
    config = _input("config")
    against = _input("against")
    staged = _input("staged")
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
    completed = subprocess.run(argv, check=False, env=env)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
