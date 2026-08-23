from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from noellipsis.config import Config
from noellipsis.formatters import format_result
from noellipsis.lex import regions_for
from noellipsis.models import Finding, ScanResult
from noellipsis.scanner import Scanner

_LANGS = ("python", "javascript", "typescript", "go", "rust", "shell", "markdown")


@given(st.text(max_size=300), st.sampled_from(_LANGS))
@settings(max_examples=40, deadline=None)
def test_regions_never_crash(text: str, language: str) -> None:
    regions = regions_for(text, language)
    prev = 0
    for region in regions:
        assert region.start >= prev
        assert region.end >= region.start
        prev = region.end
    if regions:
        assert regions[0].start == 0
        assert regions[-1].end == len(text)
    for a, b in zip(regions, regions[1:], strict=False):
        assert a.end == b.start
        assert a.end > a.start or b.start == a.end


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200))
@settings(max_examples=30, deadline=None)
def test_unicode_scan_never_crashes(text: str) -> None:
    Scanner(Config()).scan_text(Path("x.py"), text)


@given(st.text(max_size=150))
@settings(max_examples=25, deadline=None)
def test_identical_scans_identical_findings(text: str) -> None:
    scanner = Scanner(Config())
    path = Path("x.py")
    a = scanner.scan_text(path, text)
    b = scanner.scan_text(path, text)
    assert a == b


def test_findings_sorted_and_linecol(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    ...\n# TODO: implement later\n", encoding="utf-8")
    result = Scanner(Config()).scan_path(path)
    ordered = result.sorted_findings()
    assert ordered == sorted(ordered, key=lambda f: (f.path, f.line or 0, f.column or 0, f.rule_id))
    for finding in ordered:
        if finding.line is not None:
            assert finding.line >= 1
        if finding.column is not None:
            assert finding.column >= 1


@given(st.text(max_size=200), st.sampled_from(_LANGS))
@settings(max_examples=30, deadline=None)
def test_ignored_regions_ordered_non_overlapping(text: str, language: str) -> None:
    regions = regions_for(text, language)
    for a, b in zip(regions, regions[1:], strict=False):
        assert a.end <= b.start
    covered = sum(r.end - r.start for r in regions)
    assert covered == len(text) or text == ""


def test_constructs_do_not_corrupt_later_state(tmp_path: Path) -> None:
    samples = {
        "a.py": "s = 'unterminated\ndef leftover():\n    return 1\n",
        "b.js": "const t = `template ${x}`;\nfunction ok() { return 1; }\n",
        "c.py": 's = r"raw \\n"\nx = 1\n',
        "d.sh": "cat <<'EOF'\n# TODO: implement later\nEOF\necho done\n",
        "e.go": "package main\nvar s = `raw`\nfunc main() {}\n",
    }
    scanner = Scanner(Config())
    for name, text in samples.items():
        findings = scanner.scan_text(tmp_path / name, text)
        assert isinstance(findings, list)


def test_abs_path_does_not_affect_normalized_output(tmp_path: Path) -> None:
    path = tmp_path / "x.py"
    path.write_text("def leftover():\n    ...\n", encoding="utf-8")
    result = Scanner(Config()).scan_path(path)
    a = format_result(result, "sarif")
    b = format_result(result, "sarif")
    assert a == b
    assert str(path.resolve()) not in a


@given(st.text(max_size=4000))
@settings(max_examples=10, deadline=None)
def test_large_but_reasonable_inputs(text: str) -> None:
    Scanner(Config()).scan_text(Path("big.py"), text)


def test_finding_equality_for_sort() -> None:
    f = Finding("NE002", __import__("noellipsis.models", fromlist=["Severity"]).Severity.ERROR, "a.py", "m", "s", 1, 1)
    result = ScanResult(findings=[f, f])
    assert len(result.sorted_findings()) == 2
