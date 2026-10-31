from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from axioma_worker.python_complexity import analyze_python_complexity


ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/mode1/complexity-review-2026-10-29"
CASE_FILE = PACKET / "review-set-04.jsonl"
GOLD_FILE = PACKET / "gold-reviewed-04.jsonl"
OUTPUT_FILE = PACKET / "grid-bfs-diagnostic-results-2026-10-29.json"
CASE_ID = "axioma-20261029-19"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT_FILE.exists():
        raise SystemExit(f"Refusing to overwrite existing diagnostic result: {OUTPUT_FILE}")
    cases = [json.loads(line) for line in CASE_FILE.read_text(encoding="utf-8").splitlines()]
    labels = [json.loads(line) for line in GOLD_FILE.read_text(encoding="utf-8").splitlines()]
    case = next((row for row in cases if row["id"] == CASE_ID), None)
    label = next((row for row in labels if row["id"] == CASE_ID), None)
    if case is None or label is None:
        raise SystemExit(f"Missing frozen case or approved label: {CASE_ID}")
    source_hash = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
    if source_hash != case["source_sha256"] or source_hash != label["source_sha256"]:
        raise SystemExit(f"Source hash mismatch for {CASE_ID}; refusing evaluation.")

    estimate = analyze_python_complexity(case["source"], case["entrypoint"])
    expected = label["expected_time"]
    actual = estimate.estimate.split(" (", 1)[0]
    status = "exact" if actual == expected else (
        "unsupported" if actual.startswith("unknown") else "mismatch"
    )
    result = {
        "id": CASE_ID,
        "title": case["title"],
        "language": case["language"],
        "entrypoint": case["entrypoint"],
        "source_sha256": source_hash,
        "expected_time": expected,
        "expected_rationale": label["time_rationale"],
        "actual_time": estimate.estimate,
        "status": status,
        "method": estimate.method,
        "confidence": estimate.confidence,
        "explanation": estimate.explanation,
        "bfs_evidence": estimate.details.get("code_analysis", {}).get("bfs"),
    }
    report = {
        "dataset_id": "axioma-20261029-review-packet-04",
        "partition": "approved_calibration_diagnostic_development_case",
        "label_file": GOLD_FILE.name,
        "label_file_sha256": _sha256(GOLD_FILE),
        "case_file": CASE_FILE.name,
        "case_file_sha256": _sha256(CASE_FILE),
        "analyzer_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "analyzer_source_sha256": {
            "python_complexity.py": _sha256(
                ROOT / "services/worker/src/axioma_worker/python_complexity.py"
            ),
            "java_complexity.py": _sha256(
                ROOT / "services/worker/src/axioma_worker/java_complexity.py"
            ),
        },
        "run_at_utc": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "benchmark_measurements": {"state": "not_run"},
        "results": [result],
        "summary": {
            "eligible": 1,
            "exact": int(status == "exact"),
            "mismatch": int(status == "mismatch"),
            "unsupported": int(status == "unsupported"),
        },
        "note": (
            "Approved calibration data used to develop this rule; not an untouched holdout. "
            "This static result is a bounded syntax heuristic, not a formal proof or timing measurement."
        ),
    }
    OUTPUT_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT_FILE)
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
