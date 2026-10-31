# Complexity calibration — batch 05 (proposed)

**Status:** Five proposed labels, all pending owner confirmation. Axioma has not been run. Full pinned sources, rationales, assumptions, and hashes are included.

Packet SHA-256: `a401a89e5b7362e918f87afcbabd13ed6a9a5e5ca3ce180e2795889f94ca26ee`

## axioma-20261030-broad-021 — Lazy-heap Dijkstra shortest path

- **Source:** [graphs/dijkstra.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/graphs/dijkstra.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `eebe79cba9ede0138a97bd21d3bcce7ca8749b5e05b735859fa22b4d1077552a`
- **Proposed time:** `O(V + E log(E + 1))` (coarse `O(n log n)`)
- **Proposed auxiliary space:** `O(V + E)` (coarse `O(n)`)
- **Entrypoint:** `dijkstra`
- **Input size:** V = vertices, E = adjacency entries; n = V + E.
- **Assumptions:** Analyze the reachable graph with nonnegative edge weights, valid adjacency keys and endpoints, and expected O(1) hash operations. Node labels must be hashable and mutually orderable when equal-cost heap tuples are compared. Treat arithmetic as O(1).
- **Time rationale:** Each settled vertex scans its adjacency list once. Every successful relaxation pushes one heap entry, so there are O(E) pushes and pops, each O(log(E+1)); initialization and graph scans add O(V+E). The implementation may stop earlier when it reaches the destination.
- **Space rationale:** The cost map and visited set use O(V); stale duplicate heap entries can make the heap O(E). Exclude the input graph.

```python
"""
pseudo-code

DIJKSTRA(graph G, start vertex s, destination vertex d):

// all nodes initially unexplored

1 -  let H = min heap data structure, initialized with (0, s)
     // 0 is the distance from start vertex s
2 -  let costs = dictionary to store minimum costs to reach each node,
     initialized with {s: 0}
3 -  while H is non-empty:
4 -    remove the first node and cost from H, call them U and cost
5 -    if U has been previously explored:
6 -      continue // skip further processing and go back to while loop, line 3
7 -    mark U as explored
8 -    if U is d:
9 -      return cost // total cost from start to destination vertex
10 -   for each neighbor V and edge cost c of U in G:
11 -     if V has been previously explored:
12 -       continue to next neighbor V in line 10
13 -     total_cost = cost + c
14 -     if total_cost is less than costs.get(V, ∞):
15 -       update costs[V] to total_cost
16 -       add (total_cost, V) to H

// At the end, if destination d is not reachable, return -1

You can think at cost as a distance where Dijkstra finds the shortest distance
between vertices s and v in a graph G. The use of a min heap as H guarantees
that if a vertex has already been explored there will be no other path with
shortest distance, that happens because heapq.heappop will always return the
next vertex with the shortest distance, considering that the heap stores not
only the distance between previous vertex and current vertex but the entire
distance between each vertex that makes up the path from start vertex to target
vertex.
"""

import heapq


def dijkstra(graph: dict[str, list[tuple[str, int]]], start: str, end: str) -> int:
    """Return the cost of the shortest path between vertices start and end.

    >>> dijkstra(G, "E", "C")
    6
    >>> dijkstra(G2, "E", "F")
    3
    >>> dijkstra(G3, "E", "F")
    3
    """
    heap: list[tuple[int, str]] = [(0, start)]  # (cost, node)
    visited: set[str] = set()
    costs: dict[str, int] = {start: 0}  # Store minimum costs to reach each node

    while heap:
        cost, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == end:
            return cost

        for v, c in graph[u]:
            if v in visited:
                continue
            next_cost = cost + c
            # Only push to heap if a cheaper path is found
            if next_cost < costs.get(v, float("inf")):
                costs[v] = next_cost
                heapq.heappush(heap, (next_cost, v))

    return -1


G = {
    "A": [("B", 2), ("C", 5)],
    "B": [("A", 2), ("D", 3), ("E", 1), ("F", 1)],
    "C": [("A", 5), ("F", 3)],
    "D": [("B", 3)],
    "E": [("B", 4), ("F", 3)],
    "F": [("C", 3), ("E", 3)],
}

r"""
Layout of G2:

E -- 1 --> B -- 1 --> C -- 1 --> D -- 1 --> F
 \                                         /\
  \                                        ||
    ----------------- 3 --------------------
"""
G2 = {
    "B": [("C", 1)],
    "C": [("D", 1)],
    "D": [("F", 1)],
    "E": [("B", 1), ("F", 3)],
    "F": [],
}

r"""
Layout of G3:

E -- 1 --> B -- 1 --> C -- 1 --> D -- 1 --> F
 \                                         /\
  \                                        ||
    -------- 2 ---------> G ------- 1 ------
"""
G3 = {
    "B": [("C", 1)],
    "C": [("D", 1)],
    "D": [("F", 1)],
    "E": [("B", 1), ("G", 2)],
    "F": [],
    "G": [("F", 1)],
}

short_distance = dijkstra(G, "E", "C")
print(short_distance)  # E -- 3 --> F -- 3 --> C == 6

short_distance = dijkstra(G2, "E", "F")
print(short_distance)  # E -- 3 --> F == 3

short_distance = dijkstra(G3, "E", "F")
print(short_distance)  # E -- 2 --> G -- 1 --> F == 3

if __name__ == "__main__":
    import doctest

    doctest.testmod()
```

## axioma-20261030-broad-022 — Iterative ternary search with fixed-size linear tail

- **Source:** [searches/ternary_search.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/searches/ternary_search.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `24ca1e641d1a16496fc73b29f4cb2d7a997e630861af4f04f04fc35b5c018b77`
- **Proposed time:** `O(log_3 n + precision) = O(log n)` (coarse `O(log n)`)
- **Proposed auxiliary space:** `O(1)` (coarse `O(1)`)
- **Entrypoint:** `ite_ternary_search`
- **Input size:** n = len(array); precision is the module constant 10.
- **Assumptions:** Analyze ite_ternary_search only, on an array sorted in ascending order, with module precision fixed independently of n and O(1) comparisons/indexing. The file also contains a separate recursive implementation, which is not the selected entrypoint.
- **Time rationale:** Each loop iteration reduces the active interval to at most about two thirds. Once its size is below the fixed precision threshold, linear search examines at most a constant number of entries.
- **Space rationale:** The selected iterative entrypoint uses a fixed number of indices and scalar values; its tail search is also iterative.

```python
"""
This is a type of divide and conquer algorithm which divides the search space into
3 parts and finds the target value based on the property of the array or list
(usually monotonic property).

Time Complexity  : O(log3 N)
Space Complexity : O(1)
"""

from __future__ import annotations

# This is the precision for this function which can be altered.
# It is recommended for users to keep this number greater than or equal to 10.
precision = 10


# This is the linear search that will occur after the search space has become smaller.


def lin_search(left: int, right: int, array: list[int], target: int) -> int:
    """Perform linear search in list. Returns -1 if element is not found.

    Parameters
    ----------
    left : int
        left index bound.
    right : int
        right index bound.
    array : List[int]
        List of elements to be searched on
    target : int
        Element that is searched

    Returns
    -------
    int
        index of element that is looked for.

    Examples
    --------
    >>> lin_search(0, 4, [4, 5, 6, 7], 7)
    3
    >>> lin_search(0, 3, [4, 5, 6, 7], 7)
    -1
    >>> lin_search(0, 2, [-18, 2], -18)
    0
    >>> lin_search(0, 1, [5], 5)
    0
    >>> lin_search(0, 3, ['a', 'c', 'd'], 'c')
    1
    >>> lin_search(0, 3, [.1, .4 , -.1], .1)
    0
    >>> lin_search(0, 3, [.1, .4 , -.1], -.1)
    2
    """
    for i in range(left, right):
        if array[i] == target:
            return i
    return -1


def ite_ternary_search(array: list[int], target: int) -> int:
    """Iterative method of the ternary search algorithm.
    >>> test_list = [0, 1, 2, 8, 13, 17, 19, 32, 42]
    >>> ite_ternary_search(test_list, 3)
    -1
    >>> ite_ternary_search(test_list, 13)
    4
    >>> ite_ternary_search([4, 5, 6, 7], 4)
    0
    >>> ite_ternary_search([4, 5, 6, 7], -10)
    -1
    >>> ite_ternary_search([-18, 2], -18)
    0
    >>> ite_ternary_search([5], 5)
    0
    >>> ite_ternary_search(['a', 'c', 'd'], 'c')
    1
    >>> ite_ternary_search(['a', 'c', 'd'], 'f')
    -1
    >>> ite_ternary_search([], 1)
    -1
    >>> ite_ternary_search([.1, .4 , -.1], .1)
    0
    >>> test_list_large = list(range(100))
    >>> ite_ternary_search(test_list_large, 65)
    65
    >>> ite_ternary_search(test_list_large, 105)
    -1
    """

    left = 0
    right = len(array)
    while left <= right:
        if right - left < precision:
            return lin_search(left, right, array, target)

        one_third = left + (right - left) // 3
        two_third = right - (right - left) // 3

        if array[one_third] == target:
            return one_third
        elif array[two_third] == target:
            return two_third

        elif target < array[one_third]:
            right = one_third
        elif array[two_third] < target:
            left = two_third + 1

        else:
            left = one_third + 1
            right = two_third
    return -1


def rec_ternary_search(left: int, right: int, array: list[int], target: int) -> int:
    """Recursive method of the ternary search algorithm.

    >>> test_list = [0, 1, 2, 8, 13, 17, 19, 32, 42]
    >>> rec_ternary_search(0, len(test_list), test_list, 3)
    -1
    >>> rec_ternary_search(4, len(test_list), test_list, 42)
    8
    >>> rec_ternary_search(0, 2, [4, 5, 6, 7], 4)
    0
    >>> rec_ternary_search(0, 3, [4, 5, 6, 7], -10)
    -1
    >>> rec_ternary_search(0, 1, [-18, 2], -18)
    0
    >>> rec_ternary_search(0, 1, [5], 5)
    0
    >>> rec_ternary_search(0, 2, ['a', 'c', 'd'], 'c')
    1
    >>> rec_ternary_search(0, 2, ['a', 'c', 'd'], 'f')
    -1
    >>> rec_ternary_search(0, 0, [], 1)
    -1
    >>> rec_ternary_search(0, 3, [.1, .4 , -.1], .1)
    0
    >>> test_list_large = list(range(100))
    >>> rec_ternary_search(0, len(test_list_large), test_list_large, 65)
    65
    >>> rec_ternary_search(20, 80, test_list_large, 65)
    65
    >>> rec_ternary_search(20, 80, test_list_large, 15)
    -1
    """
    if left < right:
        if right - left < precision:
            return lin_search(left, right, array, target)
        one_third = left + (right - left) // 3
        two_third = right - (right - left) // 3

        if array[one_third] == target:
            return one_third
        elif array[two_third] == target:
            return two_third

        elif target < array[one_third]:
            return rec_ternary_search(left, one_third, array, target)
        elif array[two_third] < target:
            return rec_ternary_search(two_third + 1, right, array, target)
        else:
            return rec_ternary_search(one_third + 1, two_third, array, target)
    else:
        return -1


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    user_input = input("Enter numbers separated by comma:\n").strip()
    collection = [int(item.strip()) for item in user_input.split(",")]
    assert collection == sorted(collection), f"List must be ordered.\n{collection}."
    target = int(input("Enter the number to be found in the list:\n").strip())
    result1 = ite_ternary_search(collection, target)
    result2 = rec_ternary_search(0, len(collection), collection, target)
    if result2 != -1:
        print(f"Iterative search: {target} found at positions: {result1}")
        print(f"Recursive search: {target} found at positions: {result2}")
    else:
        print("Not found")
```

## axioma-20261030-broad-023 — Longest common substring dynamic programming

- **Source:** [dynamic_programming/longest_common_substring.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/dynamic_programming/longest_common_substring.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `4b60ccb26882d8fa5d87e4e2417d9ed810fb12dc4e386f6689b10a2b985bda77`
- **Proposed time:** `O(m * k)` (coarse `O(n^2)`)
- **Proposed auxiliary space:** `O(m * k)` (coarse `O(n^2)`)
- **Entrypoint:** `longest_common_substring`
- **Input size:** m = len(text1), k = len(text2), n = max(m,k).
- **Assumptions:** Inputs are nonempty strings for the coarse n² class; the exact two-parameter bound is O(mk), and an empty input returns in O(1). Character comparison and indexing are O(1). For coarse scoring assume m and k have comparable order.
- **Time rationale:** For nonempty strings the nested loops fill all m×k interior cells. The final substring slice is O(min(m,k)), dominated by O(mk). The coarse n² class assumes m and k are of comparable order, with n=max(m,k).
- **Space rationale:** The DP table has (m+1)(k+1) cells. The returned substring uses at most O(min(m,k)) additional space, dominated by the table for nonempty strings.

```python
"""
Longest Common Substring Problem Statement:
    Given two sequences, find the
    longest common substring present in both of them. A substring is
    necessarily continuous.

Example:
    ``abcdef`` and ``xabded`` have two longest common substrings, ``ab`` or ``de``.
    Therefore, algorithm should return any one of them.
"""


def longest_common_substring(text1: str, text2: str) -> str:
    """
    Finds the longest common substring between two strings.

    >>> longest_common_substring("", "")
    ''
    >>> longest_common_substring("a","")
    ''
    >>> longest_common_substring("", "a")
    ''
    >>> longest_common_substring("a", "a")
    'a'
    >>> longest_common_substring("abcdef", "bcd")
    'bcd'
    >>> longest_common_substring("abcdef", "xabded")
    'ab'
    >>> longest_common_substring("GeeksforGeeks", "GeeksQuiz")
    'Geeks'
    >>> longest_common_substring("abcdxyz", "xyzabcd")
    'abcd'
    >>> longest_common_substring("zxabcdezy", "yzabcdezx")
    'abcdez'
    >>> longest_common_substring("OldSite:GeeksforGeeks.org", "NewSite:GeeksQuiz.com")
    'Site:Geeks'
    >>> longest_common_substring(1, 1)
    Traceback (most recent call last):
        ...
    ValueError: longest_common_substring() takes two strings for inputs
    """

    if not (isinstance(text1, str) and isinstance(text2, str)):
        raise ValueError("longest_common_substring() takes two strings for inputs")

    if not text1 or not text2:
        return ""

    text1_length = len(text1)
    text2_length = len(text2)

    dp = [[0] * (text2_length + 1) for _ in range(text1_length + 1)]
    end_pos = 0
    max_length = 0

    for i in range(1, text1_length + 1):
        for j in range(1, text2_length + 1):
            if text1[i - 1] == text2[j - 1]:
                dp[i][j] = 1 + dp[i - 1][j - 1]
                if dp[i][j] > max_length:
                    end_pos = i
                    max_length = dp[i][j]

    return text1[end_pos - max_length : end_pos]


if __name__ == "__main__":
    import doctest

    doctest.testmod()
```

## axioma-20261030-broad-024 — 0/1 knapsack bottom-up tabulation

- **Source:** [src/main/java/com/thealgorithms/dynamicprogramming/KnapsackZeroOneTabulation.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/dynamicprogramming/KnapsackZeroOneTabulation.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `4dac00819b9665faf71aed11c37c83e0782acf83216a38f61fb50894b09568ed`
- **Proposed time:** `O(i * W)` (coarse `O(n^2)`)
- **Proposed auxiliary space:** `O(i * W)` (coarse `O(n^2)`)
- **Entrypoint:** `KnapsackZeroOneTabulation.compute`
- **Input size:** i = itemCount, W = capacity, n = max(i,W).
- **Assumptions:** Analyze valid arrays and itemCount i with i≥1 and capacity W≥1; use n=max(i,W) for coarse scoring. Treat primitive arithmetic and array access as O(1); exclude inputs and scalar return.
- **Time rationale:** The method allocates and fills a (i+1)×(W+1) table; each cell does constant work. The exact bound is O(iW); the coarse n² class uses n=max(i,W).
- **Space rationale:** The full two-dimensional int table contains (i+1)(W+1) cells, so space is O(iW), scored coarsely as O(n²) for n=max(i,W).

```java
package com.thealgorithms.dynamicprogramming;

/**
 * Tabulation (Bottom-Up) Solution for 0-1 Knapsack Problem.
 * This method uses dynamic programming to build up a solution iteratively,
 * filling a 2-D array where each entry dp[i][w] represents the maximum value
 * achievable with the first i items and a knapsack capacity of w.
 *
 * The tabulation approach is efficient because it avoids redundant calculations
 * by solving all subproblems in advance and storing their results, ensuring
 * each subproblem is solved only once. This is a key technique in dynamic programming,
 * making it possible to solve problems that would otherwise be infeasible due to
 * exponential time complexity in naive recursive solutions.
 *
 * Time Complexity: O(n * W), where n is the number of items and W is the knapsack capacity.
 * Space Complexity: O(n * W) for the DP table.
 *
 * For more information, see:
 * https://en.wikipedia.org/wiki/Knapsack_problem#Dynamic_programming
 */
public final class KnapsackZeroOneTabulation {

    private KnapsackZeroOneTabulation() {
        // Prevent instantiation
    }

    /**
     * Solves the 0-1 Knapsack problem using the bottom-up tabulation technique.
     * @param values the values of the items
     * @param weights the weights of the items
     * @param capacity the total capacity of the knapsack
     * @param itemCount the number of items
     * @return the maximum value that can be put in the knapsack
     * @throws IllegalArgumentException if input arrays are null, of different lengths,or if capacity or itemCount is invalid
     */
    public static int compute(final int[] values, final int[] weights, final int capacity, final int itemCount) {
        if (values == null || weights == null) {
            throw new IllegalArgumentException("Values and weights arrays must not be null.");
        }
        if (values.length != weights.length) {
            throw new IllegalArgumentException("Values and weights arrays must be non-null and of same length.");
        }
        if (capacity < 0) {
            throw new IllegalArgumentException("Capacity must not be negative.");
        }
        if (itemCount < 0 || itemCount > values.length) {
            throw new IllegalArgumentException("Item count must be between 0 and the length of the values array.");
        }

        final int[][] dp = new int[itemCount + 1][capacity + 1];

        for (int i = 1; i <= itemCount; i++) {
            final int currentValue = values[i - 1];
            final int currentWeight = weights[i - 1];

            for (int w = 1; w <= capacity; w++) {
                if (currentWeight <= w) {
                    final int includeItem = currentValue + dp[i - 1][w - currentWeight];
                    final int excludeItem = dp[i - 1][w];
                    dp[i][w] = Math.max(includeItem, excludeItem);
                } else {
                    dp[i][w] = dp[i - 1][w];
                }
            }
        }

        return dp[itemCount][capacity];
    }
}
```

## axioma-20261030-broad-025 — DFS topological sort with adjacency lists

- **Source:** [src/main/java/com/thealgorithms/sorts/TopologicalSort.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/sorts/TopologicalSort.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `d339d3eaa4e38fbb722b5b4c951412516afe40eea8c32db470c75c28083710c7`
- **Proposed time:** `O(V + E)` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(V)` (coarse `O(n)`)
- **Entrypoint:** `TopologicalSort.sort`
- **Input size:** V = vertices, E = adjacency entries; n = V + E.
- **Assumptions:** Input is a DAG represented by the source's adjacency lists; all referenced vertices are present. Hash-map operations for string labels are expected O(1), label hashing/comparison is O(1), and adjacency iteration is linear in degree. Analyze sort, not graph construction. Scoring class uses n=V+E.
- **Time rationale:** DFS colors each vertex once and checks each adjacency entry once. Linked-list front insertion is O(1), giving O(V+E) time.
- **Space rationale:** The recursion stack and returned linked list each use O(V). The existing graph input is excluded; output storage is included and remains O(V).

```java
package com.thealgorithms.sorts;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedList;

/**
 * The Topological Sorting algorithm linearly orders a DAG or Directed Acyclic Graph into
 * a linked list. A Directed Graph is proven to be acyclic when a DFS or Depth First Search is
 * performed, yielding no back-edges.
 *
 * Time Complexity: O(V + E)
 *   - V: number of vertices
 *   - E: number of edges
 *
 * Space Complexity: O(V + E)
 *   - adjacency list and recursion stack in DFS
 *
 * Reference: https://en.wikipedia.org/wiki/Topological_sorting
 *
 * Author: Jonathan Taylor (https://github.com/Jtmonument)
 * Based on Introduction to Algorithms 3rd Edition
 */
public final class TopologicalSort {
    private TopologicalSort() {
    }

    /*
     * Enum to represent the colors for the depth first search
     * */
    private enum Color {
        WHITE,
        GRAY,
        BLACK,
    }

    /*
     * Class to represent vertices
     * */
    private static class Vertex {

        /*
         * Name of vertex
         * */
        public final String label;

        /*
         * Represents the category of visit in DFS
         * */
        public Color color = Color.WHITE;

        /*
         * The array of names of descendant vertices
         * */
        public final ArrayList<String> next = new ArrayList<>();

        Vertex(String label) {
            this.label = label;
        }
    }

    /*
     * Graph class uses the adjacency list representation
     * */
    static class Graph {

        /*
         * Adjacency list representation
         * */
        private final HashMap<String, Vertex> adj = new LinkedHashMap<>();

        /*
         * Function to add an edge to the graph
         * */
        public void addEdge(String label, String... next) {
            adj.put(label, new Vertex(label));
            if (!next[0].isEmpty()) {
                Collections.addAll(adj.get(label).next, next);
            }
        }
    }

    /*
     * Depth First Search
     *
     * DFS(G)
     *   for each vertex u ∈ G.V
     *       u.color = WHITE
     *       u.π = NIL
     *   time = 0
     *   for each vertex u ∈ G.V
     *   if u.color == WHITE
     *       DFS-VISIT(G, u)
     *
     * Performed in Θ(V + E) time
     * */
    public static LinkedList<String> sort(Graph graph) {
        LinkedList<String> list = new LinkedList<>();
        graph.adj.forEach((name, vertex) -> {
            if (vertex.color == Color.WHITE) {
                list.addFirst(sort(graph, vertex, list));
            }
        });
        return list;
    }

    /*
     * Depth First Search Visit
     *
     * DFS-Visit(G, u)
     *   time = time + 1
     *   u.d = time
     *   u.color = GRAY
     *   for each v ∈ G.Adj[u]
     *       if v.color == WHITE
     *           v.π = u
     *           DFS-Visit(G, u)
     *   u.color = BLACK
     *   time = time + 1
     *   u.f = time
     * */
    private static String sort(Graph graph, Vertex u, LinkedList<String> list) {
        u.color = Color.GRAY;
        graph.adj.get(u.label).next.forEach(label -> {
            if (graph.adj.get(label).color == Color.WHITE) {
                list.addFirst(sort(graph, graph.adj.get(label), list));
            } else if (graph.adj.get(label).color == Color.GRAY) {
                /*
                 * A back edge exists if an edge (u, v) connects a vertex u to its ancestor vertex v
                 * in a depth first tree. If v.d ≤ u.d < u.f ≤ v.f
                 *
                 * In many cases, we will not know u.f, but v.color denotes the type of edge
                 * */
                throw new RuntimeException("This graph contains a cycle. No linear ordering is possible. Back edge: " + u.label + " -> " + label);
            }
        });
        u.color = Color.BLACK;
        return u.label;
    }
}
```
