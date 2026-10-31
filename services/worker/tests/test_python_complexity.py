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


def test_recognizes_insertion_sort_and_rejects_shift_near_miss() -> None:
    source = (
        "def solve(collection):\n"
        "    for insert_index in range(1, len(collection)):\n"
        "        insert_value = collection[insert_index]\n"
        "        while insert_index > 0 and insert_value < collection[insert_index - 1]:\n"
        "            collection[insert_index] = collection[insert_index - 1]\n"
        "            insert_index -= 1\n"
        "        collection[insert_index] = insert_value\n"
        "    return collection\n"
    )
    estimate = analyze_python_complexity(source, "solve")
    near_miss = analyze_python_complexity(
        source.replace("            collection[insert_index] = collection[insert_index - 1]\n", ""),
        "solve",
    )

    assert estimate.method == "static_ast_insertion_sort"
    assert estimate.estimate == "O(n^2)"
    assert estimate.confidence == "low"
    assert any(
        signal["kind"] == "insertion_sort"
        for signal in estimate.details["code_analysis"]["signals"]
    )
    assert near_miss.estimate == "unknown (data-dependent loop bound)"
    assert near_miss.method == "static_ast_loop_depth"


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


def test_recognizes_permutation_and_binary_recursive_search() -> None:
    permutations = analyze_python_complexity(
        "def solve(nums):\n"
        "    result, path = [], []\n"
        "    used = [False] * len(nums)\n"
        "    def build():\n"
        "        if len(path) == len(nums): result.append(path[:]); return\n"
        "        for i, value in enumerate(nums):\n"
        "            if not used[i]:\n"
        "                used[i] = True; path.append(value); build(); path.pop(); used[i] = False\n"
        "    build()\n"
        "    return result\n",
        "solve",
    )
    subset_search = analyze_python_complexity(
        "def solve(nums, target):\n"
        "    def search(index, total):\n"
        "        if index == len(nums): return total == target\n"
        "        return search(index + 1, total) or search(index + 1, total + nums[index])\n"
        "    return search(0, 0)\n",
        "solve",
    )

    assert permutations.estimate.startswith("O(n * n!)")
    assert subset_search.estimate.startswith("O(2^n)")


def test_recognizes_recursive_halving_in_local_helper() -> None:
    estimate = analyze_python_complexity(
        "def solve(nums1, nums2):\n"
        "    def kth(i, j, k):\n"
        "        if k == 1: return min(nums1[i], nums2[j])\n"
        "        p = k // 2\n"
        "        x, y = nums1[i + p], nums2[j + p]\n"
        "        return kth(i + p, j, k - p) if x < y else kth(i, j + p, k - p)\n"
        "    return kth(0, 0, len(nums1) + len(nums2))\n",
        "solve",
    )

    assert estimate.estimate == "O(log n)"
    assert estimate.method == "static_ast_divide_and_conquer_recursion"


def test_recognizes_accumulated_cartesian_product_expansion() -> None:
    estimate = analyze_python_complexity(
        "def solve(digits):\n"
        "    choices = ['abc', 'def', 'ghi']\n"
        "    answers = ['']\n"
        "    for digit in digits:\n"
        "        letters = choices[int(digit) % 3]\n"
        "        answers = [prefix + letter for prefix in answers for letter in letters]\n"
        "    return answers\n",
        "solve",
    )

    assert estimate.estimate.startswith("O(2^n)")
    assert estimate.method == "static_ast_cartesian_product"


def test_recognizes_cached_matrix_recursion_with_fixed_neighbor_scan() -> None:
    estimate = analyze_python_complexity(
        "from functools import cache\n"
        "from itertools import pairwise\n"
        "def solve(matrix):\n"
        "    @cache\n"
        "    def dfs(i, j):\n"
        "        best = 0\n"
        "        for a, b in pairwise((-1, 0, 1, 0, -1)):\n"
        "            x, y = i + a, j + b\n"
        "            if 0 <= x < rows and 0 <= y < cols and matrix[x][y] > matrix[i][j]:\n"
        "                best = max(best, dfs(x, y))\n"
        "        return best + 1\n"
        "    rows, cols = len(matrix), len(matrix[0])\n"
        "    return max(dfs(i, j) for i in range(rows) for j in range(cols))\n",
        "solve",
    )

    assert estimate.estimate == "O(n^2)"
    assert estimate.method == "static_ast_memoized_recursion"


def test_recognizes_parent_guarded_tree_rerooting_dfs() -> None:
    estimate = analyze_python_complexity(
        "from collections import defaultdict\n"
        "def solve(n, edges):\n"
        "    def first(node, parent):\n"
        "        for neighbor in graph[node]:\n"
        "            if neighbor != parent: first(neighbor, node)\n"
        "    def second(node, parent):\n"
        "        for neighbor in graph[node]:\n"
        "            if neighbor != parent: second(neighbor, node)\n"
        "    graph = defaultdict(list)\n"
        "    for left, right in edges:\n"
        "        graph[left].append(right)\n"
        "        graph[right].append(left)\n"
        "    first(0, -1)\n"
        "    second(0, -1)\n",
        "solve",
    )

    assert estimate.estimate == "O(V + E)"
    assert estimate.method == "static_ast_tree_graph_dfs"
    assert "input is a tree" in estimate.explanation


def test_recognizes_sieve_of_eratosthenes() -> None:
    estimate = analyze_python_complexity(
        "def solve(n):\n"
        "    prime = [True] * (n + 1)\n"
        "    p = 2\n"
        "    while p * p <= n:\n"
        "        if prime[p]:\n"
        "            for multiple in range(p * p, n + 1, p): prime[multiple] = False\n"
        "        p += 1\n"
        "    return prime\n",
        "solve",
    )

    assert estimate.estimate == "O(n log log n)"
    assert estimate.method == "static_ast_sieve_of_eratosthenes"


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
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["input_size"]["vertices"] == "V"
    assert evidence["input_size"]["adjacency_entries"] == "E"
    assert "directed adjacency entries" in evidence["input_size"]["edge_count_measure"]
    assert evidence["neighbor_enumeration"]["representation"] == "adjacency_list"
    assert evidence["complexity"] == "O(V + E)"
    assert evidence["inference_kind"] == "heuristic_static_bounded_argument"


def test_recognizes_frozen_islands_grid_bfs_as_quadratic() -> None:
    from pathlib import Path
    import json

    packet = Path(__file__).parents[3] / "evaluation/mode1/complexity-review-2026-10-29/review-set-04.jsonl"
    case = next(
        json.loads(line) for line in packet.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["id"] == "axioma-20261029-19"
    )
    estimate = analyze_python_complexity(case["source"], case["entrypoint"])

    assert estimate.method == "static_ast_grid_bfs_v1"
    assert estimate.estimate == "O(n^2)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["input_size"]["symbolic_bounds"] == ["n", "n"]
    assert evidence["visited_state"]["mark_before_neighbor_enqueue"] is True
    assert evidence["visited_state"]["initial_cell_marked_before_queue_processing"] is True
    assert evidence["visited_state"]["shared_across_component_scans"] is True
    assert evidence["neighbor_enumeration"]["fixed_neighbors_per_cell"] == 4
    assert "O(R*C)" in evidence["bounded_work_argument"]
    assert isinstance(evidence["source_locations"]["dequeue_line"], int)
    assert isinstance(evidence["source_locations"]["neighbor_enqueue_line"], int)


def test_grid_bfs_supports_rectangular_ranges_and_reports_dimensions() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(grid):\n"
        "    rows = len(grid); cols = len(grid[0]); seen = set()\n"
        "    for r in range(rows):\n"
        "        for c in range(cols):\n"
        "            if grid[r][c] != 1 or (r,c) in seen: continue\n"
        "            q = deque([(r,c)]); seen.add((r,c))\n"
        "            while q:\n"
        "                cr,cc = q.popleft()\n"
        "                for nr,nc in ((cr-1,cc),(cr+1,cc),(cr,cc-1),(cr,cc+1)):\n"
        "                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1 and (nr,nc) not in seen:\n"
        "                        seen.add((nr,nc)); q.append((nr,nc))\n",
        "solve",
    )

    assert estimate.estimate == "O(R * C)"
    evidence = estimate.details["code_analysis"]["bfs"]
    assert evidence["input_size"]["symbolic_bounds"] == ["rows", "cols"]


def test_grid_bfs_without_enqueue_time_visited_mark_remains_unknown() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(grid):\n"
        "    n=len(grid); seen=set()\n"
        "    for r in range(n):\n"
        "        for c in range(n):\n"
        "            if grid[r][c] != 1 or (r,c) in seen: continue\n"
        "            q=deque([(r,c)]); seen.add((r,c))\n"
        "            while q:\n"
        "                cr,cc=q.popleft()\n"
        "                for nr,nc in ((cr-1,cc),(cr+1,cc),(cr,cc-1),(cr,cc+1)):\n"
        "                    if grid[nr][nc] == 1 and (nr,nc) not in seen:\n"
        "                        q.append((nr,nc))\n",
        "solve",
    )

    assert estimate.estimate == "unknown (data-dependent loop bound)"
    assert "bfs" not in estimate.details["code_analysis"]


def test_grid_bfs_with_an_independent_full_grid_scan_is_not_bounded_to_one_pass() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(grid):\n"
        "    n=len(grid); seen=set()\n"
        "    for r in range(n):\n"
        "        for c in range(n):\n"
        "            if grid[r][c] != 1 or (r,c) in seen: continue\n"
        "            q=deque([(r,c)]); seen.add((r,c))\n"
        "            while q:\n"
        "                cr,cc=q.popleft()\n"
        "                for nr,nc in ((cr-1,cc),(cr+1,cc),(cr,cc-1),(cr,cc+1)):\n"
        "                    for x in range(n):\n"
        "                        for y in range(n): pass\n"
        "                    if 0 <= nr < n and 0 <= nc < n and grid[nr][nc] == 1 and (nr,nc) not in seen:\n"
        "                        seen.add((nr,nc)); q.append((nr,nc))\n",
        "solve",
    )

    assert estimate.estimate == "unknown (data-dependent loop bound)"
    assert "bfs" not in estimate.details["code_analysis"]


def test_queue_usage_unrelated_to_graph_or_grid_stays_unclassified() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(values):\n"
        "    queue=deque(values); result=[]\n"
        "    while queue: result.append(queue.popleft())\n"
        "    return result\n",
        "solve",
    )

    assert "bfs" not in estimate.details["code_analysis"]


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


def test_adjacency_list_bfs_inside_outer_loop_is_not_flattened() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def solve(graph, n):\n"
        "    for start in range(n):\n"
        "        seen={start}; q=deque([start])\n"
        "        while q:\n"
        "            node=q.popleft()\n"
        "            for neighbor in graph[node]:\n"
        "                if neighbor not in seen: seen.add(neighbor); q.append(neighbor)\n",
        "solve",
    )

    assert estimate.estimate != "O(V + E)"
    assert "bfs" not in estimate.details["code_analysis"]


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


def test_recursive_tree_generator_accounts_for_yield_from_delegation() -> None:
    estimate = analyze_python_complexity(
        "def preorder(root):\n"
        "    if root is None: return\n"
        "    yield root.value\n"
        "    yield from preorder(root.left)\n"
        "    yield from preorder(root.right)\n",
        "preorder",
    )

    assert estimate.method == "static_ast_recursive_generator_delegation"
    assert estimate.estimate == "O(n^2)"
    assert "O(n*h)" in estimate.explanation
    assert estimate.details["code_analysis"]["recursive_generator"][
        "delegation_cost_is_inside_generator"
    ] is True
    assert any(
        signal["kind"] == "recursive_generator_delegation"
        for signal in estimate.details["code_analysis"]["signals"]
    )


def test_non_tree_recursive_generator_keeps_scalar_recurrence_estimate() -> None:
    estimate = analyze_python_complexity(
        "def generate(n):\n"
        "    if n <= 0: return\n"
        "    yield n\n"
        "    yield from generate(n - 1)\n",
        "generate",
    )

    assert estimate.estimate == "O(n)"
    assert estimate.method == "static_ast_recurrence_v1"
    assert "recursive_generator" not in estimate.details["code_analysis"]


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


def test_recognizes_top_level_binary_recursive_recurrence() -> None:
    estimate = analyze_python_complexity(
        "def solve(n):\n"
        "    if n < 2: return n\n"
        "    return solve(n - 1) + solve(n - 2)\n",
        "solve",
    )

    assert estimate.estimate.startswith("O(2^n)")
    assert estimate.method == "static_ast_binary_recursive_branching"


def test_recognizes_top_level_take_skip_recursion() -> None:
    estimate = analyze_python_complexity(
        "def solve(index, values, target):\n"
        "    if index == len(values): return target == 0\n"
        "    return solve(index + 1, values, target) or solve(index + 1, values, target - values[index])\n",
        "solve",
    )

    assert estimate.estimate.startswith("O(2^n)")
    assert estimate.method == "static_ast_binary_recursive_branching"


def test_binary_recursive_branching_does_not_combine_mutually_exclusive_branches() -> None:
    estimate = analyze_python_complexity(
        "def solve(n):\n"
        "    if n <= 0: return 0\n"
        "    if n % 2: return solve(n - 1)\n"
        "    return solve(n - 1)\n",
        "solve",
    )

    assert estimate.estimate == "unknown (recursion detected)"


def test_memoized_top_level_binary_recursion_is_not_exponential() -> None:
    estimate = analyze_python_complexity(
        "from functools import cache\n"
        "@cache\n"
        "def solve(n):\n"
        "    if n < 2: return n\n"
        "    return solve(n - 1) + solve(n - 2)\n",
        "solve",
    )

    assert not estimate.estimate.startswith("O(2^n)")


def _assert_python_recurrence(estimate, expected: str, recurrence: str) -> None:
    assert estimate.estimate == expected
    evidence = estimate.details["code_analysis"]["recurrence"]
    assert evidence["rule_version"] == "bounded_recurrence_v1"
    assert evidence["recurrence"] == recurrence
    assert evidence["solving_rule"]
    assert evidence["assumptions"]
    assert evidence["inference_kind"] == "heuristic_pattern_match"
    assert any(signal["kind"] == "recurrence" for signal in estimate.details["code_analysis"]["signals"])


def test_python_bounded_scalar_recurrences() -> None:
    decrement = analyze_python_complexity(
        "def solve(n):\n    if n <= 0: return 0\n    return solve(n - 1) + 1\n", "solve"
    )
    halve = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n    return solve(n // 2)\n", "solve"
    )
    halve_with_linear_work = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n"
        "    for i in range(n):\n        value = i\n"
        "    return solve(n // 2)\n",
        "solve",
    )
    two_halves = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n"
        "    return solve(n // 2) + solve(n // 2)\n",
        "solve",
    )
    two_halves_with_linear_work = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n"
        "    for i in range(n):\n        value = i\n"
        "    return solve(n // 2) + solve(n // 2)\n",
        "solve",
    )

    _assert_python_recurrence(decrement, "O(n)", "T(n) = T(n - c) + O(1)")
    _assert_python_recurrence(halve, "O(log n)", "T(n) = T(n / 2) + O(1)")
    _assert_python_recurrence(halve_with_linear_work, "O(n)", "T(n) = T(n / 2) + O(n)")
    _assert_python_recurrence(two_halves, "O(n)", "T(n) = 2T(n / 2) + O(1)")
    _assert_python_recurrence(
        two_halves_with_linear_work, "O(n log n)", "T(n) = 2T(n / 2) + O(n)"
    )


def test_python_unbounded_cached_fibonacci_counts_distinct_states() -> None:
    estimate = analyze_python_complexity(
        "from functools import lru_cache\n"
        "@lru_cache(maxsize=None)\n"
        "def fib(n):\n"
        "    if n < 2: return n\n"
        "    return fib(n - 1) + fib(n - 2)\n",
        "fib",
    )

    _assert_python_recurrence(
        estimate, "O(n)", "O(1) work for each of at most n + 1 distinct cached states"
    )
    evidence = estimate.details["code_analysis"]["recurrence"]
    assert evidence["solving_rule"] == "memoized_monotone_scalar_states"
    assert evidence["recursive_calls_per_level"] == 2
    assert evidence["input_size_reduction"] == "constant_decrement"
    assert "average O(1)" in " ".join(evidence["assumptions"])


def test_python_unsupported_or_ambiguous_recurrences_remain_unknown() -> None:
    irregular = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n    return solve(n * n)\n", "solve"
    )
    ambiguous = analyze_python_complexity(
        "def solve(n, choose):\n    if n <= 1: return 1\n"
        "    if choose: return solve(n - 1, choose)\n"
        "    return solve(n - 2, choose)\n",
        "solve",
    )
    recursive_loop = analyze_python_complexity(
        "def solve(n):\n    if n <= 1: return 1\n"
        "    for i in range(n): solve(n // 2)\n"
        "    return 0\n",
        "solve",
    )
    bounded_cache = analyze_python_complexity(
        "from functools import lru_cache\n"
        "@lru_cache(maxsize=32)\n"
        "def solve(n):\n"
        "    if n < 2: return n\n"
        "    return solve(n - 1) + solve(n - 2)\n",
        "solve",
    )

    for estimate in (irregular, ambiguous, recursive_loop, bounded_cache):
        assert estimate.estimate == "unknown (recursion detected)"
        assert "recurrence" not in estimate.details["code_analysis"]


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


def test_grid_component_bfs_supports_delta_vectors_and_candidate_assignment() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def count_regions(cells):\n"
        "    height, width = len(cells), len(cells[0])\n"
        "    visited = set()\n"
        "    regions = 0\n"
        "    for row in range(height):\n"
        "        for col in range(width):\n"
        "            if cells[row][col] == 0 or (row, col) in visited:\n"
        "                continue\n"
        "            regions += 1\n"
        "            visited.add((row, col))\n"
        "            queue = deque([(row, col)])\n"
        "            while queue:\n"
        "                current_row, current_col = queue.popleft()\n"
        "                for row_step, col_step in ((0, 1), (1, 0), (0, -1), (-1, 0)):\n"
        "                    next_row, next_col = current_row + row_step, current_col + col_step\n"
        "                    if (0 <= next_row < height and 0 <= next_col < width\n"
        "                            and cells[next_row][next_col] == 1\n"
        "                            and (next_row, next_col) not in visited):\n"
        "                        visited.add((next_row, next_col))\n"
        "                        queue.append((next_row, next_col))\n"
        "    return regions\n",
        "count_regions",
    )

    assert estimate.method == "static_ast_grid_bfs_v1"
    assert estimate.estimate == "O(R * C)"
    assert estimate.details["code_analysis"]["bfs"]["neighbor_enumeration"][
        "fixed_neighbors_per_cell"
    ] == 4
    assert estimate.details["code_analysis"]["bfs"]["neighbor_enumeration"][
        "representation"
    ] == "delta_vectors_with_candidate_coordinates"


def test_grid_component_bfs_supports_tuple_initialized_visited_set() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def regions(board):\n"
        "    rows, cols = len(board), len(board[0])\n"
        "    seen, total = set(), 0\n"
        "    for r in range(rows):\n"
        "        for c in range(cols):\n"
        "            if not board[r][c] or (r, c) in seen:\n"
        "                continue\n"
        "            total += 1\n"
        "            seen.add((r, c))\n"
        "            q = deque([(r, c)])\n"
        "            while q:\n"
        "                x, y = q.popleft()\n"
        "                for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):\n"
        "                    a, b = x + dx, y + dy\n"
        "                    if (0 <= a < rows and 0 <= b < cols and board[a][b]\n"
        "                            and (a, b) not in seen):\n"
        "                        seen.add((a, b))\n"
        "                        q.append((a, b))\n"
        "    return total\n",
        "regions",
    )

    assert estimate.method == "static_ast_grid_bfs_v1"
    assert estimate.estimate == "O(R * C)"


def test_grid_component_bfs_abstains_when_delta_vectors_are_incomplete() -> None:
    estimate = analyze_python_complexity(
        "from collections import deque\n"
        "def regions(cells):\n"
        "    height, width = len(cells), len(cells[0])\n"
        "    seen = set()\n"
        "    for row in range(height):\n"
        "        for col in range(width):\n"
        "            if not cells[row][col] or (row, col) in seen:\n"
        "                continue\n"
        "            seen.add((row, col))\n"
        "            queue = deque([(row, col)])\n"
        "            while queue:\n"
        "                r, c = queue.popleft()\n"
        "                for dr, dc in ((0, 1), (1, 0), (0, -1)):\n"
        "                    nr, nc = r + dr, c + dc\n"
        "                    if (0 <= nr < height and 0 <= nc < width\n"
        "                            and cells[nr][nc] and (nr, nc) not in seen):\n"
        "                        seen.add((nr, nc))\n"
        "                        queue.append((nr, nc))\n"
        "    return len(seen)\n",
        "regions",
    )

    assert estimate.estimate.startswith("unknown")
