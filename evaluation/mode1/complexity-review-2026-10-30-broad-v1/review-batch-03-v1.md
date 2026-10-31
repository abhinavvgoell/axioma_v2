# Complexity calibration — batch 03 (proposed)

**Status:** Labels are proposed and pending owner review. Axioma has not been run on these cases. This packet is prepared ahead to keep work moving; review only this batch after batch 02 decisions are recorded. The packet includes the complete pinned source files.

Packet SHA-256: `df3fcbaa078a6a7471db0039bc332d55a87d307d3e29d674a5ea17c02c6354c8`

## axioma-20261030-broad-011 — Selection sort

- **Source:** [sorts/selection_sort.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/sorts/selection_sort.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `b127ba324e56ee5282b62b3336bc3c7e6e750414916c0222f6039cefb4bf2fa0`
- **Proposed time:** `O(n^2)` (scoring class `O(n^2)`)
- **Proposed auxiliary space:** `O(1)` (scoring class `O(1)`)
- **Entrypoint:** `selection_sort`
- **Input size:** n = len(collection); assume comparison of two elements is O(1).
- **Assumptions:** Input is a mutable sequence with O(1) indexed reads/writes. Element comparisons are O(1). Exclude the input and returned sequence.
- **Time rationale:** The outer loop runs n-1 times and the inner scan examines the remaining suffix. The total comparisons are (n-1)+(n-2)+...+1 = Θ(n²), independent of input order.
- **Space rationale:** The algorithm sorts the input sequence in place and uses only a fixed number of index variables and one temporary swap value.

```python
from collections.abc import MutableSequence
from typing import Any, Protocol


class Comparable(Protocol):
    def __lt__(self, other: Any, /) -> bool: ...


def selection_sort[T: Comparable](collection: MutableSequence[T]) -> MutableSequence[T]:
    """
    Sorts a list in ascending order using the selection sort algorithm.

    Selection sort divides the input list into a sorted and unsorted region.
    It repeatedly finds the minimum element from the unsorted region and
    places it at the end of the sorted region.

    Time Complexity: O(n²) in all cases
    Space Complexity: O(1)

    :param collection: A mutable sequence of comparable items to be sorted.
    :return: The same sequence sorted in ascending order.


    Time Complexity: O(n^2) - Due to the nested loops, where n is the length
        of the collection. The outer loop runs n-1 times, and the inner loop
        runs n-i-1 times for each iteration.
    Space Complexity: O(1) - Only a constant amount of extra space is used
        for variables (length, i, min_index, k).
    Examples:
    >>> selection_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]

    >>> selection_sort([])
    []

    >>> selection_sort([-2, -5, -45])
    [-45, -5, -2]

    >>> selection_sort([1])
    [1]

    >>> selection_sort([5, 4, 3, 2, 1])
    [1, 2, 3, 4, 5]

    >>> selection_sort([1, 2, 3, 4, 5])
    [1, 2, 3, 4, 5]

    >>> selection_sort([3, 3, 3, 3])
    [3, 3, 3, 3]

    >>> selection_sort([0])
    [0]

    >>> selection_sort([2, -3, 0, 5, -1])
    [-3, -1, 0, 2, 5]

    >>> selection_sort([0, 5, 3, 2, 2]) == sorted([0, 5, 3, 2, 2])
    True

    >>> selection_sort([-2, -5, -45]) == sorted([-2, -5, -45])
    True

    >>> selection_sort(["d", "a", "c", "b"])
    ['a', 'b', 'c', 'd']

    >>> selection_sort([3.2, 1.1, 2.4, 0.5])
    [0.5, 1.1, 2.4, 3.2]
    """
    length = len(collection)
    for i in range(length - 1):
        min_index = i
        for k in range(i + 1, length):
            if collection[k] < collection[min_index]:
                min_index = k
        if min_index != i:
            collection[i], collection[min_index] = collection[min_index], collection[i]
    return collection


if __name__ == "__main__":
    user_input = input("Enter numbers separated by a comma:\n").strip()
    unsorted = [int(item) for item in user_input.split(",")]
    sorted_list = selection_sort(unsorted)
    print("Sorted List:", sorted_list)
```

## axioma-20261030-broad-012 — Recursive 0/1 knapsack without memoization

- **Source:** [knapsack/recursive_approach_knapsack.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/knapsack/recursive_approach_knapsack.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `46a4586f2afc04c16fa73911f27fa63e928b3263b5854386a223efd4615acae2`
- **Proposed time:** `O(2^n) worst case` (scoring class `O(2^n)`)
- **Proposed auxiliary space:** `O(n)` (scoring class `O(n)`)
- **Entrypoint:** `knapsack`
- **Input size:** n = number_of_items; weights and values each contain at least n entries.
- **Assumptions:** Start with index=0, number_of_items=n, max_weight>=0, and valid weights/values lists. Treat integer operations and list indexing as O(1). The exponential label is the worst case (for example, capacity is at least the sum of all nonnegative item weights); pruning can reduce work on other inputs.
- **Time rationale:** For each item, the function always explores the exclude branch and explores the include branch when it fits. When all include branches remain feasible, the recursion tree has 2^n leaves; work per node is constant.
- **Space rationale:** The recursion advances index by one on every call, so the deepest call chain has at most n+1 frames. No memoization table is allocated.

```python
# To get an insight into naive recursive way to solve the Knapsack problem


"""
A shopkeeper has bags of wheat that each have different weights and different profits.
eg.
no_of_items 4
profit 5 4 8 6
weight 1 2 4 5
max_weight 5
Constraints:
max_weight > 0
profit[i] >= 0
weight[i] >= 0
Calculate the maximum profit that the shopkeeper can make given maxmum weight that can
be carried.
"""


def knapsack(
    weights: list, values: list, number_of_items: int, max_weight: int, index: int
) -> int:
    """
    Function description is as follows-
    :param weights: Take a list of weights
    :param values: Take a list of profits corresponding to the weights
    :param number_of_items: number of items available to pick from
    :param max_weight: Maximum weight that could be carried
    :param index: the element we are looking at
    :return: Maximum expected gain
    >>> knapsack([1, 2, 4, 5], [5, 4, 8, 6], 4, 5, 0)
    13
    >>> knapsack([3 ,4 , 5], [10, 9 , 8], 3, 25, 0)
    27
    """
    if index == number_of_items:
        return 0
    ans1 = 0
    ans2 = 0
    ans1 = knapsack(weights, values, number_of_items, max_weight, index + 1)
    if weights[index] <= max_weight:
        ans2 = values[index] + knapsack(
            weights, values, number_of_items, max_weight - weights[index], index + 1
        )
    return max(ans1, ans2)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
```

## axioma-20261030-broad-013 — Merge sort implementation using pop from list front

- **Source:** [sorts/merge_sort.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/sorts/merge_sort.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `c37c47ef9c269dc5024ca579433f7c0cd7e61e3bb35e4885bbcebd9a24e2d9a3`
- **Proposed time:** `O(n^2) worst case` (scoring class `O(n^2)`)
- **Proposed auxiliary space:** `O(n)` (scoring class `O(n)`)
- **Entrypoint:** `merge_sort`
- **Input size:** n = len(collection); assume element comparisons are O(1).
- **Assumptions:** Analyze merge_sort for a list of comparable values with O(1) comparisons. Python list pop(0) shifts the remaining references and is O(k) for a list of length k. Report worst-case time; returned sorted list and temporary lists are included in the O(n) peak storage bound.
- **Time rationale:** The divide-and-conquer structure would normally be O(n log n), but merge repeatedly calls list.pop(0). Removing the first element shifts the remaining list, so a merge of two Θ(n)-sized halves can take Θ(n²) time on interleaved values. This top-level merge dominates lower levels in the worst case.
- **Space rationale:** Recursive slicing and merge result lists retain O(n) elements at peak: the active recursive slices decrease geometrically, and each merge holds only O(n) list elements at a time.

```python
"""
The merge sort algorithm.

For doctests, run the following command:
python -m doctest -v merge_sort.py
or
python3 -m doctest -v merge_sort.py
For manual testing, run:
python merge_sort.py
"""

from typing import Protocol


class Comparable(Protocol):
    def __lt__(self, other: object, /) -> bool: ...


def merge_sort[T: Comparable](collection: list[T]) -> list[T]:
    """
    Sorts a list using the merge sort algorithm.

    :param collection: A collection with comparable items.
    :return: The collection ordered in ascending order.

    Time Complexity: O(n log n)
    Space Complexity: O(n)

    Examples:
    >>> merge_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]

    >>> merge_sort([])
    []

    >>> merge_sort([-2, -45, -5])
    [-45, -5, -2]
    """

    def merge(left: list[T], right: list[T]) -> list[T]:
        """
        Merge two sorted lists into a single sorted list.

        :param left: Left collection
        :param right: Right collection
        :return: Merged result
        """
        result: list[T] = []
        while left and right:
            if right[0] < left[0]:
                result.append(right.pop(0))
            else:
                result.append(left.pop(0))
        result.extend(left)
        result.extend(right)
        return result

    if len(collection) <= 1:
        return collection
    mid_index = len(collection) // 2
    return merge(merge_sort(collection[:mid_index]), merge_sort(collection[mid_index:]))


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    try:
        user_input = input("Enter numbers separated by a comma:\n").strip()
        unsorted = [int(item) for item in user_input.split(",")]
        sorted_list = merge_sort(unsorted)
        print(*sorted_list, sep=",")
    except ValueError:
        print("Invalid input. Please enter valid integers separated by commas.")
```

## axioma-20261030-broad-014 — Longest common subsequence dynamic programming (Java)

- **Source:** [src/main/java/com/thealgorithms/dynamicprogramming/LongestCommonSubsequence.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/dynamicprogramming/LongestCommonSubsequence.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `ed98d5f455bd5e792a734d763bae810767a679333f3f160f353b2769ded84b5b`
- **Proposed time:** `O(m * k)` (scoring class `O(n^2)`)
- **Proposed auxiliary space:** `O(m * k)` (scoring class `O(n^2)`)
- **Entrypoint:** `LongestCommonSubsequence.getLCS`
- **Input size:** m = str1.length(), k = str2.length(); coarse n = max(m,k).
- **Assumptions:** Both strings are non-null. For the proposed coarse n² scoring class, analyze non-empty strings and set n=max(m,k) and assume m and k are of comparable order; the exact two-parameter bound is O(mk), not necessarily Θ(n²) when lengths are highly unbalanced. Java string splitting and character comparisons are assumed linear/constant per character respectively.
- **Time rationale:** The DP fills every cell of an (m+1)×(k+1) table, taking Θ(mk). Backtracking is O(m+k); building the returned subsequence by repeated string concatenation can take O(L²), where L≤min(m,k), which is bounded by O(mk) for non-empty inputs. The coarse score class uses n=max(m,k), so O(mk) is O(n²).
- **Space rationale:** The int DP table stores Θ(mk) cells. Character arrays and the reconstructed output use O(m+k), dominated by O(mk) when both strings are non-empty. The empty-input fast path returns before allocating the table.

```java
package com.thealgorithms.dynamicprogramming;

/**
 * This class implements the Longest Common Subsequence (LCS) problem.
 * The LCS of two sequences is the longest sequence that appears in both
 * sequences
 * in the same order, but not necessarily consecutively.
 *
 * This implementation uses dynamic programming to find the LCS of two strings.
 */
final class LongestCommonSubsequence {

    private LongestCommonSubsequence() {
    }

    /**
     * Returns the Longest Common Subsequence (LCS) of two given strings.
     *
     * @param str1 The first string.
     * @param str2 The second string.
     * @return The LCS of the two strings, or null if one of the strings is null.
     */
    public static String getLCS(String str1, String str2) {
        // If either string is null, return null as LCS can't be computed.
        if (str1 == null || str2 == null) {
            return null;
        }
        // If either string is empty, return an empty string as LCS.
        if (str1.length() == 0 || str2.length() == 0) {
            return "";
        }

        // Convert the strings into arrays of characters
        String[] arr1 = str1.split("");
        String[] arr2 = str2.split("");

        // lcsMatrix[i][j] = LCS(first i characters of str1, first j characters of str2)
        int[][] lcsMatrix = new int[arr1.length + 1][arr2.length + 1];

        // Base Case: Fill the LCS matrix 0th row & 0th column with 0s
        // as LCS of any string with an empty string is 0.
        for (int i = 0; i < arr1.length + 1; i++) {
            lcsMatrix[i][0] = 0;
        }
        for (int j = 1; j < arr2.length + 1; j++) {
            lcsMatrix[0][j] = 0;
        }

        // Build the LCS matrix by comparing characters of str1 & str2
        for (int i = 1; i < arr1.length + 1; i++) {
            for (int j = 1; j < arr2.length + 1; j++) {
                // If characters match, the LCS increases by 1
                if (arr1[i - 1].equals(arr2[j - 1])) {
                    lcsMatrix[i][j] = lcsMatrix[i - 1][j - 1] + 1;
                } else {
                    // Otherwise, take the maximum of the left or above values
                    lcsMatrix[i][j] = Math.max(lcsMatrix[i - 1][j], lcsMatrix[i][j - 1]);
                }
            }
        }

        // Call helper function to reconstruct the LCS from the matrix
        return lcsString(str1, str2, lcsMatrix);
    }

    /**
     * Reconstructs the LCS string from the LCS matrix.
     *
     * @param str1      The first string.
     * @param str2      The second string.
     * @param lcsMatrix The matrix storing the lengths of LCSs
     *                  of substrings of str1 and str2.
     * @return The LCS string.
     */
    public static String lcsString(String str1, String str2, int[][] lcsMatrix) {
        StringBuilder lcs = new StringBuilder(); // Hold the LCS characters.
        int i = str1.length(); // Start from the end of str1.
        int j = str2.length(); // Start from the end of str2.

        // Trace back through the LCS matrix to reconstruct the LCS
        while (i > 0 && j > 0) {
            // If characters match, add to the LCS and move diagonally in the matrix
            if (str1.charAt(i - 1) == str2.charAt(j - 1)) {
                lcs.append(str1.charAt(i - 1));
                i--;
                j--;
            } else if (lcsMatrix[i - 1][j] > lcsMatrix[i][j - 1]) {
                // If the value above is larger, move up
                i--;
            } else {
                // If the value to the left is larger, move left
                j--;
            }
        }

        return lcs.reverse().toString(); // LCS built in reverse, so reverse it back
    }
}
```

## axioma-20261030-broad-015 — Fibonacci search with sortedness validation

- **Source:** [src/main/java/com/thealgorithms/searches/FibonacciSearch.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/searches/FibonacciSearch.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `372928b9da6ce36c1e36c3178a7503db6663bcee3a23208f1e5248b29ebcb4aa`
- **Proposed time:** `O(n)` (scoring class `O(n)`)
- **Proposed auxiliary space:** `O(1)` (scoring class `O(1)`)
- **Entrypoint:** `FibonacciSearch.find`
- **Input size:** n = array.length; array is required to be sorted.
- **Assumptions:** Analyze the full public find call, including isSorted, not just the search loop. Array is non-null and indexed access and Comparable.compareTo are O(1). An empty array is rejected in O(1). The imported SearchAlgorithm interface only declares the method contract.
- **Time rationale:** Before its Fibonacci-search loop, find calls isSorted, which scans adjacent array elements and takes O(n). The subsequent Fibonacci search takes O(log n), so total method time remains O(n).
- **Space rationale:** Both sortedness validation and Fibonacci search keep only a fixed number of indices and Fibonacci counters; no size-dependent storage or recursion is used.

```java
package com.thealgorithms.searches;

import com.thealgorithms.devutils.searches.SearchAlgorithm;

/**
 * FibonacciSearch is a search algorithm that finds the position of a target value in
 * a sorted array using Fibonacci numbers.
 *
 * <p>
 * The time complexity for this search algorithm is O(log n).
 * The space complexity for this search algorithm is O(1).
 * </p>
 *
 * <p>
 * Note: This algorithm requires that the input array be sorted.
 * </p>
 */
public final class FibonacciSearch implements SearchAlgorithm {

    /**
     * Finds the index of the specified key in a sorted array using Fibonacci search.
     *
     * @param array The sorted array to search.
     * @param key The element to search for.
     * @param <T> The type of the elements in the array, which must be comparable.
     * @throws IllegalArgumentException if the input array is null, not sorted or empty, or if the key is null.
     * @return The index of the key if found, otherwise -1.
     */
    @Override
    public <T extends Comparable<T>> int find(T[] array, T key) {
        if (array == null) {
            throw new IllegalArgumentException("Input array must not be null.");
        }
        if (array.length == 0) {
            throw new IllegalArgumentException("Input array must not be empty.");
        }
        if (!isSorted(array)) {
            throw new IllegalArgumentException("Input array must be sorted.");
        }
        if (key == null) {
            throw new IllegalArgumentException("Key must not be null.");
        }

        int fibMinus1 = 1;
        int fibMinus2 = 0;
        int fibNumber = fibMinus1 + fibMinus2;
        int n = array.length;

        while (fibNumber < n) {
            fibMinus2 = fibMinus1;
            fibMinus1 = fibNumber;
            fibNumber = fibMinus2 + fibMinus1;
        }

        int offset = -1;

        while (fibNumber > 1) {
            int i = Math.min(offset + fibMinus2, n - 1);

            if (array[i].compareTo(key) < 0) {
                fibNumber = fibMinus1;
                fibMinus1 = fibMinus2;
                fibMinus2 = fibNumber - fibMinus1;
                offset = i;
            } else if (array[i].compareTo(key) > 0) {
                fibNumber = fibMinus2;
                fibMinus1 = fibMinus1 - fibMinus2;
                fibMinus2 = fibNumber - fibMinus1;
            } else {
                return i;
            }
        }

        if (fibMinus1 == 1 && offset + 1 < n && array[offset + 1].compareTo(key) == 0) {
            return offset + 1;
        }

        return -1;
    }

    private <T extends Comparable<T>> boolean isSorted(T[] array) {
        for (int i = 1; i < array.length; i++) {
            if (array[i - 1].compareTo(array[i]) > 0) {
                return false;
            }
        }
        return true;
    }
}
```
