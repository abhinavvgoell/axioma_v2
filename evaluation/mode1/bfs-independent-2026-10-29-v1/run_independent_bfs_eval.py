from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from axioma_worker.java_complexity import analyze_java_complexity
from axioma_worker.python_complexity import analyze_python_complexity


ROOT = Path(__file__).resolve().parents[3]
DATASET = Path(__file__).resolve().parent
MANIFEST = DATASET / "manifest-pre-run.json"
CASE_FILE = DATASET / "cases.jsonl"
LABEL_FILE = DATASET / "gold-provisional.jsonl"
PREDICTIONS_FILE = DATASET / "predictions.jsonl"
RESULTS_FILE = DATASET / "results.json"
REPORT_FILE = DATASET / "evaluation-report.md"
RUN_MANIFEST_FILE = DATASET / "run-manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize(value: str) -> str:
    if value.strip().lower().startswith("unknown"):
        return "unknown"
    value = value.split(" (", 1)[0]
    return re.sub(r"\s+", "", value)


def _metrics(rows: list[dict]) -> dict:
    eligible = [row for row in rows if row["complexity_scorable"]]
    answered = [
        row for row in eligible
        if row["prediction_state"] == "estimate"
    ]
    exact = [row for row in answered if row["truth_exact"]]
    supported = [row for row in rows if row["supported_pattern_candidate"]]
    supported_answered = [row for row in supported if row["prediction_state"] == "estimate"]
    expected_unknown = [
        row for row in rows if row["expected_analyzer_response"] == "unknown"
    ]
    agreed_unknown = [
        row for row in expected_unknown if row["prediction_state"] == "unknown"
    ]
    negative_predictions = [
        row for row in expected_unknown if row["prediction_state"] == "estimate"
    ]
    return {
        "eligible_scorable": len(eligible),
        "answered": len(answered),
        "abstentions": sum(row["prediction_state"] == "unknown" for row in eligible),
        "execution_failures": sum(row["prediction_state"] == "execution_failure" for row in rows),
        "exact_predictions": len(exact),
        "exact_accuracy_among_answered": len(exact) / len(answered) if answered else None,
        "coverage": len(answered) / len(eligible) if eligible else None,
        "selective_accuracy": len(exact) / len(answered) if answered else None,
        "all_case_exact_rate": len(exact) / len(eligible) if eligible else None,
        "supported_candidates": len(supported),
        "supported_pattern_coverage": (
            len(supported_answered) / len(supported) if supported else None
        ),
        "expected_unknown_cases": len(expected_unknown),
        "expected_abstention_agreement": (
            len(agreed_unknown) / len(expected_unknown) if expected_unknown else None
        ),
        "negative_case_false_positives": len(negative_predictions),
        "negative_false_positive_truth_matches": sum(row["truth_exact"] for row in negative_predictions),
        "negative_false_positive_truth_mismatches": sum(not row["truth_exact"] for row in negative_predictions),
        "non_scorable_cases": sum(not row["complexity_scorable"] for row in rows),
    }


def _score_rows(rows: list[dict]) -> dict:
    by_language: dict[str, list[dict]] = defaultdict(list)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_language[row["language"]].append(row)
        by_category[row["category"]].append(row)
    return {
        "overall": _metrics(rows),
        "by_language": {key: _metrics(value) for key, value in sorted(by_language.items())},
        "by_pattern": {key: _metrics(value) for key, value in sorted(by_category.items())},
    }


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _validate_frozen_inputs(manifest: dict, case_bytes: bytes, label_bytes: bytes) -> None:
    if _sha256(case_bytes) != manifest["case_file_sha256"]:
        raise ValueError("Case file hash differs from the pre-run manifest.")
    if _sha256(label_bytes) != manifest["label_file_sha256"]:
        raise ValueError("Gold label hash differs from the pre-run manifest.")
    current_hashes = {
        "java_complexity.py": _sha256(
            (ROOT / "services/worker/src/axioma_worker/java_complexity.py").read_bytes()
        ),
        "python_complexity.py": _sha256(
            (ROOT / "services/worker/src/axioma_worker/python_complexity.py").read_bytes()
        ),
    }
    if current_hashes != manifest["analyzer_source_sha256"]:
        raise ValueError("Analyzer source differs from the preregistered working-tree revision.")
    current_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if current_commit != manifest["analyzer_commit"]:
        raise ValueError("Git HEAD differs from the pre-run manifest.")


def _render_report(result: dict) -> str:
    metrics = result["metrics"]
    lines = [
        "# Independent BFS complexity evaluation — 2026-10-29",
        "",
        f"- Dataset: `{result['dataset_id']}` ({result['case_count']} cases; Java {result['language_counts']['java']}, Python {result['language_counts']['python']})",
        f"- Label status: **{result['label_review_status']}**",
        f"- Frozen label SHA-256: `{result['label_file_sha256']}`",
        f"- Analyzer commit: `{result['analyzer_commit']}`; analyzer source SHA-256 values are in `run-manifest.json`.",
        f"- Rule version: `{result['rule_version']}`",
        "- No submitted code was compiled or executed; this was static analysis only.",
        "",
        "## Overall metrics",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Scorable cases | {metrics['eligible_scorable']} |",
        f"| Concrete predictions | {metrics['answered']} |",
        f"| Exact accuracy among answered | {_fmt(metrics['exact_accuracy_among_answered'])} |",
        f"| Coverage | {_fmt(metrics['coverage'])} |",
        f"| Selective accuracy (paired with coverage) | {_fmt(metrics['selective_accuracy'])} |",
        f"| All-case exact rate | {_fmt(metrics['all_case_exact_rate'])} |",
        f"| Supported-pattern candidates | {metrics['supported_candidates']} |",
        f"| Supported-pattern coverage | {_fmt(metrics['supported_pattern_coverage'])} |",
        f"| Expected-unknown cases / correct abstention agreement | {metrics['expected_unknown_cases']} / {_fmt(metrics['expected_abstention_agreement'])} |",
        f"| Unsupported-case concrete predictions | {metrics['negative_case_false_positives']} (truth-matching {metrics['negative_false_positive_truth_matches']}, mismatching {metrics['negative_false_positive_truth_mismatches']}) |",
        f"| Execution failures | {metrics['execution_failures']} |",
        "",
        "## Results by language",
        "",
        "| Language | Scorable | Answered | Exact accuracy | Coverage | Unsupported-case estimates |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for language, values in result["metrics_by_language"].items():
        lines.append(
            f"| {language} | {values['eligible_scorable']} | {values['answered']} | "
            f"{_fmt(values['exact_accuracy_among_answered'])} | {_fmt(values['coverage'])} | "
            f"{values['negative_case_false_positives']} |"
        )
    lines.extend(["", "## Results by pattern", "", "| Pattern | Cases | Answered | Exact accuracy | Coverage | Expected unknown | False positives |", "|---|---:|---:|---:|---:|---:|---:|"])
    for pattern, values in result["metrics_by_pattern"].items():
        lines.append(
            f"| {pattern} | {values['eligible_scorable'] + values['non_scorable_cases']} | "
            f"{values['answered']} | {_fmt(values['exact_accuracy_among_answered'])} | "
            f"{_fmt(values['coverage'])} | {values['expected_unknown_cases']} | "
            f"{values['negative_case_false_positives']} |"
        )
    positives = [row for row in result["predictions"] if row["negative_case_false_positive"]]
    lines.extend(["", "## Unsupported-pattern estimates and evidence review", ""])
    if positives:
        for row in positives:
            relation = "matches provisional truth" if row["truth_exact"] else "disagrees with provisional truth"
            lines.append(
                f"- `{row['id']}` ({row['category']}): predicted `{row['predicted']}`; {relation}. "
                f"Review method `{row['method']}`, evidence signals, and assumptions in `predictions.jsonl`."
            )
    else:
        lines.append("No concrete prediction occurred on a case preregistered to require abstention.")
    agreed = [row for row in result["predictions"] if row["expected_analyzer_response"] == "estimate" and row["prediction_state"] == "unknown"]
    lines.extend(["", "## Supported-pattern abstentions", ""])
    if agreed:
        for row in agreed:
            lines.append(f"- `{row['id']}` ({row['category']}): expected `{row['time_complexity']}`, analyzer abstained. See source and evidence in `predictions.jsonl`.")
    else:
        lines.append("None.")
    lines.extend([
        "",
        "## Method, limitations, and interpretation",
        "",
        "The evaluator checked the pre-run manifest hashes, each source hash, Git HEAD, and the working-tree hashes of both analyzer files before invoking the existing Java/Python analyzer. It records one prediction per case, including complete structured evidence, or a separate execution-failure record. It does not alter analyzer configuration or rules.",
        "",
        "Labels were authored before the analyzer run but were not reviewed by a second human; all are provisional. Therefore these results are exploratory and must not be reported as human-approved accuracy. There are two intentionally non-finite/nonterminating cases (one per language), excluded from complexity accuracy and coverage. Unsupported-case estimates are reviewed against both the provisional mathematical label and the preregistered expectation to abstain.",
        "",
        "No runtime benchmarks, auxiliary-space estimates, API tests, database tests, or submitted-code execution were performed. The evaluation set must not be used to tune rules and still be called independent; after examining errors it becomes development data.",
        "",
        "## Reproduction",
        "",
        "```powershell",
        "services/api/.venv/Scripts/python.exe evaluation/mode1/bfs-independent-2026-10-29-v1/run_independent_bfs_eval.py",
        "```",
        "",
        "Raw predictions/evidence: `predictions.jsonl`. Machine-readable metrics: `results.json`. Run provenance: `run-manifest.json`.",
    ])
    return "\n".join(lines) + "\n"


def _fmt(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.1%}"


def run() -> dict:
    outputs = [PREDICTIONS_FILE, RESULTS_FILE, REPORT_FILE, RUN_MANIFEST_FILE]
    existing = [path.name for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite evaluation outputs: {existing}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    case_bytes = CASE_FILE.read_bytes()
    label_bytes = LABEL_FILE.read_bytes()
    _validate_frozen_inputs(manifest, case_bytes, label_bytes)
    cases = _load_jsonl(CASE_FILE)
    labels = {row["id"]: row for row in _load_jsonl(LABEL_FILE)}
    if len(cases) != manifest["case_count"] or len(labels) != len(cases):
        raise ValueError("Frozen manifest case count or labels do not match the dataset.")
    if len({case["id"] for case in cases}) != len(cases) or set(labels) != {case["id"] for case in cases}:
        raise ValueError("Case IDs must be unique and pair exactly with frozen labels.")

    predictions = []
    for case in cases:
        label = labels[case["id"]]
        source_hash = _sha256(case["source"].encode("utf-8"))
        if source_hash != case["source_sha256"] or source_hash != label["source_sha256"]:
            raise ValueError(f"Source hash mismatch for {case['id']}.")
        record = {
            **label,
            "entrypoint": case["entrypoint"],
            "source_sha256": source_hash,
            "source": case["source"],
        }
        try:
            analyzer = analyze_java_complexity if case["language"] == "java" else analyze_python_complexity
            estimate = analyzer(case["source"], case["entrypoint"])
            raw = estimate.estimate
            predicted = _normalize(raw)
            state = "unknown" if predicted == "unknown" else "estimate"
            truth_exact = bool(
                label["complexity_scorable"]
                and state == "estimate"
                and predicted == _normalize(label["time_complexity"])
            )
            response_agreement = (
                state == "unknown" if label["expected_analyzer_response"] == "unknown"
                else state == "estimate" and predicted == _normalize(label["time_complexity"])
            )
            record.update({
                "raw_prediction": raw,
                "predicted": predicted,
                "prediction_state": state,
                "truth_exact": truth_exact,
                "expected_response_agreement": response_agreement,
                "negative_case_false_positive": (
                    label["expected_analyzer_response"] == "unknown" and state == "estimate"
                ),
                "method": estimate.method,
                "confidence": estimate.confidence,
                "explanation": estimate.explanation,
                "evidence": estimate.details,
            })
        except Exception as exc:  # recorded distinctly; it is not an abstention
            record.update({
                "raw_prediction": None,
                "predicted": "execution_failure",
                "prediction_state": "execution_failure",
                "truth_exact": False,
                "expected_response_agreement": False,
                "negative_case_false_positive": False,
                "method": None,
                "confidence": None,
                "explanation": f"Analyzer raised {type(exc).__name__}: {exc}",
                "evidence": None,
            })
        predictions.append(record)

    summary = _score_rows(predictions)
    result = {
        "dataset_id": manifest["dataset_id"],
        "case_count": len(predictions),
        "language_counts": {
            language: sum(row["language"] == language for row in predictions)
            for language in ("java", "python")
        },
        "label_review_status": manifest["label_review_status"],
        "label_file": LABEL_FILE.name,
        "label_file_sha256": _sha256(label_bytes),
        "case_file": CASE_FILE.name,
        "case_file_sha256": _sha256(case_bytes),
        "analyzer_commit": manifest["analyzer_commit"],
        "analyzer_source_sha256": manifest["analyzer_source_sha256"],
        "rule_version": manifest["rules"]["bfs"],
        "run_at_utc": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "metrics": summary["overall"],
        "metrics_by_language": summary["by_language"],
        "metrics_by_pattern": summary["by_pattern"],
        "predictions": predictions,
    }
    run_manifest = {
        "dataset_id": manifest["dataset_id"],
        "case_file_sha256": _sha256(case_bytes),
        "label_file_sha256": _sha256(label_bytes),
        "analyzer_commit": manifest["analyzer_commit"],
        "analyzer_source_sha256": manifest["analyzer_source_sha256"],
        "rule_version": manifest["rules"]["bfs"],
        "run_at_utc": result["run_at_utc"],
        "python_version": result["python_version"],
        "command": "services/api/.venv/Scripts/python.exe evaluation/mode1/bfs-independent-2026-10-29-v1/run_independent_bfs_eval.py",
    }
    # Evaluate entirely in memory first; write new, previously absent outputs only.
    PREDICTIONS_FILE.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in predictions),
        encoding="utf-8",
    )
    RESULTS_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_FILE.write_text(_render_report(result), encoding="utf-8")
    RUN_MANIFEST_FILE.write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    data = run()
    print(json.dumps(data["metrics"], sort_keys=True))
