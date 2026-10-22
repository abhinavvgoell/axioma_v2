from axioma_worker.java_complexity import (
    analyze_java_complexity,
    estimate_java_heap_pool_peak_growth,
)


def test_recognizes_java_binary_search_as_logarithmic() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int solve(int[] values, int target) { "
        "int low=0, high=values.length-1; "
        "while(low<=high) { int mid=(low+high)/2; "
        "if(values[mid]==target)return mid; "
        "if(values[mid]<target)low=mid+1; else high=mid-1; } return -1; } }",
        "Solution.solve",
    )

    assert estimate.method == "static_java_token_loop_depth"
    assert estimate.estimate == "O(log n)"
    assert estimate.confidence == "low"
    assert any(signal["kind"] == "binary_search" for signal in estimate.details["code_analysis"]["signals"])


def test_counts_nested_for_loops_in_selected_java_method() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve(int[] a) { "
        "for(int i=0;i<a.length;i++) { for(int j=0;j<a.length;j++) {} } } }",
        "Solution.solve",
    )

    assert estimate.estimate == "O(n^2)"


def test_java_code_analysis_exposes_while_loop_uncertainty() -> None:
    estimate = analyze_java_complexity(
        "class S { void f(int n) { while(n>0) n--; } }", "S.f"
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"


def test_ignores_loop_words_in_comments_and_strings() -> None:
    estimate = analyze_java_complexity(
        'class Solution { void solve() { String note = "for (;;)"; /* while (x) {} */ } }',
        "Solution.solve",
    )

    assert estimate.estimate == "O(1) (no detected loops or sorting)"


def test_code_analysis_exposes_java_patterns_without_inventing_line_numbers() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int solve(int[] values) { "
        "Set<Integer> seen = new HashSet<>(); "
        "for (int value : values) { "
        "if (seen.contains(value)) return value; "
        "seen.add(value); } return -1; } }",
        "Solution.solve",
    )

    analysis = estimate.details["code_analysis"]
    signals = analysis["signals"]
    assert analysis["language"] == "java"
    assert analysis["loop_count"] == 1
    assert any(signal["kind"] == "loop" and signal["line"] is None for signal in signals)
    assert any(signal["kind"] == "collection_operation" for signal in signals)
    assert any("line numbers" in limitation for limitation in analysis["limitations"])


def test_reports_recursion_as_unknown_and_missing_method() -> None:
    recursive = analyze_java_complexity(
        "class Solution { int solve(int n) { return solve(n - 1); } }", "Solution.solve"
    )
    missing = analyze_java_complexity("class Solution {}", "Solution.solve")

    assert recursive.estimate == "unknown (recursion detected)"
    assert missing.estimate == "unknown (method not found)"


def test_recognizes_java_recursive_binary_tree_walk() -> None:
    estimate = analyze_java_complexity(
        "class TreeNode { TreeNode left; TreeNode right; } "
        "class Solution { int solve(TreeNode node) { "
        "if (node == null) return 0; "
        "return 1 + Math.max(solve(node.left), solve(node.right)); } }",
        "Solution.solve",
    )

    assert estimate.method == "static_java_tree_recursion"
    assert estimate.estimate == "O(n)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "tree_recursion"
        for signal in estimate.details["code_analysis"]["signals"]
    )


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
