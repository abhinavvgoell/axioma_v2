import json

import pytest

from evaluate_complexity import _score, load_records


def test_score_reports_exact_within_one_method_and_confidence_metrics(tmp_path) -> None:
    records_path = tmp_path / "gold.jsonl"
    records_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "id": "py-1",
                    "method": "static",
                    "expected": "O(n)",
                    "predicted": "O(n)",
                    "confidence": "low",
                },
                {
                    "id": "py-2",
                    "method": "dynamic",
                    "expected": "O(n^2)",
                    "predicted": "O(n log n)",
                    "confidence": "low",
                },
            )
        ),
        encoding="utf-8",
    )

    report = _score(load_records(records_path))

    assert report["n"] == 2
    assert report["exact_accuracy"] == 0.5
    assert report["within_one_class_accuracy"] == 1.0
    assert report["by_method"]["static"]["exact_accuracy"] == 1.0
    assert report["by_method"]["dynamic"]["within_one_class_accuracy"] == 1.0
    assert report["by_confidence"]["low"]["n"] == 2
    assert "not calibrated" in report["confidence_note"]


def test_load_records_rejects_duplicate_id_and_method(tmp_path) -> None:
    records_path = tmp_path / "duplicate.jsonl"
    record = {
        "id": "case-1",
        "method": "static",
        "expected": "O(n)",
        "predicted": "O(n)",
    }
    records_path.write_text(json.dumps(record) + "\n" + json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate id and method"):
        load_records(records_path)


def test_load_records_rejects_unknown_complexity_class(tmp_path) -> None:
    records_path = tmp_path / "unknown.jsonl"
    records_path.write_text(
        json.dumps({"id": "case-1", "method": "static", "expected": "O(n)", "predicted": "O(n^4)"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="predicted must be one of"):
        load_records(records_path)
