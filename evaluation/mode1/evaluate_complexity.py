"""Score human-labeled Mode 1 complexity estimates from JSON Lines."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

CLASSES = ("O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)")
CONFIDENCE = {"high", "medium", "low"}
PARTITIONS = {"calibration", "evaluation"}


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
    seen: set[tuple[str, str]] = set()
    id_partitions: dict[str, str] = {}
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
            if confidence is not None and (
                not isinstance(confidence, str) or confidence not in CONFIDENCE
            ):
                raise ValueError(f"line {line_number}: confidence must be high, medium, or low")
            partition = record.get("partition", "evaluation")
            if not isinstance(partition, str) or partition not in PARTITIONS:
                raise ValueError(
                    f"line {line_number}: partition must be calibration or evaluation"
                )
            previous_partition = id_partitions.setdefault(record["id"], partition)
            if previous_partition != partition:
                raise ValueError(
                    f"line {line_number}: all methods for id {record['id']!r} "
                    "must use the same partition"
                )
            record["partition"] = partition
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
    distinct_solutions = len({record["id"] for record in records})
    minimum_solutions = 50
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
        exact = sum(item["expected"] == item["predicted"] for item in items)
        adjacent = sum(
            abs(CLASSES.index(item["expected"]) - CLASSES.index(item["predicted"])) <= 1
            for item in items
        )
        return {
            "n": n,
            "exact_accuracy": exact / n,
            "exact_accuracy_95_ci": _wilson_interval(exact, n),
            "within_one_class_accuracy": adjacent / n,
            "within_one_class_accuracy_95_ci": _wilson_interval(adjacent, n),
        }

    matrix = {
        expected: {predicted: confusion[expected][predicted] for predicted in CLASSES}
        for expected in CLASSES
    }
    calibration_records = [item for item in records if item["partition"] == "calibration"]
    evaluation_records = [item for item in records if item["partition"] == "evaluation"]
    calibration_by_method_confidence: dict[
        tuple[str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for item in calibration_records:
        if item.get("confidence") is not None:
            calibration_by_method_confidence[(item["method"], item["confidence"])].append(item)
    calibration_rates = {
        method_level: sum(item["expected"] == item["predicted"] for item in items) / len(items)
        for method_level, items in calibration_by_method_confidence.items()
    }
    held_out: list[tuple[float, bool, str, str]] = []
    excluded_unmapped = 0
    for item in evaluation_records:
        level = item.get("confidence")
        method_level = (item["method"], level)
        if (
            level is None
            or not isinstance(level, str)
            or method_level not in calibration_rates
        ):
            excluded_unmapped += 1
            continue
        held_out.append(
            (
                calibration_rates[method_level],
                item["expected"] == item["predicted"],
                item["method"],
                level,
            )
        )
    if calibration_records and evaluation_records and held_out:
        brier = sum(
            (probability - correct) ** 2 for probability, correct, _, _ in held_out
        ) / len(held_out)
        epsilon = 1e-6
        log_loss = -sum(
            correct * math.log(max(epsilon, probability))
            + (not correct) * math.log(max(epsilon, 1 - probability))
            for probability, correct, _, _ in held_out
        ) / len(held_out)
        held_out_by_method_confidence: dict[tuple[str, str], list[bool]] = defaultdict(list)
        for _, correct, method, level in held_out:
            held_out_by_method_confidence[(method, level)].append(correct)
        ece = sum(
            len(items)
            / len(held_out)
            * abs(calibration_rates[method_level] - sum(items) / len(items))
            for method_level, items in held_out_by_method_confidence.items()
        )
        held_out_calibration: dict[str, Any] = {
            "available": True,
            "calibration_records": len(calibration_records),
            "evaluation_records": len(evaluation_records),
            "scored_evaluation_records": len(held_out),
            "excluded_unmapped_evaluation_records": excluded_unmapped,
            "brier_score": brier,
            "log_loss": log_loss,
            "log_loss_probability_floor": epsilon,
            "expected_calibration_error": ece,
            "per_method_confidence": {},
            "mapping_by_method": {},
            "note": (
                "Probabilities are category accuracies learned on the calibration "
                "partition; metrics use only the held-out evaluation partition."
            ),
        }
        for (method, level), items in calibration_by_method_confidence.items():
            correct = sum(item["expected"] == item["predicted"] for item in items)
            held_out_calibration["mapping_by_method"].setdefault(method, {})[level] = {
                "calibration_n": len(items),
                "empirical_accuracy": calibration_rates[(method, level)],
                "empirical_accuracy_95_ci": _wilson_interval(correct, len(items)),
            }
        for (method, level), items in held_out_by_method_confidence.items():
            correct = sum(items)
            held_out_calibration["per_method_confidence"].setdefault(method, {})[level] = {
                "n": len(items),
                "evaluation_accuracy": correct / len(items),
                "evaluation_accuracy_95_ci": _wilson_interval(correct, len(items)),
                "calibration_probability": calibration_rates[(method, level)],
            }
    else:
        held_out_calibration = {
            "available": False,
            "reason": (
                "Provide confidence-labeled records in both calibration and evaluation "
                "partitions, with a method and confidence category represented in both."
            ),
        }

    return {
        "n": len(records),
        "distinct_solutions": distinct_solutions,
        "minimum_distinct_solutions": minimum_solutions,
        "minimum_solution_count_met": distinct_solutions >= minimum_solutions,
        "evaluation_readiness": (
            "minimum_met" if distinct_solutions >= minimum_solutions else "below_minimum"
        ),
        "interval_method": "two-sided 95% Wilson score interval (z=1.95996)",
        "class_order": list(CLASSES),
        "exact_accuracy": exact / len(records),
        "exact_accuracy_95_ci": _wilson_interval(exact, len(records)),
        "within_one_class_accuracy": within_one / len(records),
        "within_one_class_accuracy_95_ci": _wilson_interval(within_one, len(records)),
        "by_method": {method: summary(items) for method, items in sorted(by_method.items())},
        "by_partition": {
            partition: summary([item for item in records if item["partition"] == partition])
            for partition in sorted({item["partition"] for item in records})
        },
        "by_confidence": {level: summary(items) for level, items in sorted(by_confidence.items())},
        "confusion_matrix": matrix,
        "confidence_note": (
            "Without separate partitions, confidence strata are descriptive only. "
            "Held-out calibration uses category accuracy learned from the calibration "
            "partition, not assumed numeric values."
        ),
        "interval_note": (
            "Wilson intervals are record-level binomial intervals; records from different methods "
            "for the same solution are correlated, so compare method-specific intervals and treat "
            "combined intervals as descriptive."
        ),
        "held_out_confidence_calibration": held_out_calibration,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSONL file with human-reviewed gold labels")
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
