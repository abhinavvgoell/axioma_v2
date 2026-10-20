"""Evaluate output-preserving optimization candidates and paired measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

WALL_TIME = "jvm_reflective_wall_time"
WORK_METRICS = {
    "executed_source_line_events",
    "executed_cpython_opcode_events",
}
MEASUREMENT_METHODS = {WALL_TIME, *WORK_METRICS}


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> dict[str, float] | None:
    if trials == 0:
        return None
    rate = successes / trials
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials)) / denominator
    return {"lower": max(0.0, center - margin), "upper": min(1.0, center + margin)}


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


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
            if not isinstance(record.get("id"), str) or not record["id"].strip():
                raise ValueError(f"line {line_number}: id must be a non-empty string")
            if record["id"] in seen:
                raise ValueError(f"line {line_number}: duplicate id {record['id']!r}")
            seen.add(record["id"])
            checks = record.get("checks")
            if not isinstance(checks, dict) or any(
                not _nonnegative_int(checks.get(field))
                for field in ("requested", "checked", "passed", "failed", "skipped")
            ):
                raise ValueError(
                    f"line {line_number}: checks must include non-negative requested, checked, passed, failed, and skipped counts"
                )
            if checks["requested"] == 0 or checks["checked"] > checks["requested"]:
                raise ValueError(f"line {line_number}: checks requested must be positive and checked cannot exceed requested")
            if checks["passed"] + checks["failed"] + checks["skipped"] != checks["checked"]:
                raise ValueError(f"line {line_number}: passed + failed + skipped must equal checked")

            measurements = record.get("measurements", {})
            if not isinstance(measurements, dict) or set(measurements) - MEASUREMENT_METHODS:
                raise ValueError(f"line {line_number}: measurements contains an unsupported method")
            normalized: dict[str, list[dict[str, float]]] = {}
            for method, points in measurements.items():
                if not isinstance(points, list):
                    raise ValueError(f"line {line_number}: {method} measurements must be an array")
                sizes: list[float] = []
                normalized_points = []
                for point in points:
                    if not isinstance(point, dict) or any(
                        isinstance(point.get(field), bool)
                        or not isinstance(point.get(field), (int, float))
                        or not math.isfinite(point[field])
                        or point[field] <= 0
                        for field in ("size", "before", "after")
                    ):
                        raise ValueError(f"line {line_number}: {method} points require positive finite size, before, and after values")
                    sizes.append(float(point["size"]))
                    normalized_points.append({
                        "size": float(point["size"]),
                        "before": float(point["before"]),
                        "after": float(point["after"]),
                    })
                if sizes != sorted(set(sizes)):
                    raise ValueError(f"line {line_number}: {method} benchmark sizes must increase and be unique")
                normalized[method] = normalized_points
            record["measurements"] = normalized
            records.append(record)
    if not records:
        raise ValueError("input contains no optimization records")
    return records


def _preserved(record: dict[str, Any]) -> bool:
    checks = record["checks"]
    return (
        checks["checked"] == checks["requested"]
        and checks["passed"] == checks["requested"]
        and checks["failed"] == 0
        and checks["skipped"] == 0
    )


def _state(record: dict[str, Any]) -> str:
    if _preserved(record):
        return "preserved"
    if record["checks"]["failed"] > 0:
        return "failed"
    return "incomplete"


def _metric_summary(records: list[dict[str, Any]], method: str) -> dict[str, Any]:
    eligible: list[tuple[dict[str, Any], list[dict[str, float]]]] = []
    for record in records:
        points = record["measurements"].get(method, [])
        if _preserved(record) and len(points) >= 4:
            eligible.append((record, points))
    wins = [
        all(point["after"] < point["before"] for point in points)
        for _, points in eligible
    ]
    report: dict[str, Any] = {
        "eligible_candidates": len(eligible),
        "improved_at_every_size": sum(wins),
        "improved_at_every_size_rate": sum(wins) / len(wins) if wins else None,
        "improved_at_every_size_rate_95_ci": _wilson_interval(sum(wins), len(wins)),
        "excluded_for_failed_or_incomplete_equivalence": sum(
            bool(record["measurements"].get(method)) and not _preserved(record)
            for record in records
        ),
        "excluded_for_insufficient_sizes": sum(
            _preserved(record)
            and 0 < len(record["measurements"].get(method, [])) < 4
            for record in records
        ),
        "preserved_candidates_without_measurements": sum(
            _preserved(record) and not record["measurements"].get(method)
            for record in records
        ),
    }
    if method == WALL_TIME:
        ratios = [
            math.exp(sum(math.log(point["before"] / point["after"]) for point in points) / len(points))
            for _, points in eligible
        ]
        report["geometric_mean_speedup_by_candidate"] = [
            {"id": record["id"], "ratio": ratio}
            for (record, _), ratio in zip(eligible, ratios, strict=True)
        ]
        report["interpretation"] = (
            "A speedup success requires lower median wall time at every one of at least four paired sizes, "
            "and complete output equivalence. Ratios summarize these supplied inputs only."
        )
    else:
        report["work_count_method"] = method
        report["interpretation"] = (
            "This is a deterministic work-count reduction, not wall-clock speedup. "
            "A success requires a lower count at every one of at least four paired sizes and complete equivalence."
        )
    return report


def score(records: list[dict[str, Any]]) -> dict[str, Any]:
    states = Counter(_state(record) for record in records)
    evaluable = states["preserved"] + states["failed"]
    return {
        "candidate_records": len(records),
        "equivalence": {
            "preserved": states["preserved"],
            "failed": states["failed"],
            "incomplete": states["incomplete"],
            "evaluable_candidates": evaluable,
            "excluded_incomplete_candidates": states["incomplete"],
            "preservation_rate": states["preserved"] / evaluable if evaluable else None,
            "preservation_rate_95_ci": _wilson_interval(states["preserved"], evaluable),
        },
        "paired_measurements": {
            method: _metric_summary(records, method)
            for method in sorted(MEASUREMENT_METHODS)
            if any(record["measurements"].get(method) for record in records)
        },
        "limitations": [
            "Evaluation records must be selected and labeled independently of the measured outcomes.",
            "The Wilson interval treats candidate records as independent; candidates from one source solution may be correlated.",
            "Four or more paired sizes do not remove host, JVM, or harness noise. Preserve raw reports and rerun on a controlled host.",
            "Python line-event and opcode counts are work proxies and are never reported as wall-clock speedup.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSONL records joined from optimization evidence reports")
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    args = parser.parse_args()
    try:
        report = score(load_records(args.records))
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
