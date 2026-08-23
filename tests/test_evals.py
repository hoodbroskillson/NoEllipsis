from __future__ import annotations

import json
from pathlib import Path

from evals.evaluate import evaluate

ROOT = Path(__file__).resolve().parents[1]


def test_evals_match_expected() -> None:
    report = evaluate(ROOT / "evals")
    expected = json.loads((ROOT / "evals" / "expected.json").read_text(encoding="utf-8"))
    assert report["fp"] <= expected["fp"]
    assert report["fn"] <= expected["fn"]
    assert report["precision"] + 1e-12 >= expected["precision"]
    assert report["recall"] + 1e-12 >= expected["recall"]
    assert report["tp"] >= expected["tp"]
    assert report["tn"] >= expected["tn"]
    by_path = {row["path"]: row for row in report["samples"]}
    for row in expected["samples"]:
        got = by_path[row["path"]]
        if row["bucket"] in {"TP", "TN"}:
            assert got["bucket"] == row["bucket"], f"{row['path']} worsened to {got['bucket']}"


def test_evals_are_labeled_curated() -> None:
    readme = (ROOT / "evals" / "README.md").read_text(encoding="utf-8")
    assert "curated" in readme.lower()
    assert "real-world" in readme.lower()
    labels = json.loads((ROOT / "evals" / "labels.json").read_text(encoding="utf-8"))
    assert labels["curated"] is True
    positives = [s for s in labels["samples"] if s["label"] == "positive"]
    negatives = [s for s in labels["samples"] if s["label"] == "negative"]
    assert len(positives) == len(negatives)
