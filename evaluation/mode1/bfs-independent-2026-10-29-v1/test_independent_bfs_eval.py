from run_independent_bfs_eval import _metrics, _normalize


def _row(
    case_id: str,
    *,
    scorable: bool,
    expected_response: str,
    supported: bool,
    state: str,
    truth_exact: bool,
) -> dict:
    return {
        "id": case_id,
        "complexity_scorable": scorable,
        "expected_analyzer_response": expected_response,
        "supported_pattern_candidate": supported,
        "prediction_state": state,
        "truth_exact": truth_exact,
    }


def test_normalization_only_removes_spacing_and_unknown_detail() -> None:
    assert _normalize("O(R * C)") == "O(R*C)"
    assert _normalize("unknown (unsupported traversal)") == "unknown"
    assert _normalize("O(V^2)") != _normalize("O(V + E)")


def test_metrics_separate_coverage_abstention_and_negative_false_positives() -> None:
    metrics = _metrics([
        _row("supported-hit", scorable=True, expected_response="estimate", supported=True,
             state="estimate", truth_exact=True),
        _row("supported-miss", scorable=True, expected_response="estimate", supported=True,
             state="unknown", truth_exact=False),
        _row("negative-abstain", scorable=True, expected_response="unknown", supported=False,
             state="unknown", truth_exact=False),
        _row("negative-fp", scorable=True, expected_response="unknown", supported=False,
             state="estimate", truth_exact=False),
        _row("unbounded", scorable=False, expected_response="unknown", supported=False,
             state="unknown", truth_exact=False),
    ])

    assert metrics["eligible_scorable"] == 4
    assert metrics["answered"] == 2
    assert metrics["coverage"] == 0.5
    assert metrics["exact_accuracy_among_answered"] == 0.5
    assert metrics["all_case_exact_rate"] == 0.25
    assert metrics["supported_candidates"] == 2
    assert metrics["supported_pattern_coverage"] == 0.5
    assert metrics["expected_unknown_cases"] == 3
    assert metrics["expected_abstention_agreement"] == 2 / 3
    assert metrics["negative_case_false_positives"] == 1
    assert metrics["negative_false_positive_truth_mismatches"] == 1
    assert metrics["non_scorable_cases"] == 1


def test_all_abstentions_keep_accuracy_undefined_and_coverage_zero() -> None:
    metrics = _metrics([
        _row("one", scorable=True, expected_response="estimate", supported=True,
             state="unknown", truth_exact=False),
    ])

    assert metrics["coverage"] == 0
    assert metrics["exact_accuracy_among_answered"] is None
    assert metrics["selective_accuracy"] is None
