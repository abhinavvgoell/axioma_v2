"""Join frozen BFS v2 labels to raw predictions and score response/complexity separately."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from bfs_v2_complexity import compare_complexities


class EvaluationInputError(ValueError):
    """Raised when gold labels and prediction records cannot be joined safely."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationInputError(f"{path}:{line_number}: invalid JSON") from exc
        if not isinstance(record, dict):
            raise EvaluationInputError(f"{path}:{line_number}: expected a JSON object")
        records.append(record)
    return records


def _index_unique(
    records: Sequence[Mapping[str, Any]], source: str
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise EvaluationInputError(
                f"{source} contains a missing or invalid case_id"
            )
        if case_id in indexed:
            raise EvaluationInputError(
                f"{source} contains duplicate case_id {case_id!r}"
            )
        indexed[case_id] = record
    return indexed


def _evidence_summary(raw: Mapping[str, Any] | None) -> Any:
    if not raw:
        return None
    return {
        "method": raw.get("method"),
        "explanation": raw.get("explanation"),
        "details": raw.get("details"),
    }


def join_and_score(
    gold_artifact: Mapping[str, Any], predictions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Join strictly by case ID and compute separately denominated metrics."""
    if gold_artifact.get("gold_labels_frozen") is not True:
        raise EvaluationInputError("gold artifact is not frozen")
    if gold_artifact.get("owner_confirmed") is not True:
        raise EvaluationInputError("gold artifact lacks owner confirmation")
    gold_records = gold_artifact.get("cases")
    if not isinstance(gold_records, list):
        raise EvaluationInputError("gold artifact has no cases array")
    gold_by_id = _index_unique(gold_records, "gold labels")
    prediction_by_id = _index_unique(predictions, "predictions")
    missing = sorted(set(gold_by_id) - set(prediction_by_id))
    extra = sorted(set(prediction_by_id) - set(gold_by_id))
    if missing or extra:
        raise EvaluationInputError(
            f"case ID set mismatch; missing predictions={missing}; extra predictions={extra}"
        )

    results: list[dict[str, Any]] = []
    for gold in gold_records:
        case_id = gold["case_id"]
        prediction = prediction_by_id[case_id]
        if prediction.get("source_sha256") != gold.get("source_sha256"):
            raise EvaluationInputError(f"source hash mismatch for {case_id}")
        if prediction.get("language") != gold.get("language"):
            raise EvaluationInputError(f"language mismatch for {case_id}")
        status = prediction.get("execution_status")
        actual_response = prediction.get("actual_response")
        raw = prediction.get("analyzer_output")
        if status == "completed":
            if actual_response not in {"estimate", "unknown"} or not isinstance(
                raw, Mapping
            ):
                raise EvaluationInputError(
                    f"invalid completed prediction for {case_id}"
                )
            estimate = raw.get("estimate")
            if not isinstance(estimate, str):
                raise EvaluationInputError(f"missing raw estimate for {case_id}")
        elif status == "error":
            if actual_response != "error" or prediction.get("error") is None:
                raise EvaluationInputError(
                    f"execution error is not distinctly represented for {case_id}"
                )
            estimate = None
        else:
            raise EvaluationInputError(
                f"invalid execution_status for {case_id}: {status!r}"
            )

        expected_response = gold["expected_analyzer_response"]
        if expected_response not in {"estimate", "unknown"}:
            raise EvaluationInputError(f"invalid expected response for {case_id}")
        comparison = None
        if status == "completed" and actual_response == "estimate":
            comparison = compare_complexities(gold["mathematical_complexity"], estimate)
        response_agreement = actual_response == expected_response
        results.append(
            {
                "case_id": case_id,
                "language": gold["language"],
                "pattern": gold["pattern"],
                "source_sha256": gold["source_sha256"],
                "expected_complexity": gold["mathematical_complexity"],
                "expected_response": expected_response,
                "actual_response": actual_response,
                "actual_estimate": estimate,
                "complexity_comparison": comparison,
                "confidence": raw.get("confidence")
                if isinstance(raw, Mapping)
                else None,
                "evidence_summary": _evidence_summary(
                    raw if isinstance(raw, Mapping) else None
                ),
                "execution_status": status,
                "error": prediction.get("error"),
                "response_agreement": response_agreement,
            }
        )

    total = len(results)
    estimate_rows = [row for row in results if row["actual_response"] == "estimate"]
    correct_estimates = sum(
        row["expected_response"] == "estimate" and row["actual_response"] == "estimate"
        for row in results
    )
    correct_abstentions = sum(
        row["expected_response"] == "unknown" and row["actual_response"] == "unknown"
        for row in results
    )
    unexpected_estimates = sum(
        row["expected_response"] == "unknown" and row["actual_response"] == "estimate"
        for row in results
    )
    unexpected_abstentions = sum(
        row["expected_response"] == "estimate" and row["actual_response"] == "unknown"
        for row in results
    )
    exact = sum(
        row["complexity_comparison"] is not None
        and row["complexity_comparison"]["status"] == "exact_match"
        for row in results
    )
    equivalent = sum(
        row["complexity_comparison"] is not None
        and row["complexity_comparison"]["status"] == "mathematically_equivalent"
        for row in results
    )
    mismatch = sum(
        row["complexity_comparison"] is not None
        and row["complexity_comparison"]["status"] == "mismatch"
        for row in results
    )
    unscorable = sum(
        row["complexity_comparison"] is not None
        and row["complexity_comparison"]["status"] == "unscorable"
        for row in results
    )
    scorable = exact + equivalent + mismatch
    expected_estimate_total = sum(
        row["expected_response"] == "estimate" for row in results
    )
    agreement = correct_estimates + correct_abstentions

    return {
        "schema_version": "axioma.bfs-v2.evaluation.v1",
        "case_count": total,
        "response_behavior": {
            "correct_estimate_responses": correct_estimates,
            "correct_unknown_responses": correct_abstentions,
            "unexpected_estimates_on_expected_unknown": unexpected_estimates,
            "unexpected_abstentions_on_expected_estimate": unexpected_abstentions,
            "execution_errors": sum(
                row["execution_status"] == "error" for row in results
            ),
            "response_agreement_count": agreement,
            "response_agreement_denominator": total,
            "response_agreement_rate": agreement / total if total else None,
        },
        "complexity_correctness": {
            "emitted_estimates": len(estimate_rows),
            "exact_match": exact,
            "mathematically_equivalent": equivalent,
            "mismatch": mismatch,
            "unscorable": unscorable,
            "exact_accuracy_among_emitted_estimates": exact / len(estimate_rows)
            if estimate_rows
            else None,
            "equivalent_accuracy_among_emitted_estimates": (exact + equivalent)
            / len(estimate_rows)
            if estimate_rows
            else None,
            "exact_accuracy_among_scorable_estimates": exact / scorable
            if scorable
            else None,
            "equivalent_accuracy_among_scorable_estimates": (exact + equivalent)
            / scorable
            if scorable
            else None,
            "all_emitted_estimates_denominator": len(estimate_rows),
            "scorable_estimates_denominator": scorable,
            "unscorable_estimates_denominator_note": "Unscorable expressions remain in the all-emitted denominator and are excluded only from explicitly named scorable-only rates.",
        },
        "coverage": {
            "estimate_count": len(estimate_rows),
            "denominator": total,
            "rate": len(estimate_rows) / total if total else None,
            "expected_estimate_cases": expected_estimate_total,
            "estimates_on_expected_estimate_cases": correct_estimates,
            "expected_estimate_subset_coverage": correct_estimates
            / expected_estimate_total
            if expected_estimate_total
            else None,
        },
        "abstention_quality": {
            "correct_abstentions": correct_abstentions,
            "unexpected_estimates": unexpected_estimates,
            "unexpected_abstentions": unexpected_abstentions,
            "execution_errors": sum(
                row["execution_status"] == "error" for row in results
            ),
        },
        "case_results": results,
    }


def write_case_csv(path: Path, report: Mapping[str, Any]) -> None:
    """Write the human-readable comparison table without overwriting evidence."""
    fields = [
        "case_id",
        "language",
        "pattern",
        "source_sha256",
        "expected_complexity",
        "expected_response",
        "actual_response",
        "actual_estimate",
        "comparison_status",
        "comparison_reason",
        "confidence",
        "evidence_summary",
        "execution_status",
        "error",
        "response_agreement",
    ]
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in report["case_results"]:
            comparison = row["complexity_comparison"] or {}
            writer.writerow(
                {
                    **{key: row.get(key) for key in fields if key in row},
                    "comparison_status": comparison.get("status"),
                    "comparison_reason": comparison.get("reason"),
                    "evidence_summary": json.dumps(
                        row.get("evidence_summary"), ensure_ascii=False
                    ),
                    "error": json.dumps(row.get("error"), ensure_ascii=False),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", type=Path, help="frozen gold-label JSON")
    parser.add_argument("predictions", type=Path, help="raw predictions JSONL")
    parser.add_argument(
        "--output", required=True, type=Path, help="new score JSON path"
    )
    parser.add_argument("--csv", type=Path, help="optional new case-results CSV path")
    args = parser.parse_args()
    try:
        output_paths = [args.output, *([args.csv] if args.csv is not None else [])]
        if len({path.resolve() for path in output_paths}) != len(output_paths):
            parser.error("JSON and CSV output paths must be different")
        existing = [path for path in output_paths if path.exists()]
        if existing:
            parser.error(f"refusing to overwrite existing output: {existing[0]}")
        missing_parents = [
            path.parent for path in output_paths if not path.parent.is_dir()
        ]
        if missing_parents:
            parser.error(f"output directory does not exist: {missing_parents[0]}")
        gold = json.loads(args.gold.read_text(encoding="utf-8"))
        predictions = _read_jsonl(args.predictions)
        report = join_and_score(gold, predictions)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(report, output, indent=2, ensure_ascii=False)
            output.write("\n")
        if args.csv:
            write_case_csv(args.csv, report)
    except (OSError, json.JSONDecodeError, EvaluationInputError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
