"""Inspect git diffs without changing repository state."""

from __future__ import annotations

import subprocess
from pathlib import Path

from noellipsis.config import Config
from noellipsis.models import ScanResult
from noellipsis.scanner import Scanner


class GitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, shell=False
        ["git", *args],
        cwd=cwd,
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )


def require_repo(cwd: Path | None = None) -> Path:
    proc = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "not a git repository").strip()
        raise GitError(f"Not a git repository: {detail}")
    return Path(proc.stdout.strip())


def scan_git_diff(config: Config, *, staged: bool = False, cwd: Path | None = None) -> ScanResult:
    root = require_repo(cwd)
    args = ["diff", "--no-color", "--unified=0", "--find-renames"]
    if staged:
        args.append("--cached")
    proc = run_git(args, cwd=root)
    if proc.returncode != 0:
        raise GitError((proc.stderr or "git diff failed").strip())
    patches = parse_diff(proc.stdout)
    scanner = Scanner(config)
    result = ScanResult()
    for path, added in patches.items():
        if not added.strip():
            continue
        full = root / path
        findings = scanner.scan_text(full, added)
        # Only keep findings whose line text actually appears in added hunks
        added_lines = {ln.strip() for ln in added.splitlines() if ln.strip()}
        kept = []
        for finding in findings:
            if finding.line is None:
                kept.append(finding)
                continue
            lines = added.splitlines()
            if 1 <= finding.line <= len(lines) and lines[finding.line - 1].strip() in added_lines:
                kept.append(finding)
            elif any(finding.rule_id.startswith("NE00") for _ in [0]):
                # Line numbers refer to the reconstructed added text; accept them.
                kept.append(finding)
        result.findings.extend(kept)
        result.files_scanned += 1
    return result


def parse_diff(diff_text: str) -> dict[str, str]:
    """Map relative path -> concatenated added lines (plus a leading newline)."""
    files: dict[str, list[str]] = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = None
            continue
        if line.startswith("+++ "):
            rest = line[4:]
            if rest == "/dev/null":
                current = None
                continue
            if rest.startswith("b/"):
                rest = rest[2:]
            current = rest
            files.setdefault(current, [])
            continue
        if current is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            files[current].append(line[1:])
    return {path: "\n".join(lines) + ("\n" if lines else "") for path, lines in files.items()}
