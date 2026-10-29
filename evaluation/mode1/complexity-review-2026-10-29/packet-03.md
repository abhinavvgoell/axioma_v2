# Complexity review packet 03

Five new source fixtures for calibration. Axioma has not analyzed these cases. Expected labels and rationales are blank in the companion JSONL file until the owner reviews them. These are development/calibration cases, not held-out final evaluation data.

For each case, give the worst-case time complexity and one short reason. Consider the stated assumptions. Do not use Axioma predictions; none have been collected.

## 11 — Balanced brackets (Python)

Assumptions: `text` contains only the characters `()[]{}`. Treat dictionary operations and list append/pop as O(1).

```python
def solve(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for char in text:
        if char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
        else:
            stack.append(char)
    return not stack
```

## 12 — Palindrome check (Java)

Assumptions: String indexing and character comparisons are O(1); analyze the method as written.

```java
class Solution {
    public boolean isPalindrome(String text) {
        int left = 0;
        int right = text.length() - 1;
        while (left < right) {
            if (text.charAt(left) != text.charAt(right)) return false;
            left++;
            right--;
        }
        return true;
    }
}
```

## 13 — Subset-sum search (Python)

Assumptions: `values` contains positive integers. Analyze worst-case time over inputs of length `n`; do not assume memoization.

```python
def can_make(values, target, index=0):
    if target == 0:
        return True
    if index == len(values):
        return False
    return (can_make(values, target - values[index], index + 1)
            or can_make(values, target, index + 1))
```

## 14 — Reachable vertices with an adjacency matrix (Java)

Assumptions: `adjacency` is a square `V × V` boolean matrix. Queue operations and matrix access are O(1).

```java
import java.util.ArrayDeque;
import java.util.Queue;

class Solution {
    public int countReachable(boolean[][] adjacency, int start) {
        int size = adjacency.length;
        boolean[] seen = new boolean[size];
        Queue<Integer> queue = new ArrayDeque<>();
        seen[start] = true;
        queue.add(start);
        int count = 0;
        while (!queue.isEmpty()) {
            int node = queue.remove();
            count++;
            for (int neighbor = 0; neighbor < size; neighbor++) {
                if (adjacency[node][neighbor] && !seen[neighbor]) {
                    seen[neighbor] = true;
                    queue.add(neighbor);
                }
            }
        }
        return count;
    }
}
```

## 15 — Count paths in a square grid (Python)

Assumptions: `blocked` is an `n × n` grid. Each cell is processed once, and integer addition is O(1).

```python
def count_paths(blocked):
    n = len(blocked)
    ways = [[0] * n for _ in range(n)]
    for row in range(n):
        for col in range(n):
            if blocked[row][col]:
                continue
            if row == 0 and col == 0:
                ways[row][col] = 1
            else:
                from_top = ways[row - 1][col] if row else 0
                from_left = ways[row][col - 1] if col else 0
                ways[row][col] = from_top + from_left
    return ways[n - 1][n - 1] if n else 0
```

Reply in this format:

```text
11: O(...) — reason
12: O(...) — reason
13: O(...) — reason
14: O(...) — reason
15: O(...) — reason
```
