from pathlib import Path

import pytest

from run_reviewed_packet_04 import _normalized_estimate, _write_new, score_records


def _record(case_id: str, expected: str, predicted: str) -> dict:
    return {
        "id": case_id,
        "expected": expected,
        "predicted": predicted,
        "family": "test_family",
        "language": "python",
        "ambiguous": False,
    }


def test_dimension_metrics_keep_abstentions_in_coverage_denominator() -> None:
    report = score_records(
        [
            _record("one", "O(n)", "O(n)"),
            _record("two", "O(n^2)", "unknown"),
        ]
    )

    assert report["eligible"] == 2
    assert report["answered"] == 1
    assert report["abstentions"] == 1
    assert report["coverage"] == 0.5
    assert report["exact_accuracy_among_answered"] == 1.0
    assert report["conservative_accuracy_all_eligible"] == 0.5
    assert report["by_family"]["test_family"]["eligible"] == 2
    assert report["by_language"]["python"]["answered"] == 1


def test_metrics_are_undefined_when_every_prediction_abstains() -> None:
    report = score_records([_record("one", "O(n)", "unknown")])

    assert report["coverage"] == 0.0
    assert report["exact_accuracy_among_answered"] is None
    assert report["conservative_accuracy_all_eligible"] == 0.0


def test_normalization_preserves_abstention_and_supported_classes() -> None:
    assert _normalized_estimate("unknown (recurrence not solved)") == ("unknown", None)
    assert _normalized_estimate("O(n^2)") == ("O(n^2)", None)
    normalized, note = _normalized_estimate("O(n^4)")
    assert normalized == "unknown"
    assert "outside" in note


def test_output_writer_refuses_to_replace_existing_artifact(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    assert _write_new(output, b"first")
    with pytest.raises(FileExistsError):
        _write_new(output, b"second")
    assert output.read_bytes() == b"first"
