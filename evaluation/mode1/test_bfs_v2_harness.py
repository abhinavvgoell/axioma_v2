from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bfs_v2_complexity import compare_complexities, parse_complexity
from evaluate_bfs_v2 import EvaluationInputError, join_and_score
from run_bfs_v2_predictions import (
    PacketInput,
    PredictionInputError,
    read_packet,
    run_cases,
)

ROOT = Path(__file__).resolve().parent
GOLD_PATH = ROOT / "bfs-fresh-v2-review-2026-10-30" / "gold-labels-v2.json"


def _gold_case(
    case_id: str, language: str, source: str, expected: str, response: str
) -> dict:
    return {
        "case_id": case_id,
        "language": language,
        "pattern": "synthetic",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "mathematical_complexity": expected,
        "expected_analyzer_response": response,
        "mathematical_rationale": "synthetic fixture rationale",
        "input_contract": "synthetic input contract",
        "assumptions": ["synthetic fixture assumption"],
        "historical_review_disposition": "approve",
        "gold_label_approved": True,
        "decision_status": "approved_frozen",
        "owner_approved": True,
        "analyzer_executed": False,
    }


def _gold_artifact(cases: list[dict]) -> dict:
    return {"gold_labels_frozen": True, "owner_confirmed": True, "cases": cases}


def _prediction(gold: dict, raw: dict, response: str | None = None) -> dict:
    return {
        "schema_version": "axioma.bfs-v2.prediction.v1",
        "case_id": gold["case_id"],
        "language": gold["language"],
        "pattern": gold["pattern"],
        "source_sha256": gold["source_sha256"],
        "entrypoint": "stub",
        "execution_status": "completed",
        "actual_response": response
        or ("unknown" if raw["estimate"].startswith("unknown") else "estimate"),
        "analyzer_output": raw,
        "error": None,
    }


def test_all_28_frozen_expected_complexities_parse_without_running_analyzer() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert len(gold["cases"]) == 28
    parsed = []
    for case in gold["cases"]:
        try:
            parsed.append(parse_complexity(case["mathematical_complexity"]))
        except ValueError as exc:
            pytest.fail(f"{case['case_id']}: {exc}")
    assert len(parsed) == 28


@pytest.mark.parametrize(
    ("expected", "actual"),
    [
        ("O(V + E)", "O(E + V)"),
        ("O(V + VE)", "O(V(E + 1))"),
        ("O((R * C)^2)", "O(R^2 * C^2)"),
        ("O(V^2 + E)", "O(E + V²)"),
        ("O(Q * (V + E))", "O(QV + QE)"),
        ("O((V + E) * log(V + E))", "O(log(E + V) * (E + V))"),
    ],
)
def test_declared_algebraic_equivalences(expected: str, actual: str) -> None:
    assert (
        compare_complexities(expected, actual)["status"] == "mathematically_equivalent"
    )


def test_harmless_formatting_and_implicit_multiplication_are_normalized() -> None:
    result = compare_complexities(" O ( V × ( E + 1 ) ) ", "O(V*(E+1))")
    assert result["status"] == "exact_match"
    assert result["expected_normalized"] == "O(V*(E+1))"


def test_j08_equality_chain_parses_and_matches_expanded_equivalent() -> None:
    parsed = parse_complexity("O(V + VE) = O(V(E + 1))")
    assert parsed.normalized == "O(V+V*E) = O(V*(E+1))"
    assert (
        compare_complexities("O(V + VE) = O(V(E + 1))", "O(V + V*E)")["status"]
        == "mathematically_equivalent"
    )


@pytest.mark.parametrize(
    "expression",
    [
        "O(sqrt(V))",
        "O(V + n)",
        "O(V + )",
        "O((V + E)",
        "O(V^100)",
        "O(V / E)",
        "O(V) trailing",
        "O(V) = O(E)",
    ],
)
def test_unsupported_or_malformed_expressions_are_unscorable(expression: str) -> None:
    assert compare_complexities("O(V)", expression)["status"] == "unscorable"


def test_variables_are_not_silently_renamed() -> None:
    result = compare_complexities("O(V + E)", "O(V + Q)")
    assert result["status"] == "mismatch"


def test_clear_growth_difference_is_mismatch() -> None:
    assert compare_complexities("O(V^2)", "O(V + E)")["status"] == "mismatch"
    assert compare_complexities("O(V + E)", "O(VE)")["status"] == "mismatch"


def test_uncertain_asymptotic_relation_is_unscorable_not_guessed() -> None:
    result = compare_complexities("O(V)", "O(V + 1)")
    assert result["status"] == "unscorable"
    assert "cannot safely establish" in result["reason"]
    # Simplifying V + V*E to V*E requires an E>=1 condition that is not implicit here.
    assert compare_complexities("O(V + VE)", "O(VE)")["status"] == "unscorable"


def test_execution_errors_are_distinct_from_unknown_predictions() -> None:
    source = "def solve():\n    return 1\n"
    gold = _gold_case("py-error", "python", source, "O(1)", "estimate")

    def fail(_source: str, _entrypoint: str) -> dict:
        raise RuntimeError("stub failure")

    case = PacketInput(
        gold["case_id"],
        gold["language"],
        gold["pattern"],
        source,
        gold["source_sha256"],
    )
    prediction = run_cases([case], {"python": fail})[0]
    assert prediction["execution_status"] == "error"
    assert prediction["actual_response"] == "error"
    assert prediction["error"]["message"] == "stub failure"
    assert prediction["analyzer_output"] is None


def test_runner_dispatch_uses_only_source_and_entrypoint_and_preserves_raw_output(
    tmp_path: Path,
) -> None:
    source = "def solve(graph):\n    return len(graph)\n"
    row = {
        "case_id": "py-one",
        "language": "python",
        "pattern": "synthetic-pattern",
        "source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "expected_time_complexity": "O(n)",
        "expected_response_category": "unknown",
        "review": {"decision": "exclude"},
    }
    packet = tmp_path / "packet.jsonl"
    packet.write_text(json.dumps(row) + "\n", encoding="utf-8")
    calls: list[tuple[str, str]] = []
    raw = {
        "method": "stub_static",
        "estimate": "O(V + E)",
        "confidence": "low",
        "methods_disagree": False,
        "explanation": "raw explanation",
        "details": {"signals": [{"kind": "graph_bfs"}], "rule_version": "test-v1"},
    }

    def stub(source_arg: str, entrypoint: str) -> dict:
        calls.append((source_arg, entrypoint))
        return raw

    cases = read_packet(packet, hashlib.sha256(packet.read_bytes()).hexdigest())
    result = run_cases(cases, {"python": stub})[0]
    assert calls == [(source, "solve")]
    assert result["actual_response"] == "estimate"
    assert result["analyzer_output"] == raw
    assert "expected_time_complexity" not in result
    assert "review" not in result


def test_runner_resolves_java_class_and_method_without_real_analyzer() -> None:
    source = "class Demo { void run() { int n = 1; } void helper() {} }"
    case = PacketInput(
        "java-one",
        "java",
        "synthetic",
        source,
        hashlib.sha256(source.encode()).hexdigest(),
    )
    called: list[tuple[str, str]] = []

    def stub(source_arg: str, entrypoint: str) -> dict:
        called.append((source_arg, entrypoint))
        return {"estimate": "O(1)", "method": "stub", "details": {}}

    run_cases([case], {"java": stub})
    assert called == [(source, "Demo.run")]


def test_runner_rejects_source_hash_mismatch_before_call(tmp_path: Path) -> None:
    source = "def solve():\n    return 0\n"
    row = {
        "case_id": "bad-hash",
        "language": "python",
        "pattern": "test",
        "source": source,
        "source_sha256": "0" * 64,
    }
    path = tmp_path / "packet.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(PredictionInputError, match="source hash mismatch"):
        read_packet(path)


def test_runner_rejects_duplicate_case_ids_before_call(tmp_path: Path) -> None:
    source = "def solve():\n    return 0\n"
    row = {
        "case_id": "duplicate",
        "language": "python",
        "pattern": "test",
        "source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    }
    path = tmp_path / "packet.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(PredictionInputError, match="duplicate case ID"):
        read_packet(path)


def test_join_is_by_case_id_not_prediction_order_and_keeps_raw_evidence() -> None:
    source_a = "def solve():\n    return 0\n"
    source_b = "def other():\n    return 1\n"
    gold_a = _gold_case("a", "python", source_a, "O(V + E)", "estimate")
    gold_b = _gold_case("b", "python", source_b, "O(V)", "unknown")
    raw_a = {
        "method": "stub",
        "estimate": "O(E + V)",
        "confidence": "medium",
        "details": {"proof": "kept"},
    }
    raw_b = {
        "method": "stub",
        "estimate": "unknown (synthetic abstention)",
        "confidence": "low",
        "details": {"reason": "kept"},
    }
    report = join_and_score(
        _gold_artifact([gold_a, gold_b]),
        [_prediction(gold_b, raw_b), _prediction(gold_a, raw_a)],
    )
    assert [row["case_id"] for row in report["case_results"]] == ["a", "b"]
    assert (
        report["case_results"][0]["complexity_comparison"]["status"]
        == "mathematically_equivalent"
    )
    assert report["case_results"][0]["evidence_summary"]["details"] == {"proof": "kept"}
    assert report["case_results"][1]["complexity_comparison"] is None


def test_missing_and_duplicate_case_ids_fail_join() -> None:
    source = "def solve():\n    return 1\n"
    gold = _gold_case("only", "python", source, "O(1)", "estimate")
    artifact = _gold_artifact([gold])
    with pytest.raises(EvaluationInputError, match="missing predictions"):
        join_and_score(artifact, [])
    one = _prediction(gold, {"estimate": "O(1)"})
    with pytest.raises(EvaluationInputError, match="duplicate case_id"):
        join_and_score(artifact, [one, one])


def test_response_behavior_separates_unexpected_estimates_and_abstentions() -> None:
    sources = [f"def f{i}():\n    return {i}\n" for i in range(4)]
    gold = [
        _gold_case("correct-estimate", "python", sources[0], "O(V)", "estimate"),
        _gold_case("correct-unknown", "python", sources[1], "O(V)", "unknown"),
        _gold_case("unexpected-estimate", "python", sources[2], "O(V)", "unknown"),
        _gold_case("unexpected-abstention", "python", sources[3], "O(V)", "estimate"),
    ]
    raw = [
        {"estimate": "O(V)"},
        {"estimate": "unknown (expected)"},
        {"estimate": "O(V)"},
        {"estimate": "unknown (not expected)"},
    ]
    predictions = [_prediction(g, r) for g, r in zip(gold, raw)]
    report = join_and_score(_gold_artifact(gold), predictions)
    response = report["response_behavior"]
    assert response["correct_estimate_responses"] == 1
    assert response["correct_unknown_responses"] == 1
    assert response["unexpected_estimates_on_expected_unknown"] == 1
    assert response["unexpected_abstentions_on_expected_estimate"] == 1
    assert response["response_agreement_count"] == 2


def test_estimate_on_expected_abstention_is_unexpected_even_if_complexity_matches() -> (
    None
):
    source = "def solve():\n    return 1\n"
    gold = _gold_case("expected-unknown", "python", source, "O(V)", "unknown")
    prediction = _prediction(gold, {"estimate": "O(V)", "details": {}})
    report = join_and_score(_gold_artifact([gold]), [prediction])
    case = report["case_results"][0]
    assert case["response_agreement"] is False
    assert case["complexity_comparison"]["status"] == "exact_match"
    assert report["response_behavior"]["unexpected_estimates_on_expected_unknown"] == 1


def test_execution_error_is_not_coerced_to_unknown_by_scorer() -> None:
    source = "def solve():\n    return 1\n"
    gold = _gold_case("error", "python", source, "O(1)", "unknown")
    prediction = {
        "case_id": "error",
        "language": "python",
        "source_sha256": gold["source_sha256"],
        "execution_status": "error",
        "actual_response": "error",
        "analyzer_output": None,
        "error": {
            "stage": "analyzer_execution",
            "type": "RuntimeError",
            "message": "failed",
        },
    }
    report = join_and_score(_gold_artifact([gold]), [prediction])
    assert report["case_results"][0]["actual_response"] == "error"
    assert report["response_behavior"]["execution_errors"] == 1
    assert report["response_behavior"]["correct_unknown_responses"] == 0


def test_scoring_reports_separate_denominators_and_does_not_hide_unscorable() -> None:
    expected = [
        ("exact", "O(V)", "estimate", "O(V)"),
        ("equivalent", "O(V + E)", "estimate", "O(E + V)"),
        ("mismatch", "O(V^2)", "estimate", "O(V + E)"),
        ("unscorable", "O(V)", "estimate", "O(sqrt(V))"),
        ("unexpected", "O(V)", "unknown", "O(V)"),
        ("abstained", "O(V)", "unknown", "unknown (expected)"),
        ("missed", "O(V)", "estimate", "unknown (not expected)"),
    ]
    gold_cases = []
    predictions = []
    for case_id, complexity, response, actual in expected:
        source = f"def {case_id}():\n    return 1\n"
        gold = _gold_case(case_id, "python", source, complexity, response)
        gold_cases.append(gold)
        predictions.append(_prediction(gold, {"estimate": actual, "details": {}}))
    error_source = "def execution_error():\n    return 0\n"
    error_gold = _gold_case(
        "execution-error", "python", error_source, "O(1)", "estimate"
    )
    gold_cases.append(error_gold)
    predictions.append(
        {
            "case_id": error_gold["case_id"],
            "language": "python",
            "source_sha256": error_gold["source_sha256"],
            "execution_status": "error",
            "actual_response": "error",
            "analyzer_output": None,
            "error": {
                "stage": "analyzer_execution",
                "type": "RuntimeError",
                "message": "stub",
            },
        }
    )

    report = join_and_score(_gold_artifact(gold_cases), predictions)
    response = report["response_behavior"]
    assert response["response_agreement_count"] == 5
    assert response["response_agreement_denominator"] == 8
    assert response["unexpected_estimates_on_expected_unknown"] == 1
    assert response["unexpected_abstentions_on_expected_estimate"] == 1
    assert response["execution_errors"] == 1
    assert report["coverage"] == {
        "estimate_count": 5,
        "denominator": 8,
        "rate": 5 / 8,
        "expected_estimate_cases": 6,
        "estimates_on_expected_estimate_cases": 4,
        "expected_estimate_subset_coverage": 4 / 6,
    }
    correctness = report["complexity_correctness"]
    assert correctness["exact_match"] == 2
    assert correctness["mathematically_equivalent"] == 1
    assert correctness["mismatch"] == 1
    assert correctness["unscorable"] == 1
    assert correctness["all_emitted_estimates_denominator"] == 5
    assert correctness["scorable_estimates_denominator"] == 4
    assert correctness["exact_accuracy_among_emitted_estimates"] == 2 / 5
    assert correctness["equivalent_accuracy_among_emitted_estimates"] == 3 / 5
    assert correctness["exact_accuracy_among_scorable_estimates"] == 2 / 4
    assert correctness["equivalent_accuracy_among_scorable_estimates"] == 3 / 4
