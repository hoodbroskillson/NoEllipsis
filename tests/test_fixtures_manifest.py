from __future__ import annotations

import json
from pathlib import Path

from noellipsis.config import Config
from noellipsis.scanner import Scanner


def test_golden_fixtures(fixtures: Path) -> None:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    scanner = Scanner(Config())
    for group, expect_empty in (("should_flag", False), ("should_not_flag", True)):
        for item in manifest[group]:
            path = fixtures / group / item["path"]
            findings = scanner.scan_file(path)
            ids = sorted({f.rule_id for f in findings})
            expected = sorted(set(item["rule_ids"]))
            if expect_empty:
                assert ids == [], f"{path} should be clean, got {ids}"
            else:
                for rid in expected:
                    assert rid in ids, f"{path} missing {rid}, got {ids}"
