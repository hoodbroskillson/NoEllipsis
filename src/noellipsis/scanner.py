"""Walk files, apply rules, honour suppressions. Never execute scanned code."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

from noellipsis.config import Config
from noellipsis.models import Finding, ScanResult
from noellipsis.rules.generic_rules import GenericRules, looks_minified
from noellipsis.rules.markdown_rules import MarkdownRules
from noellipsis.rules.python_rules import PythonRules

SUPPRESS_LINE = re.compile(
    r"noellipsis\s*:\s*ignore\[([^\]]+)\]",
    re.IGNORECASE,
)
SUPPRESS_FILE = re.compile(r"noellipsis\s*:\s*ignore-file", re.IGNORECASE)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}

EXTENSION_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".md": "markdown",
    ".markdown": "markdown",
}

_BINARY_EXT = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


@dataclass
class FileContext:
    path: Path
    text: str
    language: str


class Scanner:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._python = PythonRules()
        self._generic = GenericRules()
        self._markdown = MarkdownRules()

    def scan_path(self, target: Path) -> ScanResult:
        result = ScanResult()
        if not target.exists():
            result.errors.append(f"Path does not exist: {target}")
            return result
        files = list(self._iter_files(target))
        for path in files:
            try:
                findings = self.scan_file(path)
            except OSError as exc:
                result.errors.append(f"Unreadable file: {path}: {exc}")
                continue
            result.findings.extend(findings)
            result.files_scanned += 1
        return result

    def scan_text(self, path: Path, text: str) -> list[Finding]:
        """Scan already-loaded text (used by compare and git-diff)."""
        language = language_for(path)
        if language is None:
            return []
        if "\x00" in text:
            return []
        if path.suffix.lower() in {".min.js", ".min.mjs"} or (
            path.suffix.lower() in {".js", ".mjs"} and looks_minified(text)
        ):
            return []
        if SUPPRESS_FILE.search(text):
            return []
        findings: list[Finding] = []
        if language == "python":
            findings.extend(self._python.check(path, text, is_stub=path.suffix == ".pyi"))
        findings.extend(self._generic.check(path, text, language))
        if language == "markdown":
            findings.extend(self._markdown.check(path, text))
        return self._filter(path, text, findings)

    def scan_file(self, path: Path) -> list[Finding]:
        if path.suffix.lower() in _BINARY_EXT:
            return []
        data = path.read_bytes()
        if b"\x00" in data:
            return []
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return self.scan_text(path, text)

    def _filter(self, path: Path, text: str, findings: list[Finding]) -> list[Finding]:
        lines = text.splitlines()
        kept: list[Finding] = []
        for finding in findings:
            if self.config.is_disabled(finding.rule_id):
                continue
            if _line_suppressed(lines, finding.line, finding.rule_id):
                continue
            kept.append(finding)
        return kept

    def _iter_files(self, target: Path) -> list[Path]:
        if target.is_file():
            if self._excluded(target):
                return []
            return [target]
        found: list[Path] = []
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if self._excluded(path):
                continue
            if language_for(path) is None:
                continue
            found.append(path)
        return found

    def _excluded(self, path: Path) -> bool:
        rel = _rel_posix(path)
        name = path.name
        for pattern in self.config.exclude:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
                return True
            # directory-style "vendor/**" already covered; also match prefix dirs
            if pattern.endswith("/**") and (
                rel == pattern[:-3] or rel.startswith(pattern[:-3] + "/")
            ):
                return True
        return False


def language_for(path: Path) -> str | None:
    return EXTENSION_LANG.get(path.suffix.lower())


def _rel_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _line_suppressed(lines: list[str], line: int | None, rule_id: str) -> bool:
    if line is None:
        return False
    candidates = []
    for offset in range(0, 3):
        idx = line - 1 - offset
        if 0 <= idx < len(lines):
            candidates.append(lines[idx])
    rid = rule_id.upper()
    for text in candidates:
        match = SUPPRESS_LINE.search(text)
        if not match:
            continue
        ids = {part.strip().upper() for part in match.group(1).split(",") if part.strip()}
        if rid in ids:
            return True
    return False
