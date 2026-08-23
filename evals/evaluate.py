"""Score the curated evals corpus. Deterministic. Stdlib + installed noellipsis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from noellipsis.config import Config
from noellipsis.scanner import Scanner

ROOT = Path(__file__).resolve().parent


def _load_labels() -> list[dict[str, str]]:
    data = json.loads((ROOT / "labels.json").read_text(encoding="utf-8"))
    return list(data["samples"])


def evaluate(root: Path | None = None) -> dict:
    base = root or ROOT
    scanner = Scanner(Config())
    tp = fp = tn = fn = 0
    rows: list[dict] = []
    for item in _load_labels():
        path = base / item["path"]
        findings = scanner.scan_file(path)
        flagged = bool(findings)
        expected_positive = item["label"] == "positive"
        if expected_positive and flagged:
            bucket = "TP"
            tp += 1
        elif expected_positive and not flagged:
            bucket = "FN"
            fn += 1
        elif not expected_positive and not flagged:
            bucket = "TN"
            tn += 1
        else:
            bucket = "FP"
            fp += 1
        rows.append(
            {
                "path": item["path"],
                "label": item["label"],
                "flagged": flagged,
                "bucket": bucket,
                "rule_ids": sorted({f.rule_id for f in findings}),
            }
        )
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    return {
        "curated": True,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "samples": rows,
    }


def main() -> int:
    report = evaluate()
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
