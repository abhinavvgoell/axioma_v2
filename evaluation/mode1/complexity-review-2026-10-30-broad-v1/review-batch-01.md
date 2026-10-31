# Broad calibration review — batch 01 of 06

This is the first five-case batch of a proposed 30-case calibration set. These labels are proposals for owner review. Axioma has not been run on these cases. The exact source snapshots and SHA-256 values are in the same folder and the JSONL packet.

**Review request:** For each case, confirm or revise the time and auxiliary-space labels, assumptions, and rationale. Give particular attention to whether the stated input-size variables and output-space exclusions are appropriate. Reply with decisions by case ID; do not infer labels from Axioma output.

| ID | Case | Time proposal | Auxiliary-space proposal | Family | Language |
|---|---|---|---|---|---|
| axioma-20261030-broad-001 | Adjacency-list breadth-first search | `O(V + E)` (score `O(n)`) | `O(V)` (score `O(n)`) | graph_traversal | python |
| axioma-20261030-broad-002 | Bottom-up edit distance | `O(m * k), worst-case O(N^2)` (score `O(n^2)`) | `O(m * k), worst-case O(N^2)` (score `O(n^2)`) | dynamic_programming | python |
| axioma-20261030-broad-003 | Knuth–Morris–Pratt string matcher | `O(m + k), hence O(N)` (score `O(n)`) | `O(k) auxiliary, excluding the returned occurrence list` (score `O(n)`) | string_search | java |
| axioma-20261030-broad-004 | Kadane maximum-subarray check | `O(n)` (score `O(n)`) | `O(1)` (score `O(1)`) | array_dynamic_programming | java |
| axioma-20261030-broad-005 | Longest substring without repeating characters | `O(n)` (score `O(n)`) | `O(U), with U <= n` (score `O(n)`) | sliding_window | python |

## axioma-20261030-broad-001 — Adjacency-list breadth-first search

- Entry point: `bfs`
- Source: `TheAlgorithms/Python` at `6e03a48579ca212a08b36be00378f887dc41a003`, `graphs/breadth_first_search.py`
- SHA-256: `621e11bd4a320c7437bba42e29715608b05e84a5939562715cde8e32a576a529`
- Input size: V = number of reachable vertices; E = adjacency entries scanned from reachable vertices; n = V + E.
- Time proposal: `O(V + E)`; scoring class `O(n)`. BFS marks a vertex visited before enqueueing, so each reachable vertex is enqueued and removed once. Its adjacency list is scanned once; total work is O(V + E). Score with n = V + E.
- Space proposal: `O(V)`; scoring class `O(n)`. The visited set and queue contain at most O(V) reachable vertices. The returned visited set is the result; counting it as working storage does not change the O(V) bound.
- Assumptions: Every reachable vertex is a key in the adjacency dictionary (the code indexes self.vertices[vertex]); start_vertex is valid; adjacency lists are the graph representation; each adjacency entry counts toward E; set operations and queue put/get are expected/amortized O(1).

### Complete source snapshot

Source file: `sources/python/graphs/breadth_first_search.py`

```python
#!/usr/bin/python

"""Author: OMKAR PATHAK"""

from __future__ import annotations

from queue import Queue


class Graph:
    def __init__(self) -> None:
        self.vertices: dict[int, list[int]] = {}

    def print_graph(self) -> None:
        """
        prints adjacency list representation of graaph
        >>> g = Graph()
        >>> g.print_graph()
        >>> g.add_edge(0, 1)
        >>> g.print_graph()
        0  :  1
        """
        for i in self.vertices:
            print(i, " : ", " -> ".join([str(j) for j in self.vertices[i]]))

    def add_edge(self, from_vertex: int, to_vertex: int) -> None:
        """
        adding the edge between two vertices
        >>> g = Graph()
        >>> g.print_graph()
        >>> g.add_edge(0, 1)
        >>> g.print_graph()
        0  :  1
        """
        if from_vertex in self.vertices:
            self.vertices[from_vertex].append(to_vertex)
        else:
            self.vertices[from_vertex] = [to_vertex]

    def bfs(self, start_vertex: int) -> set[int]:
        """
        >>> g = Graph()
        >>> g.add_edge(0, 1)
        >>> g.add_edge(0, 1)
        >>> g.add_edge(0, 2)
        >>> g.add_edge(1, 2)
        >>> g.add_edge(2, 0)
        >>> g.add_edge(2, 3)
        >>> g.add_edge(3, 3)
        >>> sorted(g.bfs(2))
        [0, 1, 2, 3]
        """
        # initialize set for storing already visited vertices
        visited = set()

        # create a first in first out queue to store all the vertices for BFS
        queue: Queue = Queue()

        # mark the source node as visited and enqueue it
        visited.add(start_vertex)
        queue.put(start_vertex)

        while not queue.empty():
            vertex = queue.get()

            # loop through all adjacent vertex and enqueue it if not yet visited
            for adjacent_vertex in self.vertices[vertex]:
                if adjacent_vertex not in visited:
                    queue.put(adjacent_vertex)
                    visited.add(adjacent_vertex)
        return visited


if __name__ == "__main__":
    from doctest import testmod

    testmod(verbose=True)

    g = Graph()
    g.add_edge(0, 1)
    g.add_edge(0, 2)
    g.add_edge(1, 2)
    g.add_edge(2, 0)
    g.add_edge(2, 3)
    g.add_edge(3, 3)

    g.print_graph()
    # 0  :  1 -> 2
    # 1  :  2
    # 2  :  0 -> 3
    # 3  :  3

    assert sorted(g.bfs(2)) == [0, 1, 2, 3]
```

## axioma-20261030-broad-002 — Bottom-up edit distance

- Entry point: `min_dist_bottom_up`
- Source: `TheAlgorithms/Python` at `6e03a48579ca212a08b36be00378f887dc41a003`, `dynamic_programming/edit_distance.py`
- SHA-256: `e844589a5505736ab8a8ee6aee2494f124a7c56c28d92ab860fb817993f0e433`
- Input size: m = len(word1); k = len(word2); N = max(m, k).
- Time proposal: `O(m * k), worst-case O(N^2)`; scoring class `O(n^2)`. The bottom-up method fills every cell of an (m+1) by (k+1) table and performs constant work per cell. The exact bound is O(m*k); for scoring, with N=max(m,k), its worst-case class is O(N^2).
- Space proposal: `O(m * k), worst-case O(N^2)`; scoring class `O(n^2)`. The method allocates an (m+1) by (k+1) table. Its exact space is O(m*k), or O(N^2) in the worst case when N=max(m,k).
- Assumptions: Score the bottom-up entrypoint only; character comparison and table access are O(1); m and k may grow independently; N=max(m,k) is used for the coarse class.

### Complete source snapshot

Source file: `sources/python/dynamic_programming/edit_distance.py`

```python
"""
Author  : Turfa Auliarachman
Date    : October 12, 2016

This is a pure Python implementation of Dynamic Programming solution to the edit
distance problem.

The problem is :
Given two strings A and B. Find the minimum number of operations to string B such that
A = B. The permitted operations are removal,  insertion, and substitution.
"""


class EditDistance:
    """
    Use :
    solver              = EditDistance()
    editDistanceResult  = solver.solve(firstString, secondString)
    """

    def __init__(self) -> None:
        self.word1 = ""
        self.word2 = ""
        self.dp = []

    def __min_dist_top_down_dp(self, m: int, n: int) -> int:
        if m == -1:
            return n + 1
        elif n == -1:
            return m + 1
        elif self.dp[m][n] > -1:
            return self.dp[m][n]
        else:
            if self.word1[m] == self.word2[n]:
                self.dp[m][n] = self.__min_dist_top_down_dp(m - 1, n - 1)
            else:
                insert = self.__min_dist_top_down_dp(m, n - 1)
                delete = self.__min_dist_top_down_dp(m - 1, n)
                replace = self.__min_dist_top_down_dp(m - 1, n - 1)
                self.dp[m][n] = 1 + min(insert, delete, replace)

            return self.dp[m][n]

    def min_dist_top_down(self, word1: str, word2: str) -> int:
        """
        >>> EditDistance().min_dist_top_down("intention", "execution")
        5
        >>> EditDistance().min_dist_top_down("intention", "")
        9
        >>> EditDistance().min_dist_top_down("", "")
        0
        """
        self.word1 = word1
        self.word2 = word2
        self.dp = [[-1 for _ in range(len(word2))] for _ in range(len(word1))]

        return self.__min_dist_top_down_dp(len(word1) - 1, len(word2) - 1)

    def min_dist_bottom_up(self, word1: str, word2: str) -> int:
        """
        >>> EditDistance().min_dist_bottom_up("intention", "execution")
        5
        >>> EditDistance().min_dist_bottom_up("intention", "")
        9
        >>> EditDistance().min_dist_bottom_up("", "")
        0
        """
        self.word1 = word1
        self.word2 = word2
        m = len(word1)
        n = len(word2)
        self.dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

        for i in range(m + 1):
            for j in range(n + 1):
                if i == 0:  # first string is empty
                    self.dp[i][j] = j
                elif j == 0:  # second string is empty
                    self.dp[i][j] = i
                elif word1[i - 1] == word2[j - 1]:  # last characters are equal
                    self.dp[i][j] = self.dp[i - 1][j - 1]
                else:
                    insert = self.dp[i][j - 1]
                    delete = self.dp[i - 1][j]
                    replace = self.dp[i - 1][j - 1]
                    self.dp[i][j] = 1 + min(insert, delete, replace)
        return self.dp[m][n]


if __name__ == "__main__":
    solver = EditDistance()

    print("****************** Testing Edit Distance DP Algorithm ******************")
    print()

    S1 = input("Enter the first string: ").strip()
    S2 = input("Enter the second string: ").strip()

    print()
    print(f"The minimum edit distance is: {solver.min_dist_top_down(S1, S2)}")
    print(f"The minimum edit distance is: {solver.min_dist_bottom_up(S1, S2)}")
    print()
    print("*************** End of Testing Edit Distance DP Algorithm ***************")
```

## axioma-20261030-broad-003 — Knuth–Morris–Pratt string matcher

- Entry point: `KMP.kmpMatcher`
- Source: `TheAlgorithms/Java` at `410f08753505a0af9e46423396e8768bc97cbc1c`, `src/main/java/com/thealgorithms/strings/KMP.java`
- SHA-256: `2b7b74597b3246e29ff751dfae3399b833fe7ae6b3367a1fd959e9c7c18a2816`
- Input size: m = haystack length; k = needle length; N = m + k.
- Time proposal: `O(m + k), hence O(N)`; scoring class `O(n)`. The prefix-function construction is O(k). In the matching pass, q only advances with the scan and fallback steps are amortized over prior advances, so the pass is O(m). Total O(m+k); score with N=m+k.
- Space proposal: `O(k) auxiliary, excluding the returned occurrence list`; scoring class `O(n)`. The prefix-function array has k entries and matching uses scalar indices. The occurrence list is returned output and is excluded from auxiliary-space scoring.
- Assumptions: Character access is O(1); treat ArrayList append as amortized O(1); k>0 for a non-early-return run; matching output is excluded from auxiliary space; the helper computePrefixFunction is part of the analyzed operation.

### Complete source snapshot

Source file: `sources/java/strings/KMP.java`

```java
package com.thealgorithms.strings;

import java.util.ArrayList;
import java.util.List;

/**
 * Implementation of Knuth–Morris–Pratt algorithm Usage: see the main function
 * for an example
 */
public final class KMP {
    private KMP() {
    }

    /**
     * find the starting index in string haystack[] that matches the search word P[]
     *
     * @param haystack The text to be searched
     * @param needle   The pattern to be searched for
     * @return A list of starting indices where the pattern is found
     */
    public static List<Integer> kmpMatcher(final String haystack, final String needle) {
        List<Integer> occurrences = new ArrayList<>();
        if (haystack == null || needle == null || needle.isEmpty()) {
            return occurrences;
        }

        final int m = haystack.length();
        final int n = needle.length();
        final int[] pi = computePrefixFunction(needle);
        int q = 0;
        for (int i = 0; i < m; i++) {
            while (q > 0 && haystack.charAt(i) != needle.charAt(q)) {
                q = pi[q - 1];
            }

            if (haystack.charAt(i) == needle.charAt(q)) {
                q++;
            }

            if (q == n) {
                occurrences.add(i + 1 - n);
                q = pi[q - 1];
            }
        }
        return occurrences;
    }

    // return the prefix function
    private static int[] computePrefixFunction(final String p) {
        final int n = p.length();
        final int[] pi = new int[n];
        pi[0] = 0;
        int q = 0;
        for (int i = 1; i < n; i++) {
            while (q > 0 && p.charAt(q) != p.charAt(i)) {
                q = pi[q - 1];
            }

            if (p.charAt(q) == p.charAt(i)) {
                q++;
            }

            pi[i] = q;
        }
        return pi;
    }
}
```

## axioma-20261030-broad-004 — Kadane maximum-subarray check

- Entry point: `KadaneAlgorithm.maxSum`
- Source: `TheAlgorithms/Java` at `410f08753505a0af9e46423396e8768bc97cbc1c`, `src/main/java/com/thealgorithms/dynamicprogramming/KadaneAlgorithm.java`
- SHA-256: `2d23e1c8f889ef2784b78faab71959a7e374281c39e7cd36658848ffba85567c`
- Input size: n = a.length.
- Time proposal: `O(n)`; scoring class `O(n)`. The enhanced for-loop visits each array element once and performs constant work per element. Initialization and final comparison are constant time.
- Space proposal: `O(1)`; scoring class `O(1)`. Only the scalar variables sum and runningSum are added; no input-sized data structure is allocated.
- Assumptions: a is non-empty because the implementation reads a[0]; integer arithmetic is treated as O(1); n=a.length.

### Complete source snapshot

Source file: `sources/java/dynamicprogramming/KadaneAlgorithm.java`

```java
package com.thealgorithms.dynamicprogramming;

/**
 * This class implements Kadane's Algorithm to find the maximum subarray sum
 * within a given array of integers. The algorithm efficiently computes the maximum
 * sum of a contiguous subarray in linear time.
 *
 * Author: <a href="https://github.com/siddhant2002">Siddhant Swarup Mallick</a>
 */
public final class KadaneAlgorithm {
    private KadaneAlgorithm() {
    }

    /**
     * Computes the maximum subarray sum using Kadane's Algorithm and checks
     * if it matches a predicted answer.
     *
     * @param a              The input array of integers for which the maximum
     *                       subarray sum is to be calculated.
     * @param predictedAnswer The expected maximum subarray sum to be verified
     *                       against the computed sum.
     * @return true if the computed maximum subarray sum equals the predicted
     *         answer, false otherwise.
     *
     * <p>Example:</p>
     * <pre>
     * Input: {89, 56, 98, 123, 26, 75, 12, 40, 39, 68, 91}
     * Output: true if the maximum subarray sum is equal to the
     *         predicted answer.
     * </pre>
     *
     * <p>Algorithmic Complexity:</p>
     * <ul>
     * <li>Time Complexity: O(n) - the algorithm iterates through the array once.</li>
     * <li>Auxiliary Space Complexity: O(1) - only a constant amount of additional space is used.</li>
     * </ul>
     */
    public static boolean maxSum(int[] a, int predictedAnswer) {
        int sum = a[0];
        int runningSum = 0;

        for (int k : a) {
            runningSum += k;
            sum = Math.max(sum, runningSum);
            if (runningSum < 0) {
                runningSum = 0;
            }
        }

        return sum == predictedAnswer;
    }
}
```

## axioma-20261030-broad-005 — Longest substring without repeating characters

- Entry point: `sliding_window`
- Source: `TheAlgorithms/Python` at `6e03a48579ca212a08b36be00378f887dc41a003`, `greedy_methods/sliding_window.py`
- SHA-256: `6d2f69289af704e62a323b78a104b538297cce92fe19478c1d4db273b6cccea2`
- Input size: n = len(input_string); U = number of distinct characters in it.
- Time proposal: `O(n)`; scoring class `O(n)`. The for-loop visits each character once. Dictionary lookup/update is expected O(1), and left only moves forward; total time is O(n).
- Space proposal: `O(U), with U <= n`; scoring class `O(n)`. The character-index dictionary stores at most one entry for each distinct character seen, so it uses O(U) space, bounded by O(n).
- Assumptions: Input is a Python string; dictionary operations are expected O(1); n is its length and U is the number of distinct characters.

### Complete source snapshot

Source file: `sources/python/greedy_methods/sliding_window.py`

```python
def sliding_window(input_string: str) -> int:
    """
    This function takes a string and returns the length of the longest substring
    without repeating characters using the sliding window algorithm.

    It runs in O(n) time, where n is the length of the string. The sliding window
    approach ensures that each character is processed at most twice.

    Args:
        input_string: A string input.

    Returns:
        int: Length of the longest substring without repeating characters.

    Raises:
        TypeError: If the input is not a string.

    Examples:
    >>> sliding_window("abcabcbb")
    3
    >>> sliding_window("bbbbb")
    1
    >>> sliding_window("pwwkew")
    3
    >>> sliding_window("")
    0
    >>> sliding_window("abcdefg")
    7
    >>> sliding_window("abccba")
    3
    >>> sliding_window("a"*10000)
    1
    """
    # Error handling for non-string inputs
    if not isinstance(input_string, str):
        raise TypeError("Input must be a string")

    # Handle empty string case immediately
    if len(input_string) == 0:
        return 0

    # Dictionary to store the most recent index of each character
    char_index_map: dict[str, int] = {}

    # Initialize the sliding window pointers
    left: int = 0
    max_len: int = 0
    # Traverse the string with a right pointer
    for right, char in enumerate(input_string):
        if char in char_index_map and char_index_map[char] >= left:
            # Move the left pointer to avoid repeating characters
            left = char_index_map[char] + 1
        # Update the latest index of the character
        char_index_map[char] = right
        # Calculate the current length of the window
        current_len = right - left + 1
        max_len = max(max_len, current_len)
    return max_len


if __name__ == "__main__":
    import doctest

    doctest.testmod()
```
