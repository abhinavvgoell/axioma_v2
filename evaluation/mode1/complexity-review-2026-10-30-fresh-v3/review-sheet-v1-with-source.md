# Owner review packet — five external cases with source

**Status:** All time and auxiliary-space labels remain proposals. No Axioma output is included. Review each implementation with its assumptions before approving, revising, or excluding it.

**Space convention:** Exclude input storage and returned output; include auxiliary structures and recursion stack. The scoring class is a documented coarse normalization of the exact mathematical expression.

## 1. Binary search lower bound — `axioma-20261030-v3-01`

- **Language / family:** python / search
- **Entry point:** `bisect_left`
- **Proposed time:** `O(log n)` — Each loop iteration halves the active interval [lo, hi), and the function returns once the interval is empty. Initialization and final return are O(1).
- **Time assumptions:** sorted_collection is sorted ascending; item comparisons and indexed access are O(1); worst-case number of loop iterations is measured.
- **Proposed auxiliary space:** `O(1)` (scoring class `O(1)`)
- **Space rationale:** The implementation keeps only scalar indices and the midpoint; it allocates no input-sized auxiliary structure.
- **Space assumptions:** n = len(sorted_collection).
- **Source:** `searches/binary_search.py` at `6e03a48579ca212a08b36be00378f887dc41a003`; snapshot hash `bf2d0a3cfb68b0518857385cfb41fccebd21c4884b1bd00f44360027b584b88e`

```python
def bisect_left(
    sorted_collection: list[int], item: int, lo: int = 0, hi: int = -1
) -> int:
    """
    Locates the first element in a sorted array that is larger or equal to a given
    value.

    It has the same interface as
    https://docs.python.org/3/library/bisect.html#bisect.bisect_left .

    :param sorted_collection: some ascending sorted collection with comparable items
    :param item: item to bisect
    :param lo: lowest index to consider (as in sorted_collection[lo:hi])
    :param hi: past the highest index to consider (as in sorted_collection[lo:hi])
    :return: index i such that all values in sorted_collection[lo:i] are < item and all
        values in sorted_collection[i:hi] are >= item.

    Examples:
    >>> bisect_left([0, 5, 7, 10, 15], 0)
    0
    >>> bisect_left([0, 5, 7, 10, 15], 6)
    2
    >>> bisect_left([0, 5, 7, 10, 15], 20)
    5
    >>> bisect_left([0, 5, 7, 10, 15], 15, 1, 3)
    3
    >>> bisect_left([0, 5, 7, 10, 15], 6, 2)
    2
    >>> bisect_left([], 2)
    0
    >>> bisect_left([2, 2, 2], 2)
    0
    >>> bisect_left([1, 2, 2, 2, 4], 2)
    1
    """
    if hi < 0:
        hi = len(sorted_collection)

    while lo < hi:
        mid = lo + (hi - lo) // 2
        if sorted_collection[mid] < item:
            lo = mid + 1
        else:
            hi = mid

    return lo
```

**Your decision:** pending — approve, revise (give corrected label and reasoning), or exclude.

## 2. Insertion sort — `axioma-20261030-v3-02`

- **Language / family:** python / sorting
- **Entry point:** `insertion_sort`
- **Proposed time:** `O(n^2)` — In reverse order, the inner while loop shifts each new item across all prior items; total shifts sum to 1 + 2 + ... + (n-1) = Theta(n^2).
- **Time assumptions:** Worst-case time; comparisons and indexed reads/writes are O(1); collection supports mutable indexed access.
- **Proposed auxiliary space:** `O(1)` (scoring class `O(1)`)
- **Space rationale:** Insertion sort keeps the current value and index scalars and shifts elements within the input collection; it allocates no input-sized auxiliary structure.
- **Space assumptions:** n = len(collection); count auxiliary storage only, excluding the mutated input collection.
- **Source:** `sorts/insertion_sort.py` at `6e03a48579ca212a08b36be00378f887dc41a003`; snapshot hash `2b244e03a5831e74fc615090828949d6155b56eb1e898e34e021c73ac0723b75`

```python
def insertion_sort[T: Comparable](collection: MutableSequence[T]) -> MutableSequence[T]:
    """A pure Python implementation of the insertion sort algorithm

    :param collection: some mutable ordered collection with heterogeneous
    comparable items inside
    :return: the same collection ordered by ascending

    Complexity Analysis:
        Time Complexity:
            - Best Case: O(n) when the collection is already sorted
            - Average Case: O(n^2)
            - Worst Case: O(n^2) when the collection is sorted in reverse order

        Space Complexity:
            - O(1) because the algorithm sorts the collection in place and
              uses only a constant amount of additional memory

    Examples:
    >>> insertion_sort([0, 5, 3, 2, 2])
    [0, 2, 2, 3, 5]
    >>> insertion_sort([]) == sorted([])
    True
    >>> insertion_sort([-2, -5, -45]) == sorted([-2, -5, -45])
    True
    >>> insertion_sort(['d', 'a', 'b', 'e', 'c']) == sorted(['d', 'a', 'b', 'e', 'c'])
    True
    >>> values = [4, 2, 7, 1]
    >>> result = insertion_sort(values)
    >>> result is values
    True
    >>> values
    [1, 2, 4, 7]

    Equal-priority items retain their original relative order:
    >>> from dataclasses import dataclass, field
    >>> @dataclass(order=True)
    ... class Item:
    ...     priority: int
    ...     label: str = field(compare=False)
    >>> items = [Item(2, "A"), Item(1, "X"), Item(2, "B"), Item(1, "Y")]
    >>> insertion_sort(items)  # doctest: +NORMALIZE_WHITESPACE
    [Item(priority=1, label='X'), Item(priority=1, label='Y'),
     Item(priority=2, label='A'), Item(priority=2, label='B')]
    >>> other = [Item(2, "B"), Item(1, "Y"), Item(2, "A"), Item(1, "X")]
    >>> insertion_sort(other)  # doctest: +NORMALIZE_WHITESPACE
    [Item(priority=1, label='Y'), Item(priority=1, label='X'),
     Item(priority=2, label='B'), Item(priority=2, label='A')]

    >>> import random
    >>> collection = random.sample(range(-50, 50), 100)
    >>> insertion_sort(collection) == sorted(collection)
    True
    >>> import string
    >>> collection = random.choices(string.ascii_letters + string.digits, k=100)
    >>> insertion_sort(collection) == sorted(collection)
    True
    """

    for insert_index in range(1, len(collection)):
        insert_value = collection[insert_index]
        while insert_index > 0 and insert_value < collection[insert_index - 1]:
            collection[insert_index] = collection[insert_index - 1]
            insert_index -= 1
        collection[insert_index] = insert_value
    return collection
```

**Your decision:** pending — approve, revise (give corrected label and reasoning), or exclude.

## 3. Recursive binary-tree preorder traversal — `axioma-20261030-v3-03`

- **Language / family:** python / tree_traversal
- **Entry point:** `preorder`
- **Proposed time:** `O(n)` — The function yields once per node and recursively visits each existing left and right child exactly once; all per-node work is O(1).
- **Time assumptions:** Input is a finite binary tree; each node has at most two child references; count traversal time, not the time a caller may spend consuming yielded values beyond one O(1) yield per node.
- **Proposed auxiliary space:** `O(h), worst case O(n)` (scoring class `O(n)`)
- **Space rationale:** Recursive yield-from traversal retains one active generator/frame per level, using O(h) stack space; the worst case is O(n).
- **Space assumptions:** n is the node count and h is tree height; exclude the input tree and streamed yielded values. Worst case permits a skewed tree with h = n.
- **Source:** `data_structures/binary_tree/binary_tree_traversals.py` at `6e03a48579ca212a08b36be00378f887dc41a003`; snapshot hash `828ca8cdba0a2f30dbace78ca4017eb83beea7266928d41de89b24cc6db434d2`

```python
def preorder(root: Node | None) -> Generator[int]:
    """
    Pre-order traversal visits root node, left subtree, right subtree.
    >>> list(preorder(make_tree()))
    [1, 2, 4, 5, 3]
    """
    if not root:
        return
    yield root.data
    yield from preorder(root.left)
    yield from preorder(root.right)
```

**Your decision:** pending — approve, revise (give corrected label and reasoning), or exclude.

## 4. Longest common subsequence — `axioma-20261030-v3-04`

- **Language / family:** java / dynamic_programming
- **Entry point:** `LongestCommonSubsequence.getLCS`
- **Proposed time:** `O(n^2)` — The DP table loops over every pair of positions, costing Theta(m*n). With m+n=n, this is O(n^2) and is Theta(n^2) for similarly sized strings. Converting strings and reconstructing the result add O(n), which is dominated.
- **Time assumptions:** Worst-case over pairs of strings with total length n; character/string operations are treated as O(1) under the standard word/cell model; null and empty inputs return in O(1) or linear setup.
- **Proposed auxiliary space:** `O(m*n)` (scoring class `O(n^2)`)
- **Space rationale:** The int DP matrix has (m+1)(n+1) cells. Character arrays add O(m+n), which is bounded by O(m*n) for non-empty inputs; null or empty inputs return in O(1) or allocate only linear arrays before a zero-dimension table.
- **Space assumptions:** m = len(str1), n_total = len(str1) + len(str2); exclude input strings and the returned LCS. The character arrays and result construction are O(m+n); the DP matrix is O(m*n). The scoring class uses n_total.
- **Source:** `src/main/java/com/thealgorithms/dynamicprogramming/LongestCommonSubsequence.java` at `410f08753505a0af9e46423396e8768bc97cbc1c`; snapshot hash `ed98d5f455bd5e792a734d763bae810767a679333f3f160f353b2769ded84b5b`

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

**Your decision:** pending — approve, revise (give corrected label and reasoning), or exclude.

## 5. Breadth-first search over child adjacency lists — `axioma-20261030-v3-05`

- **Language / family:** java / graph_traversal
- **Entry point:** `BreadthFirstSearch.search`
- **Proposed time:** `O(n)` — The visited set causes each reachable node to be expanded at most once; each child reference is enqueued at most once per edge, and queue/list/hash-set work totals O(V+E)=O(n). Early success only reduces work; the worst case exhausts the reachable graph.
- **Time assumptions:** One call on a fresh BreadthFirstSearch instance; graph nodes are reachable through child lists; getChildren iteration/addAll takes O(degree); HashSet operations are expected O(1); equality/hashCode are O(1) expected.
- **Proposed auxiliary space:** `O(V + E)` (scoring class `O(n)`)
- **Space rationale:** The visited list and set use O(V) space. Because nodes are marked when dequeued, child references are queued before duplicate detection; pending queue entries can be O(E). Total auxiliary space is O(V+E).
- **Space assumptions:** V is the number of reachable nodes, E is the number of child references examined, and n = V+E for the coarse class bucket. Exclude the input graph. Analyze one call on a fresh instance; include the retained visited list/set and queue.
- **Source:** `src/main/java/com/thealgorithms/searches/BreadthFirstSearch.java` at `410f08753505a0af9e46423396e8768bc97cbc1c`; snapshot hash `830a110a2827d491a5ce9efc4dd49110171950b587ddc2e379c89016c80690e0`

```java
package com.thealgorithms.searches;

import com.thealgorithms.datastructures.Node;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Queue;
import java.util.Set;

/**
 * Breadth-First Search implementation for tree/graph traversal.
 * @author caos321
 * @co-author @manishraj27
 * @see <a href="https://en.wikipedia.org/wiki/Breadth-first_search">Breadth-first search</a>
 */
public class BreadthFirstSearch<T> {
    private final List<T> visited = new ArrayList<>();
    private final Set<T> visitedSet = new HashSet<>();

    /**
     * Performs a breadth-first search to find a node with the given value.
     *
     * @param root The root node to start the search from
     * @param value The value to search for
     * @return Optional containing the found node, or empty if not found
     */
    public Optional<Node<T>> search(final Node<T> root, final T value) {
        if (root == null) {
            return Optional.empty();
        }

        visited.add(root.getValue());
        visitedSet.add(root.getValue());

        if (root.getValue() == value) {
            return Optional.of(root);
        }

        Queue<Node<T>> queue = new ArrayDeque<>(root.getChildren());
        while (!queue.isEmpty()) {
            final Node<T> current = queue.poll();
            T currentValue = current.getValue();

            if (visitedSet.contains(currentValue)) {
                continue;
            }

            visited.add(currentValue);
            visitedSet.add(currentValue);

            if (currentValue == value || (value != null && value.equals(currentValue))) {
                return Optional.of(current);
            }

            queue.addAll(current.getChildren());
        }

        return Optional.empty();
    }

    /**
     * Returns the list of nodes in the order they were visited.
     *
     * @return List containing the visited nodes
     */
    public List<T> getVisited() {
        return visited;
    }
}
```

**Your decision:** pending — approve, revise (give corrected label and reasoning), or exclude.

Reply with one decision per case ID, for example `axioma-20261030-v3-01: approve`.