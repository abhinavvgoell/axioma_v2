"""Score human-labeled Mode 1 complexity estimates from JSON Lines."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

CLASSES = ("O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)")
CONFIDENCE = {"high", "medium", "low"}


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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
            missing = {"id", "method", "expected", "predicted"} - record.keys()
            if missing:
                raise ValueError(
                    f"line {line_number}: missing fields: {', '.join(sorted(missing))}"
                )
            for field in ("id", "method"):
                if not isinstance(record[field], str) or not record[field].strip():
                    raise ValueError(f"line {line_number}: {field} must be a non-empty string")
            for field in ("expected", "predicted"):
                if record[field] not in CLASSES:
                    raise ValueError(
                        f"line {line_number}: {field} must be one of {', '.join(CLASSES)}"
                    )
            confidence = record.get("confidence")
            if confidence is not None and confidence not in CONFIDENCE:
                raise ValueError(f"line {line_number}: confidence must be high, medium, or low")
            key = (record["id"], record["method"])
            if key in seen:
                raise ValueError(
                    f"line {line_number}: duplicate id and method: {key[0]} / {key[1]}"
                )
            seen.add(key)
            records.append(record)
    if not records:
        raise ValueError("input contains no evaluation records")
    return records


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    exact = 0
    within_one = 0
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_confidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        distance = abs(CLASSES.index(record["expected"]) - CLASSES.index(record["predicted"]))
        exact += distance == 0
        within_one += distance <= 1
        confusion[record["expected"]][record["predicted"]] += 1
        by_method[record["method"]].append(record)
        if record.get("confidence") is not None:
            by_confidence[record["confidence"]].append(record)

    def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(items)
        return {
            "n": n,
            "exact_accuracy": sum(item["expected"] == item["predicted"] for item in items) / n,
            "within_one_class_accuracy": sum(
                abs(CLASSES.index(item["expected"]) - CLASSES.index(item["predicted"])) <= 1
                for item in items
            )
            / n,
        }

    matrix = {
        expected: {predicted: confusion[expected][predicted] for predicted in CLASSES}
        for expected in CLASSES
    }
    return {
        "n": len(records),
        "class_order": list(CLASSES),
        "exact_accuracy": exact / len(records),
        "within_one_class_accuracy": within_one / len(records),
        "by_method": {method: summary(items) for method, items in sorted(by_method.items())},
        "by_confidence": {level: summary(items) for level, items in sorted(by_confidence.items())},
        "confusion_matrix": matrix,
        "confidence_note": "Confidence strata are descriptive only; categorical labels are not calibrated probabilities.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSONL file with human-reviewed gold labels")
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    args = parser.parse_args()
    try:
        report = _score(load_records(args.records))
        report["input_sha256"] = hashlib.sha256(args.records.read_bytes()).hexdigest()
        report["evaluator_version"] = "0.1.0"
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
