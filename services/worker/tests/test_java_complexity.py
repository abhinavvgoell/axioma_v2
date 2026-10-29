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


def test_recognizes_nested_java_insertion_sort_shift_as_quadratic() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void sort(int[] data) { "
        "for (int i = 1; i < data.length; i++) { int value = data[i]; "
        "int j = i - 1; while (j >= 0 && data[j] > value) { "
        "data[j + 1] = data[j]; j--; } data[j + 1] = value; } } }",
        "Solution.sort",
    )

    assert estimate.method == "static_java_insertion_sort_shift"
    assert estimate.estimate == "O(n^2)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "insertion_sort_shift"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_does_not_classify_arbitrary_backward_while_loop_as_insertion_sort() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve(int[] data) { "
        "for (int i = 1; i < data.length; i++) { int j = i - 1; "
        "while (j >= 0 && data[j] > 0) { j--; } } } }",
        "Solution.solve",
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


def test_recognizes_java_adjacency_list_bfs_with_visited_guard() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve(Map<Integer,List<Integer>> graph, int start) { "
        "Set<Integer> visited = new HashSet<>(); Queue<Integer> queue = new ArrayDeque<>(); "
        "visited.add(start); queue.add(start); while (!queue.isEmpty()) { "
        "int node = queue.poll(); for (int neighbor : graph.get(node)) { "
        "if (visited.add(neighbor)) { queue.offer(neighbor); } } } } }",
        "Solution.solve",
    )

    assert estimate.method == "static_java_graph_bfs"
    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unvisited_java_adjacency_queue_loop_remains_unknown() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve(Map<Integer,List<Integer>> graph, int start) { "
        "Queue<Integer> queue = new ArrayDeque<>(); queue.add(start); "
        "while (!queue.isEmpty()) { int node = queue.poll(); "
        "for (int neighbor : graph.get(node)) { queue.offer(neighbor); } } } }",
        "Solution.solve",
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"


def test_recognizes_java_adjacency_bfs_with_boolean_array_visited_guard() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int count(Map<Integer,List<Integer>> graph, int start) { "
        "boolean[] seen = new boolean[graph.size()]; Queue<Integer> queue = new ArrayDeque<>(); "
        "seen[start] = true; queue.add(start); while (!queue.isEmpty()) { "
        "int node = queue.remove(); for (int neighbor : graph.get(node)) { "
        "if (!seen[neighbor]) { seen[neighbor] = true; queue.add(neighbor); } } } "
        "return 0; } }",
        "Solution.count",
    )

    assert estimate.method == "static_java_graph_bfs"
    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unmarked_java_array_visited_guard_does_not_claim_bfs_complexity() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void solve(Map<Integer,List<Integer>> graph, int start) { "
        "boolean[] seen = new boolean[graph.size()]; Queue<Integer> queue = new ArrayDeque<>(); "
        "queue.add(start); while (!queue.isEmpty()) { int node = queue.remove(); "
        "for (int neighbor : graph.get(node)) { if (!seen[neighbor]) { "
        "queue.add(neighbor); } } } } }",
        "Solution.solve",
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"


def test_recognizes_java_recursive_adjacency_list_dfs() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void dfs(int node, Map<Integer,List<Integer>> graph, "
        "Set<Integer> visited) { for (int neighbor : graph.get(node)) { "
        "if (visited.add(neighbor)) { dfs(neighbor, graph, visited); } } } }",
        "Solution.dfs",
    )

    assert estimate.method == "static_java_graph_dfs"
    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_dfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unguarded_java_graph_recursion_remains_unknown() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void dfs(int node, Map<Integer,List<Integer>> graph, "
        "Set<Integer> visited) { for (int neighbor : graph.get(node)) { "
        "dfs(neighbor, graph, visited); } } }",
        "Solution.dfs",
    )

    assert estimate.estimate == "unknown (recursion detected)"


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
