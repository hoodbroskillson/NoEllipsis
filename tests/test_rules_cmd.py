from __future__ import annotations

import json

from noellipsis.cli import main
from noellipsis.formatters import format_rules
from noellipsis.rules.catalog import RULES


def test_rules_text_deterministic() -> None:
    first = format_rules("text")
    assert first == format_rules("text")
    for rule in RULES:
        assert rule.rule_id in first
        assert rule.severity.value in first
        assert rule.short_description in first


def test_rules_json(capsys) -> None:
    assert main(["rules", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    ids = [r["id"] for r in payload["rules"]]
    assert ids == [r.rule_id for r in RULES]
    assert main(["--format", "json", "rules"]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again == payload


def test_rules_text_cli(capsys) -> None:
    assert main(["rules"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("NE001")
    assert "NE104" in out
