# Complexity calibration — batch 02 (proposed)

**Status:** All five labels are proposed and pending owner confirmation. Axioma has not been run on these cases. Please review each exact source excerpt and its assumptions. Reply with `axioma-20261030-broad-006: approve/revise` through `...010`. This is calibration data, not the untouched final evaluation.

Packet SHA-256: `3f06adcb60b84f909f1f4dc9b105cd0425d1627ba39f0820a6ab618249a493b9`

## axioma-20261030-broad-006 — Recursive binary search with list slicing

- **Source:** [searches/simple_binary_search.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/searches/simple_binary_search.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `bf133ae3719eb1ee56f418ef103236228fb871ccb1443d013c67b9f68a414807`
- **Proposed time:** `O(n)` (scored as `O(n)`)
- **Proposed auxiliary space:** `O(n)` (scored as `O(n)`)
- **Entrypoint:** `binary_search`
- **Input size:** n = len(a_list); assume O(1) element comparisons.
- **Assumptions:** Input is a sorted Python list and target comparisons are O(1). Count slice copies as auxiliary storage while recursive frames retain their arguments; exclude the input and returned scalar.
- **Time rationale:** Each call performs a slice copy of the remaining list before recursing. Across levels, copied lengths form a geometric sum n + n/2 + n/4 + ... = O(n), which dominates the O(log n) comparisons and calls.
- **Space rationale:** The recursive stack alone is O(log n), but active sliced lists across the recursive calls have geometrically decreasing lengths whose total is O(n); auxiliary space is therefore O(n).

```python
"""
Pure Python implementation of a binary search algorithm.

For doctests run following command:
python3 -m doctest -v simple_binary_search.py

For manual testing run:
python3 simple_binary_search.py
"""

from __future__ import annotations


def binary_search(a_list: list[int], item: int) -> bool:
    """
    >>> test_list = [0, 1, 2, 8, 13, 17, 19, 32, 42]
    >>> binary_search(test_list, 3)
    False
    >>> binary_search(test_list, 13)
    True
    >>> binary_search([4, 4, 5, 6, 7], 4)
    True
    >>> binary_search([4, 4, 5, 6, 7], -10)
    False
    >>> binary_search([-18, 2], -18)
    True
    >>> binary_search([5], 5)
    True
    >>> binary_search(['a', 'c', 'd'], 'c')
    True
    >>> binary_search(['a', 'c', 'd'], 'f')
    False
    >>> binary_search([], 1)
    False
    >>> binary_search([-.1, .1 , .8], .1)
    True
    >>> binary_search(range(-5000, 5000, 10), 80)
    True
    >>> binary_search(range(-5000, 5000, 10), 1255)
    False
    >>> binary_search(range(0, 10000, 5), 2)
    False
    """
    if len(a_list) == 0:
        return False
    midpoint = len(a_list) // 2
    if a_list[midpoint] == item:
        return True
    if item < a_list[midpoint]:
        return binary_search(a_list[:midpoint], item)
    else:
        return binary_search(a_list[midpoint + 1 :], item)


if __name__ == "__main__":
    user_input = input("Enter numbers separated by comma:\n").strip()
    sequence = [int(item.strip()) for item in user_input.split(",")]
    target = int(input("Enter the number to be found in the list:\n").strip())
    not_str = "" if binary_search(sequence, target) else "not "
    print(f"{target} was {not_str}found in {sequence}")
```

## axioma-20261030-broad-007 — In-place heap sort

- **Source:** [sorts/heap_sort.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/sorts/heap_sort.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `3ee8373cadc1fc534dde49496a86eb14796a6a355b896d0107758aee907395b4`
- **Proposed time:** `O(n log n)` (scored as `O(n log n)`)
- **Proposed auxiliary space:** `O(log n)` (scored as `O(log n)`)
- **Entrypoint:** `heap_sort`
- **Input size:** n = len(unsorted); assume O(1) comparisons and swaps.
- **Assumptions:** Input is a mutable list; comparisons and swaps are O(1). Count recursion stack as auxiliary space and exclude the input list.
- **Time rationale:** Heap construction by repeated heapify is O(n) in this implementation’s bottom-up build, followed by n root removals; each recursive heapify descends at most O(log n), giving O(n log n) total.
- **Space rationale:** The list is sorted in place. Recursive heapify uses at most the heap height, O(log n), stack frames.

```python
"""
A pure Python implementation of the heap sort algorithm.
"""

from typing import Protocol


class Comparable(Protocol):
    def __lt__(self, other: object, /) -> bool: ...


def heapify[T: Comparable](unsorted: list[T], index: int, heap_size: int) -> None:
    """
    :param unsorted: unsorted list containing comparable items
    :param index: index
    :param heap_size: size of the heap
    :return: None
    >>> unsorted = [1, 4, 3, 5, 2]
    >>> heapify(unsorted, 0, len(unsorted))
    >>> unsorted
    [4, 5, 3, 1, 2]
    >>> heapify(unsorted, 0, len(unsorted))
    >>> unsorted
    [5, 4, 3, 1, 2]
    """
    largest = index
    left_index = 2 * index + 1
    right_index = 2 * index + 2

    if left_index < heap_size and unsorted[largest] < unsorted[left_index]:
        largest = left_index

    if right_index < heap_size and unsorted[largest] < unsorted[right_index]:
        largest = right_index

    if largest != index:
        unsorted[largest], unsorted[index] = (unsorted[index], unsorted[largest])
        heapify(unsorted, largest, heap_size)


def heap_sort[T: Comparable](unsorted: list[T]) -> list[T]:
    """
    A pure Python implementation of the heap sort algorithm.

    :param unsorted: a mutable collection of comparable items
    :return: the same collection ordered by ascending

    Examples:
    >>> heap_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> heap_sort([])
    []
    >>> heap_sort([-2, -5, -45])
    [-45, -5, -2]
    >>> heap_sort([3, 7, 9, 28, 123, -5, 8, -30, -200, 0, 4])
    [-200, -30, -5, 0, 3, 4, 7, 8, 9, 28, 123]
    >>> heap_sort(["banana", "apple", "cherry"])
    ['apple', 'banana', 'cherry']
    >>> heap_sort([3.14, 1.5, 2.7])
    [1.5, 2.7, 3.14]
    >>> heap_sort([1, "two"])  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    TypeError: ...
    """
    n = len(unsorted)
    for i in range(n // 2 - 1, -1, -1):
        heapify(unsorted, i, n)
    for i in range(n - 1, 0, -1):
        unsorted[0], unsorted[i] = unsorted[i], unsorted[0]
        heapify(unsorted, 0, i)
    return unsorted


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    user_input = input("Enter numbers separated by a comma:\n").strip()
    if user_input:
        unsorted = [int(item) for item in user_input.split(",")]
        print(f"{heap_sort(unsorted) = }")
```

## axioma-20261030-broad-008 — Recursive binary search in Java

- **Source:** [src/main/java/com/thealgorithms/searches/RecursiveBinarySearch.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/searches/RecursiveBinarySearch.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `97b9025bad50969b7ae559c06947f45353e3ec23d996ae0f5f96cc4ba39eaf7b`
- **Proposed time:** `O(log n)` (scored as `O(log n)`)
- **Proposed auxiliary space:** `O(log n)` (scored as `O(log n)`)
- **Entrypoint:** `RecursiveBinarySearch.find`
- **Input size:** n = array length; sorted input.
- **Assumptions:** Analyze find and its recursive helper, not the interactive main method. Input array is non-null, sorted under the comparator, indexed access and compareTo are O(1); exclude input storage.
- **Time rationale:** Each recursive call halves the inclusive search interval and does constant work, so there are O(log n) calls.
- **Space rationale:** The recursive call stack has one frame per halving step, O(log n).

```java
// Code by Pronay Debnath
// Created:- 1/10/2023
// File Name should be RecursiveBinarySearch.java
// Explanation:- https://www.tutorialspoint.com/java-program-for-binary-search-recursive
package com.thealgorithms.searches;

import java.util.Scanner;

// Create a SearchAlgorithm class with a generic type
abstract class SearchAlgorithm<T extends Comparable<T>> {
    // Abstract find method to be implemented by subclasses
    public abstract int find(T[] arr, T target);
}

public class RecursiveBinarySearch<T extends Comparable<T>> extends SearchAlgorithm<T> {

    // Override the find method as required
    @Override
    public int find(T[] arr, T target) {
        // Call the recursive binary search function
        return binsear(arr, 0, arr.length - 1, target);
    }

    // Recursive binary search function
    public int binsear(T[] arr, int left, int right, T target) {
        if (right < left) {
            // Element is not present in the array
            return -1;
        }
        final int mid = left + (right - left) / 2;

        // Compare the element at the middle with the target
        final int comparison = arr[mid].compareTo(target);

        // If the element is equal to the target, return its index
        if (comparison == 0) {
            return mid;
        }

        // If the element is greater than the target, search in the left subarray
        if (comparison > 0) {
            return binsear(arr, left, mid - 1, target);
        }

        // Otherwise, search in the right subarray
        return binsear(arr, mid + 1, right, target);
    }

    public static void main(String[] args) {
        try (Scanner sc = new Scanner(System.in)) {
            // User inputs
            System.out.print("Enter the number of elements in the array: ");
            int n = sc.nextInt();

            Integer[] a = new Integer[n]; // You can change the array type as needed

            System.out.println("Enter the elements in sorted order:");

            for (int i = 0; i < n; i++) {
                a[i] = sc.nextInt();
            }

            System.out.print("Enter the target element to search for: ");
            int t = sc.nextInt();

            RecursiveBinarySearch<Integer> searcher = new RecursiveBinarySearch<>();
            int res = searcher.find(a, t);

            if (res == -1) {
                System.out.println("Element not found in the array.");
            } else {
                System.out.println("Element found at index " + res);
            }
        }
    }
}
```

## axioma-20261030-broad-009 — Naive recursive Fibonacci

- **Source:** [src/main/java/com/thealgorithms/recursion/FibonacciSeries.java](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/recursion/FibonacciSeries.java) (commit `410f08753505a0af9e46423396e8768bc97cbc1c`)
- **SHA-256:** `9db818ba99b12a4a145275eac1a46e5d9d52253063318850f2487520156c70e4`
- **Proposed time:** `Theta(phi^n), bounded above by O(2^n)` (scored as `O(2^n)`)
- **Proposed auxiliary space:** `O(n)` (scored as `O(n)`)
- **Entrypoint:** `FibonacciSeries.fibonacci`
- **Input size:** n is a non-negative integer.
- **Assumptions:** Analyze the recursive method for n >= 0; primitive integer addition and comparisons are treated as O(1). Integer overflow does not change the number of calls. The exact Θ(φ^n) note is explanatory; proposed coarse label is O(2^n).
- **Time rationale:** The recurrence is T(n)=T(n-1)+T(n-2)+O(1), whose tight growth is Θ(φ^n). The conventional coarser class accepted for this packet is O(2^n).
- **Space rationale:** The deepest recursive chain decreases n by one until the base case, so the stack depth is O(n).

```java
package com.thealgorithms.recursion;

/**
 * The Fibonacci series is a sequence of numbers where each number is the sum of the two preceding ones,
 * starting with 0 and 1.
 * <p>
 * Example:
 * 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ...
 * </p>
 * <p>
 * This specific implementation demonstrates a <b>Naive Recursive approach</b> with {@code O(2^n)} time complexity.
 * For more performant variations or different programming paradigms, see:
 * <ul>
 * <li>{@link com.thealgorithms.maths.FibonacciLoop} - Standard Iterative (Loop) approach</li>
 * <li>{@link com.thealgorithms.dynamicprogramming.Fibonacci} - Dynamic Programming variants (Memoization / Bottom-Up)</li>
 * <li>{@link com.thealgorithms.maths.FibonacciJavaStreams} - Functional approach using Java Streams</li>
 * <li>{@link com.thealgorithms.maths.FibonacciNumberGoldenRation} - Closed-form expression using Binet's formula</li>
 * <li>{@link com.thealgorithms.maths.FibonacciNumberCheck} - Utility to check if a given number is a Fibonacci number</li>
 * <li>{@link com.thealgorithms.matrix.matrixexponentiation.Fibonacci} - O(log n) Matrix Exponentiation approach</li>
 * </ul>
 */
public final class FibonacciSeries {
    private FibonacciSeries() {
        throw new UnsupportedOperationException("Utility class");
    }

    /**
     * Calculates the nth term in the Fibonacci sequence using recursion.
     *
     * @param n the position in the Fibonacci sequence (must be non-negative)
     * @return the nth Fibonacci number
     * @throws IllegalArgumentException if n is negative
     */
    public static int fibonacci(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("n must be a non-negative integer");
        }
        if (n <= 1) {
            return n;
        }
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}
```

## axioma-20261030-broad-010 — Matrix-chain order dynamic programming

- **Source:** [dynamic_programming/matrix_chain_order.py](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/dynamic_programming/matrix_chain_order.py) (commit `6e03a48579ca212a08b36be00378f887dc41a003`)
- **SHA-256:** `18cd15dd9f58090498d093f2db586f62bc3ffa5ae65f0358de34aaef62872032`
- **Proposed time:** `O(d^3) = O(M^3)` (scored as `O(n^3)`)
- **Proposed auxiliary space:** `O(d^2) = O(M^2)` (scored as `O(n^2)`)
- **Entrypoint:** `matrix_chain_order`
- **Input size:** d = len(array), M = d - 1 matrices.
- **Assumptions:** Input dimensions list has length d >= 2 and represents M=d-1 matrices. Treat integer arithmetic/comparison as O(1), as is standard for algorithmic complexity; exclude the input list and scalar return.
- **Time rationale:** The algorithm fills two d-by-d tables. The chain-length, start-index, and split-index loops perform Θ(d³) total candidate splits, with constant-time arithmetic/comparisons assumed.
- **Space rationale:** Two d-by-d tables are allocated, so auxiliary storage is Θ(d²).

```python
import sys

"""
Dynamic Programming
Implementation of Matrix Chain Multiplication
Time Complexity: O(n^3)
Space Complexity: O(n^2)

Reference: https://en.wikipedia.org/wiki/Matrix_chain_multiplication
"""


def matrix_chain_order(array: list[int]) -> tuple[list[list[int]], list[list[int]]]:
    """
    >>> matrix_chain_order([10, 30, 5])
    ([[0, 0, 0], [0, 0, 1500], [0, 0, 0]], [[0, 0, 0], [0, 0, 1], [0, 0, 0]])
    """
    n = len(array)
    matrix = [[0 for _ in range(n)] for _ in range(n)]
    sol = [[0 for _ in range(n)] for _ in range(n)]

    for chain_length in range(2, n):
        for a in range(1, n - chain_length + 1):
            b = a + chain_length - 1

            matrix[a][b] = sys.maxsize
            for c in range(a, b):
                cost = (
                    matrix[a][c] + matrix[c + 1][b] + array[a - 1] * array[c] * array[b]
                )
                if cost < matrix[a][b]:
                    matrix[a][b] = cost
                    sol[a][b] = c
    return matrix, sol


def print_optimal_solution(optimal_solution: list[list[int]], i: int, j: int) -> None:
    """
    Print order of matrix with Ai as Matrix.
    """

    if i == j:
        print("A" + str(i), end=" ")
    else:
        print("(", end=" ")
        print_optimal_solution(optimal_solution, i, optimal_solution[i][j])
        print_optimal_solution(optimal_solution, optimal_solution[i][j] + 1, j)
        print(")", end=" ")


def main() -> None:
    """
    Size of matrix created from array [30, 35, 15, 5, 10, 20, 25] will be:
    30*35 35*15 15*5 5*10 10*20 20*25
    """

    array = [30, 35, 15, 5, 10, 20, 25]
    n = len(array)

    matrix, optimal_solution = matrix_chain_order(array)

    print("No. of Operation required: " + str(matrix[1][n - 1]))
    print_optimal_solution(optimal_solution, 1, n - 1)


if __name__ == "__main__":
    main()
```
