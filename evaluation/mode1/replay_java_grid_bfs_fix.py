from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from axioma_worker.java_complexity import analyze_java_complexity


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation/mode1/bfs-independent-2026-10-29-v1"
PREDICTIONS = DATASET / "predictions.jsonl"
OUTPUT = ROOT / "evaluation/mode1/complexity-review-2026-10-29/java-grid-bfs-fix-diagnostic-2026-10-29.json"
ANALYZER = ROOT / "services/worker/src/axioma_worker/java_complexity.py"
CASE_ID = "bfs-ind-010"
EXPECTED_SOURCE_SHA256 = "9d75899b2760a19d3aa3d6ac3287e3f3a784e04d7c9c898093c7314753a67551"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def run() -> dict:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    case = next(row for row in _rows(DATASET / "cases.jsonl") if row["id"] == CASE_ID)
    label = next(row for row in _rows(DATASET / "gold-provisional.jsonl") if row["id"] == CASE_ID)
    previous = next(row for row in _rows(PREDICTIONS) if row["id"] == CASE_ID)
    source_hash = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
    if source_hash != EXPECTED_SOURCE_SHA256 or source_hash != case["source_sha256"]:
        raise ValueError("The frozen regression source no longer matches its recorded SHA-256.")
    if label["source_sha256"] != source_hash or label["time_complexity"] != "O((R * C)^2)":
        raise ValueError("The provisional expected label or source provenance changed.")

    estimate = analyze_java_complexity(case["source"], case["entrypoint"])
    normalized_prediction = "".join(estimate.estimate.split())
    normalized_expected = "".join(label["time_complexity"].split())
    assessment = (
        "exact_against_provisional_label"
        if normalized_prediction == normalized_expected
        else "unsupported"
        if normalized_prediction.startswith("unknown")
        else "mismatch"
    )
    result = {
        "diagnostic_id": "java-grid-bfs-extra-full-scan-2026-10-29-v1",
        "case_id": CASE_ID,
        "case_source_sha256": source_hash,
        "label_file_sha256": hashlib.sha256(
            (DATASET / "gold-provisional.jsonl").read_bytes()
        ).hexdigest(),
        "label_review_status": "provisional_not_human_reviewed",
        "expected_label_unchanged": label["time_complexity"],
        "original_incorrect_result": {
            "prediction": previous["raw_prediction"],
            "method": previous["method"],
            "analyzer_commit": "55ba24c3edac23a83ebbf610be63ee3e3b30e15f",
            "assessment": "mismatch",
        },
        "updated_result": {
            "prediction": estimate.estimate,
            "method": estimate.method,
            "confidence": estimate.confidence,
            "rule_version": estimate.details["code_analysis"]["bfs"]["rule_version"],
            "assessment": assessment,
            "explanation": estimate.explanation,
            "evidence": estimate.details["code_analysis"]["bfs"],
        },
        "analyzer_source_sha256": hashlib.sha256(ANALYZER.read_bytes()).hexdigest(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "note": "Development diagnostic only; this previously inspected case is not a fresh independent evaluation.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
