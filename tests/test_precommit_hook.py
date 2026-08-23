from __future__ import annotations

from pathlib import Path

import yaml


def test_precommit_hook_metadata() -> None:
    path = Path(__file__).resolve().parents[1] / ".pre-commit-hooks.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        text = path.read_text(encoding="utf-8")
        assert "id: noellipsis" in text
        assert "noellipsis git-diff --staged" in text
        assert "pass_filenames: false" in text
        assert "rev: v1.0.0" in text
        return
    hooks = data if isinstance(data, list) else []
    hook = next(h for h in hooks if h["id"] == "noellipsis")
    assert hook["entry"] == "noellipsis git-diff --staged"
    assert hook["pass_filenames"] is False
    assert hook["language"] == "python"
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "rev: v1.0.0" in readme
