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


class ConfigError(ValueError):
    """Invalid configuration in CLI or pyproject.toml."""


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



def _parse_threshold(value: object, *, source: str) -> int:
    try:
        threshold_i = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{source}: shrink-threshold must be an integer from 0 to 100") from exc
    if threshold_i < 0 or threshold_i > 100:
        raise ConfigError(f"{source}: shrink-threshold must be an integer from 0 to 100")
    return threshold_i


def _config_from_tool(tool: dict, *, source: str) -> Config:
    extras = _as_str_list(tool.get("exclude"))
    disable = _as_str_list(tool.get("disable"))
    threshold = tool.get("shrink-threshold", tool.get("shrink_threshold", 40))
    fail_on = str(tool.get("fail-on", tool.get("fail_on", "error")))
    threshold_i = _parse_threshold(threshold, source=source)
    if fail_on not in {"error", "warning"}:
        raise ConfigError(f"{source}: fail-on must be 'error' or 'warning'")
    return replace(
        Config(),
        shrink_threshold=threshold_i,
        fail_on=fail_on,
        exclude=list(DEFAULT_EXCLUDES) + extras,
        disable=disable,
    )


def load_config_file(path: Path) -> Config:
    """Load an explicit TOML file that must contain [tool.noellipsis].

    Missing, unreadable, malformed, or invalid files raise ConfigError.
    There is no silent fallback to defaults or to pyproject.toml.
    """
    candidate = Path(path)
    if not candidate.is_file():
        raise ConfigError(f"config file does not exist: {candidate}")
    try:
        raw = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config file {candidate}: {exc}") from exc
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {candidate}: {exc}") from exc
    tool = data.get("tool", {}).get("noellipsis") if isinstance(data, dict) else None
    if not isinstance(tool, dict):
        raise ConfigError(f"{candidate}: missing [tool.noellipsis] table")
    return _config_from_tool(tool, source=str(candidate))


def load_pyproject(start: Path | None = None) -> Config:
    """Walk upward from *start* (or cwd) looking for [tool.noellipsis]."""
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
        except OSError:
            continue
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML in {candidate}: {exc}") from exc
        tool = data.get("tool", {}).get("noellipsis")
        if not isinstance(tool, dict):
            # Keep walking; this pyproject may belong to another project.
            if folder == directory:
                continue
            break
        return _config_from_tool(tool, source=str(candidate))
    return Config()


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
