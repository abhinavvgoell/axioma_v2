from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("consolidate_reviewed_calibration.py")
SPEC = importlib.util.spec_from_file_location("consolidate_reviewed_calibration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
consolidate_reviewed_calibration = MODULE.consolidate_reviewed_calibration


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> bytes:
    data = b"".join(_json_bytes(row) for row in rows)
    path.write_bytes(data)
    return data


def _fixture(root: Path) -> list[Path]:
    root.mkdir(parents=True)
    record_paths = []
    for batch_index in range(1, 7):
        case_ids = [f"axioma-20261030-broad-{(batch_index - 1) * 5 + offset:03d}" for offset in range(1, 6)]
        candidates = []
        sources = {}
        for case_id in case_ids:
            source = f"def solve_{case_id.replace('-', '_')}():\n    return 1\n"
            source_hash = hashlib.sha256(source.encode()).hexdigest()
            source_path = root / "sources" / f"{case_id}.py"
            source_path.parent.mkdir(exist_ok=True)
            source_path.write_bytes(source.encode("utf-8"))
            sources[case_id] = source_hash
            candidates.append(
                {
                    "id": case_id,
                    "source": source,
                    "source_sha256": source_hash,
                    "local_path": (Path("sources") / f"{case_id}.py").as_posix(),
                    "expected_time": "O(n)",
                    "expected_auxiliary_space": "O(1)",
                    "partition": "calibration",
                }
            )

        packet_name = f"candidates-{batch_index}.jsonl"
        packet_path = root / packet_name
        packet_bytes = _write_jsonl(packet_path, candidates)
        manifest_name = f"manifest-{batch_index}.json"
        manifest = {
            "dataset_id": "calibration-fixture",
            "candidate_file": packet_name,
            "candidate_file_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "case_ids": case_ids,
            "source_sha256": sources,
            "gold_labels_frozen": False,
            "analyzer_run": False,
        }
        manifest_bytes = _json_bytes(manifest)
        (root / manifest_name).write_bytes(manifest_bytes)

        gold_rows = [
            {
                "id": case_id,
                "expected_time": "O(n)",
                "expected_auxiliary_space": "O(1)",
                "expected_time_exact": "O(n)",
                "expected_auxiliary_space_exact": "O(1)",
                "partition": "calibration",
                "reviewer": "project_owner",
                "review_date": "2026-11-02",
                "rationale": "Reviewed against the implementation.",
                "assumptions": "n is input length.",
                "owner_decision": "approve",
                "source_sha256": sources[case_id],
            }
            for case_id in case_ids
        ]
        gold_name = f"gold-{batch_index}.jsonl"
        gold_path = root / gold_name
        gold_bytes = _write_jsonl(gold_path, gold_rows)
        record = {
            "status": "human_reviewed_batch_frozen",
            "partial_batch_only": True,
            "dataset_gold_labels_frozen": False,
            "analyzer_run": False,
            "case_count": 5,
            "case_ids": case_ids,
            "candidate_manifest": manifest_name,
            "candidate_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "candidate_packet": packet_name,
            "candidate_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "gold_labels_file": gold_name,
            "gold_labels_sha256": hashlib.sha256(gold_bytes).hexdigest(),
            "source_sha256": sources,
        }
        record_path = root / f"freeze-{batch_index}.manifest.json"
        record_path.write_bytes(_json_bytes(record))
        record_paths.append(record_path)
    return record_paths


def test_consolidation_freezes_all_verified_batches_deterministically(tmp_path: Path) -> None:
    records = _fixture(tmp_path / "batches")
    output = tmp_path / "gold-reviewed-calibration.jsonl"

    gold_path, manifest_path, digest = consolidate_reviewed_calibration(
        batch_record_paths=records,
        output_path=output,
    )

    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(rows) == 30
    assert len({row["id"] for row in rows}) == 30
    assert [row["id"] for row in rows] == sorted(row["id"] for row in rows)
    assert manifest["dataset_gold_labels_frozen"] is True
    assert manifest["analyzer_run"] is False
    assert manifest["gold_labels_sha256"] == digest


def test_consolidation_requires_six_unique_batches(tmp_path: Path) -> None:
    records = _fixture(tmp_path / "batches")
    with pytest.raises(ValueError, match="exactly six"):
        consolidate_reviewed_calibration(batch_record_paths=records[:5], output_path=tmp_path / "gold.jsonl")


def test_consolidation_rejects_tampered_partial_gold_hash(tmp_path: Path) -> None:
    records = _fixture(tmp_path / "batches")
    record = json.loads(records[0].read_text(encoding="utf-8"))
    (records[0].parent / record["gold_labels_file"]).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="partial gold-label hash mismatch"):
        consolidate_reviewed_calibration(batch_record_paths=records, output_path=tmp_path / "gold.jsonl")
    assert not (tmp_path / "gold.jsonl").exists()
