"""Inspect git diffs without changing repository state."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from noellipsis.config import Config
from noellipsis.models import Finding, ScanResult, Severity
from noellipsis.scanner import SKIP_DIR_NAMES, Scanner, path_is_excluded


class GitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 — fixed argv, shell=False
            ["git", *args],
            cwd=cwd,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except UnicodeDecodeError:
        proc = subprocess.run(  # noqa: S603 — fixed argv, shell=False
            ["git", *args],
            cwd=cwd,
            shell=False,
            capture_output=True,
            check=False,
        )
        return subprocess.CompletedProcess(
            proc.args,
            proc.returncode,
            stdout=(proc.stdout or b"").decode("utf-8", errors="replace"),
            stderr=(proc.stderr or b"").decode("utf-8", errors="replace"),
        )


def require_repo(cwd: Path | None = None) -> Path:
    proc = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "not a git repository").strip()
        raise GitError(f"Not a git repository: {detail}")
    return Path(proc.stdout.strip())


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_LONE_ELLIPSIS = re.compile(r"^\s*\.\.\.\s*;?\s*$")


@dataclass
class DiffFile:
    path: str
    added_text: str
    added_lines: set[int] = field(default_factory=set)
    is_new: bool = False
    old_path: str | None = None
    hunks: list[list[tuple[int, str]]] = field(default_factory=list)


def scan_git_diff(config: Config, *, staged: bool = False, cwd: Path | None = None) -> ScanResult:
    root = require_repo(cwd)
    args = ["diff", "--no-color", "--unified=0", "--find-renames"]
    if staged:
        args.append("--cached")
    proc = run_git(args, cwd=root)
    if proc.returncode != 0:
        raise GitError((proc.stderr or "git diff failed").strip())
    patches = parse_diff_details(proc.stdout)
    scanner = Scanner(config, root=root)
    result = ScanResult()
    for patch in patches:
        # Delete-only hunks have no plus lines; still scan WT/index so
        # NE005/NE006 can fire when a closer or leftover syntax is gone.
        rel = patch.path
        if any(part in SKIP_DIR_NAMES for part in Path(rel).parts):
            continue
        full = root / rel
        if path_is_excluded(full, config, root=root) or path_is_excluded(Path(rel), config, root=root):
            continue
        if staged:
            blob = _index_blob(root, rel)
            if blob is None:
                findings = scanner.scan_text(full, patch.added_text)
            else:
                findings = scanner.scan_text(full, blob)
        elif full.is_file():
            findings = scanner.scan_file(full)
        else:
            findings = scanner.scan_text(full, patch.added_text)
        pre_ids: set[str] | None = None
        is_new = patch.is_new
        rel_path = rel
        scan_path = full
        kept: list[Finding] = []
        for finding in findings:
            on_added = finding.line is None or finding.line in patch.added_lines
            if finding.rule_id in {"NE005", "NE006"}:
                if not on_added and not is_new:
                    if pre_ids is None:
                        prior = _prior_blob(root, rel_path, patch.old_path)
                        pre_ids = (
                            set()
                            if prior is None
                            else {item.rule_id for item in scanner.scan_text(scan_path, prior)}
                        )
                    if finding.rule_id in pre_ids:
                        continue
                kept.append(finding)
                continue
            if on_added:
                kept.append(finding)
        kept.extend(_ellipsis_only_hunks(full, patch, kept))
        result.findings.extend(kept)
        result.files_scanned += 1
    return result



def _prior_blob(root: Path, rel: str, old_path: str | None) -> str | None:
    """HEAD contents for rel, following an uncommitted or recent rename if needed."""
    prior = _git_blob(root, f"HEAD:{rel}")
    if prior is not None:
        return prior
    seen: set[str] = {rel}
    for candidate in (old_path, _resolve_pre_rename_path(root, rel)):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        prior = _git_blob(root, f"HEAD:{candidate}")
        if prior is not None:
            return prior
    return None


def _resolve_pre_rename_path(root: Path, rel: str) -> str | None:
    """Best-effort path of rel as it existed at HEAD (staged git mv, --follow)."""
    proc = run_git(["diff", "HEAD", "--find-renames", "--name-status"], cwd=root)
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].startswith("R"):
                old, new = _decode_quoted_path(parts[1]), _decode_quoted_path(parts[2])
                if new == rel and old != rel:
                    return old
    proc = run_git(["log", "--follow", "--name-only", "--format=", "--", rel], cwd=root)
    if proc.returncode == 0:
        for name in proc.stdout.splitlines():
            name = _decode_quoted_path(name.strip())
            if name and name != rel:
                return name
    return None


def _git_blob(root: Path, spec: str) -> str | None:
    try:
        proc = run_git(["show", spec], cwd=root)
    except UnicodeDecodeError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _index_blob(root: Path, rel: str) -> str | None:
    """Return the staged (index) contents of rel, or None if git cannot show it."""
    return _git_blob(root, f":{rel}")


def _ellipsis_only_hunks(path: Path, patch: DiffFile, existing: list[Finding]) -> list[Finding]:
    have = {(f.rule_id, f.line) for f in existing}
    extra: list[Finding] = []
    for hunk in patch.hunks:
        nonempty = [(n, t) for n, t in hunk if t.strip()]
        if not nonempty:
            continue
        if not all(_LONE_ELLIPSIS.match(t) for _, t in nonempty):
            continue
        line = nonempty[0][0]
        if ("NE002", line) in have:
            continue
        extra.append(
            Finding(
                rule_id="NE002",
                severity=Severity.ERROR,
                path=str(path),
                message="Bare ellipsis used as a standalone statement",
                suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
                line=line,
                column=1,
            )
        )
    return extra


def parse_diff(diff_text: str) -> dict[str, str]:
    """Map relative path -> concatenated added lines (plus a leading newline)."""
    return {item.path: item.added_text for item in parse_diff_details(diff_text)}


def parse_diff_details(diff_text: str) -> list[DiffFile]:
    files: dict[str, DiffFile] = {}
    current: DiffFile | None = None
    new_line = 0
    hunk: list[tuple[int, str]] | None = None
    pending_new = False
    pending_old: str | None = None
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            if current is not None and hunk:
                current.hunks.append(hunk)
            current = None
            hunk = None
            pending_new = False
            pending_old = None
            continue
        if raw.startswith("rename from "):
            renamed = raw[len("rename from "):].strip()
            if renamed.startswith('"'):
                renamed = _c_unquote(renamed)
            pending_old = renamed
            continue
        if raw.startswith("--- "):
            decoded_old = _decode_git_path(raw[4:])
            pending_new = decoded_old is None
            if decoded_old is not None:
                pending_old = decoded_old
            continue
        if raw.startswith("+++ "):
            decoded = _decode_git_path(raw[4:])
            if decoded is None:
                current = None
                continue
            current = files.get(decoded)
            if current is None:
                current = DiffFile(
                    path=decoded, added_text="", is_new=pending_new, old_path=pending_old
                )
                files[decoded] = current
            else:
                current.is_new = current.is_new or pending_new
                if pending_old and not current.old_path:
                    current.old_path = pending_old
            continue
        header = _HUNK.match(raw)
        if header and current is not None:
            if hunk:
                current.hunks.append(hunk)
            hunk = []
            new_line = int(header.group(3))
            continue
        if current is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            content = raw[1:]
            current.added_lines.add(new_line)
            if hunk is not None:
                hunk.append((new_line, content))
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif raw.startswith("\\"):
            continue
        else:
            new_line += 1
    if current is not None and hunk:
        current.hunks.append(hunk)
    for item in files.values():
        collected = []
        for h in item.hunks:
            collected.extend(t for _, t in h)
        item.added_text = "\n".join(collected) + ("\n" if collected else "")
    return list(files.values())


def _decode_quoted_path(value: str) -> str:
    """Unquote a git C-quoted path field if needed."""
    value = value.strip()
    if value.startswith('"'):
        return _c_unquote(value)
    return value


def _c_unquote(value: str) -> str:
    """Decode a git C-quoted string (octal escapes are UTF-8 bytes, not code points)."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    out = bytearray()
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\" or i + 1 >= len(value):
            out.extend(ch.encode("utf-8"))
            i += 1
            continue
        nxt = value[i + 1]
        simple = {
            "a": b"\a",
            "b": b"\b",
            "f": b"\f",
            "n": b"\n",
            "r": b"\r",
            "t": b"\t",
            "v": b"\v",
            '"': b'"',
            "\\": b"\\",
        }
        if nxt in simple:
            out.extend(simple[nxt])
            i += 2
            continue
        if nxt in "01234567":
            j = i + 1
            digits = []
            while j < len(value) and len(digits) < 3 and value[j] in "01234567":
                digits.append(value[j])
                j += 1
            out.append(int("".join(digits), 8))
            i = j
            continue
        out.extend(nxt.encode("utf-8"))
        i += 2
    return out.decode("utf-8")


def _decode_git_path(rest: str) -> str | None:
    rest = rest.strip()
    if rest in {"/dev/null", '"/dev/null"'}:
        return None
    if rest.startswith('"'):
        rest = _c_unquote(rest)
    if rest.startswith(("a/", "b/")):
        rest = rest[2:]
    return rest

