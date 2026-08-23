"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from noellipsis import __version__
from noellipsis.compare import compare_files
from noellipsis.config import ConfigError, apply_cli_overrides, load_pyproject
from noellipsis.formatters import format_result, format_rules
from noellipsis.git import GitError, scan_git_diff
from noellipsis.models import ScanResult
from noellipsis.scanner import Scanner

_SHARED_VALUE = {
    "--format",
    "--fail-on",
    "--exclude",
    "--disable",
    "--shrink-threshold",
}
_SHARED_FLAGS = {"--verbose"}


def _hoist_shared(argv: list[str]) -> list[str]:
    """Allow shared options before or after the subcommand."""
    shared: list[str] = []
    other: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        name = arg.split("=", 1)[0]
        if name in _SHARED_VALUE:
            if "=" in arg:
                shared.append(arg)
                i += 1
                continue
            shared.append(arg)
            i += 1
            if i < len(argv):
                shared.append(argv[i])
                i += 1
            continue
        if name in _SHARED_FLAGS:
            shared.append(arg)
            i += 1
            continue
        other.append(arg)
        i += 1
    return shared + other


def _threshold(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--shrink-threshold must be an integer from 0 to 100") from exc
    if number < 0 or number > 100:
        raise argparse.ArgumentTypeError("--shrink-threshold must be an integer from 0 to 100")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="noellipsis",
        description=(
            "Detect incomplete or dangerously truncated LLM-generated code. "
            "Runs entirely locally. Never executes scanned code or changes Git state."
        ),
    )
    parser.add_argument("--version", action="version", version=f"noellipsis {__version__}")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json", "github", "sarif"),
        default=None,
        help="Output format: text, json, github, or sarif (default: text)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default=None,
        help="Minimum severity that yields exit code 1 (default: error)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        metavar="PATTERN",
        help="Glob pattern to exclude (repeatable)",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=None,
        metavar="RULE_ID",
        help="Disable a rule id such as NE103 (repeatable)",
    )
    parser.add_argument(
        "--shrink-threshold",
        type=_threshold,
        default=None,
        metavar="N",
        help="Percent size reduction that triggers NE101 (0-100, default: 40)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print scan progress on stderr")

    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="Scan a file or directory")
    check.add_argument("path", help="File or directory to scan")

    compare = sub.add_parser(
        "compare",
        help="Compare generated output against the original file",
    )
    compare.add_argument("generated", help="Generated / candidate file")
    compare.add_argument(
        "--against",
        required=True,
        dest="original",
        help="Original file to compare with",
    )

    git_diff = sub.add_parser(
        "git-diff",
        help="Scan added lines in the working tree (or index) diff",
    )
    git_diff.add_argument(
        "--staged",
        action="store_true",
        help="Inspect staged changes only",
    )

    sub.add_parser(
        "rules",
        help="List built-in rules (id, default severity, short description)",
    )
    return parser


def _exit_from(result: ScanResult, fail_on: str) -> int:
    if any(f.at_or_above(fail_on) for f in result.findings):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]
    try:
        args = parser.parse_args(_hoist_shared(raw))
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 2

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "rules":
        fmt = args.output_format or "text"
        if fmt not in {"text", "json"}:
            fmt = "text"
        sys.stdout.write(format_rules(fmt))
        return 0

    start = Path.cwd()
    if args.command == "check":
        start = Path(args.path)
    elif args.command == "compare":
        start = Path(args.generated)

    try:
        cfg = apply_cli_overrides(
            load_pyproject(start if start.exists() else Path.cwd()),
            output_format=args.output_format,
            fail_on=args.fail_on,
            exclude=args.exclude,
            disable=args.disable,
            shrink_threshold=args.shrink_threshold,
            verbose=args.verbose,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "check":
            target = Path(args.path)
            if not target.exists():
                print(f"error: path does not exist: {target}", file=sys.stderr)
                return 2
            if args.verbose:
                print(f"scanning {target}", file=sys.stderr)
            result = Scanner(cfg).scan_path(target)
            if args.verbose:
                print(f"scanned {result.files_scanned} file(s)", file=sys.stderr)
        elif args.command == "compare":
            gen = Path(args.generated)
            orig = Path(args.original)
            if not gen.exists():
                print(f"error: path does not exist: {gen}", file=sys.stderr)
                return 2
            if not orig.exists():
                print(f"error: path does not exist: {orig}", file=sys.stderr)
                return 2
            result = compare_files(gen, orig, cfg)
        else:
            result = scan_git_diff(cfg, staged=args.staged)
    except GitError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: internal error: {exc}", file=sys.stderr)
        return 2

    for err in result.errors:
        print(f"error: {err}", file=sys.stderr)

    sys.stdout.write(format_result(result, cfg.output_format))
    if result.errors:
        return 2
    return _exit_from(result, cfg.fail_on)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
