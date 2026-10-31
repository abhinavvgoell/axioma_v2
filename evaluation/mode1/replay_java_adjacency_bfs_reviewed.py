from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from axioma_worker.java_complexity import analyze_java_complexity

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation/mode1/bfs-independent-2026-10-29-v1"
OUTPUT = ROOT / "evaluation/mode1/complexity-review-2026-10-29/java-adjacency-bfs-diagnostic-2026-10-29.json"
ANALYZER = ROOT / "services/worker/src/axioma_worker/java_complexity.py"
REVIEWED_SHA256 = "a6a8aaad56b0dc09141ec8e7ecb2db73d39870ed92628ac94743691493cb6eff"


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def run() -> dict:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    reviewed_path = DATASET / "gold-reviewed-java-adjacency-2026-10-29.json"
    reviewed_sha = hashlib.sha256(reviewed_path.read_bytes()).hexdigest()
    if reviewed_sha != REVIEWED_SHA256:
        raise ValueError("Reviewed labels changed; refusing diagnostic replay.")
    cases = read_rows(DATASET / "cases.jsonl")
    previous = {row["id"]: row for row in read_rows(DATASET / "predictions.jsonl")}
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    results = []
    for case_id in ("bfs-ind-001", "bfs-ind-003"):
        case = next(row for row in cases if row["id"] == case_id)
        label = next(row for row in reviewed["cases"] if row["id"] == case_id)
        source_sha = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if source_sha != case["source_sha256"] or source_sha != label["source_sha256"]:
            raise ValueError(f"Frozen source hash mismatch for {case_id}.")
        estimate = analyze_java_complexity(case["source"], case["entrypoint"])
        evidence = estimate.details["code_analysis"].get("bfs")
        expected = label["reviewed_complexity"]
        assessment = "exact_match" if estimate.estimate == expected else (
            "unsupported" if estimate.estimate.startswith("unknown") else "mismatch"
        )
        results.append({
            "case_id": case_id,
            "source_sha256": source_sha,
            "reviewed_complexity": expected,
            "original_output": {
                "prediction": previous[case_id]["raw_prediction"],
                "method": previous[case_id]["method"],
                "analyzer_commit": "55ba24c3edac23a83ebbf610be63ee3e3b30e15f",
            },
            "new_output": {
                "prediction": estimate.estimate,
                "method": estimate.method,
                "confidence": estimate.confidence,
                "rule_version": evidence["rule_version"] if evidence else None,
                "assessment": assessment,
                "explanation": estimate.explanation,
                "evidence": evidence,
            },
        })
    result = {
        "diagnostic_id": "java-adjacency-list-bfs-reviewed-cases-2026-10-29-v1",
        "reviewed_label_artifact_sha256": reviewed_sha,
        "dataset_case_file_sha256": hashlib.sha256((DATASET / "cases.jsonl").read_bytes()).hexdigest(),
        "original_provisional_label_sha256": hashlib.sha256((DATASET / "gold-provisional.jsonl").read_bytes()).hexdigest(),
        "analyzer_source_sha256": hashlib.sha256(ANALYZER.read_bytes()).hexdigest(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "rule_version": "bounded_bfs_traversal_v2",
        "evaluation_status": "diagnostic_regression_only; reviewed examples were used for rule development and are not an untouched evaluation",
        "cases": results,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
