from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_complexity_evaluation import load_gold  # noqa: E402

SCRIPT = Path(__file__).with_name("freeze_reviewed_batch.py")
SPEC = importlib.util.spec_from_file_location("freeze_reviewed_batch", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
freeze_reviewed_batch = MODULE.freeze_reviewed_batch


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> bytes:
    data = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows).encode()
    path.write_bytes(data)
    return data


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    batch = tmp_path / "batch"
    (batch / "sources").mkdir(parents=True)
    source = "def scan(items):\n    return len(items)\n"
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    (batch / "sources" / "case.py").write_bytes(source.encode("utf-8"))
    candidate = {
        "id": "case-001",
        "source": source,
        "source_sha256": source_hash,
        "local_path": "sources/case.py",
        "expected_time": "O(n)",
        "expected_auxiliary_space": "O(1)",
        "expected_time_exact": "O(n)",
        "expected_auxiliary_space_exact": "O(1)",
        "time_rationale": "One scan.",
        "space_rationale": "Uses scalar state.",
        "assumptions": "List length is n.",
        "input_size": "n is the list length.",
        "family": "array",
        "language": "python",
        "partition": "calibration",
        "decision_status": "proposed_pending_owner_confirmation",
        "owner_decision": None,
        "reviewer": None,
    }
    candidate_path = batch / "candidate.jsonl"
    candidate_bytes = _write_jsonl(candidate_path, [candidate])
    manifest = {
        "candidate_file": candidate_path.name,
        "candidate_file_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "case_ids": ["case-001"],
        "source_sha256": {"case-001": source_hash},
        "gold_labels_frozen": False,
        "analyzer_run": False,
    }
    manifest_path = batch / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    decision = {
        "id": "case-001",
        "decision": "approve",
        "expected_time": "O(n)",
        "expected_auxiliary_space": "O(1)",
        "source_sha256": source_hash,
        "reviewer_id": "owner-1",
        "review_date": "2026-10-31",
        "rationale": "Confirmed against the implementation.",
    }
    decisions_path = batch / "decisions.jsonl"
    _write_jsonl(decisions_path, [decision])
    return manifest_path, decisions_path, batch / "gold.jsonl", source_hash


def test_freeze_requires_explicit_approval_and_emits_evaluator_gold(tmp_path: Path) -> None:
    manifest, decisions, output, source_hash = _fixture(tmp_path)
    gold_path, record_path, digest = freeze_reviewed_batch(
        manifest_path=manifest,
        decisions_path=decisions,
        output_path=output,
        reviewer_id="owner-1",
        review_date="2026-10-31",
    )
    parsed = load_gold(gold_path)
    assert parsed["case-001"]["expected_time"] == "O(n)"
    assert parsed["case-001"]["source_sha256"] == source_hash
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["status"] == "human_reviewed_batch_frozen"
    assert record["dataset_gold_labels_frozen"] is False
    assert record["gold_labels_sha256"] == digest


def test_freeze_refuses_pending_decision(tmp_path: Path) -> None:
    manifest, decisions, output, _ = _fixture(tmp_path)
    rows = [json.loads(line) for line in decisions.read_text(encoding="utf-8").splitlines()]
    rows[0]["decision"] = "pending"
    _write_jsonl(decisions, rows)
    with pytest.raises(ValueError, match="only explicit approve"):
        freeze_reviewed_batch(
            manifest_path=manifest, decisions_path=decisions, output_path=output,
            reviewer_id="owner-1", review_date="2026-10-31",
        )
    assert not output.exists()


def test_freeze_refuses_mismatched_hash_and_label(tmp_path: Path) -> None:
    manifest, decisions, output, _ = _fixture(tmp_path)
    rows = [json.loads(line) for line in decisions.read_text(encoding="utf-8").splitlines()]
    rows[0]["expected_time"] = "O(n^2)"
    _write_jsonl(decisions, rows)
    with pytest.raises(ValueError, match="approved time class differs"):
        freeze_reviewed_batch(
            manifest_path=manifest, decisions_path=decisions, output_path=output,
            reviewer_id="owner-1", review_date="2026-10-31",
        )


def test_freeze_refuses_incomplete_decisions_and_overwrite(tmp_path: Path) -> None:
    manifest, decisions, output, _ = _fixture(tmp_path)
    decisions.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no records"):
        freeze_reviewed_batch(
            manifest_path=manifest, decisions_path=decisions, output_path=output,
            reviewer_id="owner-1", review_date="2026-10-31",
        )
    manifest, decisions, output, _ = _fixture(tmp_path / "second")
    output.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        freeze_reviewed_batch(
            manifest_path=manifest, decisions_path=decisions, output_path=output,
            reviewer_id="owner-1", review_date="2026-10-31",
        )
