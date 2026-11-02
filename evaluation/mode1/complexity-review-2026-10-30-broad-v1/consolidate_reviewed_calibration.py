"""Consolidate six owner-reviewed batches into one frozen calibration set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evaluation.mode1.evaluate_complexity import CLASSES, PARTITIONS  # noqa: E402


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{label} line {line_number}: expected an object")
        rows.append(row)
    return rows


def consolidate_reviewed_calibration(
    *, batch_record_paths: list[Path], output_path: Path
) -> tuple[Path, Path, str]:
    if len(batch_record_paths) != 6:
        raise ValueError("exactly six reviewed batch freeze records are required")

    records = [path.resolve() for path in batch_record_paths]
    batch_dir = records[0].parent
    if any(path.parent != batch_dir for path in records):
        raise ValueError("all batch freeze records must be in the same evaluation directory")
    if len(set(records)) != len(records):
        raise ValueError("batch freeze records must be unique")

    gold_rows: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    batch_inputs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    dataset_ids: set[str] = set()

    for record_path in records:
        record_bytes = record_path.read_bytes()
        record = json.loads(record_bytes)
        if (
            record.get("status") != "human_reviewed_batch_frozen"
            or record.get("partial_batch_only") is not True
            or record.get("dataset_gold_labels_frozen") is not False
            or record.get("analyzer_run") is not False
        ):
            raise ValueError(f"{record_path.name}: not an unanalyzed partial-batch freeze record")
        if record.get("case_count") != 5:
            raise ValueError(f"{record_path.name}: each reviewed batch must contain exactly five cases")

        manifest_path = batch_dir / record["candidate_manifest"]
        manifest_bytes = manifest_path.read_bytes()
        if _sha256(manifest_bytes) != record.get("candidate_manifest_sha256"):
            raise ValueError(f"{record_path.name}: candidate manifest hash mismatch")
        manifest = json.loads(manifest_bytes)
        if manifest.get("gold_labels_frozen") is not False or manifest.get("analyzer_run") is not False:
            raise ValueError(f"{manifest_path.name}: candidate manifest must remain unfrozen and unanalyzed")
        dataset_ids.add(manifest.get("dataset_id"))

        packet_path = batch_dir / manifest["candidate_file"]
        packet_bytes = packet_path.read_bytes()
        if (
            manifest.get("candidate_file_sha256") != record.get("candidate_packet_sha256")
            or _sha256(packet_bytes) != manifest.get("candidate_file_sha256")
            or packet_path.name != record.get("candidate_packet")
        ):
            raise ValueError(f"{record_path.name}: candidate packet hash or identity mismatch")
        candidates = _read_jsonl(packet_path, "candidate packet")
        candidate_by_id = {row.get("id"): row for row in candidates}
        if len(candidate_by_id) != 5 or None in candidate_by_id:
            raise ValueError(f"{packet_path.name}: expected five unique candidate IDs")
        if sorted(candidate_by_id) != sorted(manifest.get("case_ids", [])):
            raise ValueError(f"{packet_path.name}: candidate IDs do not match its manifest")

        gold_path = batch_dir / record["gold_labels_file"]
        gold_bytes = gold_path.read_bytes()
        if _sha256(gold_bytes) != record.get("gold_labels_sha256"):
            raise ValueError(f"{record_path.name}: partial gold-label hash mismatch")
        rows = _read_jsonl(gold_path, "partial gold labels")
        gold_by_id = {row.get("id"): row for row in rows}
        expected_ids = set(candidate_by_id)
        if len(gold_by_id) != 5 or None in gold_by_id or set(gold_by_id) != expected_ids:
            raise ValueError(f"{gold_path.name}: gold labels must cover the five candidate IDs exactly")
        if sorted(expected_ids) != sorted(record.get("case_ids", [])):
            raise ValueError(f"{record_path.name}: case IDs do not match its freeze record")

        record_hashes = record.get("source_sha256", {})
        for case_id, candidate in candidate_by_id.items():
            row = gold_by_id[case_id]
            source_hash = candidate.get("source_sha256")
            if (
                source_hash != manifest.get("source_sha256", {}).get(case_id)
                or source_hash != record_hashes.get(case_id)
                or source_hash != row.get("source_sha256")
            ):
                raise ValueError(f"{case_id}: source hash mismatch across artifacts")
            source = candidate.get("source")
            if not isinstance(source, str) or _sha256(source.encode("utf-8")) != source_hash:
                raise ValueError(f"{case_id}: embedded source hash mismatch")
            source_path = (batch_dir / candidate["local_path"]).resolve()
            if batch_dir not in source_path.parents or source_path.read_bytes() != source.encode("utf-8"):
                raise ValueError(f"{case_id}: local pinned source mismatch or path escapes the batch")
            if row.get("owner_decision") not in {"approve", "revise"}:
                raise ValueError(f"{case_id}: owner decision is missing")
            if row.get("partition") != "calibration" or row.get("partition") not in PARTITIONS:
                raise ValueError(f"{case_id}: all cases must belong to the calibration partition")
            if row.get("expected_time") not in CLASSES or row.get("expected_auxiliary_space") not in CLASSES:
                raise ValueError(f"{case_id}: unsupported time or auxiliary-space scoring class")
            for field in ("reviewer", "review_date", "rationale", "assumptions", "expected_time_exact", "expected_auxiliary_space_exact"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"{case_id}: {field} is required in a frozen reviewed label")
            if case_id in seen_ids:
                raise ValueError(f"{case_id}: duplicate case across batches")
            seen_ids.add(case_id)
            gold_rows.append(row)
            source_hashes[case_id] = source_hash

        batch_inputs.append(
            {
                "freeze_record": record_path.name,
                "freeze_record_sha256": _sha256(record_bytes),
                "candidate_manifest": manifest_path.name,
                "candidate_manifest_sha256": _sha256(manifest_bytes),
                "candidate_packet": packet_path.name,
                "candidate_packet_sha256": _sha256(packet_bytes),
                "partial_gold_labels": gold_path.name,
                "partial_gold_labels_sha256": _sha256(gold_bytes),
                "case_ids": sorted(expected_ids),
            }
        )

    if len(dataset_ids) != 1 or None in dataset_ids:
        raise ValueError("all batch manifests must identify the same calibration dataset")
    if len(gold_rows) != 30 or len(seen_ids) != 30:
        raise ValueError("the consolidated calibration set must contain 30 unique reviewed cases")

    gold_rows.sort(key=lambda row: row["id"])
    gold_bytes = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in gold_rows
    ).encode("utf-8")
    output_path = output_path.resolve()
    manifest_path = output_path.with_suffix(".manifest.json")
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite an existing consolidated gold artifact or manifest")

    freeze_manifest = {
        "status": "human_reviewed_calibration_frozen",
        "dataset_id": next(iter(dataset_ids)),
        "partition": "calibration",
        "case_count": len(gold_rows),
        "case_ids": [row["id"] for row in gold_rows],
        "dataset_gold_labels_frozen": True,
        "analyzer_run": False,
        "gold_labels_file": output_path.name,
        "gold_labels_sha256": _sha256(gold_bytes),
        "source_sha256": source_hashes,
        "reviewed_batches": batch_inputs,
    }
    output_path.write_bytes(gold_bytes)
    manifest_bytes = (json.dumps(freeze_manifest, indent=2, ensure_ascii=False) + "\n").replace("\n", "\r\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    return output_path, manifest_path, freeze_manifest["gold_labels_sha256"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_freeze_records", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        gold_path, manifest_path, digest = consolidate_reviewed_calibration(
            batch_record_paths=args.batch_freeze_records,
            output_path=args.output,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"gold_labels": str(gold_path), "manifest": str(manifest_path), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
