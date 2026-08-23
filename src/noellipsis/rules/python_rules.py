"""Python AST rules: NE002, NE003, NE006."""

from __future__ import annotations

import ast
from pathlib import Path

from noellipsis.models import Finding, Severity


def _is_ellipsis(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def _is_pass(node: ast.AST) -> bool:
    return isinstance(node, ast.Pass)


def _is_not_implemented(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise):
        return False
    exc = node.exc
    if exc is None:
        return False
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Attribute):
        return exc.attr == "NotImplementedError"
    return False


def _decorator_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    decorators = getattr(node, "decorator_list", [])
    for dec in decorators:
        if isinstance(dec, ast.Name):
            names.add(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.add(dec.attr)
        elif isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _docstring_only(body: list[ast.stmt]) -> bool:
    return (
        len(body) == 1
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], "value", None), ast.Constant)
        and isinstance(body[0].value.value, str)
    )


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(getattr(stmt, "value", None), ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _sole_stmt(body: list[ast.stmt]) -> ast.stmt | None:
    stmts = [s for s in body if not _is_docstring_stmt(s)]
    if len(stmts) == 1:
        return stmts[0]
    return None


class PythonRules:
    """Analyse one Python file via the stdlib AST."""

    def check(self, path: Path, text: str, *, is_stub: bool) -> list[Finding]:
        findings: list[Finding] = []
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            findings.append(
                Finding(
                    rule_id="NE006",
                    severity=Severity.ERROR,
                    path=str(path),
                    message=f"Syntax error or truncated statement: {exc.msg}",
                    suggestion="Restore the missing tokens or re-generate a complete file.",
                    line=exc.lineno,
                    column=exc.offset,
                )
            )
            return findings

        if is_stub:
            return findings

        self._walk(tree, path, findings, class_stack=[])
        return findings

    def _walk(
        self,
        node: ast.AST,
        path: Path,
        findings: list[Finding],
        class_stack: list[ast.ClassDef],
    ) -> None:
        if isinstance(node, ast.ClassDef):
            self._check_class(node, path, findings)
            class_stack.append(node)
            for child in ast.iter_child_nodes(node):
                self._walk(child, path, findings, class_stack)
            class_stack.pop()
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._check_function(node, path, findings, class_stack)
            for child in ast.iter_child_nodes(node):
                self._walk(child, path, findings, class_stack)
            return
        for child in ast.iter_child_nodes(node):
            self._walk(child, path, findings, class_stack)

    def _intentional_stub(self, func: ast.AST, class_stack: list[ast.ClassDef]) -> bool:
        names = _decorator_names(func)
        if names & {"abstractmethod", "abstractclassmethod", "abstractstaticmethod", "abstractproperty", "overload"}:
            return True
        if not class_stack:
            return False
        bases = _base_names(class_stack[-1])
        if bases & {"Protocol", "ABC"}:
            return True
        class_decs = _decorator_names(class_stack[-1])
        if "runtime_checkable" in class_decs:
            return True
        return False

    def _check_class(self, node: ast.ClassDef, path: Path, findings: list[Finding]) -> None:
        if _docstring_only(node.body):
            return
        sole = _sole_stmt(node.body)
        if sole is None:
            return
        if _is_ellipsis(sole) or (isinstance(sole, ast.Expr) and _is_ellipsis(sole.value)):
            if _base_names(node) & {"Protocol", "ABC"}:
                return
            findings.append(
                Finding(
                    rule_id="NE002",
                    severity=Severity.ERROR,
                    path=str(path),
                    message="Bare ellipsis used as class body",
                    suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
                    line=getattr(sole, "lineno", node.lineno),
                    column=getattr(sole, "col_offset", 0) + 1,
                )
            )

    def _check_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        path: Path,
        findings: list[Finding],
        class_stack: list[ast.ClassDef],
    ) -> None:
        if _docstring_only(node.body):
            return
        sole = _sole_stmt(node.body)
        if sole is None:
            return

        intentional = self._intentional_stub(node, class_stack)
        ctor = node.name in {"__init__", "__new__", "__post_init__"}

        ellipsis_body = _is_ellipsis(sole) or (isinstance(sole, ast.Expr) and _is_ellipsis(sole.value))
        pass_body = _is_pass(sole)
        not_impl = _is_not_implemented(sole)

        if ellipsis_body:
            if intentional:
                return
            findings.append(
                Finding(
                    rule_id="NE002",
                    severity=Severity.ERROR,
                    path=str(path),
                    message="Bare ellipsis used as function body",
                    suggestion="Replace the placeholder with an implementation or suppress NE002 if intentional.",
                    line=getattr(sole, "lineno", node.lineno),
                    column=getattr(sole, "col_offset", 0) + 1,
                )
            )
            return

        if pass_body or not_impl:
            if intentional or ctor:
                return
            kind = "pass-only" if pass_body else "NotImplementedError-only"
            findings.append(
                Finding(
                    rule_id="NE003",
                    severity=Severity.WARNING,
                    path=str(path),
                    message=f"Stub or empty implementation ({kind} function)",
                    suggestion="Implement the function, mark it abstract, or suppress NE003 if intentional.",
                    line=getattr(sole, "lineno", node.lineno),
                    column=getattr(sole, "col_offset", 0) + 1,
                )
            )
