"""Run the frozen broad Mode 1 calibration set against current static analyzers."""

from __future__ import annotations

import hashlib
import json
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
GOLD_PATH = REVIEW_DIR / "gold-reviewed-calibration-v1.jsonl"
GOLD_MANIFEST_PATH = REVIEW_DIR / "gold-reviewed-calibration-v1.manifest.json"
CASE_PACKETS = (
    "candidate-cases-batch-01-v2.jsonl",
    "candidate-cases-batch-02-v1.jsonl",
    "candidate-cases-batch-03-v1.jsonl",
    "candidate-cases-batch-04-v1.jsonl",
    "candidate-cases-batch-05-v1.jsonl",
    "candidate-cases-batch-06-v1.jsonl",
)
OUTPUT_DIR = REVIEW_DIR / "calibration-run-v1"
OUTPUT_NAMES = (
    "analysis-output-calibration-v1.json",
    "predictions-calibration-v1.jsonl",
    "joined-calibration-v1.jsonl",
    "evaluation-report-calibration-v1.json",
    "run-manifest-calibration-v1.json",
)
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


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalize_estimate(estimate: object) -> str:
    if not isinstance(estimate, str):
        return UNKNOWN
    label = estimate.split(" (", maxsplit=1)[0].strip().replace("²", "^2")
    compact = re.sub(r"\s+", "", label)
    for supported in CLASSES:
        if compact == re.sub(r"\s+", "", supported):
            return supported
    return UNKNOWN


def _case_packets() -> tuple[list[dict[str, Any]], dict[str, str]]:
    cases: list[dict[str, Any]] = []
    packet_hashes: dict[str, str] = {}
    for name in CASE_PACKETS:
        path = REVIEW_DIR / name
        payload = path.read_bytes()
        packet_hashes[name] = _sha256(payload)
        cases.extend(_read_jsonl(path))
    return cases, packet_hashes


def main() -> int:
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite calibration outputs: {OUTPUT_DIR}")
    gold_manifest = json.loads(GOLD_MANIFEST_PATH.read_text(encoding="utf-8"))
    gold_bytes = GOLD_PATH.read_bytes()
    if _sha256(gold_bytes) != gold_manifest.get("gold_labels_sha256"):
        raise ValueError("Frozen calibration label hash does not match its manifest")
    if gold_manifest.get("dataset_gold_labels_frozen") is not True:
        raise ValueError("Calibration labels are not frozen")
    if gold_manifest.get("analyzer_run") is not False:
        raise ValueError("Expected a not-yet-run calibration manifest")

    cases, packet_hashes = _case_packets()
    case_by_id = {case.get("id"): case for case in cases}
    expected_ids = set(gold_manifest["case_ids"])
    if len(cases) != gold_manifest.get("case_count") or len(case_by_id) != len(cases):
        raise ValueError("Candidate packet set has a wrong count or duplicate IDs")
    if set(case_by_id) != expected_ids:
        raise ValueError("Candidate case IDs do not match the frozen calibration manifest")

    # Validate source identity from the frozen manifest; no expected labels are passed
    # into either analyzer call.
    for case_id, case in case_by_id.items():
        source = case.get("source")
        digest = _sha256(source.encode("utf-8")) if isinstance(source, str) else None
        if digest != gold_manifest["source_sha256"].get(case_id):
            raise ValueError(f"Candidate source hash mismatch for {case_id}")
        if digest != case.get("source_sha256"):
            raise ValueError(f"Embedded source hash mismatch for {case_id}")

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    analyzer_paths = {
        "python_complexity.py": ROOT / "services/worker/src/axioma_worker/python_complexity.py",
        "java_complexity.py": ROOT / "services/worker/src/axioma_worker/java_complexity.py",
        "recurrence.py": ROOT / "services/worker/src/axioma_worker/recurrence.py",
    }
    analyzer_hashes = {name: _sha256(path.read_bytes()) for name, path in analyzer_paths.items()}
    raw_cases: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []

    for case_id in sorted(case_by_id):
        case = case_by_id[case_id]
        source = case["source"]
        entrypoint = case["entrypoint"]
        estimate = (
            analyze_java_complexity(source, entrypoint)
            if case["language"] == "java"
            else analyze_python_complexity(source, entrypoint)
        )
        time_prediction = _normalize_estimate(estimate.estimate)
        code_analysis = estimate.details.get("code_analysis", {})
        space_signal = code_analysis.get("auxiliary_space", {})
        space_prediction = (
            _normalize_estimate(space_signal.get("estimate"))
            if space_signal.get("state") == "estimated"
            else UNKNOWN
        )
        raw_cases.append({
            "id": case_id,
            "title": case.get("title"),
            "language": case["language"],
            "family": case.get("family"),
            "entrypoint": entrypoint,
            "source_sha256": case["source_sha256"],
            "time": {
                "method": estimate.method,
                "raw_estimate": estimate.estimate,
                "predicted": time_prediction,
                "confidence": estimate.confidence,
                "methods_disagree": estimate.methods_disagree,
                "explanation": estimate.explanation,
                "details": estimate.details,
            },
            "auxiliary_space": {
                "method": space_signal.get("method", "not_emitted"),
                "state": space_signal.get("state", "not_emitted"),
                "raw_estimate": space_signal.get("estimate"),
                "predicted": space_prediction,
                "confidence": space_signal.get("confidence"),
                "reasoning": space_signal.get("reasoning"),
                "limitations": space_signal.get("limitations", []),
            },
        })
        predictions.extend((
            {
                "id": case_id,
                "dimension": "time",
                "method": estimate.method,
                "predicted": time_prediction,
                "confidence": estimate.confidence,
                "report_sha256": "0" * 64,
            },
            {
                "id": case_id,
                "dimension": "auxiliary_space",
                "method": space_signal.get("method", "not_emitted_by_current_static_analyzer"),
                "predicted": space_prediction,
                "confidence": space_signal.get("confidence"),
                "report_sha256": "0" * 64,
            },
        ))

    analysis = {
        "schema_version": "axioma.mode1.calibration-analysis.v1",
        "dataset_id": gold_manifest["dataset_id"],
        "partition": "calibration",
        "run_at_utc": datetime.now(UTC).isoformat(),
        "analyzer_commit": commit,
        "analyzer_branch": branch,
        "analyzer_source_sha256": analyzer_hashes,
        "candidate_packet_sha256": packet_hashes,
        "gold_labels_sha256": _sha256(gold_bytes),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "benchmark_measurements": {"state": "not_run", "reason": "This packet evaluates static estimates only."},
        "scope": "30 owner-reviewed calibration cases; not an untouched holdout; labels were not passed to analyzers.",
        "cases": raw_cases,
    }
    analysis_bytes = _json_bytes(analysis)
    analysis_hash = _sha256(analysis_bytes)
    for row in predictions:
        row["report_sha256"] = analysis_hash
    prediction_bytes = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in predictions
    ).encode("utf-8")

    # Join and score only after all analyzer outputs are captured.
    gold = load_gold(GOLD_PATH)
    with tempfile.TemporaryDirectory(prefix="axioma-broad-calibration-") as temp_dir:
        prediction_path = Path(temp_dir) / "predictions.jsonl"
        prediction_path.write_bytes(prediction_bytes)
        loaded_predictions = load_predictions(prediction_path, gold)
        joined = combine(gold, loaded_predictions, _sha256(gold_bytes), _sha256(prediction_bytes))
        joined_bytes = "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in joined
        ).encode("utf-8")
        joined_path = Path(temp_dir) / "joined.jsonl"
        joined_path.write_bytes(joined_bytes)
        report = _score(load_records(joined_path))
    report.update({
        "dataset_id": gold_manifest["dataset_id"],
        "partition": "calibration",
        "joined_input_sha256": _sha256(joined_bytes),
        "evaluator_version": "0.4.0",
        "interpretation": "Calibration diagnostics only; do not report as held-out performance.",
    })

    output_payloads = {
        OUTPUT_NAMES[0]: analysis_bytes,
        OUTPUT_NAMES[1]: prediction_bytes,
        OUTPUT_NAMES[2]: joined_bytes,
        OUTPUT_NAMES[3]: _json_bytes(report),
    }
    hashes = {name: _sha256(payload) for name, payload in output_payloads.items()}
    run_manifest = {
        "dataset_id": gold_manifest["dataset_id"],
        "partition": "calibration",
        "frozen_gold_manifest_sha256": _sha256(GOLD_MANIFEST_PATH.read_bytes()),
        "gold_labels_sha256": _sha256(gold_bytes),
        "candidate_packet_sha256": packet_hashes,
        "analyzer_commit": commit,
        "analyzer_branch": branch,
        "analyzer_source_sha256": analyzer_hashes,
        "runner_source_sha256": _sha256(Path(__file__).read_bytes()),
        "outputs": hashes,
        "limitations": [
            "Calibration data shares source repositories with earlier development work.",
            "No benchmark timings were run; this measures static analyzer predictions only.",
            "Auxiliary-space estimates are bounded static heuristics and may abstain.",
        ],
    }
    output_payloads[OUTPUT_NAMES[4]] = _json_bytes(run_manifest)
    OUTPUT_DIR.mkdir(parents=False, exist_ok=False)
    for name, payload in output_payloads.items():
        with (OUTPUT_DIR / name).open("xb") as output:
            output.write(payload)

    print(json.dumps({
        "case_count": len(raw_cases),
        "prediction_rows": len(predictions),
        "time": report.get("dimensions", {}).get("time", {}),
        "auxiliary_space": report.get("dimensions", {}).get("auxiliary_space", {}),
        "outputs": {name: _sha256(payload) for name, payload in output_payloads.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
