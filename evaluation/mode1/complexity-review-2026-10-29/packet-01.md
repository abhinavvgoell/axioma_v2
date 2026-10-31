# Complexity review packet 01

This is the first five cases of a new, preselected Mode 1 review set. They are
kept separate from Axioma's analyzer until the expected classes are recorded.
Cases 01–25 are assigned to calibration; cases 26–50 will be reserved for the
untouched evaluation partition.

For each case, label the worst-case time complexity using one of:
`O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, or `O(2^n)`.
Use the dominant input size `n` (or the normal standard-problem assumption
when the input has multiple dimensions). Add a short rationale. Do not use
Axioma's prediction; it has not been run on these cases.

## 01 — Count values (Python)

```python
def solve(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
```

## 02 — Sort values (Java)

```java
class Solution {
    private int[] temp;

    public int[] sortArray(int[] values) {
        temp = new int[values.length];
        sort(values, 0, values.length);
        return values;
    }

    private void sort(int[] values, int low, int high) {
        if (high - low <= 1) return;
        int middle = low + (high - low) / 2;
        sort(values, low, middle);
        sort(values, middle, high);
        int left = low, right = middle, write = low;
        while (left < middle && right < high) {
            temp[write++] = values[left] <= values[right] ? values[left++] : values[right++];
        }
        while (left < middle) temp[write++] = values[left++];
        while (right < high) temp[write++] = values[right++];
        for (write = low; write < high; write++) values[write] = temp[write];
    }
}
```

## 03 — Check every pair (Python)

```python
def solve(values):
    best = None
    for left in range(len(values)):
        for right in range(left + 1, len(values)):
            difference = values[right] - values[left]
            if best is None or difference > best:
                best = difference
    return best
```

## 04 — Find a value (Java)

```java
class Solution {
    public int search(int[] values, int target) {
        int low = 0;
        int high = values.length - 1;
        while (low <= high) {
            int middle = low + (high - low) / 2;
            if (values[middle] == target) return middle;
            if (values[middle] < target) low = middle + 1;
            else high = middle - 1;
        }
        return -1;
    }
}
```

## 05 — Fixed clock scan (Python)

```python
def solve():
    matches = []
    for hour in range(12):
        for minute in range(60):
            if (hour + minute) % 7 == 0:
                matches.append((hour, minute))
    return matches
```

## Your labels

Reply with one complexity and one short reason per number, for example:

```text
1: O(n) — ...
2: O(n log n) — ...
3: ...
4: ...
5: ...
```
