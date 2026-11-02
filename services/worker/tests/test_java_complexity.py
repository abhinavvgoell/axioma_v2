import hashlib
import json
from pathlib import Path

from axioma_worker.java_complexity import (
    analyze_java_complexity,
    estimate_java_heap_pool_peak_growth,
)


def _reviewed_java_bfs_case(case_id: str) -> tuple[dict, dict]:
    root = Path(__file__).resolve().parents[3]
    dataset = root / "evaluation/mode1/bfs-independent-2026-10-29-v1"
    artifact_path = dataset / "gold-reviewed-java-adjacency-2026-10-29.json"
    assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == (
        "a6a8aaad56b0dc09141ec8e7ecb2db73d39870ed92628ac94743691493cb6eff"
    )
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text().splitlines()]
    artifact = json.loads(artifact_path.read_text())
    return (
        next(row for row in cases if row["id"] == case_id),
        next(row for row in artifact["cases"] if row["id"] == case_id),
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


def test_static_auxiliary_space_recognizes_java_hash_map_growth() -> None:
    estimate = analyze_java_complexity(
        "import java.util.*; class Solution { int[] twoSum(int[] nums, int target) { "
        "Map<Integer,Integer> seen = new HashMap<>(); "
        "for (int i=0; i<nums.length; i++) { "
        "if (seen.containsKey(target-nums[i])) return new int[]{seen.get(target-nums[i]),i}; "
        "seen.put(nums[i],i); } return new int[0]; } }",
        "Solution.twoSum",
    )

    space = estimate.details["code_analysis"]["auxiliary_space"]
    assert space["state"] == "estimated"
    assert space["estimate"] == "O(n)"


def test_static_auxiliary_space_recognizes_scalar_java_scan() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int solve(int[] nums) { int sum=0; "
        "for(int value : nums) sum += value; return sum; } }",
        "Solution.solve",
    )

    space = estimate.details["code_analysis"]["auxiliary_space"]
    assert space["state"] == "estimated"
    assert space["estimate"] == "O(1)"


def test_static_auxiliary_space_recognizes_allocation_free_java_scan() -> None:
    estimate = analyze_java_complexity(
        "class Solution { boolean check(int[] values) { int left=0, right=values.length-1; "
        "while(left<right) { if(values[left]!=values[right]) return false; "
        "left++; right--; } return true; } }",
        "Solution.check",
    )

    space = estimate.details["code_analysis"]["auxiliary_space"]
    assert space["state"] == "estimated"
    assert space["estimate"] == "O(1)"
    assert space["method"] == "static_java_allocation_free_state"


def test_static_auxiliary_space_abstains_on_java_allocation_and_helper_calls() -> None:
    allocated = analyze_java_complexity(
        "class S { int[] f(int[] values) { int[] copy = new int[values.length]; return copy; } }",
        "S.f",
    )
    helper = analyze_java_complexity(
        "class S { int f(int value) { return custom(value); } }", "S.f"
    )

    assert allocated.details["code_analysis"]["auxiliary_space"]["state"] == "unknown"
    assert helper.details["code_analysis"]["auxiliary_space"]["state"] == "unknown"


def test_static_auxiliary_space_abstains_on_java_string_concatenation() -> None:
    estimate = analyze_java_complexity(
        "class S { String f(String text) { String result = \"\"; "
        "for(int i=0;i<text.length();i++) result += text.charAt(i); return result; } }",
        "S.f",
    )

    assert estimate.details["code_analysis"]["auxiliary_space"]["state"] == "unknown"


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


def test_recognizes_java_inward_two_pointer_scan() -> None:
    estimate = analyze_java_complexity(
        "class Solution { boolean check(String letters) { "
        "int start = 0; int end = letters.length() - 1; "
        "while (start < end) { "
        "if (letters.charAt(start) != letters.charAt(end)) return false; "
        "start++; end--; } return true; } }",
        "Solution.check",
    )

    assert estimate.method == "static_java_inward_two_pointer_scan"
    assert estimate.estimate == "O(n)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "inward_two_pointer_scan"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_inward_two_pointer_rule_rejects_missing_cursor_progress() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void scan(int[] values) { "
        "int left = 0; int right = values.length - 1; "
        "while (left < right) { left++; } } }",
        "Solution.scan",
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"
    assert not any(
        signal["kind"] == "inward_two_pointer_scan"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_inward_two_pointer_rule_rejects_conditional_cursor_progress() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void scan(int[] values) { "
        "int left = 0; int right = values.length - 1; "
        "while (left < right) { if (values[left] < 0) left++; right--; } } }",
        "Solution.scan",
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


def _assert_amortized_monotonic_stack(estimate, expected_pops: int, has_drain: bool) -> None:
    assert estimate.method == "static_java_amortized_monotonic_stack_v1"
    assert estimate.estimate == "O(n)"
    assert estimate.confidence == "low"
    evidence = estimate.details["code_analysis"]["monotonic_stack"]
    assert evidence["language"] == "java"
    assert evidence["rule_version"] == "java_monotonic_stack_amortized_v1"
    assert evidence["pattern_id"] == "java_arraydeque_single_push_monotonic_pop"
    assert evidence["bounded_push_evidence"]["push_sites"] == 1
    assert evidence["bounded_push_evidence"]["push_once_per_iteration"] is True
    assert evidence["bounded_removal_evidence"]["pop_sites"] == expected_pops
    assert evidence["bounded_removal_evidence"]["popped_entries_reinserted"] is False
    assert evidence["bounded_removal_evidence"]["optional_final_drain"] is has_drain
    assert "pushes each array index once" in evidence["amortized_argument"]
    assert evidence["complexity"] == "O(n)"
    assert evidence["assumptions"]
    assert evidence["limitations"]
    assert evidence["inference_kind"] == "heuristic_static_amortized_argument"
    assert all(isinstance(index, int) for index in evidence["source_locations"]["pop_token_indices"])
    assert any(
        signal["kind"] == "amortized_monotonic_stack"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_recognizes_next_greater_style_monotonic_stack_with_drain() -> None:
    estimate = analyze_java_complexity(
        "import java.util.ArrayDeque; import java.util.Deque; class S { "
        "int[] solve(int[] values) { int[] answer = new int[values.length]; "
        "Deque<Integer> stack = new ArrayDeque<>(); "
        "for (int i = 0; i < values.length; i++) { "
        "while (!stack.isEmpty() && values[stack.peek()] < values[i]) { "
        "answer[stack.pop()] = values[i]; } stack.push(i); } "
        "while (!stack.isEmpty()) { answer[stack.pop()] = -1; } return answer; } }",
        "S.solve",
    )

    _assert_amortized_monotonic_stack(estimate, expected_pops=2, has_drain=True)
    evidence = estimate.details["code_analysis"]["monotonic_stack"]
    assert evidence["bounded_removal_evidence"]["monotonic_condition"] == (
        "values[stack.peek()] < values[i]"
    )
    assert "final_drain_while_token_index" in evidence["source_locations"]


def test_recognizes_previous_smaller_style_monotonic_stack() -> None:
    estimate = analyze_java_complexity(
        "import java.util.ArrayDeque; import java.util.Deque; class S { "
        "int[] solve(int[] values) { int[] previous = new int[values.length]; "
        "Deque<Integer> stack = new ArrayDeque<>(); "
        "for (int i = 0; i < values.length; i++) { "
            "while (!stack.isEmpty() && values[stack.peek()] >= values[i]) { "
            "stack.pop(); } stack.push(i); } "
        "return previous; } }",
        "S.solve",
    )

    _assert_amortized_monotonic_stack(estimate, expected_pops=1, has_drain=False)


def test_recognizes_arraydeque_concrete_stack_declaration() -> None:
    estimate = analyze_java_complexity(
        "import java.util.ArrayDeque; class S { "
        "int[] solve(int[] values) { int[] answer = new int[values.length]; "
        "ArrayDeque<Integer> mono = new ArrayDeque<>(); "
        "for (int i = 0; i < values.length; i++) { "
        "while (!mono.isEmpty() && values[mono.peek()] > values[i]) { "
        "answer[mono.pop()] = values[i]; } mono.push(i); } return answer; } }",
        "S.solve",
    )

    _assert_amortized_monotonic_stack(estimate, expected_pops=1, has_drain=False)
    assert (
        estimate.details["code_analysis"]["monotonic_stack"]["bounded_push_evidence"]["container"]
        == "ArrayDeque"
    )


def test_monotonic_stack_accounts_for_multiple_pops_in_one_iteration() -> None:
    estimate = analyze_java_complexity(
        "import java.util.ArrayDeque; import java.util.Deque; class S { "
        "int[] solve(int[] values) { int[] answer = new int[values.length]; "
        "Deque<Integer> stack = new ArrayDeque<>(); "
        "for (int i = 0; i < values.length; i++) { "
        "while (!stack.isEmpty() && values[stack.peek()] < values[i]) { "
        "answer[stack.pop()] = values[i]; } stack.push(i); } return answer; } }",
        "S.solve",
    )

    _assert_amortized_monotonic_stack(estimate, expected_pops=1, has_drain=False)
    assert "each index can be popped at most once" in (
        estimate.details["code_analysis"]["monotonic_stack"]["amortized_argument"]
    )


def test_monotonic_stack_supports_single_push_and_single_removal_site() -> None:
    estimate = analyze_java_complexity(
        "import java.util.ArrayDeque; class S { "
        "int solve(int[] values) { ArrayDeque<Integer> stack = new ArrayDeque<>(); int count = 0; "
        "for (int i = 0; i < values.length; i++) { "
        "while (!stack.isEmpty() && values[stack.peek()] <= values[i]) { stack.pop(); } "
        "stack.push(i); count++; } return count; } }",
        "S.solve",
    )

    _assert_amortized_monotonic_stack(estimate, expected_pops=1, has_drain=False)


def test_java_monotonic_stack_rule_rejects_adversarial_near_misses() -> None:
    cases = [
        (
            "quadratic nested traversal",
            "import java.util.ArrayDeque; class S { void solve(int[] values) { "
            "ArrayDeque<Integer> stack = new ArrayDeque<>(); "
            "for (int i = 0; i < values.length; i++) { "
            "for (int j = 0; j < values.length; j++) { stack.push(j); stack.pop(); } } } }",
            "O(n^2)",
        ),
        (
            "reinsertion after a pop",
            "import java.util.ArrayDeque; class S { void solve(int[] values) { "
            "ArrayDeque<Integer> stack = new ArrayDeque<>(); "
            "for (int i = 0; i < values.length; i++) { stack.push(i); "
            "while (!stack.isEmpty() && values[stack.peek()] < values[i]) { "
            "stack.pop(); stack.push(i); } } } }",
            "unknown (data-dependent or incomplete loop)",
        ),
        (
            "repeated stack search",
            "import java.util.ArrayDeque; class S { void solve(int[] values) { "
            "ArrayDeque<Integer> stack = new ArrayDeque<>(); "
            "for (int i = 0; i < values.length; i++) { "
            "while (!stack.isEmpty()) { if (stack.contains(values[i])) stack.pop(); else break; } "
            "stack.push(i); } } }",
            "unknown (data-dependent or incomplete loop)",
        ),
        (
            "no monotonic value condition",
            "import java.util.ArrayDeque; class S { void solve(int[] values) { "
            "ArrayDeque<Integer> stack = new ArrayDeque<>(); "
            "for (int i = 0; i < values.length; i++) { "
            "while (!stack.isEmpty()) stack.pop(); stack.push(i); } } }",
            "unknown (data-dependent or incomplete loop)",
        ),
        (
            "unrecognized removal operation",
            "import java.util.ArrayDeque; class S { void solve(int[] values) { "
            "ArrayDeque<Integer> stack = new ArrayDeque<>(); "
            "for (int i = 0; i < values.length; i++) { "
            "while (!stack.isEmpty() && values[stack.peek()] < values[i]) { "
            "stack.removeFirst(); } stack.push(i); } } }",
            "unknown (data-dependent or incomplete loop)",
        ),
    ]

    for name, source, expected in cases:
        estimate = analyze_java_complexity(source, "S.solve")
        assert estimate.estimate == expected, name
        assert estimate.method != "static_java_amortized_monotonic_stack_v1", name


def test_reports_recursion_as_unknown_and_missing_method() -> None:
    recursive = analyze_java_complexity(
        "class Solution { int solve(int n) { return solve(n - 1); } }", "Solution.solve"
    )
    missing = analyze_java_complexity("class Solution {}", "Solution.solve")

    assert recursive.estimate == "unknown (recursion detected)"
    assert missing.estimate == "unknown (method not found)"


def _assert_java_recurrence(estimate, expected: str, recurrence: str) -> None:
    assert estimate.estimate == expected
    evidence = estimate.details["code_analysis"]["recurrence"]
    assert evidence["rule_version"] == "bounded_recurrence_v1"
    assert evidence["recurrence"] == recurrence
    assert evidence["solving_rule"]
    assert evidence["assumptions"]
    assert evidence["inference_kind"] == "heuristic_pattern_match"
    assert any(signal["kind"] == "recurrence" for signal in estimate.details["code_analysis"]["signals"])


def test_java_bounded_scalar_recurrences() -> None:
    decrement = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 0) return 0; return f(n - 1) + 1; } }",
        "S.f",
    )
    halve = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; return f(n / 2); } }", "S.f"
    )
    halve_with_linear_work = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; "
        "for (int i = 0; i < n; i++) { int x = i; } return f(n / 2); } }",
        "S.f",
    )
    two_halves = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; return f(n / 2) + f(n / 2); } }",
        "S.f",
    )
    two_halves_with_linear_work = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; "
        "for (int i = 0; i < n; i++) { int x = i; } "
        "return f(n / 2) + f(n / 2); } }",
        "S.f",
    )

    _assert_java_recurrence(decrement, "O(n)", "T(n) = T(n - c) + O(1)")
    _assert_java_recurrence(halve, "O(log n)", "T(n) = T(n / 2) + O(1)")
    _assert_java_recurrence(halve_with_linear_work, "O(n)", "T(n) = T(n / 2) + O(n)")
    _assert_java_recurrence(two_halves, "O(n)", "T(n) = 2T(n / 2) + O(1)")
    _assert_java_recurrence(
        two_halves_with_linear_work, "O(n log n)", "T(n) = 2T(n / 2) + O(n)"
    )


def test_java_recursive_binary_search_has_recurrence_evidence() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int search(int[] values, int target, int low, int high) { "
        "if (low > high) return -1; int middle = low + (high - low) / 2; "
        "if (values[middle] == target) return middle; "
        "if (values[middle] < target) { return search(values, target, middle + 1, high); } "
        "return search(values, target, low, middle - 1); } }",
        "Solution.search",
    )

    _assert_java_recurrence(estimate, "O(log n)", "T(n) = T(n / 2) + O(1)")
    evidence = estimate.details["code_analysis"]["recurrence"]
    assert evidence["recursive_calls_per_level"] == 1
    assert evidence["input_size_reduction"] == "factor_two"


def test_java_entrypoint_delegating_to_recursive_binary_search_is_logarithmic() -> None:
    estimate = analyze_java_complexity(
        "class Search { "
        "int find(Integer[] arr, Integer target) { "
        "return binsear(arr, 0, arr.length - 1, target); } "
        "int binsear(Integer[] arr, int left, int right, Integer target) { "
        "if (right < left) return -1; "
        "int mid = left + (right - left) / 2; "
        "int comparison = arr[mid].compareTo(target); "
        "if (comparison == 0) return mid; "
        "if (comparison > 0) { return binsear(arr, left, mid - 1, target); } "
        "return binsear(arr, mid + 1, right, target); } }",
        "Search.find",
    )

    assert estimate.method == "static_java_delegated_binary_search_recurrence"
    assert estimate.estimate == "O(log n)"
    assert estimate.details["code_analysis"]["scope"] == (
        "selected entrypoint and one directly returned binary-search helper"
    )
    assert any(
        signal["kind"] == "delegated_binary_search"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_java_last_pivot_quicksort_reports_worst_case_recurrence() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void sort(int[] values, int low, int high) { "
        "if (low >= high) return; int pivot = partition(values, low, high); "
        "sort(values, low, pivot - 1); sort(values, pivot + 1, high); } "
        "int partition(int[] values, int low, int high) { int pivot = values[high]; "
        "int boundary = low - 1; for (int current = low; current < high; current++) { "
        "if (values[current] <= pivot) boundary++; } return boundary + 1; } }",
        "Solution.sort",
    )

    _assert_java_recurrence(estimate, "O(n^2)", "T(n) = T(n - 1) + O(n)")
    assert estimate.method == "static_java_worst_case_quicksort_recurrence"
    assert not any(signal["kind"] == "sorting" for signal in estimate.details["code_analysis"]["signals"])
    assert any("last array element" in assumption for assumption in estimate.details["code_analysis"]["recurrence"]["assumptions"])


def test_java_unsupported_recurrences_remain_unknown() -> None:
    irregular = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; return f(n * n); } }", "S.f"
    )
    ambiguous = analyze_java_complexity(
        "class S { int f(int n, boolean choose) { if (n <= 1) return 1; "
        "if (choose) return f(n - 1, choose); return f(n - 2, choose); } }",
        "S.f",
    )
    recursive_loop = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; "
        "for (int i = 0; i < n; i++) { f(n / 2); } return 0; } }",
        "S.f",
    )
    unsupported_branching = analyze_java_complexity(
        "class S { int f(int n) { if (n <= 1) return 1; "
        "return f(n / 2) + f(n / 2) + f(n / 2); } }",
        "S.f",
    )

    for estimate in (irregular, ambiguous, recursive_loop, unsupported_branching):
        assert estimate.estimate == "unknown (recursion detected)"
        assert "recurrence" not in estimate.details["code_analysis"]


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

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["input_size"]["vertices"] == "V"
    assert evidence["input_size"]["adjacency_entries"] == "E"
    assert "directed adjacency entries" in evidence["input_size"]["edge_count_measure"]
    assert evidence["neighbor_enumeration"]["representation"] == "adjacency_list"
    assert evidence["complexity"] == "O(V + E)"
    assert evidence["inference_kind"] == "heuristic_static_bounded_argument"


def test_recognizes_node_child_bfs_with_dequeue_time_deduplication() -> None:
    source = (
        "class Node<T> { T getValue(); List<Node<T>> getChildren(); } "
        "class Search<T> { Set<T> visitedSet = new HashSet<>(); "
        "Optional<Node<T>> search(Node<T> root, T value) { "
        "if (root == null) return Optional.empty(); "
        "visitedSet.add(root.getValue()); "
        "Queue<Node<T>> queue = new ArrayDeque<>(root.getChildren()); "
        "while (!queue.isEmpty()) { Node<T> current = queue.poll(); "
        "T currentValue = current.getValue(); "
        "if (visitedSet.contains(currentValue)) { continue; } "
        "visitedSet.add(currentValue); queue.addAll(current.getChildren()); } "
        "return Optional.empty(); } }"
    )
    near_miss = source.replace(
        "if (visitedSet.contains(currentValue)) { continue; }",
        "if (visitedSet.contains(currentValue)) { currentValue = currentValue; }",
    )

    estimate = analyze_java_complexity(source, "Search.search")
    rejected = analyze_java_complexity(near_miss, "Search.search")

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["rule_version"] == "bounded_object_bfs_v1"
    assert evidence["visited_state"]["deduplication"] == "on dequeue"
    assert evidence["visited_state"]["one_enqueue_per_vertex"] is False
    assert evidence["pending_queue_bound"].startswith("O(E)")
    assert rejected.estimate.startswith("unknown")
    assert "bfs" not in rejected.details["code_analysis"]


def test_recognizes_reviewed_java_adjacency_bfs_case_001() -> None:
    case, label = _reviewed_java_bfs_case("bfs-ind-001")
    assert hashlib.sha256(case["source"].encode()).hexdigest() == label["source_sha256"]

    estimate = analyze_java_complexity(case["source"], case["entrypoint"])

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["rule_version"] == "bounded_bfs_traversal_v2"
    assert evidence["visited_state"]["guard_kind"] == "set_add_true_condition"
    assert evidence["visited_state"]["one_enqueue_per_vertex"] is True
    assert evidence["neighbor_enumeration"]["representation"] == "adjacency_list"
    assert evidence["complexity"] == label["reviewed_complexity"]
    assert evidence["source_locations"]["neighbor_loop_line"] is not None
    assert evidence["source_locations"]["visited_guard_line"] is not None
    assert evidence["source_locations"]["neighbor_enqueue_line"] is not None


def test_recognizes_reviewed_multi_source_case_with_general_s_bound() -> None:
    case, label = _reviewed_java_bfs_case("bfs-ind-003")
    assert hashlib.sha256(case["source"].encode()).hexdigest() == label["source_sha256"]

    estimate = analyze_java_complexity(case["source"], case["entrypoint"])

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(S + V + E)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["input_size"]["start_entries"] == "S"
    assert evidence["seed_initialization"]["bound"] == "O(S)"
    assert evidence["seed_initialization"]["duplicate_starts_deduplicated"] is True
    assert evidence["complexity"] == label["reviewed_complexity"]
    assert evidence["source_locations"]["seed_loop_line"] is not None


def test_recognizes_adjacency_bfs_with_hashmap_declaration_and_braced_guard() -> None:
    estimate = analyze_java_complexity(
        "class S { void run(HashMap<Integer,List<Integer>> graph,int source) { "
        "Set<Integer> seen=new HashSet<>(); Queue<Integer> q=new ArrayDeque<>(); "
        "seen.add(source); q.add(source); while(!q.isEmpty()) { int node=q.remove(); "
        "for(int next:graph.get(node)) { if(seen.add(next)) { q.offer(next); } } } } }",
        "S.run",
    )

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["adjacency_list_evidence"]["parameter_type"] == "HashMap<Integer,List<Integer>>"
    assert evidence["visited_state"]["guard_body"] == "braced"


def test_recognizes_disconnected_components_with_one_global_visited_set() -> None:
    estimate = analyze_java_complexity(
        "class S { void all(Map<Integer,List<Integer>> graph) { "
        "Set<Integer> seen=new HashSet<>(); "
        "for(int root=0;root<graph.size();root++) { if(seen.add(root)) { "
        "Queue<Integer> q=new ArrayDeque<>(); q.add(root); while(!q.isEmpty()) { "
        "int node=q.remove(); for(int next:graph.get(node)) { "
        "if(seen.add(next)) q.add(next); } } } } } } }",
        "S.all",
    )

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["component_traversal"]["global_visited_state"] is True
    assert evidence["component_traversal"]["each_component_seeded_once"] is True


def test_unbraced_set_guard_with_wrong_queue_argument_remains_unknown() -> None:
    estimate = analyze_java_complexity(
        "class S { void run(Map<Integer,List<Integer>> graph,int source) { "
        "Set<Integer> seen=new HashSet<>(); Queue<Integer> q=new ArrayDeque<>(); "
        "seen.add(source); q.add(source); while(!q.isEmpty()) { int node=q.remove(); "
        "for(int next:graph.get(node)) if(seen.add(next)) q.add(node); } } }",
        "S.run",
    )

    assert estimate.estimate.startswith("unknown")
    assert "bfs" not in estimate.details["code_analysis"]


def test_java_adjacency_bfs_with_extra_nested_graph_scan_abstains() -> None:
    estimate = analyze_java_complexity(
        "class S { void run(Map<Integer,List<Integer>> graph,int source,int n) { "
        "Set<Integer> seen=new HashSet<>(); Queue<Integer> q=new ArrayDeque<>(); "
        "seen.add(source); q.add(source); while(!q.isEmpty()) { int node=q.remove(); "
        "for(int i=0;i<n;i++) { for(int j=0;j<n;j++) { int edge=i+j; } } "
        "for(int next:graph.get(node)) if(seen.add(next)) q.add(next); } } }",
        "S.run",
    )

    assert estimate.estimate.startswith("unknown")
    assert "bfs" not in estimate.details["code_analysis"]


def test_java_adjacency_bfs_without_marked_initial_vertex_abstains() -> None:
    estimate = analyze_java_complexity(
        "class S { void run(Map<Integer,List<Integer>> graph,int source) { "
        "Set<Integer> seen=new HashSet<>(); Queue<Integer> q=new ArrayDeque<>(); "
        "q.add(source); while(!q.isEmpty()) { int node=q.remove(); "
        "for(int next:graph.get(node)) if(seen.add(next)) q.add(next); } } }",
        "S.run",
    )

    assert estimate.estimate.startswith("unknown")
    assert "bfs" not in estimate.details["code_analysis"]


def test_java_adjacency_bfs_with_unsupported_neighbor_container_abstains() -> None:
    estimate = analyze_java_complexity(
        "class S { void run(Map<Integer,Set<Integer>> graph,int source) { "
        "Set<Integer> seen=new HashSet<>(); Queue<Integer> q=new ArrayDeque<>(); "
        "seen.add(source); q.add(source); while(!q.isEmpty()) { int node=q.remove(); "
        "for(int next:graph.get(node)) if(seen.add(next)) q.add(next); } } }",
        "S.run",
    )

    assert estimate.estimate.startswith("unknown")
    assert "bfs" not in estimate.details["code_analysis"]


def test_recognizes_java_adjacency_matrix_bfs_as_quadratic() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int reachable(boolean[][] matrix, int source) { "
        "int size = matrix.length; boolean[] visited = new boolean[size]; "
        "Queue<Integer> queue = new ArrayDeque<>(); visited[source] = true; "
        "queue.add(source); int count = 0; while (!queue.isEmpty()) { "
        "int node = queue.remove(); count++; "
        "for (int column = 0; column < size; column++) { "
        "if (matrix[node][column] && !visited[column]) { "
        "visited[column] = true; queue.add(column); } } } return count; } }",
        "Solution.reachable",
    )

    assert estimate.method == "static_java_matrix_bfs"
    assert estimate.estimate == "O(V^2)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_matrix_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["neighbor_enumeration"]["representation"] == "adjacency_matrix"
    assert evidence["input_size"]["matrix_cells"] == "V * V"


def test_matrix_bfs_without_visited_mark_before_enqueue_remains_unknown() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void walk(boolean[][] matrix, int source) { "
        "int size = matrix.length; boolean[] visited = new boolean[size]; "
        "Queue<Integer> queue = new ArrayDeque<>(); queue.add(source); "
        "while (!queue.isEmpty()) { int node = queue.remove(); "
        "for (int column = 0; column < size; column++) { "
        "if (matrix[node][column] && !visited[column]) { "
        "queue.add(column); visited[column] = true; } } } } }",
        "Solution.walk",
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"
    assert not any(
        signal["kind"] == "graph_matrix_bfs"
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

    assert estimate.method == "static_java_graph_bfs_v2"
    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_recognizes_java_grid_bfs_with_four_fixed_directions() -> None:
    estimate = analyze_java_complexity(
        "class Solution { int walk(int[][] grid, int rows, int cols, int sr, int sc) { "
        "boolean[][] seen = new boolean[rows][cols]; int[] dr = {-1,1,0,0}; "
        "int[] dc = {0,0,-1,1}; Queue<int[]> q = new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] cell=q.remove(); for(int d=0; d<4; d++) { "
        "int nr=cell[0]+dr[d]; int nc=cell[1]+dc[d]; "
        "if(nr>=0 && nr<rows && nc>=0 && nc<cols && grid[nr][nc]==1 && !seen[nr][nc]) { "
        "seen[nr][nc]=true; q.add(new int[]{nr,nc}); } } } return 0; } }",
        "Solution.walk",
    )

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O(R * C)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["pattern_id"] == "java_grid_bfs_fixed_direction_loop"
    assert evidence["neighbor_enumeration"]["fixed_neighbors_per_cell"] == 4
    assert evidence["visited_state"]["mark_before_enqueue"] is True
    assert evidence["inference_kind"] == "heuristic_static_bounded_argument"
    assert isinstance(evidence["source_locations"]["dequeue_call_token_index"], int)
    assert isinstance(evidence["source_locations"]["neighbor_enqueue_token_index"], int)


def test_java_grid_bfs_reports_a_fixed_eight_neighbor_loop() -> None:
    estimate = analyze_java_complexity(
        "class S { void walk(int[][] grid, int rows, int cols, int sr, int sc) { "
        "boolean[][] seen=new boolean[rows][cols]; int[] dr={-1,-1,-1,0,0,1,1,1}; "
        "int[] dc={-1,0,1,-1,1,-1,0,1}; Queue<int[]> q=new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] cell=q.removeFirst(); for(int d=0;d<8;d++) { int nr=cell[0]+dr[d]; "
        "int nc=cell[1]+dc[d]; if(nr>=0 && nr<rows && nc>=0 && nc<cols "
        "&& grid[nr][nc]==1 && !seen[nr][nc]) { seen[nr][nc]=true; "
        "q.add(new int[]{nr,nc}); } } } } }",
        "S.walk",
    )

    assert estimate.estimate == "O(R * C)"
    assert estimate.details["code_analysis"]["bfs"]["neighbor_enumeration"][
        "fixed_neighbors_per_cell"
    ] == 8


def test_java_grid_bfs_counts_unbraced_full_grid_scan_inside_neighbor_guard() -> None:
    estimate = analyze_java_complexity(
        "import java.util.*; class GridScan { int run(int[][] a,int sr,int sc) { "
        "int r=a.length,c=a[0].length; boolean[][] seen=new boolean[r][c]; "
        "int[] dr={1,0,-1,0},dc={0,1,0,-1}; Queue<int[]> q=new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] p=q.remove(); for(int d=0;d<4;d++) { int x=p[0]+dr[d],y=p[1]+dc[d]; "
        "if(x>=0&&x<r&&y>=0&&y<c) { for(int i=0;i<r;i++) "
        "for(int j=0;j<c;j++) inspect(a[i][j]); "
        "if(!seen[x][y]) { seen[x][y]=true; q.add(new int[]{x,y}); } } "
        "} } return 0; } void inspect(int x) {} }",
        "GridScan.run",
    )

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O((R * C)^2)"


def test_java_graph_bfs_inside_outer_loop_is_not_flattened_to_single_pass() -> None:
    estimate = analyze_java_complexity(
        "class S { void all(Map<Integer,List<Integer>> graph, int n) { "
        "for(int start=0; start<n; start++) { Set<Integer> seen=new HashSet<>(); "
        "Queue<Integer> q=new ArrayDeque<>(); seen.add(start); q.add(start); "
        "while(!q.isEmpty()) { int node=q.poll(); for(int v:graph.get(node)) "
        "if(seen.add(v)) q.add(v); } } } }",
        "S.all",
    )

    assert estimate.estimate != "O(V + E)"
    assert "bfs" not in estimate.details["code_analysis"]


def test_java_grid_bfs_inside_outer_loop_is_not_flattened_to_one_traversal() -> None:
    estimate = analyze_java_complexity(
        "class S { void all(int[][] grid,int rows,int cols) { "
        "for(int s=0;s<rows;s++) { boolean[][] seen=new boolean[rows][cols]; "
        "Queue<int[]> q=new ArrayDeque<>(); seen[s][0]=true; q.add(new int[]{s,0}); "
        "while(!q.isEmpty()) { int[] cell=q.remove(); for(int d=0;d<4;d++) { "
        "int nr=cell[0]+dr[d], nc=cell[1]+dc[d]; if(nr>=0 && nr<rows && nc>=0 "
        "&& nc<cols && grid[nr][nc]==1 && !seen[nr][nc]) { seen[nr][nc]=true; "
        "q.add(new int[]{nr,nc}); } } } } } }",
        "S.all",
    )

    assert estimate.estimate != "O(R * C)"
    assert "bfs" not in estimate.details["code_analysis"]


def test_frozen_java_grid_full_scan_case_accounts_for_nested_work() -> None:
    root = Path(__file__).resolve().parents[3]
    dataset = root / "evaluation/mode1/bfs-independent-2026-10-29-v1"
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text().splitlines()]
    labels = [
        json.loads(line) for line in (dataset / "gold-provisional.jsonl").read_text().splitlines()
    ]
    case = next(row for row in cases if row["id"] == "bfs-ind-010")
    label = next(row for row in labels if row["id"] == case["id"])
    source_hash = hashlib.sha256(case["source"].encode()).hexdigest()

    assert source_hash == "9d75899b2760a19d3aa3d6ac3287e3f3a784e04d7c9c898093c7314753a67551"
    assert source_hash == case["source_sha256"] == label["source_sha256"]
    assert label["time_complexity"] == "O((R * C)^2)"

    estimate = analyze_java_complexity(case["source"], case["entrypoint"])

    assert estimate.estimate != "O(R * C)"
    if estimate.estimate == "O((R * C)^2)":
        evidence = estimate.details["code_analysis"]["bfs"]
        scan = evidence["additional_grid_scans"][0]
        assert evidence["complexity"] == "O((R * C)^2)"
        assert scan["placement"] == "inside_neighbor_processing"
        assert scan["estimated_cost"] == "O(R*C)"
        assert evidence["loop_costs"]["neighbor_enumeration"] == (
            "O(1) per dequeued cell (4 fixed directions)"
        )
        assert scan["source_locations"]["row_loop_line"] is not None
        assert scan["source_locations"]["column_loop_line"] is not None
        assert evidence["aggregate_work"] == (
            "O(R*C) dequeued cells * O(R*C) full-grid work per cell = O((R*C)^2)"
        )
    else:
        assert estimate.estimate.startswith("unknown")


def test_java_grid_full_scan_once_before_bfs_remains_linear() -> None:
    source = (
        "class S { void walk(int[][] grid,int rows,int cols,int sr,int sc) { "
        "for(int r=0;r<rows;r++) { for(int c=0;c<cols;c++) { int x=grid[r][c]; } } "
        "boolean[][] seen=new boolean[rows][cols]; int[] dr={-1,1,0,0}; "
        "int[] dc={0,0,-1,1}; Queue<int[]> q=new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] p=q.remove(); for(int d=0;d<4;d++) { int nr=p[0]+dr[d], nc=p[1]+dc[d]; "
        "if(nr>=0 && nr<rows && nc>=0 && nc<cols && grid[nr][nc]==1 && !seen[nr][nc]) { "
        "seen[nr][nc]=true; q.add(new int[]{nr,nc}); } } } } }"
    )

    estimate = analyze_java_complexity(source, "S.walk")

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O(R * C)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["additional_grid_scans"][0]["placement"] == "outside_traversal"
    assert evidence["aggregate_work"] == (
        "O(R*C) pre/post traversal scan + O(R*C) bounded BFS = O(R*C)"
    )


def test_java_grid_full_scan_per_dequeued_cell_is_quadratic() -> None:
    source = (
        "class S { void walk(int[][] grid,int rows,int cols,int sr,int sc) { "
        "boolean[][] seen=new boolean[rows][cols]; int[] dr={-1,1,0,0}; "
        "int[] dc={0,0,-1,1}; Queue<int[]> q=new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] p=q.remove(); for(int r=0;r<rows;r++) { for(int c=0;c<cols;c++) { "
        "int x=grid[r][c]; } } for(int d=0;d<4;d++) { int nr=p[0]+dr[d], nc=p[1]+dc[d]; "
        "if(nr>=0 && nr<rows && nc>=0 && nc<cols && grid[nr][nc]==1 && !seen[nr][nc]) { "
        "seen[nr][nc]=true; q.add(new int[]{nr,nc}); } } } } }"
    )

    estimate = analyze_java_complexity(source, "S.walk")

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O((R * C)^2)"
    scan = estimate.details["code_analysis"]["bfs"]["additional_grid_scans"][0]
    assert scan["placement"] == "inside_queue_processing"
    assert estimate.details["code_analysis"]["bfs"]["aggregate_work"] == (
        "O(R*C) dequeued cells * O(R*C) full-grid work per cell = O((R*C)^2)"
    )


def test_java_grid_ambiguous_nested_loop_abstains() -> None:
    source = (
        "class S { void walk(int[][] grid,int rows,int cols,int sr,int sc,int limit) { "
        "boolean[][] seen=new boolean[rows][cols]; int[] dr={-1,1,0,0}; "
        "int[] dc={0,0,-1,1}; Queue<int[]> q=new ArrayDeque<>(); "
        "seen[sr][sc]=true; q.add(new int[]{sr,sc}); while(!q.isEmpty()) { "
        "int[] p=q.remove(); for(int d=0;d<4;d++) { "
        "for(int k=0;k<limit;k++) { consume(k); } int nr=p[0]+dr[d], nc=p[1]+dc[d]; "
        "if(nr>=0 && nr<rows && nc>=0 && nc<cols && grid[nr][nc]==1 && !seen[nr][nc]) { "
        "seen[nr][nc]=true; q.add(new int[]{nr,nc}); } } } } }"
    )

    estimate = analyze_java_complexity(source, "S.walk")

    assert estimate.estimate.startswith("unknown")
    assert "bfs" not in estimate.details["code_analysis"]


def test_java_matrix_bfs_without_visited_marking_stays_inconclusive() -> None:
    estimate = analyze_java_complexity(
        "class Solution { void traverse(boolean[][] adjacency, int start) { "
        "int size = adjacency.length; boolean[] seen = new boolean[size]; "
        "Queue<Integer> queue = new ArrayDeque<>(); queue.add(start); "
        "while (!queue.isEmpty()) { int node = queue.remove(); "
        "for (int neighbor = 0; neighbor < size; neighbor++) { "
        "if (adjacency[node][neighbor] && !seen[neighbor]) { "
        "queue.add(neighbor); } } } } }",
        "Solution.traverse",
    )

    assert estimate.estimate == "unknown (data-dependent or incomplete loop)"
    assert not any(
        signal["kind"] == "graph_matrix_bfs"
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


def test_java_grid_bfs_supports_local_dimension_aliases() -> None:
    estimate = analyze_java_complexity(
        "class Board { void traverse(int[][] cells, int sr, int sc) { "
        "int height = cells.length, width = cells[0].length; "
        "boolean[][] marked = new boolean[height][width]; "
        "int[] dr = {-1, 1, 0, 0}, dc = {0, 0, -1, 1}; "
        "ArrayDeque<int[]> pending = new ArrayDeque<>(); "
        "marked[sr][sc] = true; pending.addLast(new int[]{sr, sc}); "
        "while (!pending.isEmpty()) { int[] point = pending.remove(); "
        "for (int direction = 0; direction < 4; direction++) { "
        "int nr = point[0] + dr[direction], nc = point[1] + dc[direction]; "
        "if (nr >= 0 && nr < height && nc >= 0 && nc < width "
        "&& cells[nr][nc] != 0 && !marked[nr][nc]) { "
        "marked[nr][nc] = true; pending.addLast(new int[]{nr, nc}); } } } } }",
        "Board.traverse",
    )

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O(R * C)"
    assert estimate.details["code_analysis"]["bfs"]["input_size"] == {
        "rows": "R",
        "columns": "C",
    }


def test_java_grid_bfs_costs_repeated_scan_with_dimension_aliases() -> None:
    estimate = analyze_java_complexity(
        "class Board { void traverse(int[][] cells, int sr, int sc) { "
        "int height = cells.length, width = cells[0].length; "
        "boolean[][] marked = new boolean[height][width]; "
        "int[] dr = {-1, 1, 0, 0}, dc = {0, 0, -1, 1}; "
        "ArrayDeque<int[]> pending = new ArrayDeque<>(); "
        "marked[sr][sc] = true; pending.add(new int[]{sr, sc}); "
        "while (!pending.isEmpty()) { int[] point = pending.remove(); "
        "for (int direction = 0; direction < 4; direction++) { "
        "int nr = point[0] + dr[direction], nc = point[1] + dc[direction]; "
        "if (nr >= 0 && nr < height && nc >= 0 && nc < width "
        "&& cells[nr][nc] != 0 && !marked[nr][nc]) { "
        "for (int row = 0; row < height; row++) { "
        "for (int col = 0; col < width; col++) { inspect(cells[row][col]); } } "
        "marked[nr][nc] = true; "
        "pending.add(new int[]{nr, nc}); } } } } } "
        "void inspect(int cell) {} }",
        "Board.traverse",
    )

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O((R * C)^2)"
    scan = estimate.details["code_analysis"]["bfs"]["additional_grid_scans"][0]
    assert scan["row_bound"] == "height"
    assert scan["column_bound"] == "width"


def test_java_grid_bfs_does_not_trust_unverified_column_dimension_alias() -> None:
    estimate = analyze_java_complexity(
        "class Board { void traverse(int[][] cells, int sr, int sc) { "
        "int height = cells.length, width = cells.length; "
        "boolean[][] marked = new boolean[height][width]; "
        "ArrayDeque<int[]> pending = new ArrayDeque<>(); "
        "marked[sr][sc] = true; pending.add(new int[]{sr, sc}); "
        "while (!pending.isEmpty()) { int[] point = pending.remove(); "
        "for (int direction = 0; direction < 4; direction++) { "
        "int nr = point[0], nc = point[1]; "
        "if (nr >= 0 && nr < height && nc >= 0 && nc < width "
        "&& cells[nr][nc] != 0 && !marked[nr][nc]) { "
        "marked[nr][nc] = true; pending.add(new int[]{nr, nc}); } } } } }",
        "Board.traverse",
    )

    assert estimate.estimate.startswith("unknown")


def test_matrix_bfs_supports_unbraced_neighbor_loop_with_guard_block() -> None:
    estimate = analyze_java_complexity(
        "class Network { int reachable(boolean[][] links, int root) { "
        "int order = links.length; boolean[] done = new boolean[order]; "
        "ArrayDeque<Integer> work = new ArrayDeque<>(); done[root] = true; "
        "work.add(root); while (!work.isEmpty()) { int vertex = work.removeFirst(); "
        "for (int candidate = 0; candidate < order; candidate++) "
        "if (links[vertex][candidate] && !done[candidate]) { "
        "done[candidate] = true; work.addLast(candidate); } } return 0; } }",
        "Network.reachable",
    )

    assert estimate.method == "static_java_matrix_bfs"
    assert estimate.estimate == "O(V^2)"


def test_unbraced_matrix_bfs_with_enqueue_before_marking_stays_unknown() -> None:
    estimate = analyze_java_complexity(
        "class Network { void traverse(boolean[][] links, int root) { "
        "int order = links.length; boolean[] done = new boolean[order]; "
        "ArrayDeque<Integer> work = new ArrayDeque<>(); work.add(root); "
        "while (!work.isEmpty()) { int vertex = work.removeFirst(); "
        "for (int candidate = 0; candidate < order; candidate++) "
        "if (links[vertex][candidate] && !done[candidate]) { "
        "work.addLast(candidate); done[candidate] = true; } } } }",
        "Network.traverse",
    )

    assert estimate.estimate.startswith("unknown")


def _java_grid_scan_before_visited_source() -> str:
    return (
        "class Board { void explore(int[][] cells, int sr, int sc) { "
        "int height = cells.length, width = cells[0].length; "
        "boolean[][] seen = new boolean[height][width]; "
        "int[] dr = {1, 0, -1, 0}, dc = {0, 1, 0, -1}; "
        "ArrayDeque<int[]> queue = new ArrayDeque<>(); "
        "seen[sr][sc] = true; queue.add(new int[]{sr, sc}); "
        "while (!queue.isEmpty()) { int[] point = queue.remove(); "
        "for (int direction = 0; direction < 4; direction++) { "
        "int nr = point[0] + dr[direction], nc = point[1] + dc[direction]; "
        "if (nr >= 0 && nr < height && nc >= 0 && nc < width) { "
        "for (int row = 0; row < height; row++) { "
        "for (int col = 0; col < width; col++) { inspect(cells[row][col]); } } "
        "if (!seen[nr][nc]) { seen[nr][nc] = true; "
        "queue.add(new int[]{nr, nc}); } } } } } "
        "void inspect(int cell) {} }"
    )


def test_java_grid_bfs_costs_scan_before_separate_visited_guard() -> None:
    estimate = analyze_java_complexity(_java_grid_scan_before_visited_source(), "Board.explore")

    assert estimate.method == "static_java_grid_bfs_v2"
    assert estimate.estimate == "O((R * C)^2)"


def test_java_grid_scan_before_visited_requires_complete_neighbor_bounds() -> None:
    source = _java_grid_scan_before_visited_source().replace(
        "if (nr >= 0 && nr < height && nc >= 0 && nc < width)",
        "if (nr < height && nc >= 0 && nc < width)",
    )
    estimate = analyze_java_complexity(
        source,
        "Board.explore",
    )

    assert estimate.estimate.startswith("unknown")


def test_java_grid_scan_with_non_neighbor_offsets_stays_unknown() -> None:
    source = _java_grid_scan_before_visited_source().replace(
        "int[] dr = {1, 0, -1, 0}, dc = {0, 1, 0, -1};",
        "int[] dr = {0, 0, 0, 0}, dc = {0, 0, 0, 0};",
    )
    estimate = analyze_java_complexity(source, "Board.explore")

    assert estimate.estimate.startswith("unknown")
