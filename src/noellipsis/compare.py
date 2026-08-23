"""Compare a generated file against an original (NE101–NE104)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from noellipsis.config import Config
from noellipsis.models import Finding, ScanResult, Severity
from noellipsis.scanner import Scanner, file_is_suppressed, language_for

_IDENT = re.compile(r"\b(?:function|class|def|fn|func|pub\s+fn|public\s+class)\s+([A-Za-z_][\w]*)")
_JS_FUNC = re.compile(
    r"(?:function\s+([A-Za-z_][\w]*)|(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)|"
    r"(?:const|let|var)\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?(?:function|\())"
)
_PY_IMPORT = re.compile(r"^(?:from\s+(\S+)\s+import|import\s+([A-Za-z0-9_.,\s]+))", re.M)


def compare_files(generated: Path, original: Path, config: Config) -> ScanResult:
    result = ScanResult()
    try:
        gen_text = generated.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"Unreadable file: {generated}: {exc}")
        return result
    try:
        orig_text = original.read_text(encoding="utf-8")
    except OSError as exc:
        result.errors.append(f"Unreadable file: {original}: {exc}")
        return result

    scanner = Scanner(config)
    result.files_scanned = 1
    lang = language_for(generated) or language_for(original) or ""
    if file_is_suppressed(gen_text, lang):
        return result
    result.findings.extend(scanner.scan_text(generated, gen_text))
    extra = _compare_texts(generated, gen_text, original, orig_text, config)
    extra = scanner.filter_findings(generated, gen_text, extra)
    result.findings.extend(extra)
    result.findings = [f for f in result.findings if not config.is_disabled(f.rule_id)]
    return result


def _compare_texts(
    gen_path: Path,
    gen_text: str,
    orig_path: Path,
    orig_text: str,
    config: Config,
) -> list[Finding]:
    findings: list[Finding] = []
    orig_size = max(len(orig_text), 1)
    gen_size = len(gen_text)
    reduction = (1.0 - gen_size / orig_size) * 100.0
    lang = language_for(gen_path) or language_for(orig_path) or ""

    if reduction >= config.shrink_threshold:
        findings.append(
            Finding(
                rule_id="NE101",
                severity=Severity.ERROR,
                path=str(gen_path),
                message=(
                    f"Candidate is {reduction:.1f}% shorter than the original "
                    f"({gen_size} vs {len(orig_text)} bytes; threshold {config.shrink_threshold}%)"
                ),
                suggestion="Confirm the model did not drop the rest of the file before replacing it.",
                line=None,
                column=None,
            )
        )

    if lang == "python":
        findings.extend(_python_symbol_diff(gen_path, gen_text, orig_text, config))
    else:
        findings.extend(_heuristic_symbol_diff(gen_path, gen_text, orig_text, config))

    if _looks_like_snippet_replacement(gen_text, orig_text, reduction, config):
        findings.append(
            Finding(
                rule_id="NE104",
                severity=Severity.ERROR,
                path=str(gen_path),
                message="Probable full-file replacement with a partial snippet",
                suggestion="Paste only into the intended region, or request a complete file from the model.",
                line=None,
                column=None,
            )
        )
    return findings


def _python_symbol_diff(
    gen_path: Path, gen_text: str, orig_text: str, config: Config
) -> list[Finding]:
    findings: list[Finding] = []
    orig_tree = _try_parse(orig_text)
    gen_tree = _try_parse(gen_text)
    if orig_tree is None or gen_tree is None:
        return _heuristic_symbol_diff(gen_path, gen_text, orig_text, config)

    orig_funcs, orig_classes, orig_methods = _py_symbols(orig_tree)
    gen_funcs, gen_classes, gen_methods = _py_symbols(gen_tree)

    for name in sorted(orig_funcs - gen_funcs):
        findings.append(
            Finding(
                rule_id="NE102",
                severity=Severity.ERROR,
                path=str(gen_path),
                message=f"Top-level function removed: {name}()",
                suggestion=(
                    "Restore the missing function or merge the generated "
                    "fragment instead of replacing the file."
                ),
                line=None,
                column=None,
            )
        )
    for name in sorted(orig_classes - gen_classes):
        findings.append(
            Finding(
                rule_id="NE102",
                severity=Severity.ERROR,
                path=str(gen_path),
                message=f"Top-level class removed: {name}",
                suggestion="Restore the missing class or merge the generated fragment instead of replacing the file.",
                line=None,
                column=None,
            )
        )
    for key in sorted(orig_methods - gen_methods):
        findings.append(
            Finding(
                rule_id="NE102",
                severity=Severity.ERROR,
                path=str(gen_path),
                message=f"Method removed: {key}",
                suggestion="Restore the missing method; the generated file may be a partial snippet.",
                line=None,
                column=None,
            )
        )

    orig_imports = _py_imports(orig_tree)
    gen_imports = _py_imports(gen_tree)
    missing = sorted(orig_imports - gen_imports)
    if missing and not config.is_disabled("NE103"):
        preview = ", ".join(missing[:8])
        extra = "" if len(missing) <= 8 else f" (+{len(missing) - 8} more)"
        findings.append(
            Finding(
                rule_id="NE103",
                severity=Severity.WARNING,
                path=str(gen_path),
                message=f"Imports unexpectedly removed: {preview}{extra}",
                suggestion="Re-introduce the dropped imports or confirm they are unused after a complete rewrite.",
                line=None,
                column=None,
            )
        )
    return findings


def _heuristic_symbol_diff(
    gen_path: Path, gen_text: str, orig_text: str, config: Config
) -> list[Finding]:
    findings: list[Finding] = []
    orig_names = _loose_names(orig_text)
    gen_names = _loose_names(gen_text)
    for name in sorted(orig_names - gen_names):
        findings.append(
            Finding(
                rule_id="NE102",
                severity=Severity.ERROR,
                path=str(gen_path),
                message=f"Top-level function/class removed: {name}",
                suggestion="Restore the missing symbol or merge the snippet instead of replacing the file.",
                line=None,
                column=None,
            )
        )
    orig_imp = set(_import_names_loose(orig_text))
    gen_imp = set(_import_names_loose(gen_text))
    missing = sorted(orig_imp - gen_imp)
    if missing and not config.is_disabled("NE103"):
        findings.append(
            Finding(
                rule_id="NE103",
                severity=Severity.WARNING,
                path=str(gen_path),
                message=f"Imports unexpectedly removed: {', '.join(missing[:8])}",
                suggestion="Re-introduce the dropped imports or confirm they are unused.",
                line=None,
                column=None,
            )
        )
    return findings


def _looks_like_snippet_replacement(gen_text: str, orig_text: str, reduction: float, config: Config) -> bool:
    stripped = gen_text.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return True
    if reduction < config.shrink_threshold:
        return False
    first = next((ln for ln in gen_text.splitlines() if ln.strip()), "")
    if first.startswith((" ", "\t")):
        return True
    orig_defs = len(re.findall(r"^(?:def |class |function |fn |func )", orig_text, re.M))
    gen_defs = len(re.findall(r"^(?:def |class |function |fn |func )", gen_text, re.M))
    return orig_defs >= 3 and gen_defs <= 1


def _try_parse(text: str) -> ast.AST | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _py_symbols(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    funcs: set[str] = set()
    classes: set[str] = set()
    methods: set[str] = set()
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(f"{node.name}.{item.name}")
    return funcs, classes, methods


def _py_imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.module:
                    names.add("." * node.level + node.module)
                else:
                    names.add("." * node.level)
            elif node.module:
                names.add(node.module.split(".")[0])
    return names


def _loose_names(text: str) -> set[str]:
    names: set[str] = set()
    for match in _IDENT.finditer(text):
        names.add(match.group(1))
    for match in _JS_FUNC.finditer(text):
        for g in match.groups():
            if g:
                names.add(g)
    return names


def _import_names_loose(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(
        r"^\s*(?:import|from|using|require\(|#include)\s+['\"]?([.A-Za-z0-9_/\\-]+)",
        text,
        re.M,
    ):
        raw = match.group(1).strip("'\"")
        if raw.startswith("."):
            names.add(raw.rstrip("/"))
        else:
            names.add(raw.split("/")[-1].split(".")[0])
    return names
