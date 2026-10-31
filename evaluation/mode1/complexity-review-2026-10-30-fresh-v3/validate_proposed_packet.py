"""Validate integrity and pending-review state for the external five-case packet."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CLASSES = {"O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"}
ROOT = Path(__file__).resolve().parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _python_entrypoint(source: str, name: str) -> str:
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    segment = ast.get_source_segment(source, function)
    if segment is None:
        raise ValueError(f"could not extract Python entrypoint {name}")
    return segment.rstrip()


def validate(directory: Path = ROOT) -> dict[str, Any]:
    packet_path = directory / "review-packet-v1.jsonl"
    manifest_path = directory / "manifest-v1.json"
    review_path = directory / "review-sheet-v1-with-source.md"
    space_path = directory / "space-review-v1.jsonl"
    space_manifest_path = directory / "space-review-manifest-v1.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    space_manifest = json.loads(space_manifest_path.read_text(encoding="utf-8"))
    packet_hash = _sha256(packet_path)
    if packet_hash != manifest["case_file_sha256"]:
        raise ValueError("time review packet hash does not match manifest")
    if packet_hash != space_manifest["parent_packet_sha256"]:
        raise ValueError("space review manifest points to a different parent packet")
    if _sha256(space_path) != space_manifest["artifact_sha256"]:
        raise ValueError("space review artifact hash does not match manifest")
    if manifest["gold_labels_frozen"] or manifest["analyzer_run"]:
        raise ValueError("proposed packet must remain unfrozen and unanalyzed")
    if space_manifest["gold_labels_frozen"] or space_manifest["analyzer_run"]:
        raise ValueError("space review must remain unfrozen and unanalyzed")

    cases = _jsonl(packet_path)
    space_labels = _jsonl(space_path)
    case_ids = [case["id"] for case in cases]
    if len(cases) != manifest["case_count"] or len(set(case_ids)) != len(case_ids):
        raise ValueError("time packet case count or IDs are invalid")
    if len(space_labels) != len(case_ids) or {row["id"] for row in space_labels} != set(case_ids):
        raise ValueError("space labels do not cover the same unique cases")
    if set(space_manifest["source_sha256"]) != set(case_ids):
        raise ValueError("space manifest source IDs do not match the packet")

    space_by_id = {row["id"]: row for row in space_labels}
    review_text = review_path.read_text(encoding="utf-8")
    code_blocks = [
        block.replace("\r\n", "\n").rstrip()
        for block in re.findall(r"```(?:python|java)\n(.*?)\n```", review_text, re.DOTALL)
    ]
    for case in cases:
        case_id = case["id"]
        source_path = (directory / case["local_path"]).resolve()
        if not source_path.is_relative_to((directory / "sources").resolve()):
            raise ValueError(f"source path escapes packet directory for {case_id}")
        source_hash = _sha256(source_path)
        if source_hash != case["source_sha256"]:
            raise ValueError(f"source snapshot hash mismatch for {case_id}")
        if source_hash != manifest["source_sha256"].get(case_id):
            raise ValueError(f"time manifest source hash mismatch for {case_id}")
        if source_hash != space_manifest["source_sha256"].get(case_id):
            raise ValueError(f"space manifest source hash mismatch for {case_id}")
        if case.get("decision_status") != "proposed_pending_owner_confirmation" or case.get("owner_decision") is not None:
            raise ValueError(f"time label is not pending owner confirmation for {case_id}")
        if case.get("expected") not in CLASSES:
            raise ValueError(f"unsupported time label for {case_id}")
        space = space_by_id[case_id]
        if space.get("dimension") != "auxiliary_space":
            raise ValueError(f"missing auxiliary-space dimension for {case_id}")
        if space.get("decision_status") != "proposed_pending_owner_confirmation" or space.get("owner_decision") is not None:
            raise ValueError(f"space label is not pending owner confirmation for {case_id}")
        if space.get("expected_scoring_class") not in CLASSES:
            raise ValueError(f"unsupported auxiliary-space scoring class for {case_id}")
        if space.get("source_sha256") != source_hash:
            raise ValueError(f"space label source hash mismatch for {case_id}")
        if case_id not in review_text:
            raise ValueError(f"review sheet omits {case_id}")

        source = source_path.read_text(encoding="utf-8")
        if case["language"] == "python":
            snippet = _python_entrypoint(source, case["entrypoint"])
        else:
            snippet = source.replace("\r\n", "\n").rstrip()
        if snippet not in code_blocks:
            raise ValueError(f"review sheet source snippet does not match snapshot for {case_id}")

    return {
        "case_count": len(cases),
        "time_packet_sha256": packet_hash,
        "space_packet_sha256": _sha256(space_path),
        "source_hashes_match": True,
        "review_status": "proposed_pending_owner_confirmation",
        "analyzer_run": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
