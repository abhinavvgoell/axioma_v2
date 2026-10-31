"""Run the current static analyzers on owner-approved packet 04 without overwriting outputs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "evaluation" / "mode1" / "complexity-review-2026-10-29"
MANIFEST_PATH = REVIEW_DIR / "manifest-04-approved.json"
CASE_PATH = REVIEW_DIR / "review-set-04.jsonl"
GOLD_PATH = REVIEW_DIR / "gold-reviewed-04.jsonl"
OUTPUTS = {
    "analysis": REVIEW_DIR / "analysis-output-04-approved.json",
    "predictions": REVIEW_DIR / "predictions-04-approved.jsonl",
    "evaluation": REVIEW_DIR / "evaluation-report-04-approved.json",
    "manifest": REVIEW_DIR / "results-manifest-04-approved.json",
}
CLASSES = ("O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)")
UNKNOWN = "unknown"

sys.path.insert(0, str(ROOT / "services" / "worker" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
from axioma_worker.java_complexity import analyze_java_complexity  # noqa: E402
from axioma_worker.python_complexity import analyze_python_complexity  # noqa: E402


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalized_estimate(estimate: str) -> tuple[str, str | None]:
    label = estimate.split(" (", maxsplit=1)[0].replace("²", "^2")
    if label.startswith("unknown"):
        return UNKNOWN, None
    if label not in CLASSES:
        return UNKNOWN, f"Estimate {label!r} is outside the predeclared class vocabulary."
    return label, None


def score_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        scorable = [record for record in items if not record["ambiguous"]]
        predicted = [record for record in scorable if record["predicted"] != UNKNOWN]
        right = sum(record["predicted"] == record["expected"] for record in scorable)
        return {
            "eligible": len(scorable),
            "answered": len(predicted),
            "abstentions": len(scorable) - len(predicted),
            "correct": right,
            "coverage": len(predicted) / len(scorable) if scorable else None,
            "exact_accuracy_among_answered": (
                sum(record["predicted"] == record["expected"] for record in predicted)
                / len(predicted)
                if predicted
                else None
            ),
            "conservative_accuracy_all_eligible": right / len(scorable) if scorable else None,
        }

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_family[record["family"]].append(record)
        by_language[record["language"]].append(record)
    return {
        **summarize(records),
        "by_family": {key: summarize(value) for key, value in sorted(by_family.items())},
        "by_language": {key: summarize(value) for key, value in sorted(by_language.items())},
    }


def _write_new(path: Path, content: bytes) -> str:
    with path.open("xb") as output:
        output.write(content)
    return _sha256(content)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def main() -> int:
    if any(path.exists() for path in OUTPUTS.values()):
        existing = [str(path.relative_to(ROOT)) for path in OUTPUTS.values() if path.exists()]
        raise FileExistsError(f"Refusing to overwrite evaluation outputs: {', '.join(existing)}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    case_bytes = CASE_PATH.read_bytes()
    gold_bytes = GOLD_PATH.read_bytes()
    if manifest["status"] != "labels_frozen_before_analysis":
        raise ValueError("Approved labels must be frozen before analyzer execution")
    if _sha256(case_bytes) != manifest["case_file_sha256"]:
        raise ValueError("Case file hash does not match the approved manifest")
    if _sha256(gold_bytes) != manifest["label_file_sha256"]:
        raise ValueError("Gold label hash does not match the approved manifest")

    cases = _read_jsonl(CASE_PATH)
    labels = _read_jsonl(GOLD_PATH)
    case_by_id = {case["id"]: case for case in cases}
    label_by_id = {label["id"]: label for label in labels}
    if len(case_by_id) != len(cases) or len(label_by_id) != len(labels):
        raise ValueError("Duplicate case or label IDs")
    if set(case_by_id) != set(label_by_id):
        raise ValueError("Case IDs and approved label IDs do not match")

    for case_id, case in case_by_id.items():
        source_hash = _sha256(case["source"].encode("utf-8"))
        if source_hash != case["source_sha256"] or source_hash != manifest["case_source_sha256"][case_id]:
            raise ValueError(f"Source hash mismatch for {case_id}")
        label = label_by_id[case_id]
        if label["label_status"] != "owner_approved_before_analysis" or label["ambiguous"]:
            raise ValueError(f"Case {case_id} is not an approved, scorable label")
        if label["source_sha256"] != source_hash:
            raise ValueError(f"Approved source hash mismatch for {case_id}")

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if commit != manifest["analyzer_commit"]:
        raise ValueError("Analyzer commit changed after labels were frozen")
    analyzer_paths = {
        "python_complexity.py": ROOT / "services" / "worker" / "src" / "axioma_worker" / "python_complexity.py",
        "java_complexity.py": ROOT / "services" / "worker" / "src" / "axioma_worker" / "java_complexity.py",
    }
    analyzer_hashes = {name: _sha256(path.read_bytes()) for name, path in analyzer_paths.items()}
    if analyzer_hashes != manifest["analyzer_source_sha256"]:
        raise ValueError("Analyzer source changed after labels were frozen")

    raw_cases: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    time_records: list[dict[str, Any]] = []
    space_records: list[dict[str, Any]] = []
    for case_id in sorted(case_by_id):
        case = case_by_id[case_id]
        label = label_by_id[case_id]
        estimate = (
            analyze_java_complexity(case["source"], case["entrypoint"])
            if case["language"] == "java"
            else analyze_python_complexity(case["source"], case["entrypoint"])
        )
        predicted_time, normalization_note = _normalized_estimate(estimate.estimate)
        raw = {
            "id": case_id,
            "title": case["title"],
            "language": case["language"],
            "family": case["family"],
            "entrypoint": case["entrypoint"],
            "source_sha256": case["source_sha256"],
            "method": estimate.method,
            "estimate": estimate.estimate,
            "normalized_time_estimate": predicted_time,
            "normalization_note": normalization_note,
            "confidence": estimate.confidence,
            "methods_disagree": estimate.methods_disagree,
            "explanation": estimate.explanation,
            "details": estimate.details,
        }
        raw_cases.append(raw)
        time_record = {
            "id": case_id,
            "dimension": "time",
            "method": estimate.method,
            "expected": label["expected_time"],
            "predicted": predicted_time,
            "confidence": estimate.confidence,
            "family": case["family"],
            "language": case["language"],
            "ambiguous": False,
            "evidence": {
                "estimate": estimate.estimate,
                "explanation": estimate.explanation,
                "details": estimate.details,
                "normalization_note": normalization_note,
            },
        }
        space_record = {
            "id": case_id,
            "dimension": "auxiliary_space",
            "method": "not_emitted_by_current_static_analyzer",
            "expected": label["expected_auxiliary_space"],
            "predicted": UNKNOWN,
            "confidence": None,
            "family": case["family"],
            "language": case["language"],
            "ambiguous": False,
            "evidence": {
                "reason": "Current analyzer does not emit an auxiliary-space complexity class."
            },
        }
        time_records.append(time_record)
        space_records.append(space_record)
        predictions.extend((time_record, space_record))

    analysis_data = {
        "dataset_id": manifest["dataset_id"],
        "partition": manifest["partition"],
        "analyzer_commit": commit,
        "analyzer_source_sha256": analyzer_hashes,
        "case_file_sha256": _sha256(case_bytes),
        "approved_label_file_sha256": _sha256(gold_bytes),
        "run_at_utc": datetime.now(UTC).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "benchmark_measurements": {
            "state": "not_run",
            "reason": "The packet has no benchmark inputs or benchmark configuration; static predictions are evaluated separately.",
        },
        "cases": raw_cases,
    }
    analysis_hash = _write_new(OUTPUTS["analysis"], _json_bytes(analysis_data))

    prediction_lines = []
    for prediction in predictions:
        prediction["analysis_output_sha256"] = analysis_hash
        prediction_lines.append(json.dumps(prediction, sort_keys=True, separators=(",", ":")))
    predictions_bytes = ("\n".join(prediction_lines) + "\n").encode("utf-8")
    predictions_hash = _write_new(OUTPUTS["predictions"], predictions_bytes)

    evaluation_data = {
        "dataset_id": manifest["dataset_id"],
        "partition": manifest["partition"],
        "metric_definitions": {
            "coverage": "answered scorable cases / all scorable cases",
            "exact_accuracy_among_answered": "exact correct predictions / answered scorable cases; null if none answered",
            "conservative_accuracy_all_eligible": "exact correct predictions / all scorable cases, treating abstentions as incorrect",
            "abstention": "unknown prediction; remains in the eligible denominator but not answered denominator",
        },
        "time": score_records(time_records),
        "auxiliary_space": score_records(space_records),
        "errors": [
            {
                "id": record["id"],
                "dimension": record["dimension"],
                "expected": record["expected"],
                "predicted": record["predicted"],
                "method": record["method"],
                "evidence": record["evidence"],
                "initial_interpretation": (
                    "Auxiliary-space classifier is not implemented; this is a dimension-wide coverage gap."
                    if record["dimension"] == "auxiliary_space"
                    else "Prediction is wrong or abstained; inspect the recorded analyzer evidence before assigning a case-specific cause."
                ),
                "ambiguous": record["ambiguous"],
            }
            for record in predictions
            if record["predicted"] == UNKNOWN or record["predicted"] != record["expected"]
        ],
        "raw_analysis_file": OUTPUTS["analysis"].name,
        "raw_analysis_sha256": analysis_hash,
        "predictions_file": OUTPUTS["predictions"].name,
        "predictions_sha256": predictions_hash,
    }
    evaluation_hash = _write_new(OUTPUTS["evaluation"], _json_bytes(evaluation_data))
    result_manifest = {
        "dataset_id": manifest["dataset_id"],
        "approved_manifest_file": MANIFEST_PATH.name,
        "approved_label_file": GOLD_PATH.name,
        "approved_label_file_sha256": _sha256(gold_bytes),
        "analyzer_commit": commit,
        "analyzer_source_sha256": analyzer_hashes,
        "analysis_output_file": OUTPUTS["analysis"].name,
        "analysis_output_sha256": analysis_hash,
        "predictions_file": OUTPUTS["predictions"].name,
        "predictions_sha256": predictions_hash,
        "evaluation_report_file": OUTPUTS["evaluation"].name,
        "evaluation_report_sha256": evaluation_hash,
    }
    _write_new(OUTPUTS["manifest"], _json_bytes(result_manifest))
    print(f"Time: exact among answered={evaluation_data['time']['exact_accuracy_among_answered']}; coverage={evaluation_data['time']['coverage']:.0%} ({evaluation_data['time']['answered']}/{evaluation_data['time']['eligible']})")
    print(f"Auxiliary space: exact among answered={evaluation_data['auxiliary_space']['exact_accuracy_among_answered']}; coverage={evaluation_data['auxiliary_space']['coverage']:.0%} ({evaluation_data['auxiliary_space']['answered']}/{evaluation_data['auxiliary_space']['eligible']})")
    print(f"Evaluation report: {OUTPUTS['evaluation'].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
