from axioma_api.contracts import ConstraintRange
from axioma_worker.python_complexity import (
    add_opcode_count_fit,
    add_line_event_fit,
    analyze_python_complexity,
    estimate_constraint_scale,
    estimate_python_peak_memory,
    triangulate_python_complexity,
)


def test_complexity_estimator_uses_maximum_nested_loop_depth() -> None:
    estimate = analyze_python_complexity(
        "def solve(values):\n    for x in values:\n        for y in values:\n            print(x, y)\n",
        "solve",
    )

    assert estimate.estimate == "O(n^2)"
    assert estimate.confidence == "low"
    assert estimate.methods_disagree is False


def test_complexity_estimator_accounts_for_sort_and_recursion_limits() -> None:
    sorted_case = analyze_python_complexity(
        "def solve(values):\n    return sorted(values)\n", "solve"
    )
    recursive_case = analyze_python_complexity("def solve(n):\n    return solve(n - 1)\n", "solve")

    assert sorted_case.estimate == "O(n log n)"
    assert recursive_case.estimate == "unknown (recursion detected)"


def test_complexity_estimator_counts_iterable_consuming_builtins() -> None:
    estimate = analyze_python_complexity(
        "def solve(values):\n    return sum(values)\n", "solve"
    )

    assert estimate.estimate == "O(n)"
    assert "iterable-consuming built-in" in estimate.explanation


def test_recognizes_binary_search_as_logarithmic() -> None:
    estimate = analyze_python_complexity(
        "def solve(values, target):\n"
        "    low, high = 0, len(values) - 1\n"
        "    while low <= high:\n"
        "        middle = (low + high) // 2\n"
        "        if values[middle] == target: return middle\n"
        "        if values[middle] < target: low = middle + 1\n"
        "        else: high = middle - 1\n"
        "    return -1\n",
        "solve",
    )

    assert estimate.estimate == "O(log n)"
    assert estimate.confidence == "low"
    assert any(signal["kind"] == "binary_search" for signal in estimate.details["code_analysis"]["signals"])


def test_recognizes_lower_bound_binary_search_and_bisect() -> None:
    lower_bound = analyze_python_complexity(
        "def solve(values, target):\n"
        "    left, right = 0, len(values)\n"
        "    while left < right:\n"
        "        mid = (left + right) // 2\n"
        "        if values[mid] < target: left = mid + 1\n"
        "        else: right = mid\n"
        "    return left\n",
        "solve",
    )
    bisect = analyze_python_complexity(
        "from bisect import bisect_left\n"
        "def solve(values, target): return bisect_left(values, target)\n",
        "solve",
    )

    assert lower_bound.estimate == "O(log n)"
    assert bisect.estimate == "O(log n)"
    assert any(
        signal["kind"] == "binary_search"
        for signal in bisect.details["code_analysis"]["signals"]
    )


def test_fixed_bound_loops_do_not_inflate_input_growth() -> None:
    fixed = analyze_python_complexity(
        "def solve():\n"
        "    for hour in range(12):\n"
        "        for minute in range(60):\n"
        "            pass\n",
        "solve",
    )
    mixed = analyze_python_complexity(
        "def solve(values):\n"
        "    for value in values:\n"
        "        for option in range(4):\n"
        "            pass\n",
        "solve",
    )

    assert fixed.estimate.startswith("O(1)")
    assert fixed.details["code_analysis"]["maximum_data_dependent_loop_nesting"] == 0
    assert mixed.estimate == "O(n)"


def test_recognizes_amortized_monotonic_stack_scan() -> None:
    estimate = analyze_python_complexity(
        "def solve(values):\n"
        "    stack = []\n"
        "    for value in values:\n"
        "        while stack and stack[-1] < value:\n"
        "            stack.pop()\n"
        "        stack.append(value)\n"
        "    return stack\n",
        "solve",
    )

    assert estimate.estimate == "O(n)"
    assert any(
        signal["kind"] == "amortized_stack_scan"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_recognizes_kahn_topological_sort() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(graph, indegree):\n"
        "    queue = deque(i for i, degree in enumerate(indegree) if degree == 0)\n"
        "    while queue:\n"
        "        node = queue.popleft()\n"
        "        for neighbor in graph[node]:\n"
        "            indegree[neighbor] -= 1\n"
        "            if indegree[neighbor] == 0: queue.append(neighbor)\n"
        "    return []\n",
        "solve",
    )

    assert estimate.estimate == "O(V + E)"
    assert any(
        signal["kind"] == "topological_sort"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_memoized_recursive_state_is_estimated_by_state_dimensions() -> None:
    estimate = analyze_python_complexity(
        "from functools import cache\n"
        "def solve(rows, cols):\n"
        "    @cache\n"
        "    def dfs(i, j):\n"
        "        if i == rows or j == cols: return 0\n"
        "        return 1 + dfs(i + 1, j) + dfs(i, j + 1)\n"
        "    return dfs(0, 0)\n",
        "solve",
    )

    assert estimate.estimate == "O(n^2)"
    assert any(
        signal["kind"] == "memoized_recursion"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unrecognized_nested_recursive_helper_is_not_called_constant() -> None:
    estimate = analyze_python_complexity(
        "def solve(first, second):\n"
        "    def compare(i, j):\n"
        "        if i == len(first) or j == len(second): return 0\n"
        "        return compare(i + 1, j + 1)\n"
        "    return compare(0, 0)\n",
        "solve",
    )

    assert estimate.estimate == "unknown (recursion detected)"


def test_recognizes_sort_then_two_pointer_scan() -> None:
    estimate = analyze_python_complexity(
        "def solve(nums):\n"
        "    nums.sort()\n"
        "    left, right = 0, len(nums) - 1\n"
        "    while left < right:\n"
        "        total = nums[left] + nums[right]\n"
        "        if total < 0: left += 1\n"
        "        else: right -= 1\n"
        "    return False\n",
        "solve",
    )

    assert estimate.estimate == "O(n log n)"
    assert estimate.method == "static_ast_sort_two_pointer_scan"


def test_recognizes_floyd_cycle_detection() -> None:
    estimate = analyze_python_complexity(
        "def solve(head):\n"
        "    slow = fast = head\n"
        "    while fast and fast.next:\n"
        "        slow = slow.next\n"
        "        fast = fast.next.next\n"
        "        if slow is fast: return True\n"
        "    return False\n",
        "solve",
    )

    assert estimate.estimate == "O(n)"
    assert estimate.method == "static_ast_floyd_cycle_detection"


def test_recognizes_local_recursive_graph_dfs() -> None:
    estimate = analyze_python_complexity(
        "def solve(graph, start):\n"
        "    seen = set()\n"
        "    def visit(node):\n"
        "        if node in seen: return\n"
        "        seen.add(node)\n"
        "        for neighbor in graph[node]:\n"
        "            visit(neighbor)\n"
        "    visit(start)\n"
        "    return seen\n",
        "solve",
    )

    assert estimate.estimate == "O(V + E)"
    assert any(
        signal["kind"] == "graph_dfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_recognizes_matrix_staircase_search() -> None:
    estimate = analyze_python_complexity(
        "def solve(matrix, target):\n"
        "    row, col = 0, len(matrix[0]) - 1\n"
        "    while row < len(matrix) and col >= 0:\n"
        "        value = matrix[row][col]\n"
        "        if value > target: col -= 1\n"
        "        else: row += 1\n"
        "    return False\n",
        "solve",
    )

    assert estimate.estimate == "O(m + n)"
    assert estimate.method == "static_ast_matrix_staircase_search"


def test_recognizes_heap_pops_and_character_trie_build() -> None:
    heap_case = analyze_python_complexity(
        "import heapq\n"
        "def solve(nums, k):\n"
        "    heap = nums[:]\n"
        "    heapq.heapify(heap)\n"
        "    for _ in range(min(k, len(heap))):\n"
        "        heapq.heappop(heap)\n"
        "    return heap\n",
        "solve",
    )
    trie_case = analyze_python_complexity(
        "def solve(words):\n"
        "    root = {}\n"
        "    for word in words:\n"
        "        node = root\n"
        "        for char in word:\n"
        "            node = node.setdefault(char, {})\n"
        "    return root\n",
        "solve",
    )

    assert heap_case.estimate == "O(n log n)"
    assert trie_case.estimate == "O(n)"


def test_recognizes_ternary_search_and_fenwick_prefix_loops() -> None:
    ternary = analyze_python_complexity(
        "def solve(left, right, score):\n"
        "    while right - left > 2:\n"
        "        third = (right - left) // 3\n"
        "        first, second = left + third, right - third\n"
        "        if score(first) < score(second): left = first\n"
        "        else: right = second\n"
        "    return left\n",
        "solve",
    )
    fenwick = analyze_python_complexity(
        "def solve(values, index):\n"
        "    total = 0\n"
        "    while index > 0:\n"
        "        index -= index & -index\n"
        "        total += values[index]\n"
        "    return total\n",
        "solve",
    )

    assert ternary.estimate == "O(log n)"
    assert fenwick.estimate == "O(log n)"


def test_recognizes_heap_based_graph_traversal_and_z_algorithm() -> None:
    dijkstra = analyze_python_complexity(
        "import heapq\n"
        "def solve(graph, start):\n"
        "    distance = {start: 0}\n"
        "    heap = [(0, start)]\n"
        "    while heap:\n"
        "        cost, node = heapq.heappop(heap)\n"
        "        for neighbor, weight in graph[node]:\n"
        "            new_cost = cost + weight\n"
        "            if new_cost < distance.get(neighbor, float('inf')):\n"
        "                distance[neighbor] = new_cost\n"
        "                heapq.heappush(heap, (new_cost, neighbor))\n"
        "    return distance\n",
        "solve",
    )
    z_algorithm = analyze_python_complexity(
        "def solve(text):\n"
        "    n = len(text)\n"
        "    z = [0] * n\n"
        "    left = right = 0\n"
        "    for i in range(1, n):\n"
        "        while i + z[i] < n and text[z[i]] == text[i + z[i]]:\n"
        "            z[i] += 1\n"
        "        if i + z[i] - 1 > right:\n"
        "            left, right = i, i + z[i] - 1\n"
        "    return z\n",
        "solve",
    )

    assert dijkstra.estimate == "O((V + E) log V)"
    assert z_algorithm.estimate == "O(n)"


def test_unrecognized_data_dependent_loop_remains_unknown() -> None:
    estimate = analyze_python_complexity(
        "def solve(value):\n    while value > 0:\n        value -= 3\n", "solve"
    )

    assert estimate.estimate == "unknown (data-dependent loop bound)"


def test_recognizes_adjacency_list_bfs_with_queue_and_visited_guard() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(graph, start):\n"
        "    visited = {start}\n"
        "    queue = deque([start])\n"
        "    while queue:\n"
        "        node = queue.popleft()\n"
        "        for neighbor in graph[node]:\n"
        "            if neighbor not in visited:\n"
        "                visited.add(neighbor)\n"
        "                queue.append(neighbor)\n",
        "solve",
    )

    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_bfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unvisited_adjacency_queue_loop_remains_unknown() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(graph, start):\n"
        "    queue = deque([start])\n"
        "    while queue:\n"
        "        node = queue.popleft()\n"
        "        for neighbor in graph[node]:\n"
        "            queue.append(neighbor)\n",
        "solve",
    )

    assert estimate.estimate == "unknown (data-dependent loop bound)"


def test_recognizes_recursive_binary_tree_walk() -> None:
    estimate = analyze_python_complexity(
        "def solve(node):\n"
        "    if node is None: return 0\n"
        "    return 1 + solve(node.left) + solve(node.right)\n",
        "solve",
    )

    assert estimate.estimate == "O(n)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "tree_recursion"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_recognizes_recursive_adjacency_list_dfs() -> None:
    estimate = analyze_python_complexity(
        "def solve(graph, node, visited):\n"
        "    for neighbor in graph[node]:\n"
        "        if neighbor not in visited:\n"
        "            visited.add(neighbor)\n"
        "            solve(graph, neighbor, visited)\n",
        "solve",
    )

    assert estimate.estimate == "O(V + E)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "graph_dfs"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_unrecognized_recursive_recurrence_remains_unknown() -> None:
    estimate = analyze_python_complexity(
        "def solve(n):\n"
        "    if n < 2: return n\n"
        "    return solve(n - 1) + solve(n - 2)\n",
        "solve",
    )

    assert estimate.estimate == "unknown (recursion detected)"


def test_code_analysis_exposes_python_patterns_and_source_lines() -> None:
    estimate = analyze_python_complexity(
        "def solve(values, target):\n"
        "    seen = set()\n"
        "    for value in values:\n"
        "        if target - value in seen:\n"
        "            return True\n"
        "        seen.add(value)\n"
        "    return False\n",
        "solve",
    )

    analysis = estimate.details["code_analysis"]
    signals = analysis["signals"]
    assert analysis["language"] == "python"
    assert analysis["loop_count"] == 1
    assert any(signal["kind"] == "loop" and signal["line"] == 3 for signal in signals)
    assert any(signal["kind"] == "membership" and signal["line"] == 4 for signal in signals)
    assert any(signal["kind"] == "collection_operation" and signal["line"] == 6 for signal in signals)


def test_complexity_estimator_reports_unavailable_entrypoint() -> None:
    estimate = analyze_python_complexity("def other(): pass", "solve")

    assert estimate.estimate == "unknown (entrypoint not found)"


def test_line_event_fit_compares_coarse_growth_and_keeps_raw_points() -> None:
    static = analyze_python_complexity(
        "def solve(value):\n    for item in range(value):\n        pass\n", "solve"
    )
    measured = add_line_event_fit(
        static,
        [
            {"size": 10, "line_events": 30},
            {"size": 20, "line_events": 60},
            {"size": 40, "line_events": 120},
            {"size": 80, "line_events": 240},
        ],
    )

    assert measured.method == "static_ast_loop_depth+dynamic_line_event_fit"
    assert measured.methods_disagree is False
    assert measured.confidence == "low"
    assert measured.details["measurement_method"] == "executed_source_line_events"
    assert measured.details["code_analysis"]["language"] == "python"
    assert len(measured.details["points"]) == 4


def test_line_event_fit_flags_disagreement_with_static_estimate() -> None:
    static = analyze_python_complexity("def solve(value): return value + 1", "solve")
    measured = add_line_event_fit(
        static,
        [
            {"size": 10, "line_events": 10},
            {"size": 20, "line_events": 40},
            {"size": 40, "line_events": 160},
            {"size": 80, "line_events": 640},
        ],
    )

    assert measured.methods_disagree is True
    assert "static O(1)" in measured.estimate
    assert "measured line-event fit O(n^2)" in measured.estimate
    assert measured.details["goodness_of_fit_r2"] == 1.0


def test_opcode_fit_is_reported_separately_from_line_event_fit() -> None:
    static = analyze_python_complexity(
        "def solve(values):\n    for value in values:\n        pass\n", "solve"
    )
    points = [
        {"size": 10, "line_events": 10, "opcode_events": 100},
        {"size": 20, "line_events": 20, "opcode_events": 400},
        {"size": 40, "line_events": 40, "opcode_events": 1600},
        {"size": 80, "line_events": 80, "opcode_events": 6400},
    ]

    opcode_fit = add_opcode_count_fit(static, points)
    triangulated = triangulate_python_complexity(static, points)

    assert opcode_fit.method.endswith("+dynamic_opcode_count_fit")
    assert opcode_fit.details["measurement_method"] == "executed_python_opcode_count"
    assert opcode_fit.details["fit"] == "O(n^2)"
    assert triangulated.methods_disagree is True
    assert triangulated.details["signals"]["line_event_fit"]["estimate"] == "O(n)"
    assert triangulated.details["signals"]["opcode_count_fit"]["estimate"] == "O(n^2)"


def test_constraint_scale_estimate_uses_declared_collection_maximum() -> None:
    result = estimate_constraint_scale(
        [ConstraintRange(path="args[0].length", minimum=0, maximum=1000)], "O(n^2)"
    )

    assert result["state"] == "estimated"
    assert result["rough_growth_scale"] == "about 1000000 growth units"
    assert result["confidence"] == "low"


def test_constraint_scale_does_not_infer_size_from_scalar_ranges() -> None:
    result = estimate_constraint_scale(
        [ConstraintRange(path="args[0]", minimum=0, maximum=1000)], "O(n)"
    )

    assert result["state"] == "not_estimated"


def test_peak_traced_memory_fit_is_separate_from_time_method_disagreement() -> None:
    points = [
        {"size": size, "peak_traced_bytes": size * 16}
        for size in (10, 20, 40, 80)
    ]

    result = estimate_python_peak_memory(points)

    assert result["method"] == "python_tracemalloc_peak_fit"
    assert result["state"] == "estimated"
    assert result["estimate"] == "O(n)"
    assert result["confidence"] == "low"
    assert len(result["points"]) == 4


def test_peak_traced_memory_fit_requires_four_sizes() -> None:
    result = estimate_python_peak_memory([{"size": 10, "peak_traced_bytes": 100}])

    assert result["state"] == "not_estimated"


def test_peak_traced_memory_does_not_fit_when_every_observation_is_zero() -> None:
    points = [{"size": size, "peak_traced_bytes": 0} for size in (10, 20, 40, 80)]

    result = estimate_python_peak_memory(points)

    assert result["state"] == "not_estimated"
    assert "No positive" in result["reason"]


def test_peak_traced_memory_does_not_fit_flat_or_decreasing_noise() -> None:
    points = [
        {"size": 32, "peak_traced_bytes": 6842},
        {"size": 64, "peak_traced_bytes": 6690},
        {"size": 128, "peak_traced_bytes": 6530},
        {"size": 256, "peak_traced_bytes": 6362},
    ]

    result = estimate_python_peak_memory(points)

    assert result["state"] == "not_estimated"
    assert "measurement noise" in result["reason"]
