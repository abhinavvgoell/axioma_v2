"""Execute the frozen five-case external multi-family static evaluation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REVIEW_DIR = Path(__file__).resolve().parent
CASE_PATH = REVIEW_DIR / "review-packet-v1.jsonl"
GOLD_PATH = REVIEW_DIR / "gold-reviewed-v1.jsonl"
DECISIONS_PATH = REVIEW_DIR / "owner-decisions-v1.json"
MANIFEST_PATH = REVIEW_DIR / "manifest-approved-v1.json"
OUTPUTS = {
    "analysis": REVIEW_DIR / "analysis-output-v1.json",
    "predictions": REVIEW_DIR / "predictions-v1.jsonl",
    "joined": REVIEW_DIR / "joined-evaluation-v1.jsonl",
    "evaluation": REVIEW_DIR / "evaluation-report-v1.json",
    "manifest": REVIEW_DIR / "run-manifest-v1.json",
}
CLASSES = {"O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"}
UNKNOWN = "unknown"

sys.path.insert(0, str(ROOT / "services" / "worker" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
sys.path.insert(0, str(ROOT / "evaluation" / "mode1"))
from axioma_worker.java_complexity import analyze_java_complexity  # noqa: E402
from axioma_worker.python_complexity import analyze_python_complexity  # noqa: E402
from evaluate_complexity import _score, load_records  # noqa: E402
from prepare_complexity_evaluation import combine, load_gold, load_predictions  # noqa: E402


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _normalized_time(estimate: str) -> tuple[str, str | None]:
    label = estimate.split(" (", maxsplit=1)[0].replace("²", "^2").strip()
    compact = re.sub(r"\s+", "", label)
    if compact.startswith("unknown"):
        return UNKNOWN, None
    if compact in CLASSES:
        return compact, None
    if compact == "O(V+E)":
        return "O(n)", "Normalized O(V + E) to O(n) using the reviewed n = V + E convention."
    return UNKNOWN, f"Estimate {label!r} is outside the predeclared scoring vocabulary."


def _write_exclusive(contents: dict[Path, bytes]) -> dict[str, str]:
    existing = [path.name for path in contents if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite evaluation outputs: {', '.join(existing)}")
    hashes: dict[str, str] = {}
    for path, data in contents.items():
        with path.open("xb") as output:
            output.write(data)
        hashes[path.name] = _sha256(data)
    return hashes


def main() -> int:
    existing = [path.name for path in OUTPUTS.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite evaluation outputs: {', '.join(existing)}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    case_bytes = CASE_PATH.read_bytes()
    gold_bytes = GOLD_PATH.read_bytes()
    decision_bytes = DECISIONS_PATH.read_bytes()
    if manifest.get("status") != "labels_frozen_before_analysis":
        raise ValueError("Owner-approved labels must be frozen before analysis")
    for path, expected, label in (
        (CASE_PATH, manifest["case_file_sha256"], "case packet"),
        (GOLD_PATH, manifest["label_file_sha256"], "approved labels"),
        (DECISIONS_PATH, manifest["owner_decisions_sha256"], "owner decisions"),
    ):
        if _sha256(path.read_bytes()) != expected:
            raise ValueError(f"{label} hash does not match the frozen manifest")

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if commit != manifest["analyzer_commit"] or branch != manifest["analyzer_branch"]:
        raise ValueError("Analyzer Git identity changed after labels were frozen")
    analyzer_paths = {
        "python_complexity.py": ROOT / "services/worker/src/axioma_worker/python_complexity.py",
        "java_complexity.py": ROOT / "services/worker/src/axioma_worker/java_complexity.py",
        "recurrence.py": ROOT / "services/worker/src/axioma_worker/recurrence.py",
    }
    analyzer_hashes = {name: _sha256(path.read_bytes()) for name, path in analyzer_paths.items()}
    if analyzer_hashes != manifest["analyzer_source_sha256"]:
        raise ValueError("Analyzer source files changed after labels were frozen")
    if _sha256(Path(__file__).read_bytes()) != manifest["runner_source_sha256"]:
        raise ValueError("Evaluation runner changed after labels were frozen")

    cases = _read_jsonl(CASE_PATH)
    labels = _read_jsonl(GOLD_PATH)
    case_by_id = {case["id"]: case for case in cases}
    label_by_id = {label["id"]: label for label in labels}
    if len(case_by_id) != len(cases) or len(label_by_id) != len(labels):
        raise ValueError("Duplicate case or approved-label IDs")
    if set(case_by_id) != set(label_by_id):
        raise ValueError("Case IDs and approved label IDs do not match")
    if len(cases) != manifest["case_count"]:
        raise ValueError("Case count does not match the frozen manifest")
    for case_id, case in case_by_id.items():
        source_path = (REVIEW_DIR / case["local_path"]).resolve()
        if not source_path.is_relative_to((REVIEW_DIR / "sources").resolve()):
            raise ValueError(f"Source path escapes packet directory for {case_id}")
        source_hash = _sha256(source_path.read_bytes())
        if source_hash != case["source_sha256"] or source_hash != manifest["source_sha256"].get(case_id):
            raise ValueError(f"Source hash mismatch for {case_id}")
        label = label_by_id[case_id]
        if label.get("label_status") != "owner_approved_before_analysis":
            raise ValueError(f"Label is not owner-approved for {case_id}")
        if label.get("source_sha256") != source_hash:
            raise ValueError(f"Approved label source hash mismatch for {case_id}")
        if label.get("expected_time") not in CLASSES or label.get("expected_auxiliary_space") not in CLASSES:
            raise ValueError(f"Unsupported scoring label for {case_id}")

    raw_cases: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for case_id in sorted(case_by_id):
        case = case_by_id[case_id]
        label = label_by_id[case_id]
        source = (REVIEW_DIR / case["local_path"]).read_text(encoding="utf-8")
        estimate = (
            analyze_java_complexity(source, case["entrypoint"])
            if case["language"] == "java"
            else analyze_python_complexity(source, case["entrypoint"])
        )
        predicted_time, normalization_note = _normalized_time(estimate.estimate)
        raw_cases.append({
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
            "auxiliary_space_static": {
                "state": "not_emitted",
                "estimate": UNKNOWN,
                "reason": "Current static analyzer does not emit an auxiliary-space class.",
            },
        })
        predictions.extend((
            {
                "id": case_id,
                "dimension": "time",
                "method": estimate.method,
                "predicted": predicted_time,
                "confidence": estimate.confidence,
                "report_sha256": "0" * 64,
            },
            {
                "id": case_id,
                "dimension": "auxiliary_space",
                "method": "not_emitted_by_current_static_analyzer",
                "predicted": UNKNOWN,
                "confidence": None,
                "report_sha256": "0" * 64,
            },
        ))

    analysis_data = {
        "dataset_id": manifest["dataset_id"],
        "partition": manifest["partition"],
        "analyzer_commit": commit,
        "analyzer_branch": branch,
        "analyzer_source_sha256": analyzer_hashes,
        "case_file_sha256": _sha256(case_bytes),
        "approved_label_file_sha256": _sha256(gold_bytes),
        "owner_decisions_sha256": _sha256(decision_bytes),
        "run_at_utc": datetime.now(UTC).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "benchmark_measurements": {"state": "not_run", "reason": "This static evaluation packet has no benchmark input configuration."},
        "cases": raw_cases,
    }
    analysis_bytes = _json_bytes(analysis_data)
    analysis_hash = _sha256(analysis_bytes)
    for row in predictions:
        row["report_sha256"] = analysis_hash
    predictions_bytes = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in predictions).encode("utf-8")

    gold = load_gold(GOLD_PATH)
    loaded_predictions = load_predictions_from_bytes(predictions_bytes, gold)
    joined = combine(
        gold,
        loaded_predictions,
        _sha256(gold_bytes),
        _sha256(predictions_bytes),
    )
    joined_bytes = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in joined).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="axioma-eval-v3-") as temp_dir:
        temp_joined = Path(temp_dir) / "joined.jsonl"
        temp_joined.write_bytes(joined_bytes)
        evaluation_data = _score(load_records(temp_joined))
    evaluation_data.update({
        "dataset_id": manifest["dataset_id"],
        "joined_input_sha256": _sha256(joined_bytes),
        "evaluator_version": "0.4.0",
    })

    outputs = {
        OUTPUTS["analysis"]: analysis_bytes,
        OUTPUTS["predictions"]: predictions_bytes,
        OUTPUTS["joined"]: joined_bytes,
        OUTPUTS["evaluation"]: _json_bytes(evaluation_data),
    }
    output_hashes = _write_exclusive(outputs)
    run_manifest = {
        "dataset_id": manifest["dataset_id"],
        "partition": manifest["partition"],
        "approved_manifest_sha256": _sha256(MANIFEST_PATH.read_bytes()),
        "approved_label_file_sha256": _sha256(gold_bytes),
        "case_file_sha256": _sha256(case_bytes),
        "owner_decisions_sha256": _sha256(decision_bytes),
        "analyzer_commit": commit,
        "analyzer_branch": branch,
        "analyzer_source_sha256": analyzer_hashes,
        "runner_source_sha256": _sha256(Path(__file__).read_bytes()),
        "outputs": output_hashes,
    }
    manifest_bytes = _json_bytes(run_manifest)
    with OUTPUTS["manifest"].open("xb") as output:
        output.write(manifest_bytes)
    exact = evaluation_data.get("dimensions", {})
    print(json.dumps({
        "case_count": len(cases),
        "time": exact.get("time", {}).get("exact_accuracy"),
        "time_coverage": exact.get("time", {}).get("coverage"),
        "auxiliary_space_coverage": exact.get("auxiliary_space", {}).get("coverage"),
        "outputs": {path.name: digest for path, digest in output_hashes.items()},
    }, indent=2))
    return 0


def load_predictions_from_bytes(data: bytes, gold: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="axioma-predictions-v3-") as temp_dir:
        temp_path = Path(temp_dir) / "predictions.jsonl"
        temp_path.write_bytes(data)
        return load_predictions(temp_path, gold)


if __name__ == "__main__":
    raise SystemExit(main())
