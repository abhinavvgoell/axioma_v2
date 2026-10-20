import json

import pytest

from evaluate_detection import _score, load_records


def test_score_reports_recall_false_positives_and_excludes_incomplete_records(tmp_path) -> None:
    records_path = tmp_path / "detection.jsonl"
    entries = [
        {"id": "mutant-killed", "label": "mutant", "passed": 4, "failed": 1, "skipped": 0},
        {"id": "mutant-survived", "label": "mutant", "passed": 5, "failed": 0, "skipped": 0},
        {"id": "mutant-incomplete", "label": "mutant", "passed": 0, "failed": 0, "skipped": 3},
        {"id": "control-flagged", "label": "correct", "passed": 3, "failed": 1, "skipped": 0},
        {"id": "control-clean", "label": "correct", "passed": 4, "failed": 0, "skipped": 0},
        {"id": "control-incomplete", "label": "correct", "passed": 1, "failed": 0, "skipped": 1},
    ]
    records_path.write_text("\n".join(json.dumps(row) for row in entries), encoding="utf-8")

    report = _score(load_records(records_path))

    assert report["records"] == 6
    assert report["scored_mutants"] == 2
    assert report["scored_correct_controls"] == 2
    assert report["mutant_detection_recall"] == 0.5
    assert report["correct_control_false_positive_rate"] == 0.5
    assert report["precision"] == 0.5
    assert report["excluded_incomplete"] == {"correct": 1, "mutant": 1}


def test_load_records_rejects_negative_counts_and_duplicate_ids(tmp_path) -> None:
    records_path = tmp_path / "bad.jsonl"
    record = {"id": "same", "label": "mutant", "passed": 0, "failed": -1, "skipped": 0}
    records_path.write_text(json.dumps(record) + "\n" + json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="failed must be a non-negative integer"):
        load_records(records_path)


def test_score_returns_null_rates_when_a_class_has_no_evaluable_records() -> None:
    report = _score([{"id": "pending", "label": "mutant", "passed": 0, "failed": 0, "skipped": 2}])

    assert report["mutant_detection_recall"] is None
    assert report["correct_control_false_positive_rate"] is None
    assert report["precision"] is None
