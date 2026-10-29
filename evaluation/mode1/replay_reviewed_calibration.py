"""Reproduce the post-fix replay for reviewed calibration packets 01-03 only."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "evaluation" / "mode1" / "complexity-review-2026-10-29"
PACKETS = (
    ("gold-reviewed.jsonl", "gold-reviewed.jsonl"),
    ("gold-reviewed-02.jsonl", "gold-reviewed-02.jsonl"),
    ("gold-reviewed-03.jsonl", "review-set-03.jsonl"),
)
OUTPUT_STEM = "calibration-current-2026-10-29"

sys.path.insert(0, str(ROOT / "services" / "worker" / "src"))
from axioma_worker.java_complexity import analyze_java_complexity  # noqa: E402
from axioma_worker.python_complexity import analyze_python_complexity  # noqa: E402


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_class(estimate: str) -> str:
    label = estimate.split(" (", maxsplit=1)[0]
    if label.startswith("unknown"):
        return "unknown"
    return {"O(V + E)": "O(n)", "O(V^2)": "O(n^2)"}.get(label, label)


def main() -> int:
    labels: list[dict] = []
    cases: dict[str, dict] = {}
    for gold_name, case_name in PACKETS:
        packet_labels = _read_jsonl(REVIEW_DIR / gold_name)
        packet_cases = _read_jsonl(REVIEW_DIR / case_name)
        labels.extend(packet_labels)
        cases.update({case["id"]: case for case in packet_cases})

    labels.sort(key=lambda item: item["id"])
    for label in labels:
        case = cases[label["id"]]
        actual_hash = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if actual_hash != label["source_sha256"] or actual_hash != case["source_sha256"]:
            raise ValueError(f"source hash mismatch for {label['id']}")
        if label.get("partition") != "calibration":
            raise ValueError(f"refusing to replay non-calibration case {label['id']}")

    gold_path = REVIEW_DIR / f"gold-reviewed-{OUTPUT_STEM}.jsonl"
    gold_bytes = "".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in labels
    ).encode("utf-8")
    gold_path.write_bytes(gold_bytes)

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("could not record the analyzer Git revision") from exc

    analyses = []
    for label in labels:
        case = cases[label["id"]]
        estimate = (
            analyze_java_complexity(case["source"], case["entrypoint"])
            if case["language"] == "java"
            else analyze_python_complexity(case["source"], case["entrypoint"])
        )
        analyses.append(
            {
                "id": label["id"],
                "language": case["language"],
                "source_sha256": case["source_sha256"],
                "method": estimate.method,
                "estimate": estimate.estimate,
                "normalized_estimate": _canonical_class(estimate.estimate),
                "confidence": estimate.confidence,
                "methods_disagree": estimate.methods_disagree,
                "explanation": estimate.explanation,
                "details": estimate.details,
            }
        )

    report = {
        "dataset_ids": [
            "axioma-20261029-review-packet-01",
            "axioma-20261029-review-packet-02",
            "axioma-20261029-review-packet-03",
        ],
        "partition": "calibration",
        "analyzer_commit": commit,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "gold_sha256": hashlib.sha256(gold_bytes).hexdigest(),
        "scope": "time complexity only; post-fix calibration replay; not held-out evaluation",
        "normalization": "O(V + E) => O(n) and O(V^2) => O(n^2) for these frozen labels",
        "cases": analyses,
    }
    report_path = REVIEW_DIR / f"analysis-output-{OUTPUT_STEM}.json"
    report_bytes = (json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    report_path.write_bytes(report_bytes)
    report_hash = hashlib.sha256(report_bytes).hexdigest()

    predictions = [
        {
            "id": item["id"],
            "method": item["method"],
            "predicted": item["normalized_estimate"],
            "confidence": item["confidence"],
            "report_sha256": report_hash,
        }
        for item in analyses
    ]
    predictions_path = REVIEW_DIR / f"predictions-{OUTPUT_STEM}.jsonl"
    predictions_path.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in predictions),
        encoding="utf-8",
    )

    joined_path = REVIEW_DIR / f"joined-{OUTPUT_STEM}.jsonl"
    evaluation_path = REVIEW_DIR / f"evaluation-{OUTPUT_STEM}.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "evaluation" / "mode1" / "prepare_complexity_evaluation.py"),
            str(gold_path),
            str(predictions_path),
            "--output",
            str(joined_path),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "evaluation" / "mode1" / "evaluate_complexity.py"),
            str(joined_path),
            "--output",
            str(evaluation_path),
        ],
        cwd=ROOT,
        check=True,
    )
    summary = json.loads(evaluation_path.read_text(encoding="utf-8"))
    calibration = summary["by_partition"]["calibration"]
    print(
        f"Calibration replay: {calibration['exact_accuracy']:.1%} exact, "
        f"{calibration['coverage']:.1%} coverage "
        f"({calibration['answered']}/{calibration['n']} answered); "
        f"{summary['evaluation_readiness']}. This is not held-out evaluation."
    )
    print(f"Analyzer commit: {commit}")
    print(f"Evaluation report: {evaluation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
