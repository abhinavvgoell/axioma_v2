from run_calibration_v1 import UNKNOWN, _normalize_estimate


def test_normalize_supported_estimates_and_abstain_on_other_forms() -> None:
    assert _normalize_estimate("O(n^2)") == "O(n^2)"
    assert _normalize_estimate("O(n log n) (static estimate)") == "O(n log n)"
    assert _normalize_estimate("unknown (recursive structure unsupported)") == UNKNOWN
    assert _normalize_estimate("O(V + E)") == UNKNOWN
