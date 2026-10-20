import pytest
from pydantic import ValidationError

from axioma_api.contracts import (
    ComplexityResult,
    Confidence,
    EvidenceClaim,
    EvidenceType,
    GateState,
    TestResultSummary as ResultCounts,
    VerificationGate,
)


def test_evidence_claim_requires_type_and_categorical_confidence() -> None:
    claim = EvidenceClaim(
        id="claim-1",
        type=EvidenceType.EXECUTED,
        confidence=Confidence.HIGH,
        summary="All sample tests passed",
    )
    assert claim.type == EvidenceType.EXECUTED
    assert claim.confidence == Confidence.HIGH


def test_test_counts_must_reconcile() -> None:
    with pytest.raises(ValidationError, match="total must equal"):
        ResultCounts(total=15, passed=14, failed=0, skipped=0)


def test_complexity_exposes_method_and_disagreement() -> None:
    result = ComplexityResult(
        method="empirical_growth_fit",
        estimate="O(n log n)",
        confidence=Confidence.MEDIUM,
        methods_disagree=True,
    )
    assert result.methods_disagree is True


def test_verification_gate_has_order_and_explicit_state() -> None:
    gate = VerificationGate(order=2, name="tests_pass", state=GateState.NOT_RUN)
    assert gate.order == 2
    assert gate.state == GateState.NOT_RUN
