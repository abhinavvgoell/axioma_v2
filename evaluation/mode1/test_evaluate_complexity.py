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
    assert report["distinct_solutions"] == 2
    assert report["minimum_distinct_solutions"] == 50
    assert report["minimum_solution_count_met"] is False
    assert report["evaluation_readiness"] == "below_minimum"
    assert report["exact_accuracy"] == 0.5
    assert report["exact_accuracy_95_ci"]["lower"] < 0.5
    assert report["exact_accuracy_95_ci"]["upper"] > 0.5
    assert report["within_one_class_accuracy"] == 1.0
    assert report["by_method"]["static"]["exact_accuracy"] == 1.0
    assert report["by_method"]["dynamic"]["within_one_class_accuracy"] == 1.0
    assert report["by_confidence"]["low"]["n"] == 2
    assert "Without separate partitions" in report["confidence_note"]


def test_unknown_counts_as_abstention_and_reports_coverage_and_selective_accuracy() -> None:
    records = [
        {
            "id": "correct",
            "method": "static",
            "expected": "O(n)",
            "predicted": "O(n)",
            "confidence": "low",
            "partition": "evaluation",
        },
        {
            "id": "abstained",
            "method": "static",
            "expected": "O(n^2)",
            "predicted": "unknown",
            "confidence": "low",
            "partition": "evaluation",
        },
        {
            "id": "wrong",
            "method": "static",
            "expected": "O(n^2)",
            "predicted": "O(n)",
            "confidence": "low",
            "partition": "evaluation",
        },
    ]

    report = _score(records)

    assert report["answered"] == 2
    assert report["abstentions"] == 1
    assert report["coverage"] == pytest.approx(2 / 3)
    assert report["exact_accuracy"] == pytest.approx(1 / 3)
    assert report["selective_exact_accuracy"] == 0.5
    assert report["selective_within_one_class_accuracy"] == 0.5
    assert report["by_method"]["static"]["abstentions"] == 1
    assert report["by_confidence"]["low"]["n"] == 2
    assert report["confusion_matrix"]["O(n^2)"]["unknown"] == 1


def test_selective_accuracy_is_unavailable_when_every_record_abstains() -> None:
    report = _score(
        [
            {
                "id": "abstained",
                "method": "static",
                "expected": "O(n)",
                "predicted": "unknown",
                "partition": "evaluation",
            }
        ]
    )

    assert report["coverage"] == 0
    assert report["selective_exact_accuracy"] is None
    assert report["selective_exact_accuracy_95_ci"] is None


def test_held_out_confidence_mapping_uses_separate_solution_partitions() -> None:
    records = [
        {
            "id": "cal-1",
            "method": "static",
            "expected": "O(n)",
            "predicted": "O(n)",
            "confidence": "high",
            "partition": "calibration",
        },
        {
            "id": "cal-2",
            "method": "static",
            "expected": "O(n)",
            "predicted": "O(n^2)",
            "confidence": "high",
            "partition": "calibration",
        },
        {
            "id": "eval-1",
            "method": "static",
            "expected": "O(n)",
            "predicted": "O(n)",
            "confidence": "high",
            "partition": "evaluation",
        },
        {
            "id": "eval-2",
            "method": "static",
            "expected": "O(n)",
            "predicted": "O(n^2)",
            "confidence": "high",
            "partition": "evaluation",
        },
    ]

    report = _score(records)

    calibration = report["held_out_confidence_calibration"]
    assert calibration["available"] is True
    assert calibration["mapping_by_method"]["static"]["high"]["empirical_accuracy"] == 0.5
    assert calibration["per_method_confidence"]["static"]["high"]["evaluation_accuracy"] == 0.5
    assert calibration["brier_score"] == 0.25
    assert calibration["expected_calibration_error"] == 0.0


def test_minimum_dataset_gate_counts_distinct_solutions_not_method_rows() -> None:
    records = [
        {
            "id": f"solution-{solution}",
            "method": method,
            "expected": "O(n)",
            "predicted": "O(n)",
            "partition": "evaluation",
        }
        for solution in range(50)
        for method in ("static", "measured")
    ]

    report = _score(records)

    assert report["n"] == 100
    assert report["distinct_solutions"] == 50
    assert report["minimum_solution_count_met"] is True
    assert report["evaluation_readiness"] == "minimum_met"


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


def test_load_records_rejects_solution_leakage_across_partitions(tmp_path) -> None:
    records_path = tmp_path / "leakage.jsonl"
    records_path.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "id": "same-solution",
                    "method": "static",
                    "expected": "O(n)",
                    "predicted": "O(n)",
                    "partition": "calibration",
                },
                {
                    "id": "same-solution",
                    "method": "dynamic",
                    "expected": "O(n)",
                    "predicted": "O(n)",
                    "partition": "evaluation",
                },
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="same partition"):
        load_records(records_path)
