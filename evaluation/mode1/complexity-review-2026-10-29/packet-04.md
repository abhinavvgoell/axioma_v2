# Complexity review packet 04

Five additional source fixtures for calibration, continuing the user-reviewed set. Axioma has not analyzed these cases. Expected labels and rationales are intentionally omitted until owner review.

For each case, give worst-case time complexity and a short rationale. Use the stated assumptions; do not use or request Axioma predictions before labels are recorded.

## 16 — Recursive binary search (Java)

Assumptions: values is sorted; analyze worst-case time in n = values.length; array indexing and integer arithmetic are O(1).

```java
class Solution {
    public int search(int[] values, int target, int low, int high) {
        if (low > high) return -1;
        int middle = low + (high - low) / 2;
        if (values[middle] == target) return middle;
        if (values[middle] < target) {
            return search(values, target, middle + 1, high);
        }
        return search(values, target, low, middle - 1);
    }
}
```

## 17 — Memoized Fibonacci (Python)

Assumptions: n is a non-negative integer; functools.lru_cache provides average O(1) cache lookup and insertion; analyze time only.

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
```

## 18 — Next greater element with a monotonic stack (Java)

Assumptions: values is an integer array; analyze worst-case time in n = values.length; ArrayDeque stack operations and array access are O(1).

```java
import java.util.ArrayDeque;
import java.util.Deque;

class Solution {
    public int[] nextGreater(int[] values) {
        int[] answer = new int[values.length];
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < values.length; i++) {
            while (!stack.isEmpty() && values[stack.peek()] < values[i]) {
                answer[stack.pop()] = values[i];
            }
            stack.push(i);
        }
        while (!stack.isEmpty()) answer[stack.pop()] = -1;
        return answer;
    }
}
```

## 19 — Count islands in a square grid (Python)

Assumptions: grid is a square n by n array of "0"/"1" characters; each cell is enqueued at most once; deque and set operations are average O(1).

```python
from collections import deque

def count_islands(grid):
    n = len(grid)
    visited = set()
    islands = 0
    for row in range(n):
        for col in range(n):
            if grid[row][col] != "1" or (row, col) in visited:
                continue
            islands += 1
            queue = deque([(row, col)])
            visited.add((row, col))
            while queue:
                current_row, current_col = queue.popleft()
                for next_row, next_col in (
                    (current_row - 1, current_col),
                    (current_row + 1, current_col),
                    (current_row, current_col - 1),
                    (current_row, current_col + 1),
                ):
                    if (0 <= next_row < n and 0 <= next_col < n
                            and grid[next_row][next_col] == "1"
                            and (next_row, next_col) not in visited):
                        visited.add((next_row, next_col))
                        queue.append((next_row, next_col))
    return islands
```

## 20 — Quicksort with last-element pivot (Java)

Assumptions: Report worst-case time in n = array length; pivot is always the last element; sorted or reverse-sorted inputs may produce maximally unbalanced partitions.

```java
class Solution {
    public void sort(int[] values, int low, int high) {
        if (low >= high) return;
        int pivot = partition(values, low, high);
        sort(values, low, pivot - 1);
        sort(values, pivot + 1, high);
    }

    private int partition(int[] values, int low, int high) {
        int pivot = values[high];
        int boundary = low - 1;
        for (int current = low; current < high; current++) {
            if (values[current] <= pivot) {
                boundary++;
                int temporary = values[boundary];
                values[boundary] = values[current];
                values[current] = temporary;
            }
        }
        int temporary = values[boundary + 1];
        values[boundary + 1] = values[high];
        values[high] = temporary;
        return boundary + 1;
    }
}
```

Reply in this format:

```text
16: O(...) — short rationale
17: O(...) — short rationale
18: O(...) — short rationale
19: O(...) — short rationale
20: O(...) — short rationale
```
