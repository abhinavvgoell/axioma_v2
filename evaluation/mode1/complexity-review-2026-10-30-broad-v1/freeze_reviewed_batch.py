"""Freeze an explicitly owner-reviewed candidate batch as evaluator gold JSONL."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from evaluation.mode1.evaluate_complexity import CLASSES, PARTITIONS  # noqa: E402


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{label} line {line_number}: expected a JSON object")
        rows.append(row)
    if not rows:
        raise ValueError(f"{label} file contains no records")
    return rows


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze_reviewed_batch(
    *,
    manifest_path: Path,
    decisions_path: Path,
    output_path: Path,
    reviewer_id: str,
    review_date: str,
) -> tuple[Path, Path, str]:
    if not reviewer_id.strip():
        raise ValueError("reviewer_id must not be empty")
    try:
        date.fromisoformat(review_date)
    except ValueError as exc:
        raise ValueError("review_date must be an ISO date (YYYY-MM-DD)") from exc

    manifest_path = manifest_path.resolve()
    batch_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("gold_labels_frozen") or manifest.get("analyzer_run"):
        raise ValueError("candidate manifest must remain unfrozen and unanalyzed")

    packet_path = batch_dir / manifest["candidate_file"]
    packet_bytes = packet_path.read_bytes()
    if _sha256(packet_bytes) != manifest.get("candidate_file_sha256"):
        raise ValueError("candidate packet SHA-256 does not match its manifest")
    candidates = _read_jsonl(packet_path, "candidate")
    decisions = _read_jsonl(decisions_path.resolve(), "review decisions")

    candidate_by_id = {row.get("id"): row for row in candidates}
    decision_by_id = {row.get("id"): row for row in decisions}
    if len(candidate_by_id) != len(candidates) or None in candidate_by_id:
        raise ValueError("candidate IDs must be present and unique")
    if len(decision_by_id) != len(decisions) or None in decision_by_id:
        raise ValueError("review decision IDs must be present and unique")
    if set(candidate_by_id) != set(decision_by_id):
        raise ValueError("review decisions must cover exactly the candidate case IDs")
    if sorted(candidate_by_id) != sorted(manifest.get("case_ids", [])):
        raise ValueError("candidate IDs do not match the manifest")

    gold_rows = []
    source_hashes = {}
    review_flags = []
    for case_id, candidate in candidate_by_id.items():
        decision = decision_by_id[case_id]
        if candidate.get("decision_status") != "proposed_pending_owner_confirmation":
            raise ValueError(f"{case_id}: candidate is not pending owner confirmation")
        if candidate.get("owner_decision") is not None or candidate.get("reviewer") is not None:
            raise ValueError(f"{case_id}: candidate already contains review fields")
        decision_status = decision.get("decision")
        if decision_status not in {"approve", "revise"}:
            raise ValueError(f"{case_id}: only explicit approve or revise decisions can be frozen")
        if decision.get("reviewer_id") != reviewer_id.strip():
            raise ValueError(f"{case_id}: reviewer_id does not match the freeze metadata")
        if decision.get("review_date") != review_date:
            raise ValueError(f"{case_id}: review_date does not match the freeze metadata")
        source_hash = candidate.get("source_sha256")
        embedded_source = candidate.get("source")
        if not isinstance(embedded_source, str) or _sha256(embedded_source.encode("utf-8")) != source_hash:
            raise ValueError(f"{case_id}: embedded source hash mismatch")
        if decision.get("source_sha256") != source_hash:
            raise ValueError(f"{case_id}: reviewer source hash does not match candidate")
        if manifest.get("source_sha256", {}).get(case_id) != source_hash:
            raise ValueError(f"{case_id}: source hash does not match manifest")
        source_path = (batch_dir / candidate["local_path"]).resolve()
        if batch_dir.resolve() not in source_path.parents:
            raise ValueError(f"{case_id}: source snapshot path escapes the batch directory")
        if source_path.read_bytes() != embedded_source.encode("utf-8"):
            raise ValueError(f"{case_id}: local source snapshot hash mismatch")
        if decision.get("rationale") is None or not str(decision["rationale"]).strip():
            raise ValueError(f"{case_id}: reviewer rationale is required")
        labels = {
            "expected_time": decision.get("expected_time"),
            "expected_auxiliary_space": decision.get("expected_auxiliary_space"),
        }
        for field, value in labels.items():
            if value not in CLASSES:
                raise ValueError(f"{case_id}: {field} is not an evaluator-supported class")
        if decision_status == "approve":
            for field, value in labels.items():
                if value != candidate.get(field):
                    dimension = "time" if field == "expected_time" else "space"
                    raise ValueError(f"{case_id}: approved {dimension} class differs from the proposed scoring class")
            exact_labels = {
                "expected_time_exact": candidate["expected_time_exact"],
                "expected_auxiliary_space_exact": candidate["expected_auxiliary_space_exact"],
            }
            assumptions = candidate["assumptions"]
        else:
            exact_labels = {
                "expected_time_exact": decision.get("expected_time_exact"),
                "expected_auxiliary_space_exact": decision.get("expected_auxiliary_space_exact"),
            }
            if any(not isinstance(value, str) or not value.strip() for value in exact_labels.values()):
                raise ValueError(f"{case_id}: revised labels require both exact complexity expressions")
            assumptions = decision.get("assumptions")
            if not isinstance(assumptions, str) or not assumptions.strip():
                raise ValueError(f"{case_id}: revised labels require updated input assumptions")
        for field, value in exact_labels.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{case_id}: {field} must be a non-empty expression")
        partition = candidate.get("partition")
        if partition not in PARTITIONS:
            raise ValueError(f"{case_id}: partition is not supported by the evaluator")

        rationale_override = decision.get("rationale_override")
        if rationale_override is not None:
            if not isinstance(rationale_override, str) or not rationale_override.strip():
                raise ValueError(f"{case_id}: rationale_override must be a non-empty string")
            rationale = rationale_override.strip()
        else:
            rationale = (
                f"Time: {candidate['time_rationale']} Auxiliary space: {candidate['space_rationale']} "
                f"Owner review: {decision['rationale'].strip()}"
                if decision_status == "approve"
                else f"Owner-reviewed time and auxiliary-space rationale: {decision['rationale'].strip()}"
            )
        gold_rows.append(
            {
                "id": case_id,
                "expected_time": labels["expected_time"],
                "expected_auxiliary_space": labels["expected_auxiliary_space"],
                "partition": partition,
                "reviewer": reviewer_id.strip(),
                "review_date": review_date,
                "rationale": rationale,
                "family": candidate["family"],
                "language": candidate["language"],
                "source_sha256": source_hash,
                "expected_time_exact": exact_labels["expected_time_exact"],
                "expected_auxiliary_space_exact": exact_labels["expected_auxiliary_space_exact"],
                "assumptions": assumptions,
                "input_size": candidate["input_size"],
                "owner_decision": decision_status,
            }
        )
        source_hashes[case_id] = source_hash
        flags = decision.get("review_flags", [])
        if not isinstance(flags, list) or any(not isinstance(flag, str) or not flag.strip() for flag in flags):
            raise ValueError(f"{case_id}: review_flags must be a list of non-empty strings")
        review_flags.extend({"case_id": case_id, "flag": flag.strip()} for flag in flags)

    gold_bytes = (
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for row in gold_rows)
    ).encode("utf-8")
    output_path = output_path.resolve()
    record_path = output_path.with_suffix(".manifest.json")
    if output_path.exists() or record_path.exists():
        raise FileExistsError("refusing to overwrite an existing gold artifact or freeze record")
    decisions_path = decisions_path.resolve()
    freeze_record = {
        "status": "human_reviewed_batch_frozen",
        "dataset_gold_labels_frozen": False,
        "partial_batch_only": True,
        "reviewer_id": reviewer_id.strip(),
        "review_date": review_date,
        "case_count": len(gold_rows),
        "case_ids": sorted(candidate_by_id),
        "candidate_manifest": manifest_path.name,
        "candidate_manifest_sha256": _sha256(manifest_path.read_bytes()),
        "candidate_packet": packet_path.name,
        "candidate_packet_sha256": _sha256(packet_bytes),
        "review_decisions_sha256": _sha256(decisions_path.read_bytes()),
        "gold_labels_file": output_path.name,
        "gold_labels_sha256": _sha256(gold_bytes),
        "source_sha256": source_hashes,
        "review_flags": review_flags,
        "analyzer_run": False,
    }
    output_path.write_bytes(gold_bytes)
    record_bytes = (json.dumps(freeze_record, indent=2, ensure_ascii=False) + "\n").replace("\n", "\r\n").encode("utf-8")
    record_path.write_bytes(record_bytes)
    return output_path, record_path, freeze_record["gold_labels_sha256"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="candidate manifest for a pending batch")
    parser.add_argument("review_decisions", type=Path, help="owner decision JSONL, one explicit decision per case")
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--review-date", required=True, help="ISO date YYYY-MM-DD")
    parser.add_argument("--output", required=True, type=Path, help="new gold JSONL path; existing files are never overwritten")
    args = parser.parse_args()
    try:
        output, record, digest = freeze_reviewed_batch(
            manifest_path=args.manifest,
            decisions_path=args.review_decisions,
            output_path=args.output,
            reviewer_id=args.reviewer_id,
            review_date=args.review_date,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"gold_labels": str(output), "freeze_record": str(record), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
