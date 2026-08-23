from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT = [sys.executable, "-m", "pre_commit"]


def test_precommit_hook_metadata() -> None:
    text = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert "id: noellipsis" in text
    assert "entry: noellipsis git-diff --staged" in text
    assert "pass_filenames: false" in text
    assert "language: python" in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "rev: v1.1.1" in readme


def test_consumer_repo_hook_fails_on_incomplete_staged(tmp_path: Path) -> None:
    """Install the hook into a throwaway git repo; do not mutate NoEllipsis."""
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    subprocess.run(["git", "init"], cwd=consumer, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "--allow-empty", "-m", "init"],
        cwd=consumer,
        check=True,
        capture_output=True,
    )
    (consumer / ".pre-commit-config.yaml").write_text(
        f"repos:\n  - repo: {ROOT}\n    rev: HEAD\n    hooks:\n      - id: noellipsis\n",
        encoding="utf-8",
    )
    (consumer / "incomplete.py").write_text("def leftover():\n    ...\n", encoding="utf-8")
    subprocess.run(["git", "add", "incomplete.py"], cwd=consumer, check=True, capture_output=True)
    run = subprocess.run(
        [*PRE_COMMIT, "run", "noellipsis"],
        cwd=consumer,
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0, run.stdout + run.stderr
