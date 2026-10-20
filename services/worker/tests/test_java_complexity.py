from axioma_worker.java_complexity import (
    analyze_java_complexity,
    estimate_java_heap_pool_peak_growth,
)


def test_counts_braced_nested_loops_in_selected_method() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve() { for (;;) { while (true) { work(); } } } }",
        "Solution.solve",
    )

    assert estimate.method == "static_java_token_loop_depth"
    assert estimate.estimate == "O(n^2)"
    assert estimate.confidence == "low"
    assert "not a proof" in estimate.explanation


def test_ignores_loop_words_in_comments_and_strings() -> None:
    estimate = analyze_java_complexity(
        'class Solution { void solve() { String note = "for (;;)"; /* while (x) {} */ } }',
        "Solution.solve",
    )

    assert estimate.estimate == "O(1) (no detected loops or sorting)"


def test_reports_recursion_as_unknown_and_missing_method() -> None:
    recursive = analyze_java_complexity(
        "class Solution { int solve(int n) { return solve(n - 1); } }", "Solution.solve"
    )
    missing = analyze_java_complexity("class Solution {}", "Solution.solve")

    assert recursive.estimate == "unknown (recursion detected)"
    assert missing.estimate == "unknown (method not found)"


def test_heap_pool_peak_increase_fit_estimates_space_separately() -> None:
    points = [
        {"size": size, "heap_pool_peak_increase_bytes": size * 24}
        for size in (10, 20, 40, 80)
    ]

    result = estimate_java_heap_pool_peak_growth(points)

    assert result["method"] == "java_heap_pool_peak_increase_fit"
    assert result["state"] == "estimated"
    assert result["estimate"] == "O(n)"
    assert result["confidence"] == "low"
    assert len(result["points"]) == 4


def test_heap_pool_peak_increase_does_not_fit_when_every_observation_is_zero() -> None:
    points = [
        {"size": size, "heap_pool_peak_increase_bytes": 0}
        for size in (10, 20, 40, 80)
    ]

    result = estimate_java_heap_pool_peak_growth(points)

    assert result["state"] == "not_estimated"
    assert "No positive" in result["reason"]
