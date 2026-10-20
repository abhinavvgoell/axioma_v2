"""Score Mode 1 test detection against labeled correct and mutated solutions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054
) -> dict[str, float] | None:
    """Return a two-sided 95% Wilson score interval for a binomial rate."""
    if trials == 0:
        return None
    rate = successes / trials
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    margin = (
        z
        * (rate * (1 - rate) / trials + z * z / (4 * trials * trials)) ** 0.5
        / denominator
    )
    return {"lower": max(0.0, center - margin), "upper": min(1.0, center + margin)}


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number}: each record must be a JSON object")
            missing = {"id", "label", "passed", "failed", "skipped"} - record.keys()
            if missing:
                raise ValueError(
                    f"line {line_number}: missing fields: {', '.join(sorted(missing))}"
                )
            if not isinstance(record["id"], str) or not record["id"].strip():
                raise ValueError(f"line {line_number}: id must be a non-empty string")
            if record["id"] in seen:
                raise ValueError(f"line {line_number}: duplicate id {record['id']!r}")
            seen.add(record["id"])
            if not isinstance(record["label"], str) or record["label"] not in {
                "correct",
                "mutant",
            }:
                raise ValueError(f"line {line_number}: label must be correct or mutant")
            for field in ("passed", "failed", "skipped"):
                value = record[field]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"line {line_number}: {field} must be a non-negative integer")
            if record["passed"] + record["failed"] + record["skipped"] == 0:
                raise ValueError(f"line {line_number}: test counts cannot all be zero")
            records.append(record)
    if not records:
        raise ValueError("input contains no evaluation records")
    return records


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: Counter[tuple[str, str]] = Counter()
    excluded: Counter[str] = Counter()
    for record in records:
        if record["failed"]:
            prediction = "detected"
        elif record["skipped"]:
            excluded[record["label"]] += 1
            continue
        else:
            prediction = "not_detected"
        matrix[(record["label"], prediction)] += 1

    true_positive = matrix[("mutant", "detected")]
    false_negative = matrix[("mutant", "not_detected")]
    false_positive = matrix[("correct", "detected")]
    true_negative = matrix[("correct", "not_detected")]
    mutant_total = true_positive + false_negative
    correct_total = false_positive + true_negative
    predicted_positive = true_positive + false_positive
    return {
        "records": len(records),
        "scored_mutants": mutant_total,
        "scored_correct_controls": correct_total,
        "excluded_incomplete": dict(sorted(excluded.items())),
        "mutant_detection_recall": true_positive / mutant_total if mutant_total else None,
        "mutant_detection_recall_95_ci": _wilson_interval(true_positive, mutant_total),
        "correct_control_false_positive_rate": (
            false_positive / correct_total if correct_total else None
        ),
        "correct_control_false_positive_rate_95_ci": _wilson_interval(
            false_positive, correct_total
        ),
        "precision": true_positive / predicted_positive if predicted_positive else None,
        "precision_95_ci": _wilson_interval(true_positive, predicted_positive),
        "confusion": {
            "mutants_detected": true_positive,
            "mutants_not_detected": false_negative,
            "correct_flagged": false_positive,
            "correct_not_flagged": true_negative,
        },
        "interpretation": (
            "A failed test marks a mutant as detected or a correct control as a false positive. "
            "Records with no failure and at least one skipped test are excluded as incomplete. "
            "These metrics describe only the labeled evaluation set."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSONL labels joined with Axioma test counts")
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    args = parser.parse_args()
    try:
        report = _score(load_records(args.records))
        report["input_sha256"] = hashlib.sha256(args.records.read_bytes()).hexdigest()
        report["evaluator_version"] = "0.2.0"
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
