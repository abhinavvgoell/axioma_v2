# Complexity calibration — batch 04 (proposed)

**Status:** Five labels are proposed and pending owner confirmation. Axioma has not been run. Full source code is included; review cases 016–020 after the preceding batches.

Packet SHA-256: `a8b8cf234741da71407c014ec5a2b2b8d21ae57d27c5d16c4e9af596175d8e4b`

## axioma-20261030-broad-016 — Merge overlapping intervals

- **Source:** [data_structures/arrays/merge_intervals.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/data_structures/arrays/merge_intervals.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `af3ae62a436979f4023b8492605b3b2d12c385147ad8621563e03e958e2cb7de`
- **Proposed time:** `O(n log n)` (coarse `O(n log n)`)
- **Proposed auxiliary space:** `O(n)` (coarse `O(n)`)
- **Entrypoint:** `merge_intervals`
- **Input size:** n = number of intervals.
- **Assumptions:** Intervals are two-element lists of integers. Sorting uses O(n log n) comparisons, each O(1). Count returned intervals and temporary copies in space; exclude the input.
- **Time rationale:** Sorting the copied interval list by start takes O(n log n). Validation and the one-pass merge each take O(n), so sorting dominates.
- **Space rationale:** The sorted copy, merged output, and interval copies each require O(n) storage.

```python
def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """
    Merge all overlapping intervals.

    Each interval is represented as a list of two integers [start, end].
    The function merges overlapping intervals and returns a list of
    non-overlapping intervals sorted by start time.

    Parameters:
    intervals (list[list[int]]): A list of intervals.

    Returns:
    list[list[int]]: A list of merged non-overlapping intervals.

    Edge Cases Handled:
    - Empty list: returns []
    - Single interval: returns the interval itself
    - Intervals already sorted or unsorted
    - Fully overlapping intervals
    - Invalid intervals (e.g., [[]] or intervals not having exactly
      2 integers) raise ValueError

    Examples:
    >>> merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
    [[1, 6], [8, 10], [15, 18]]
    >>> merge_intervals([[1, 4], [4, 5]])
    [[1, 5]]
    >>> merge_intervals([[6, 8], [1, 3], [2, 4]])
    [[1, 4], [6, 8]]
    >>> merge_intervals([])
    []
    >>> merge_intervals([[1, 4]])
    [[1, 4]]

    Time Complexity:
    O(n log n) - sorting the intervals, where n is the number of intervals.

    Space Complexity:
    O(n) - storing the merged intervals.
    """

    if not intervals:
        return []

    for interval in intervals:
        msg = f"Each interval must have exactly 2 integers, got {interval}"
        if len(interval) != 2:
            raise ValueError(msg)

    # Sort intervals based on the start time
    # Sort a copy so the caller's list (and its inner lists) are never mutated
    sorted_intervals = sorted(intervals, key=lambda interval: interval[0])

    merged: list[list[int]] = [sorted_intervals[0][:]]

    for current in sorted_intervals[1:]:
        last = merged[-1]

        # If current interval overlaps with the last merged interval
        if current[0] <= last[1]:
            last[1] = max(last[1], current[1])
        else:
            merged.append(current[:])
    return merged
```

## axioma-20261030-broad-017 — Fractional knapsack by value-to-weight ratio

- **Source:** [greedy_methods/fractional_knapsack.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/greedy_methods/fractional_knapsack.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `af6c079f473bb580087192af278732b54b48a5cb2e7742ac374d3352bc57916f`
- **Proposed time:** `O(n log n)` (coarse `O(n log n)`)
- **Proposed auxiliary space:** `O(n)` (coarse `O(n)`)
- **Entrypoint:** `frac_knapsack`
- **Input size:** n = number of items; vl and wt have length n.
- **Assumptions:** Analyze valid input with vl and wt equal in length n, n matching that length, positive weights, and O(1) arithmetic/comparisons. Exclude input and scalar output.
- **Time rationale:** Sorting n value/weight pairs takes O(n log n). Building lists and prefix sums is O(n), bisect is O(log n), and the final slice sum is O(n); sorting dominates.
- **Space rationale:** The sorted tuple list, copied value and weight lists, and accumulated weights each use O(n) storage.

```python
from bisect import bisect
from itertools import accumulate


def frac_knapsack(vl, wt, w, n):
    """
    >>> frac_knapsack([60, 100, 120], [10, 20, 30], 50, 3)
    240.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 10, 4)
    105.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 8, 4)
    95.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6], 8, 4)
    60.0
    >>> frac_knapsack([10, 40, 30], [5, 4, 6, 3], 8, 4)
    60.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 0, 4)
    0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 8, 0)
    95.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], -8, 4)
    0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 8, -4)
    95.0
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 800, 4)
    130
    >>> frac_knapsack([10, 40, 30, 50], [5, 4, 6, 3], 8, 400)
    95.0
    >>> frac_knapsack("ABCD", [5, 4, 6, 3], 8, 400)
    Traceback (most recent call last):
        ...
    TypeError: unsupported operand type(s) for /: 'str' and 'int'
    """

    r = sorted(zip(vl, wt), key=lambda x: x[0] / x[1], reverse=True)
    vl, wt = [i[0] for i in r], [i[1] for i in r]
    acc = list(accumulate(wt))
    k = bisect(acc, w)
    return (
        0
        if k == 0
        else sum(vl[:k]) + (w - acc[k - 1]) * (vl[k]) / (wt[k])
        if k != n
        else sum(vl[:k])
    )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
```

## axioma-20261030-broad-018 — DFS topological ordering

- **Source:** [graphs/g_topological_sort.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/graphs/g_topological_sort.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `8f885c3f490986ab1d25e81a3186f8fb40e47cd3b9e337f4ef41420917caa6d0`
- **Proposed time:** `O(V + E)` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(V)` (coarse `O(n)`)
- **Entrypoint:** `topological_sort`
- **Input size:** V = len(graph); E = total adjacency entries; n = V + E.
- **Assumptions:** Analyze one call on a DAG with dense vertex IDs 0..V-1, valid adjacency endpoints, a zero-initialized visited list of length V, and an empty global stack. The recursive implementation may hit Python recursion limits on deep graphs. Scoring class uses n=V+E.
- **Time rationale:** With a zeroed visited list, the driver starts DFS once per unvisited vertex. Each vertex is marked before descent and each adjacency entry is checked once, so work is O(V+E).
- **Space rationale:** Recursion depth is at most V and each vertex is appended once to the output stack, giving O(V) space.

```python
# Author: Phyllipe Bezerra (https://github.com/pmba)

clothes = {
    0: "underwear",
    1: "pants",
    2: "belt",
    3: "suit",
    4: "shoe",
    5: "socks",
    6: "shirt",
    7: "tie",
    8: "watch",
}

graph = [[1, 4], [2, 4], [3], [], [], [4], [2, 7], [3], []]

visited = [0 for x in range(len(graph))]
stack = []


def print_stack(stack, clothes) -> None:
    order = 1
    while stack:
        current_clothing = stack.pop()
        print(order, clothes[current_clothing])
        order += 1


def depth_first_search(u, visited, graph) -> None:
    visited[u] = 1
    for v in graph[u]:
        if not visited[v]:
            depth_first_search(v, visited, graph)

    stack.append(u)


def topological_sort(graph, visited) -> None:
    for v in range(len(graph)):
        if not visited[v]:
            depth_first_search(v, visited, graph)


if __name__ == "__main__":
    topological_sort(graph, visited)
    print(stack)
    print_stack(stack, clothes)
```

## axioma-20261030-broad-019 — Sentinel linear search

- **Source:** [src/main/java/com/thealgorithms/searches/SentinelLinearSearch.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/searches/SentinelLinearSearch.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `8dcad37b5d63c1e26c482b91e8a34fe2fec14848ae037dbcd91046747153eca0`
- **Proposed time:** `O(n) worst case` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(1)` (coarse `O(1)`)
- **Entrypoint:** `SentinelLinearSearch.find`
- **Input size:** n = array.length.
- **Assumptions:** Analyze one find call with O(1) comparisons. The method temporarily replaces the last array element and restores it. The imported SearchAlgorithm type only declares the method contract.
- **Time rationale:** The sentinel loop can inspect n entries when the key is absent; the null-key helper also scans n entries. Setup and restoration are constant-time.
- **Space rationale:** The methods store only the prior last value and a loop index.

```java
package com.thealgorithms.searches;

import com.thealgorithms.devutils.searches.SearchAlgorithm;

/**
 * Sentinel Linear Search is a variation of linear search that eliminates the
 * need to check the array bounds in each iteration by placing the search key
 * at the end of the array as a sentinel value.
 *
 * <p>
 * The algorithm works by:
 * 1. Storing the last element of the array
 * 2. Placing the search key at the last position (sentinel)
 * 3. Searching from the beginning without bound checking
 * 4. If found before the last position, return the index
 * 5. If found at the last position, check if it was originally there
 *
 * <p>
 * Time Complexity:
 * - Best case: O(1) - when the element is at the first position
 * - Average case: O(n) - when the element is in the middle
 * - Worst case: O(n) - when the element is not present
 *
 * <p>
 * Space Complexity: O(1) - only uses constant extra space
 *
 * <p>
 * Advantages over regular linear search:
 * - Reduces the number of comparisons by eliminating bound checking
 * - Slightly more efficient in practice due to fewer conditional checks
 *
 * @author TheAlgorithms Contributors
 * @see LinearSearch
 * @see SearchAlgorithm
 */
public final class SentinelLinearSearch implements SearchAlgorithm {
    /**
     * Performs sentinel linear search on the given array.
     *
     * @param array the array to search in
     * @param key the element to search for
     * @param <T> the type of elements in the array, must be Comparable
     * @return the index of the first occurrence of the key, or -1 if not found
     * @throws IllegalArgumentException if the array is null
     */
    @Override
    public <T extends Comparable<T>> int find(T[] array, T key) {
        if (array == null) {
            throw new IllegalArgumentException("Array cannot be null");
        }

        if (array.length == 0) {
            return -1;
        }

        if (key == null) {
            return findNull(array);
        }

        // Store the last element
        T lastElement = array[array.length - 1];

        // Place the sentinel (search key) at the end
        array[array.length - 1] = key;

        int i = 0;
        // Search without bound checking since sentinel guarantees we'll find the key
        // Null check for array element to skip nulls and prevent NPE when array contains null elements
        while (array[i] == null || array[i].compareTo(key) != 0) {
            i++;
        }

        // Restore the original last element
        array[array.length - 1] = lastElement;

        // Check if we found the key before the sentinel position
        // or if the original last element was the key we were looking for
        if (i < array.length - 1 || (lastElement != null && lastElement.compareTo(key) == 0)) {
            return i;
        }

        return -1; // Key not found
    }

    /**
     * Helper method to find null values in the array.
     *
     * @param array the array to search in
     * @param <T> the type of elements in the array
     * @return the index of the first null element, or -1 if not found
     */
    private <T extends Comparable<T>> int findNull(T[] array) {
        for (int i = 0; i < array.length; i++) {
            if (array[i] == null) {
                return i;
            }
        }
        return -1;
    }
}
```

## axioma-20261030-broad-020 — Counting sort with value-range histogram

- **Source:** [src/main/java/com/thealgorithms/sorts/CountingSort.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/sorts/CountingSort.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `861aec19c0c3234874d11014c0af65aed14dcab64361fbcbd54d1cfb1d30be74`
- **Proposed time:** `O(n + k)` (coarse `O(n)`)
- **Proposed auxiliary space:** `O(n + k)` (coarse `O(n)`)
- **Entrypoint:** `CountingSort.sort`
- **Input size:** n = array length; k = max(array)-min(array)+1.
- **Assumptions:** Input is an int array; k is positive and fits array-size limits. For coarse scoring assume value spread k=O(n); exact time and auxiliary space are O(n+k). Treat fixed-width integer operations and array access as O(1).
- **Time rationale:** The method scans n values for min/max, builds a k-cell histogram, accumulates k counts, and reconstructs n outputs: O(n+k). The coarse O(n) score requires k=O(n).
- **Space rationale:** The count array has k entries and the result has n entries, so space is O(n+k); coarse O(n) requires k=O(n).

```java
package com.thealgorithms.sorts;

import java.util.Arrays;

/**
 * A standard implementation of the Counting Sort algorithm for integer arrays.
 * This implementation has a time complexity of O(n + k), where n is the number
 * of elements in the input array and k is the range of the input.
 * It works only with integer arrays.
 *
 * The space complexity is O(k), where k is the range of the input integers.
 *
 * Note: This implementation handles negative integers as it
 * calculates the range based on the minimum and maximum values of the array.
 *
 */
public final class CountingSort {
    private CountingSort() {
    }

    /**
     * Sorts an array of integers using the Counting Sort algorithm.
     *
     * @param array the array to be sorted
     * @return the sorted array
     */
    public static int[] sort(int[] array) {
        if (array.length == 0) {
            return array;
        }
        final var stats = Arrays.stream(array).summaryStatistics();
        final int min = stats.getMin();
        int[] count = computeHistogram(array, min, stats.getMax() - min + 1);
        toCumulative(count);
        return reconstructSorted(count, min, array);
    }

    private static int[] computeHistogram(final int[] array, final int shift, final int spread) {
        int[] res = new int[spread];
        for (final var value : array) {
            res[value - shift]++;
        }
        return res;
    }

    private static void toCumulative(int[] count) {
        for (int i = 1; i < count.length; i++) {
            count[i] += count[i - 1];
        }
    }

    private static int[] reconstructSorted(final int[] cumulativeCount, final int shift, final int[] array) {
        int[] res = new int[array.length];
        for (int i = array.length - 1; i >= 0; i--) {
            res[cumulativeCount[array[i] - shift] - 1] = array[i];
            cumulativeCount[array[i] - shift]--;
        }
        return res;
    }
}
```
