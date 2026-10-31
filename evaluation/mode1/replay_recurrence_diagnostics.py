from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from axioma_worker.java_complexity import analyze_java_complexity
from axioma_worker.python_complexity import analyze_python_complexity


ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/mode1/complexity-review-2026-10-29"
CASE_FILE = PACKET / "review-set-04.jsonl"
GOLD_FILE = PACKET / "gold-reviewed-04.jsonl"
OUTPUT_FILE = PACKET / "recurrence-diagnostic-results-2026-10-29-final.json"
DIAGNOSTIC_IDS = {
    "axioma-20261029-16",
    "axioma-20261029-17",
    "axioma-20261029-20",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> None:
    if OUTPUT_FILE.exists():
        raise SystemExit(f"Refusing to overwrite existing diagnostic result: {OUTPUT_FILE}")

    cases = {
        case["id"]: case
        for case in (json.loads(line) for line in CASE_FILE.read_text(encoding="utf-8").splitlines())
        if case["id"] in DIAGNOSTIC_IDS
    }
    labels = {
        label["id"]: label
        for label in (json.loads(line) for line in GOLD_FILE.read_text(encoding="utf-8").splitlines())
        if label["id"] in DIAGNOSTIC_IDS
    }
    if set(cases) != DIAGNOSTIC_IDS or set(labels) != DIAGNOSTIC_IDS:
        raise SystemExit("The saved case packet or frozen labels do not contain the exact diagnostic IDs.")

    results = []
    for case_id in sorted(DIAGNOSTIC_IDS):
        case = cases[case_id]
        label = labels[case_id]
        source_hash = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if source_hash != case["source_sha256"] or source_hash != label["source_sha256"]:
            raise SystemExit(f"Source hash mismatch for {case_id}; refusing evaluation.")
        analyzer = analyze_java_complexity if case["language"] == "java" else analyze_python_complexity
        estimate = analyzer(case["source"], case["entrypoint"])
        expected = label["expected_time"]
        normalized_estimate = estimate.estimate.split(" (", 1)[0]
        status = "exact" if normalized_estimate == expected else (
            "unsupported" if normalized_estimate.startswith("unknown") else "mismatch"
        )
        results.append({
            "id": case_id,
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
            "recurrence_evidence": estimate.details.get("code_analysis", {}).get("recurrence"),
        })

    report = {
        "dataset_id": "axioma-20261029-review-packet-04",
        "partition": "calibration_diagnostic_development_case",
        "label_file": GOLD_FILE.name,
        "label_file_sha256": _sha256(GOLD_FILE),
        "case_file": CASE_FILE.name,
        "case_file_sha256": _sha256(CASE_FILE),
        "analyzer_commit": _git_commit(),
        "analyzer_source_sha256": {
            "java_complexity.py": _sha256(
                ROOT / "services/worker/src/axioma_worker/java_complexity.py"
            ),
            "python_complexity.py": _sha256(
                ROOT / "services/worker/src/axioma_worker/python_complexity.py"
            ),
            "recurrence.py": _sha256(ROOT / "services/worker/src/axioma_worker/recurrence.py"),
        },
        "run_at_utc": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "benchmark_measurements": {"state": "not_run"},
        "results": results,
        "summary": {
            "eligible": len(results),
            "exact": sum(result["status"] == "exact" for result in results),
            "mismatch": sum(result["status"] == "mismatch" for result in results),
            "unsupported": sum(result["status"] == "unsupported" for result in results),
        },
        "note": (
            "These previously approved calibration cases are diagnostic development data, "
            "not an untouched holdout. Gold labels were read without modification."
        ),
    }
    OUTPUT_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT_FILE)
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
