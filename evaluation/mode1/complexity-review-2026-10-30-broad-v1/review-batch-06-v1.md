# Complexity calibration — batch 06 (proposed)

**Status:** Five labels proposed and pending owner confirmation. Axioma has not been run. Complete pinned source code, assumptions, rationales, and hashes are included.

Packet SHA-256: `ed64db43ec0c3a13851e37f9f2086b7abd4e9aa70045770b1f85ac860a07e96b`

## axioma-20261030-broad-026 — Linear two-pointer palindrome check

- **Source:** [strings/palindrome.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/strings/palindrome.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `0f3bb5314dc0f9c912db888dd7742663381b525afc279b6a7cea726d58e5c38d`
- **Proposed time:** `O(n)` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(1)` (coarse `O(1)`)
- **Entrypoint:** `is_palindrome`
- **Input size:** n = len(s).
- **Assumptions:** Analyze is_palindrome only, not the other functions or module-level benchmark. String indexing and character equality are O(1); input is excluded.
- **Time rationale:** The two indices move inward, comparing at most floor(n/2) character pairs. In the worst case all pairs are examined, so time is O(n).
- **Space rationale:** Only two integer indices are stored; no substring or reversed copy is created.

```python
# Algorithms to determine if a string is palindrome

from timeit import timeit

test_data = {
    "MALAYALAM": True,
    "String": False,
    "rotor": True,
    "level": True,
    "A": True,
    "BB": True,
    "ABC": False,
    "amanaplanacanalpanama": True,  # "a man a plan a canal panama"
    "abcdba": False,
    "AB": False,
}
# Ensure our test data is valid
assert all((key == key[::-1]) == value for key, value in test_data.items())


def is_palindrome(s: str) -> bool:
    """
    Return True if s is a palindrome otherwise return False.

    >>> all(is_palindrome(key) == value for key, value in test_data.items())
    True
    >>> is_palindrome("")
    True
    """

    start_i = 0
    end_i = len(s) - 1
    while start_i < end_i:
        if s[start_i] == s[end_i]:
            start_i += 1
            end_i -= 1
        else:
            return False
    return True


def is_palindrome_traversal(s: str) -> bool:
    """
    Return True if s is a palindrome otherwise return False.

    >>> all(is_palindrome_traversal(key) == value for key, value in test_data.items())
    True
    >>> is_palindrome_traversal("")
    True
    """
    end = len(s) // 2
    n = len(s)

    # We need to traverse till half of the length of string
    # as we can get access of the i'th last element from
    # i'th index.
    # eg: [0,1,2,3,4,5] => 4th index can be accessed
    # with the help of 1st index (i==n-i-1)
    # where n is length of string
    return all(s[i] == s[n - i - 1] for i in range(end))


def is_palindrome_recursive(s: str) -> bool:
    """
    Return True if s is a palindrome otherwise return False.

    >>> all(is_palindrome_recursive(key) == value for key, value in test_data.items())
    True
    >>> is_palindrome_recursive("")
    True
    """
    if len(s) <= 1:
        return True
    if s[0] == s[len(s) - 1]:
        return is_palindrome_recursive(s[1:-1])
    else:
        return False


def is_palindrome_slice(s: str) -> bool:
    """
    Return True if s is a palindrome otherwise return False.

    >>> all(is_palindrome_slice(key) == value for key, value in test_data.items())
    True
    >>> is_palindrome_slice("")
    True
    """
    return s == s[::-1]


def is_palindrome_ignore_case_and_spaces(s: str) -> bool:
    """
    Return True if s is a palindrome, ignoring case, spaces, and punctuation.
    Otherwise return False.

    >>> is_palindrome_ignore_case_and_spaces("A man a plan a canal Panama")
    True
    >>> is_palindrome_ignore_case_and_spaces("Was it a car or a cat I saw?")
    True
    >>> is_palindrome_ignore_case_and_spaces("Hello World")
    False
    >>> is_palindrome_ignore_case_and_spaces("Never Odd or Even")
    True
    >>> is_palindrome_ignore_case_and_spaces("")
    True
    >>> is_palindrome_ignore_case_and_spaces(" !?. ")
    True
    >>> is_palindrome_ignore_case_and_spaces("1a2")
    False
    """
    s = "".join(char.lower() for char in s if char.isalnum())
    return s == s[::-1]


test_data_ignore_case_and_spaces = {
    "A man a plan a canal Panama": True,
    "Was it a car or a cat I saw?": True,
    "Hello World": False,
    "Never Odd or Even": True,
    "": True,
}


def benchmark_function(name: str) -> None:
    stmt = f"all({name}(key) == value for key, value in test_data.items())"
    setup = f"from __main__ import test_data, {name}"
    number = 500000
    result = timeit(stmt=stmt, setup=setup, number=number)
    print(f"{name:<35} finished {number:,} runs in {result:.5f} seconds")


if __name__ == "__main__":
    for key, value in test_data.items():
        assert is_palindrome(key) == is_palindrome_recursive(key)
        assert is_palindrome(key) == is_palindrome_slice(key)
        print(f"{key:21} {value}")
    for key, value in test_data_ignore_case_and_spaces.items():
        assert is_palindrome_ignore_case_and_spaces(key) == value
    print("a man a plan a canal panama")

    # finished 500,000 runs in 0.46793 seconds
    benchmark_function("is_palindrome_slice")
    # finished 500,000 runs in 0.85234 seconds
    benchmark_function("is_palindrome")
    # finished 500,000 runs in 1.32028 seconds
    benchmark_function("is_palindrome_recursive")
    # finished 500,000 runs in 2.08679 seconds
    benchmark_function("is_palindrome_traversal")
    # finished 500,000 runs in 4.27493 seconds
    benchmark_function("is_palindrome_ignore_case_and_spaces")
```

## axioma-20261030-broad-027 — Randomized quick sort with list partitions

- **Source:** [sorts/quick_sort.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/sorts/quick_sort.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `2cdf0918efd16829cd4ac63a11b675e73b61ec77cf58f9d470f5c0730ec301c4`
- **Proposed time:** `O(n^2) worst case; expected O(n log n) with uniformly random pivot ranks and distinct values` (coarse `O(n^2)`)
- **Proposed auxiliary space:** `O(n^2) worst case; expected O(n) for uniformly random pivot ranks` (coarse `O(n^2)`)
- **Entrypoint:** `quick_sort`
- **Input size:** n = len(collection).
- **Assumptions:** Use worst-case labels for scoring. Each pivot selection and comparison is O(1); the random pivot can repeatedly produce a one-sided partition. The expected-case note assumes uniformly random pivot ranks and distinct values. Count partition lists and returned lists as auxiliary storage; exclude the original input.
- **Time rationale:** Every call builds lesser/equal/greater lists in O(k) for its subproblem size k. Repeated maximally unbalanced pivots yield n+(n-1)+...=O(n²) work; random pivots give expected O(n log n) comparisons for distinct values.
- **Space rationale:** The recursive frames retain partition lists. With maximally unbalanced partitions, live lists across the call chain sum to n+(n-1)+...=O(n²); balanced random partitions use expected O(n) peak list storage.

```python
"""
A pure Python implementation of the quick sort algorithm

For doctests run following command:
python3 -m doctest -v quick_sort.py

For manual testing run:
python3 quick_sort.py
"""

from __future__ import annotations

from random import randrange
from typing import Any, Protocol


class Comparable(Protocol):
    def __lt__(self, other: Any, /) -> bool: ...


def quick_sort[T: Comparable](collection: list[T]) -> list[T]:
    """A pure Python implementation of quicksort algorithm.

    :param collection: a mutable collection of comparable items
    :return: the same collection ordered in ascending order

    Examples:
    >>> quick_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> quick_sort([])
    []
    >>> quick_sort([-2, 5, 0, -45])
    [-45, -2, 0, 5]
    >>> quick_sort(["z", "a", "m", "b"])
    ['a', 'b', 'm', 'z']
    >>> quick_sort([3.14, -1.0, 2.71])
    [-1.0, 2.71, 3.14]
    >>> quick_sort([0, 5, 3, 2, 2]) == sorted([0, 5, 3, 2, 2])
    True
    >>> quick_sort(["z", "a", "m"]) == sorted(["z", "a", "m"])
    True
    """
    if len(collection) < 2:
        return collection
    pivot_index = randrange(len(collection))
    pivot = collection[pivot_index]
    lesser = [item for item in collection if item < pivot]
    equal = [item for item in collection if item == pivot]
    greater = [item for item in collection if item > pivot]
    return [*quick_sort(lesser), *equal, *quick_sort(greater)]


if __name__ == "__main__":
    user_input = input("Enter numbers separated by a comma:\n").strip()
    unsorted = [int(item) for item in user_input.split(",")]
    print(quick_sort(unsorted))
```

## axioma-20261030-broad-028 — Lazy-priority-queue Dijkstra on an adjacency matrix

- **Source:** [src/main/java/com/thealgorithms/datastructures/graphs/DijkstraAlgorithm.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/datastructures/graphs/DijkstraAlgorithm.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `5162609a392cb3cfb17b54aa41af77c26a595d5be437dd0e22182d4d335a78f0`
- **Proposed time:** `O(V^2 + E log(E + 1))` (coarse `O(n log n)`)
- **Proposed auxiliary space:** `O(V + E)` (coarse `O(n)`)
- **Entrypoint:** `DijkstraAlgorithm.run`
- **Input size:** V = vertexCount; E = nonzero matrix entries; n = V + E.
- **Assumptions:** Analyze a valid V×V adjacency matrix with nonnegative edge weights, 0 meaning no edge, valid source, and primitive comparisons/heap node comparisons O(1). Score with n=V+E; exact time is O(V²+E log(E+1)). Include the method's O(V) output printing in time.
- **Time rationale:** Each processed vertex scans an entire matrix row, for O(V²) scans. Every successful relaxation may enqueue another Node, so up to O(E) heap entries can be inserted and removed at O(log(E+1)) each. Printing distances adds O(V).
- **Space rationale:** Distances and processed flags use O(V); lazy duplicate queue entries can occupy O(E). The input adjacency matrix is excluded.

```java
package com.thealgorithms.datastructures.graphs;

import java.util.Arrays;
import java.util.PriorityQueue;

/**
 * Dijkstra's algorithm for finding the shortest path from a single source vertex to all other vertices in a graph.
 */
public class DijkstraAlgorithm {

    private final int vertexCount;

    /**
     * Constructs a Dijkstra object with the given number of vertices.
     *
     * @param vertexCount The number of vertices in the graph.
     */
    public DijkstraAlgorithm(int vertexCount) {
        this.vertexCount = vertexCount;
    }

    private static class Node implements Comparable<Node> {
        int id;
        int distance;

        Node(int id, int distance) {
            this.id = id;
            this.distance = distance;
        }

        @Override
        public int compareTo(Node other) {
            return Integer.compare(this.distance, other.distance);
        }
    }

    /**
     * Executes Dijkstra's algorithm on the provided graph to find the shortest paths from the source vertex to all other vertices.
     *
     * The graph is represented as an adjacency matrix where {@code graph[i][j]} represents the weight of the edge from vertex {@code i}
     * to vertex {@code j}. A value of 0 indicates no edge exists between the vertices.
     *
     * @param graph The graph represented as an adjacency matrix.
     * @param source The source vertex.
     * @return An array where the value at each index {@code i} represents the shortest distance from the source vertex to vertex {@code i}.
     * @throws IllegalArgumentException if the source vertex is out of range.
     */
    public int[] run(int[][] graph, int source) {
        if (source < 0 || source >= vertexCount) {
            throw new IllegalArgumentException("Incorrect source");
        }

        int[] distances = new int[vertexCount];
        boolean[] processed = new boolean[vertexCount];
        PriorityQueue<Node> unprocessed = new PriorityQueue<>();

        Arrays.fill(distances, Integer.MAX_VALUE);
        distances[source] = 0;
        unprocessed.add(new Node(source, 0));

        while (!unprocessed.isEmpty()) {
            Node current = unprocessed.poll();
            int u = current.id;

            if (processed[u]) {
                continue;
            }
            processed[u] = true;

            for (int v = 0; v < vertexCount; v++) {
                if (!processed[v] && graph[u][v] != 0 && distances[u] != Integer.MAX_VALUE && distances[u] + graph[u][v] < distances[v]) {
                    distances[v] = distances[u] + graph[u][v];
                    unprocessed.add(new Node(v, distances[v]));
                }
            }
        }

        printDistances(distances);
        return distances;
    }

    /**
     * Prints the shortest distances from the source vertex to all other vertices.
     *
     * @param distances The array of shortest distances.
     */
    private void printDistances(int[] distances) {
        System.out.println("Vertex \t Distance");
        for (int i = 0; i < vertexCount; i++) {
            System.out.println(i + " \t " + distances[i]);
        }
    }
}
```

## axioma-20261030-broad-029 — Minimum coin count by bottom-up dynamic programming

- **Source:** [src/main/java/com/thealgorithms/dynamicprogramming/CoinChange.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/dynamicprogramming/CoinChange.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `c0ab0923f717537f0c9e52c9044d0b4e9ca8124d8c6e625c4759f956b0871db9`
- **Proposed time:** `O(A * C)` (coarse `O(n^2)`)
- **Proposed auxiliary space:** `O(A)` (coarse `O(n)`)
- **Entrypoint:** `CoinChange.minimumCoins`
- **Input size:** A = amount; C = number of coin denominations; n = max(A,C).
- **Assumptions:** Analyze minimumCoins, not change. Amount A≥1 and denominations are positive; C≥1. Use n=max(A,C) for coarse scoring and treat fixed-width integer operations as O(1). Exclude input and scalar output.
- **Time rationale:** The method initializes A+1 entries, then for each of A positive amounts scans all C coin denominations. Time is O(A*C + A); for A,C≤n this is O(n²).
- **Space rationale:** The single minimumCoins array has A+1 integer entries, so auxiliary space is O(A), bounded by O(n).

```java
package com.thealgorithms.dynamicprogramming;

/**
 * @author Varun Upadhyay (https://github.com/varunu28)
 */
public final class CoinChange {
    private CoinChange() {
    }

    /**
     * This method finds the number of combinations of getting change for a
     * given amount and change coins
     *
     * @param coins The list of coins
     * @param amount The amount for which we need to find the change Finds the
     * number of combinations of change
     */
    public static int change(int[] coins, int amount) {
        int[] combinations = new int[amount + 1];
        combinations[0] = 1;

        for (int coin : coins) {
            for (int i = coin; i < amount + 1; i++) {
                combinations[i] += combinations[i - coin];
            }
        }

        return combinations[amount];
    }

    /**
     * This method finds the minimum number of coins needed for a given amount.
     *
     * @param coins The list of coins
     * @param amount The amount for which we need to find the minimum number of
     * coins. Finds the minimum number of coins that make a given value.
     */
    public static int minimumCoins(int[] coins, int amount) {
        // minimumCoins[i] will store the minimum coins needed for amount i
        int[] minimumCoins = new int[amount + 1];

        minimumCoins[0] = 0;

        for (int i = 1; i <= amount; i++) {
            minimumCoins[i] = Integer.MAX_VALUE;
        }
        for (int i = 1; i <= amount; i++) {
            for (int coin : coins) {
                if (coin <= i) {
                    int subRes = minimumCoins[i - coin];
                    if (subRes != Integer.MAX_VALUE && subRes + 1 < minimumCoins[i]) {
                        minimumCoins[i] = subRes + 1;
                    }
                }
            }
        }

        return minimumCoins[amount];
    }
}
```

## axioma-20261030-broad-030 — Linear search

- **Source:** [searches/linear_search.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/searches/linear_search.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `1336d1906f4a77f0eaf8f8a49d2395bde1517d67deb3e6d94af67c4f9f9405d4`
- **Proposed time:** `O(n) worst case` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(1)` (coarse `O(1)`)
- **Entrypoint:** `linear_search`
- **Input size:** n = len(sequence).
- **Assumptions:** Analyze the iterative linear_search entrypoint only, not the recursive helper or command-line code. Element equality is O(1); input sequence is excluded.
- **Time rationale:** The loop compares items in order and may inspect every element when the target is absent or last. Each iteration does constant work.
- **Space rationale:** The loop stores only the current index and item reference.

```python
"""
This is a pure Python implementation of the linear search algorithm.

For doctests run following command:
python3 -m doctest -v linear_search.py

For manual testing run:
python3 linear_search.py
"""


def linear_search(sequence: list, target: int) -> int:
    """A pure Python implementation of a linear search algorithm

    :param sequence: a collection with comparable items (sorting is not required for
        linear search)
    :param target: item value to search
    :return: index of found item or -1 if item is not found

    Examples:
    >>> linear_search([0, 5, 7, 10, 15], 0)
    0
    >>> linear_search([0, 5, 7, 10, 15], 15)
    4
    >>> linear_search([0, 5, 7, 10, 15], 5)
    1
    >>> linear_search([0, 5, 7, 10, 15], 6)
    -1
    """
    for index, item in enumerate(sequence):
        if item == target:
            return index
    return -1


def rec_linear_search(sequence: list, low: int, high: int, target: int) -> int:
    """
    A pure Python implementation of a recursive linear search algorithm

    :param sequence: a collection with comparable items (as sorted items not required
        in Linear Search)
    :param low: Lower bound of the array
    :param high: Higher bound of the array
    :param target: The element to be found
    :return: Index of the key or -1 if key not found

    Examples:
    >>> rec_linear_search([0, 30, 500, 100, 700], 0, 4, 0)
    0
    >>> rec_linear_search([0, 30, 500, 100, 700], 0, 4, 700)
    4
    >>> rec_linear_search([0, 30, 500, 100, 700], 0, 4, 30)
    1
    >>> rec_linear_search([0, 30, 500, 100, 700], 0, 4, -6)
    -1
    """
    if not (0 <= high < len(sequence) and 0 <= low < len(sequence)):
        raise ValueError("Invalid upper or lower bound!")
    if high < low:
        return -1
    if sequence[low] == target:
        return low
    if sequence[high] == target:
        return high
    return rec_linear_search(sequence, low + 1, high - 1, target)


if __name__ == "__main__":
    user_input = input("Enter numbers separated by comma:\n").strip()
    sequence = [int(item.strip()) for item in user_input.split(",")]

    target = int(input("Enter a single number to be found in the list:\n").strip())
    result = linear_search(sequence, target)
    if result != -1:
        print(f"linear_search({sequence}, {target}) = {result}")
    else:
        print(f"{target} was not found in {sequence}")
```
