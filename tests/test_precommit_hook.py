from __future__ import annotations

from pathlib import Path


def test_precommit_hook_metadata() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert "id: noellipsis" in text
    assert "entry: noellipsis git-diff --staged" in text
    assert "pass_filenames: false" in text
    assert "language: python" in text
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "rev: v1.1.0" in readme
