"""Stable rule catalog used by CLI, SARIF, and docs."""

from __future__ import annotations

from dataclasses import dataclass

from noellipsis import __version__
from noellipsis.models import Severity

HELP_URI = f"https://github.com/hoodbroskillson/NoEllipsis/blob/v{__version__}/README.md#rules"
DOCS_URI = f"https://github.com/hoodbroskillson/NoEllipsis/blob/v{__version__}/docs/sarif.md"


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    severity: Severity
    short_description: str
    full_description: str
    help_uri: str = HELP_URI


RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        "NE001",
        Severity.ERROR,
        "Placeholder phrase in a real comment",
        "Detects LLM-style placeholder comments such as 'Rest of code unchanged', "
        "'Insert your code here', or stub-like TODO/FIXME notes. Phrases inside "
        "strings, docstrings, templates, raw strings, and heredocs are ignored.",
    ),
    RuleSpec(
        "NE002",
        Severity.ERROR,
        "Bare ellipsis used as an incomplete body",
        "A Python function whose entire body is '...' is an error. Other languages "
        "flag a lone '...' statement that is not inside a string or comment.",
    ),
    RuleSpec(
        "NE003",
        Severity.WARNING,
        "pass-only or NotImplementedError-only function",
        "Warns when a Python function body is only 'pass' or 'raise NotImplementedError', "
        "unless the function is abstract, a Protocol stub, a .pyi stub, or an empty constructor.",
    ),
    RuleSpec(
        "NE004",
        Severity.ERROR,
        "Unclosed Markdown code fence",
        "A Markdown file opened a fenced code block (``` or ~~~) that was never closed.",
    ),
    RuleSpec(
        "NE005",
        Severity.ERROR,
        "Unbalanced brackets",
        "Parentheses, brackets, or braces are unbalanced after skipping strings and comments.",
    ),
    RuleSpec(
        "NE006",
        Severity.ERROR,
        "Python syntax error or truncated statement",
        "ast.parse failed, which often means the file was cut off mid-statement.",
    ),
    RuleSpec(
        "NE007",
        Severity.ERROR,
        "Unresolved merge-conflict markers",
        "Git conflict markers (<<<<<<< / ======= / >>>>>>>) remain in the file.",
    ),
    RuleSpec(
        "NE101",
        Severity.ERROR,
        "Candidate dramatically shorter than the original",
        "compare: the generated file is at least shrink-threshold percent smaller than the original.",
    ),
    RuleSpec(
        "NE102",
        Severity.ERROR,
        "Top-level function, class, or method removed",
        "compare: a top-level symbol present in the original is missing from the candidate.",
    ),
    RuleSpec(
        "NE103",
        Severity.WARNING,
        "Imports unexpectedly removed",
        "compare: import statements present in the original are missing from the candidate.",
    ),
    RuleSpec(
        "NE104",
        Severity.ERROR,
        "Probable full-file replacement with a partial snippet",
        "compare: the candidate looks like a snippet pasted over an entire original file.",
    ),
)

RULES_BY_ID = {rule.rule_id: rule for rule in RULES}


def all_rules() -> tuple[RuleSpec, ...]:
    return RULES
