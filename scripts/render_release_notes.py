"""Render versioned GitHub release notes and inject SHA256SUMS. Stdlib only."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from pathlib import Path

MARKER = "{{SHA256SUMS}}"
PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")


def project_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data["project"]["version"]
    if not isinstance(version, str) or not version:
        raise SystemExit("error: pyproject.toml is missing project.version")
    return version


def notes_path(root: Path, version: str) -> Path:
    return root / "docs" / f"release-notes-{version}.md"


def write_sha256sums(dist: Path) -> str:
    dist = Path(dist)
    if not dist.is_dir():
        raise SystemExit(f"error: dist directory does not exist: {dist}")
    names = sorted([p.name for p in dist.iterdir() if p.suffix == ".whl" or p.name.endswith(".tar.gz")])
    if not names:
        raise SystemExit(f"error: no wheel or sdist in {dist}")
    lines: list[str] = []
    for name in names:
        digest = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    body = "\n".join(lines) + "\n"
    (dist / "SHA256SUMS").write_text(body, encoding="utf-8")
    return body.rstrip("\n")


def render_notes(template: str, checksums: str) -> str:
    count = template.count(MARKER)
    if count != 1:
        raise SystemExit(f"error: {MARKER} must appear exactly once (found {count})")
    rendered = template.replace(MARKER, checksums, 1)
    leftovers = PLACEHOLDER.findall(rendered)
    if leftovers:
        raise SystemExit(f"error: leftover placeholders: {', '.join(leftovers)}")
    return rendered


def render_release_notes(root: Path, dist: Path, output: Path) -> Path:
    version = project_version(root)
    source = notes_path(root, version)
    if not source.is_file():
        raise SystemExit(f"error: missing release notes {source} (required before gh release create)")
    checksums = write_sha256sums(dist)
    rendered = render_notes(source.read_text(encoding="utf-8"), checksums)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render docs/release-notes-<version>.md with SHA256SUMS")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        render_release_notes(args.root.resolve(), args.dist, args.output)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, str):
            print(code, file=sys.stderr)
            return 2
        return 0 if code is None else int(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
