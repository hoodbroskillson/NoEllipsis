from __future__ import annotations

import subprocess
from pathlib import Path

from noellipsis.cli import main
from noellipsis.config import Config
from noellipsis.git import (
    GitError,
    _resolve_pre_rename_path,
    parse_diff,
    parse_diff_details,
    require_repo,
    run_git,
    scan_git_diff,
)


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

def test_git_diff_unstaged_after_staged_rename_keeps_preexisting(tmp_path: Path) -> None:
    """Staged git mv + comment without restaging: WT vs index must not treat the file as new."""
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "old.js"
    target.write_text("function f() {\n  return foo(\n}\n", encoding="utf-8")
    _git(["add", "old.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    _git(["mv", "old.js", "new.js"], tmp_path)
    renamed = tmp_path / "new.js"
    renamed.write_text("function f() {\n  return foo(\n}\n// note\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert not any(f.rule_id == "NE005" for f in result.findings)


def test_resolve_pre_rename_path_from_name_status(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    (tmp_path / "old.js").write_text("function f() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "old.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    _git(["mv", "old.js", "new.js"], tmp_path)
    assert _resolve_pre_rename_path(tmp_path, "new.js") == "old.js"


def test_resolve_pre_rename_path_follow_after_commit(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    (tmp_path / "old.js").write_text("function f() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "old.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    _git(["mv", "old.js", "new.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "rename"], tmp_path)
    # HEAD already has new.js, so name-status vs HEAD is empty; --follow still sees old.js.
    followed = _resolve_pre_rename_path(tmp_path, "new.js")
    assert followed == "old.js"


def test_run_git_and_scan_latin1_blob(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    body = b"def ok():\n    # caf\xe9\n    return 1\n"
    (tmp_path / "app.py").write_bytes(body)
    _git(["add", "app.py"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    shown = run_git(["show", "HEAD:app.py"], cwd=tmp_path)
    assert shown.returncode == 0
    assert "caf" in shown.stdout
    (tmp_path / "app.py").write_bytes(body + b"# Rest of code unchanged\n")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert result.files_scanned >= 1
    _git(["add", "app.py"], tmp_path)
    staged = scan_git_diff(Config(), staged=True, cwd=tmp_path)
    assert staged.files_scanned >= 1

def test_run_git_unicode_decode_fallback(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    from noellipsis import git as gitmod

    real = subprocess.run
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "test")
        kwargs.pop("encoding", None)
        kwargs.pop("errors", None)
        kwargs["text"] = False
        return real(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake)
    proc = gitmod.run_git(["--version"], cwd=tmp_path)
    assert proc.returncode == 0
    assert "git" in proc.stdout.lower() or proc.stdout



def test_parse_diff_c_quoted_utf8_path() -> None:
    diff = (
        'diff --git "a/caf\\303\\251.js" "b/caf\\303\\251.js"\n'
        '--- "a/caf\\303\\251.js"\n'
        '+++ "b/caf\\303\\251.js"\n'
        "@@ -3,1 +2,0 @@\n"
        "-}\n"
    )
    files = parse_diff_details(diff)
    assert len(files) == 1
    assert files[0].path == "café.js"


def test_git_diff_quoted_utf8_filename_reports_delete_closer(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    target = tmp_path / "café.js"
    target.write_text("function f() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "café.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    target.write_text("function f() {\n  return 1;\n", encoding="utf-8")
    result = scan_git_diff(Config(), staged=False, cwd=tmp_path)
    assert any(f.rule_id == "NE005" for f in result.findings)


def test_resolve_pre_rename_path_quoted_utf8(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "checkout", "-b", "main"], tmp_path)
    (tmp_path / "café.js").write_text("function f() {\n  return 1;\n}\n", encoding="utf-8")
    _git(["add", "café.js"], tmp_path)
    _git(["-c", "user.email=t@t.test", "-c", "user.name=t", "commit", "-m", "init"], tmp_path)
    _git(["mv", "café.js", "café2.js"], tmp_path)
    assert _resolve_pre_rename_path(tmp_path, "café2.js") == "café.js"
