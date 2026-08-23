"""Configuration: defaults, pyproject.toml, CLI overrides."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_EXCLUDES = [
    ".git",
    ".git/**",
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    "node_modules",
    "node_modules/**",
    "vendor",
    "vendor/**",
    "dist",
    "dist/**",
    "build",
    "build/**",
    "coverage",
    "coverage/**",
    "__pycache__",
    "__pycache__/**",
    "*.min.js",
    "*.min.mjs",
    "*.min.css",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.bin",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.gz",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
]


@dataclass
class Config:
    shrink_threshold: int = 40
    fail_on: str = "error"
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    disable: list[str] = field(default_factory=list)
    output_format: str = "text"
    verbose: bool = False

    def is_disabled(self, rule_id: str) -> bool:
        return rule_id.upper() in {d.upper() for d in self.disable}


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def load_pyproject(start: Path | None = None) -> Config:
    """Walk upward from *start* (or cwd) looking for [tool.noellipsis]."""
    cfg = Config()
    directory = (start or Path.cwd()).resolve()
    if directory.is_file():
        directory = directory.parent
    for folder in [directory, *directory.parents]:
        candidate = folder / "pyproject.toml"
        if not candidate.is_file():
            continue
        try:
            raw = candidate.read_text(encoding="utf-8")
            data = tomllib.loads(raw)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        tool = data.get("tool", {}).get("noellipsis")
        if not isinstance(tool, dict):
            # Keep walking; this pyproject may belong to another project.
            if folder == directory:
                continue
            break
        extras = _as_str_list(tool.get("exclude"))
        disable = _as_str_list(tool.get("disable"))
        threshold = tool.get("shrink-threshold", tool.get("shrink_threshold", cfg.shrink_threshold))
        fail_on = str(tool.get("fail-on", tool.get("fail_on", cfg.fail_on)))
        try:
            threshold_i = int(threshold)
        except (TypeError, ValueError):
            threshold_i = cfg.shrink_threshold
        return replace(
            cfg,
            shrink_threshold=threshold_i,
            fail_on=fail_on if fail_on in {"error", "warning"} else "error",
            exclude=list(DEFAULT_EXCLUDES) + extras,
            disable=disable,
        )
    return cfg


def apply_cli_overrides(
    cfg: Config,
    *,
    output_format: str | None = None,
    fail_on: str | None = None,
    exclude: list[str] | None = None,
    disable: list[str] | None = None,
    shrink_threshold: int | None = None,
    verbose: bool = False,
) -> Config:
    exclude_list = list(cfg.exclude)
    if exclude:
        exclude_list.extend(exclude)
    disable_list = list(cfg.disable)
    if disable:
        disable_list.extend(disable)
    return replace(
        cfg,
        output_format=output_format or cfg.output_format,
        fail_on=fail_on or cfg.fail_on,
        exclude=exclude_list,
        disable=disable_list,
        shrink_threshold=cfg.shrink_threshold if shrink_threshold is None else shrink_threshold,
        verbose=verbose,
    )
