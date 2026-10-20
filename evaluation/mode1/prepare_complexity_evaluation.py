"""Join frozen human complexity labels with Axioma predictions and provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from evaluate_complexity import CLASSES, CONFIDENCE, PARTITIONS

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label} line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{label} line {line_number}: each row must be a JSON object")
            records.append(record)
    if not records:
        raise ValueError(f"{label} file contains no records")
    return records


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    gold: dict[str, dict[str, Any]] = {}
    for line_number, record in enumerate(_read_jsonl(path, "gold"), start=1):
        solution_id = record.get("id")
        if not isinstance(solution_id, str) or not solution_id.strip():
            raise ValueError(f"gold line {line_number}: id must be a non-empty string")
        if solution_id in gold:
            raise ValueError(f"gold line {line_number}: duplicate solution id {solution_id!r}")
        if record.get("expected") not in CLASSES:
            raise ValueError(f"gold line {line_number}: expected must be a supported complexity class")
        partition = record.get("partition")
        if not isinstance(partition, str) or partition not in PARTITIONS:
            raise ValueError(f"gold line {line_number}: partition must be calibration or evaluation")
        for field in ("reviewer", "rationale"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"gold line {line_number}: {field} must be a non-empty string")
        if not isinstance(record.get("source_sha256"), str) or not _SHA256.fullmatch(
            record["source_sha256"]
        ):
            raise ValueError(f"gold line {line_number}: source_sha256 must be a lowercase SHA-256 digest")
        gold[solution_id] = record
    return gold


def load_predictions(path: Path, gold: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    predicted_ids: set[str] = set()
    for line_number, record in enumerate(_read_jsonl(path, "predictions"), start=1):
        solution_id = record.get("id")
        method = record.get("method")
        if not isinstance(solution_id, str) or not solution_id.strip():
            raise ValueError(f"predictions line {line_number}: id must be a non-empty string")
        if solution_id not in gold:
            raise ValueError(f"predictions line {line_number}: unknown solution id {solution_id!r}")
        if not isinstance(method, str) or not method.strip():
            raise ValueError(f"predictions line {line_number}: method must be a non-empty string")
        key = (solution_id, method)
        if key in seen:
            raise ValueError(f"predictions line {line_number}: duplicate id and method")
        seen.add(key)
        predicted_ids.add(solution_id)
        if record.get("predicted") not in CLASSES:
            raise ValueError(f"predictions line {line_number}: predicted must be a supported complexity class")
        confidence = record.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, str) or confidence not in CONFIDENCE
        ):
            raise ValueError(f"predictions line {line_number}: confidence must be high, medium, or low")
        report_hash = record.get("report_sha256")
        if not isinstance(report_hash, str) or not _SHA256.fullmatch(report_hash):
            raise ValueError(f"predictions line {line_number}: report_sha256 must be a lowercase SHA-256 digest")
        predictions.append(record)
    missing = sorted(set(gold) - predicted_ids)
    if missing:
        raise ValueError(f"no Axioma prediction exists for solution IDs: {', '.join(missing[:10])}")
    return predictions


def combine(gold: dict[str, dict[str, Any]], predictions: list[dict[str, Any]], gold_hash: str, predictions_hash: str) -> list[dict[str, Any]]:
    joined = []
    for prediction in predictions:
        label = gold[prediction["id"]]
        joined.append({
            "id": prediction["id"],
            "method": prediction["method"],
            "expected": label["expected"],
            "predicted": prediction["predicted"],
            "confidence": prediction.get("confidence"),
            "partition": label["partition"],
            "source_sha256": label["source_sha256"],
            "reviewer": label["reviewer"],
            "rationale": label["rationale"],
            "report_sha256": prediction["report_sha256"],
            "gold_file_sha256": gold_hash,
            "predictions_file_sha256": predictions_hash,
        })
    return sorted(joined, key=lambda item: (item["id"], item["method"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", type=Path, help="frozen, independently reviewed labels in JSONL")
    parser.add_argument("predictions", type=Path, help="Axioma method outputs joined to saved report hashes")
    parser.add_argument("--output", type=Path, help="write the joined evaluator JSONL to this path")
    args = parser.parse_args()
    try:
        gold = load_gold(args.gold)
        predictions = load_predictions(args.predictions, gold)
        records = combine(
            gold,
            predictions,
            hashlib.sha256(args.gold.read_bytes()).hexdigest(),
            hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
