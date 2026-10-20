import json

import pytest

from evaluate_optimization import load_records, score


def _record(identifier, *, passed=4, failed=0, skipped=0, checked=4, points=None):
    return {
        "id": identifier,
        "checks": {
            "requested": 4,
            "checked": checked,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "measurements": {
            "jvm_reflective_wall_time": points or [
                {"size": size, "before": 1000 * size, "after": 800 * size}
                for size in (10, 20, 40, 80)
            ]
        },
    }


def test_scores_only_equivalent_candidates_and_requires_wins_at_all_sizes() -> None:
    records = [
        _record("faster"),
        _record(
            "mixed",
            points=[
                {"size": 10, "before": 1000, "after": 900},
                {"size": 20, "before": 2000, "after": 2100},
                {"size": 40, "before": 4000, "after": 3500},
                {"size": 80, "before": 8000, "after": 7000},
            ],
        ),
        _record("incorrect", passed=3, failed=1),
    ]

    report = score(records)

    wall_time = report["paired_measurements"]["jvm_reflective_wall_time"]
    assert report["equivalence"]["preserved"] == 2
    assert report["equivalence"]["failed"] == 1
    assert wall_time["eligible_candidates"] == 2
    assert wall_time["improved_at_every_size"] == 1
    assert len(wall_time["geometric_mean_speedup_by_candidate"]) == 2


def test_incomplete_equivalence_is_excluded_from_preservation_denominator() -> None:
    report = score([_record("complete"), _record("incomplete", checked=3, passed=3)])

    assert report["equivalence"]["preserved"] == 1
    assert report["equivalence"]["excluded_incomplete_candidates"] == 1
    assert report["equivalence"]["evaluable_candidates"] == 1
    assert report["equivalence"]["preservation_rate"] == 1.0


def test_python_work_counts_are_not_labeled_as_speedup() -> None:
    record = _record("python")
    record["measurements"] = {
        "executed_cpython_opcode_events": [
            {"size": size, "before": size * 20, "after": size * 10}
            for size in (10, 20, 40, 80)
        ]
    }

    report = score([record])
    metric = report["paired_measurements"]["executed_cpython_opcode_events"]

    assert metric["improved_at_every_size"] == 1
    assert "not wall-clock speedup" in metric["interpretation"]
    assert "geometric_mean_speedup_by_candidate" not in metric


def test_load_records_rejects_inconsistent_counts(tmp_path) -> None:
    path = tmp_path / "optimization.jsonl"
    record = _record("bad", passed=3, failed=0, checked=4)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"passed \+ failed \+ skipped must equal checked"):
        load_records(path)


def test_load_records_rejects_non_increasing_sizes(tmp_path) -> None:
    path = tmp_path / "optimization.jsonl"
    record = _record("bad", points=[
        {"size": 10, "before": 100, "after": 90},
        {"size": 20, "before": 200, "after": 180},
        {"size": 20, "before": 400, "after": 360},
        {"size": 80, "before": 800, "after": 720},
    ])
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must increase and be unique"):
        load_records(path)
