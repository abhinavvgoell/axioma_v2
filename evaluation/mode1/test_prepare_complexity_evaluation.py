import hashlib
import json

import pytest

from prepare_complexity_evaluation import combine, load_gold, load_predictions


def _write_jsonl(path, records) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_join_keeps_review_and_report_provenance(tmp_path) -> None:
    source_hash = "a" * 64
    report_hash = "b" * 64
    gold_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    gold_records = [
        {
            "id": "case-1",
            "expected": "O(n)",
            "partition": "calibration",
            "reviewer": "reviewer-1",
            "rationale": "One pass over the input.",
            "source_sha256": source_hash,
        }
    ]
    prediction_records = [
        {
            "id": "case-1",
            "method": "static_ast_loop_depth",
            "predicted": "O(n)",
            "confidence": "medium",
            "report_sha256": report_hash,
        }
    ]
    _write_jsonl(gold_path, gold_records)
    _write_jsonl(prediction_path, prediction_records)

    joined = combine(
        load_gold(gold_path),
        load_predictions(prediction_path, load_gold(gold_path)),
        hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
    )

    assert joined == [
        {
            "id": "case-1",
            "method": "static_ast_loop_depth",
            "expected": "O(n)",
            "predicted": "O(n)",
            "confidence": "medium",
            "partition": "calibration",
            "source_sha256": source_hash,
            "reviewer": "reviewer-1",
            "rationale": "One pass over the input.",
            "report_sha256": report_hash,
            "gold_file_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
            "predictions_file_sha256": hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
        }
    ]


def test_predictions_are_sorted_deterministically(tmp_path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    _write_jsonl(
        gold_path,
        [
            {
                "id": f"case-{n}",
                "expected": "O(n)",
                "partition": "evaluation",
                "reviewer": "reviewer-1",
                "rationale": "Reviewed control.",
                "source_sha256": "a" * 64,
            }
            for n in (2, 1)
        ],
    )
    gold = load_gold(gold_path)
    _write_jsonl(
        prediction_path,
        [
            {
                "id": solution_id,
                "method": method,
                "predicted": "O(n)",
                "report_sha256": "b" * 64,
            }
            for solution_id, method in (("case-2", "z-method"), ("case-1", "static"), ("case-1", "measured"))
        ],
    )

    joined = combine(gold, load_predictions(prediction_path, gold), "c" * 64, "d" * 64)

    assert [(row["id"], row["method"]) for row in joined] == [
        ("case-1", "measured"),
        ("case-1", "static"),
        ("case-2", "z-method"),
    ]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda row: row.update(id="unknown"), "unknown solution id"),
        (lambda row: row.update(report_sha256="not-a-hash"), "report_sha256"),
        (lambda row: row.update(confidence=[]), "confidence must be high, medium, or low"),
    ],
)
def test_predictions_reject_invalid_or_unknown_rows(tmp_path, mutate, message) -> None:
    gold_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    _write_jsonl(
        gold_path,
        [
            {
                "id": "case-1",
                "expected": "O(n)",
                "partition": "evaluation",
                "reviewer": "reviewer-1",
                "rationale": "Reviewed control.",
                "source_sha256": "a" * 64,
            }
        ],
    )
    record = {
        "id": "case-1",
        "method": "static",
        "predicted": "O(n)",
        "confidence": "high",
        "report_sha256": "b" * 64,
    }
    mutate(record)
    _write_jsonl(prediction_path, [record])

    with pytest.raises(ValueError, match=message):
        load_predictions(prediction_path, load_gold(gold_path))


def test_predictions_must_cover_every_gold_solution(tmp_path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    prediction_path = tmp_path / "predictions.jsonl"
    gold = [
        {
            "id": solution_id,
            "expected": "O(n)",
            "partition": "evaluation",
            "reviewer": "reviewer-1",
            "rationale": "Reviewed control.",
            "source_sha256": "a" * 64,
        }
        for solution_id in ("case-1", "case-2")
    ]
    _write_jsonl(gold_path, gold)
    _write_jsonl(
        prediction_path,
        [
            {
                "id": "case-1",
                "method": "static",
                "predicted": "O(n)",
                "report_sha256": "b" * 64,
            }
        ],
    )

    with pytest.raises(ValueError, match="no Axioma prediction exists"):
        load_predictions(prediction_path, load_gold(gold_path))


def test_gold_rejects_duplicate_solution_ids(tmp_path) -> None:
    path = tmp_path / "gold.jsonl"
    record = {
        "id": "case-1",
        "expected": "O(n)",
        "partition": "evaluation",
        "reviewer": "reviewer-1",
        "rationale": "Reviewed control.",
        "source_sha256": "a" * 64,
    }
    _write_jsonl(path, [record, record])

    with pytest.raises(ValueError, match="duplicate solution id"):
        load_gold(path)
