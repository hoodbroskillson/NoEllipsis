from __future__ import annotations

import subprocess
from pathlib import Path

from noellipsis.cli import main
from noellipsis.config import Config
from noellipsis.git import GitError, parse_diff, parse_diff_details, require_repo, scan_git_diff


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_parse_diff_added_lines() -> None:
    diff = """diff --git a/x.py b/x.py
index 111..222 100644
--- a/x.py
+++ b/x.py
@@ -1,0 +1,2 @@
+def calculate_total():
+    ...
"""
    files = parse_diff(diff)
    assert "x.py" in files
    assert "..." in files["x.py"]


def test_git_diff_outside_repo(tmp_path: Path) -> None:
    import os

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert main(["git-diff"]) == 2
    finally:
        os.chdir(old)


def test_git_diff_detects_new_placeholder(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "app.py"
    target.write_text("def ok():\n    return 1\n", encoding="utf-8")
    _git(["add", "app.py"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("def ok():\n    return 1\n\ndef calculate_total():\n    ...\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert any(f.rule_id == "NE002" for f in result.findings)


def test_git_diff_staged(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    target = tmp_path / "app.py"
    target.write_text("def ok():\n    return 1\n", encoding="utf-8")
    _git(["add", "app.py"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text(
        "def ok():\n    return 1\n\ndef leftover():\n    # Rest of code unchanged\n    return 2\n",
        encoding="utf-8",
    )
    _git(["add", "app.py"], tmp_path)
    result = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert any(f.rule_id == "NE001" for f in result.findings)


def test_require_repo_error(tmp_path: Path) -> None:
    try:
        require_repo(tmp_path)
        raise AssertionError("expected GitError")
    except GitError as exc:
        assert "git" in exc.message.lower() or "not" in exc.message.lower()



def test_parse_diff_keeps_old_path_on_rename() -> None:
    diff = """diff --git a/old.js b/new.js
similarity index 90%
rename from old.js
rename to new.js
--- a/old.js
+++ b/new.js
@@ -3,0 +4 @@
+// note
"""
    files = parse_diff_details(diff)
    assert len(files) == 1
    assert files[0].path == "new.js"
    assert files[0].old_path == "old.js"


def test_git_diff_rename_keeps_preexisting_unbalance(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "old.js"
    target.write_text("function f() {\n  return foo(\n}\n", encoding="utf-8")
    _git(["add", "old.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    _git(["mv", "old.js", "new.js"], tmp_path)
    renamed = tmp_path / "new.js"
    renamed.write_text("function f() {\n  return foo(\n}\n// note\n", encoding="utf-8")
    _git(["add", "new.js"], tmp_path)
    result = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert not any(f.rule_id == "NE005" for f in result.findings)
