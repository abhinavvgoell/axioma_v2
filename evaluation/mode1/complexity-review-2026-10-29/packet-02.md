# Complexity review packet 02

Five new source fixtures for calibration. Axioma has not analyzed these cases. Expected labels and rationales are blank in the companion JSONL file until the owner reviews them. These are development/calibration cases, not held-out final evaluation data.

For each, give worst-case time complexity and one short reason. Consider the stated input assumptions. Do not use Axioma predictions; none have been collected.

## 06 — Longest unique substring window (Python)

Assumptions: Assume ordinary Python string indexing and average O(1) dictionary operations.

```python
def solve(text):
    left = 0
    latest = {}
    longest = 0
    for right, char in enumerate(text):
        if char in latest and latest[char] >= left:
            left = latest[char] + 1
        latest[char] = right
        longest = max(longest, right - left + 1)
    return longest
```

## 07 — Insertion sort (Java)

Assumptions: Worst case is a reverse-sorted integer array; assume primitive array access and arithmetic are O(1).

```java
class Solution {
    public int[] sortArray(int[] values) {
        for (int i = 1; i < values.length; i++) {
            int current = values[i];
            int j = i - 1;
            while (j >= 0 && values[j] > current) {
                values[j + 1] = values[j];
                j--;
            }
            values[j + 1] = current;
        }
        return values;
    }
}
```

## 08 — Longest increasing subsequence by dynamic programming (Python)

Assumptions: Input is an integer list; analyze the implementation shown, not alternative algorithms.

```python
def solve(values):
    if not values:
        return 0
    lengths = [1] * len(values)
    for i in range(len(values)):
        for j in range(i):
            if values[j] < values[i]:
                lengths[i] = max(lengths[i], lengths[j] + 1)
    return max(lengths)
```

## 09 — Reachable vertices with breadth-first search (Java)

Assumptions: The input is an adjacency-list graph with V vertices and E listed edges; analyze in V and E.

```java
import java.util.ArrayDeque;
import java.util.List;
import java.util.Queue;

class Solution {
    public int countReachable(List<List<Integer>> graph, int start) {
        boolean[] seen = new boolean[graph.size()];
        Queue<Integer> queue = new ArrayDeque<>();
        seen[start] = true;
        queue.add(start);
        int count = 0;
        while (!queue.isEmpty()) {
            int node = queue.remove();
            count++;
            for (int neighbor : graph.get(node)) {
                if (!seen[neighbor]) {
                    seen[neighbor] = true;
                    queue.add(neighbor);
                }
            }
        }
        return count;
    }
}
```

## 10 — Binary tree height (Java)

Assumptions: The input is a finite binary tree without cycles or shared child nodes; each node is processed once if reached.

```java
class TreeNode {
    int value;
    TreeNode left;
    TreeNode right;
}

class Solution {
    public int height(TreeNode node) {
        if (node == null) return 0;
        return 1 + Math.max(height(node.left), height(node.right));
    }
}
```

Reply in this format:

```text
6: O(...) — reason
7: O(...) — reason
8: O(...) — reason
9: O(...) — reason
10: O(...) — reason
```
