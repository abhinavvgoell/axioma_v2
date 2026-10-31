from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
EVALUATION_DIR = REPOSITORY / "evaluation" / "mode1"
sys.path.insert(0, str(EVALUATION_DIR))

from evaluate_complexity import load_records, _score  # noqa: E402
from prepare_complexity_evaluation import combine, load_gold, load_predictions  # noqa: E402


CLASSES = ("O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)")
UNKNOWN = "unknown"
OUTPUTS = {
    "predictions": ROOT / "predictions-v2.jsonl",
    "joined": ROOT / "joined-evaluation-v2.jsonl",
    "report": ROOT / "evaluation-report-v2.json",
    "manifest": ROOT / "run-manifest-v2.json",
    "summary": ROOT / "run-report-v2.md",
}
V1_INPUTS = (
    "analysis-output-v1.json",
    "predictions-v1.jsonl",
    "joined-evaluation-v1.jsonl",
    "evaluation-report-v1.json",
    "run-manifest-v1.json",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def normalize_saved_estimate(estimate: str) -> tuple[str, str | None]:
    label = estimate.split(" (", maxsplit=1)[0].replace("²", "^2").strip()
    compact = re.sub(r"\s+", "", label)
    canonical_by_compact = {re.sub(r"\s+", "", item): item for item in CLASSES}
    if compact.startswith(UNKNOWN):
        return UNKNOWN, None
    if compact in canonical_by_compact:
        return canonical_by_compact[compact], None
    if compact == "O(V+E)":
        return "O(n)", "Normalized O(V + E) to O(n) using reviewed n = V + E convention."
    return UNKNOWN, f"Estimate {label!r} is outside the predeclared scoring vocabulary."


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_exclusive(payloads: dict[Path, bytes]) -> dict[str, str]:
    existing = [path.name for path in payloads if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite v2 outputs: {', '.join(existing)}")
    hashes: dict[str, str] = {}
    for path, payload in payloads.items():
        with path.open("xb") as output:
            output.write(payload)
        hashes[path.name] = sha256(payload)
    return hashes


def main() -> int:
    approved_path = ROOT / "manifest-approved-v1.json"
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    analysis_path = ROOT / "analysis-output-v1.json"
    analysis_bytes = analysis_path.read_bytes()
    analysis = json.loads(analysis_bytes)
    gold_path = ROOT / "gold-reviewed-v1.jsonl"
    packet_path = ROOT / "review-packet-v1.jsonl"
    original_run_manifest_path = ROOT / "run-manifest-v1.json"
    original_run_manifest = json.loads(original_run_manifest_path.read_text(encoding="utf-8"))

    if sha256(approved_path.read_bytes()) != original_run_manifest["approved_manifest_sha256"]:
        raise ValueError("Frozen approved manifest hash changed")
    if sha256(gold_path.read_bytes()) != approved["label_file_sha256"]:
        raise ValueError("Frozen gold-label hash changed")
    if sha256(packet_path.read_bytes()) != approved["case_file_sha256"]:
        raise ValueError("Frozen case packet hash changed")
    if sha256(analysis_bytes) != original_run_manifest["outputs"].get(analysis_path.name):
        raise ValueError("Saved raw analysis output hash does not match v1 run manifest")
    if analysis.get("approved_label_file_sha256") != approved["label_file_sha256"]:
        raise ValueError("Raw analyzer output is not bound to the frozen label file")
    if analysis.get("case_file_sha256") != approved["case_file_sha256"]:
        raise ValueError("Raw analyzer output is not bound to the frozen case packet")
    if analysis.get("analyzer_source_sha256") != approved["analyzer_source_sha256"]:
        raise ValueError("Raw analyzer source hashes do not match the frozen manifest")

    cases = analysis.get("cases")
    expected_ids = set(approved["case_ids"])
    if not isinstance(cases, list) or {case.get("id") for case in cases} != expected_ids:
        raise ValueError("Saved raw analysis cases differ from the frozen case IDs")
    gold = load_gold(gold_path)
    predictions: list[dict[str, Any]] = []
    for case in cases:
        case_id = case["id"]
        if case.get("source_sha256") != approved["source_sha256"].get(case_id):
            raise ValueError(f"Saved source hash mismatch for {case_id}")
        prediction, note = normalize_saved_estimate(case["estimate"])
        case["normalized_time_estimate_v2"] = prediction
        case["normalization_note_v2"] = note
        predictions.extend((
            {
                "id": case_id,
                "dimension": "time",
                "method": case["method"],
                "predicted": prediction,
                "confidence": case["confidence"],
                "report_sha256": sha256(analysis_bytes),
            },
            {
                "id": case_id,
                "dimension": "auxiliary_space",
                "method": "not_emitted_by_current_static_analyzer",
                "predicted": UNKNOWN,
                "confidence": None,
                "report_sha256": sha256(analysis_bytes),
            },
        ))

    prediction_bytes = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in predictions
    ).encode()
    with tempfile.TemporaryDirectory(prefix="axioma-v3-reprocess-") as temp:
        prediction_path = Path(temp) / "predictions.jsonl"
        prediction_path.write_bytes(prediction_bytes)
        validated_predictions = load_predictions(prediction_path, gold)
        joined = combine(
            gold,
            validated_predictions,
            sha256(gold_path.read_bytes()),
            sha256(prediction_bytes),
        )
        joined_bytes = "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in joined
        ).encode()
        joined_path = Path(temp) / "joined.jsonl"
        joined_path.write_bytes(joined_bytes)
        report = _score(load_records(joined_path))

    report.update({
        "dataset_id": approved["dataset_id"],
        "joined_input_sha256": sha256(joined_bytes),
        "evaluator_version": "0.4.0",
        "postprocessing_version": "complexity-label-normalizer-v2",
        "postprocessing_note": (
            "Reprocessed the saved raw analyzer output; no Axioma analysis was rerun. "
            "Canonical labels are matched after whitespace normalization on both the estimate "
            "and supported vocabulary, preserving the canonical class spelling."
        ),
    })
    summary = [
        "# Axioma external multifamily pilot v2 — corrected postprocessing",
        "",
        "This is a corrected scoring pass over the saved raw output from the original five-case calibration pilot. Axioma was **not rerun**. The v1 artifacts remain unchanged and preserve the original scoring defect for auditability.",
        "",
        "## Corrected metrics",
        "",
        "| Dimension | Cases | Answered | Coverage | Exact accuracy | Exact among answered |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for dimension, label in (("time", "Worst-case time"), ("auxiliary_space", "Auxiliary space")):
        metrics = report["dimensions"][dimension]
        answered = metrics["answered"]
        exact_selective = metrics["selective_exact_accuracy"]
        summary.append(
            f"| {label} | {metrics['n']} | {answered} | {metrics['coverage']:.0%} "
            f"({answered}/{metrics['n']}) | {metrics['exact_accuracy']:.0%} "
            f"({round(metrics['exact_accuracy'] * metrics['n'])}/{metrics['n']}) | "
            f"{('Not defined' if exact_selective is None else f'{exact_selective:.0%}') } |"
        )
    summary += [
        "",
        "## Why the score changed",
        "",
        "The v1 normalizer removed whitespace from Axioma labels but compared them to canonical labels containing spaces. As a result, the valid analyzer estimate `O(log n)` became `unknown`. The v2 normalizer canonicalizes both sides and records `O(log n)` as a supported class.",
        "",
        "The pilot remains a five-case calibration diagnostic, not an untouched holdout. Its small sample is not a broad accuracy claim. Auxiliary-space coverage remains zero because the current static analyzer did not emit that class.",
        "",
        "See `predictions-v2.jsonl`, `joined-evaluation-v2.jsonl`, `evaluation-report-v2.json`, and `run-manifest-v2.json` for the corrected, hash-bound artifacts.",
        "",
    ]
    summary_bytes = "\n".join(summary).encode()
    output_payloads = {
        OUTPUTS["predictions"]: prediction_bytes,
        OUTPUTS["joined"]: joined_bytes,
        OUTPUTS["report"]: json_bytes(report),
        OUTPUTS["summary"]: summary_bytes,
    }
    output_hashes = write_exclusive(output_payloads)
    reprocessor_hash = sha256(Path(__file__).read_bytes())
    run_manifest = {
        "dataset_id": approved["dataset_id"],
        "partition": approved["partition"],
        "run_type": "postprocessing_only_no_analyzer_rerun",
        "source_run_manifest_sha256": sha256(original_run_manifest_path.read_bytes()),
        "source_analysis_output_sha256": sha256(analysis_bytes),
        "approved_manifest_sha256": sha256(approved_path.read_bytes()),
        "approved_label_file_sha256": sha256(gold_path.read_bytes()),
        "case_file_sha256": sha256(packet_path.read_bytes()),
        "analyzer_commit": analysis["analyzer_commit"],
        "analyzer_source_sha256": analysis["analyzer_source_sha256"],
        "postprocessing_version": "complexity-label-normalizer-v2",
        "reprocessor_source_sha256": reprocessor_hash,
        "correction": "Normalize whitespace against canonical class spellings on both sides; v1 incorrectly converted O(log n) to unknown.",
        "outputs": output_hashes,
    }
    manifest_bytes = json_bytes(run_manifest)
    with OUTPUTS["manifest"].open("xb") as output:
        output.write(manifest_bytes)

    print(json.dumps({
        "time": {
            "n": report["dimensions"]["time"]["n"],
            "answered": report["dimensions"]["time"]["answered"],
            "coverage": report["dimensions"]["time"]["coverage"],
            "exact_accuracy": report["dimensions"]["time"]["exact_accuracy"],
            "selective_exact_accuracy": report["dimensions"]["time"]["selective_exact_accuracy"],
        },
        "auxiliary_space": {
            "n": report["dimensions"]["auxiliary_space"]["n"],
            "answered": report["dimensions"]["auxiliary_space"]["answered"],
            "coverage": report["dimensions"]["auxiliary_space"]["coverage"],
        },
        "outputs": output_hashes,
        "reprocessor_source_sha256": reprocessor_hash,
        "analyzer_rerun": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
