# Bounded Java monotonic-stack analysis — 2026-10-29

## Scope

This milestone adds one narrow Java static-analysis pattern for a single traversal of an input array with an `ArrayDeque` index stack. It does not add general amortized analysis, BFS analysis, auxiliary-space analysis, a database/API change, a dependency, or a benchmark/timing claim. The approved calibration label was read-only and remains unchanged.

## Recognized shape and evidence

The rule recognizes one braced `for` loop traversing `i = 0` through `values.length - 1`, one nested `while` that checks the top index's array value against the current value, one `pop()` site in that loop, and one `push(i)` site after the pop loop. It permits a final drain loop that only removes remaining entries. It rejects nested traversal, re-insertion, repeated searches, non-monotonic conditions, and unrecognized removal operations.

An accepted result remains a low-confidence heuristic estimate. `details.code_analysis.monotonic_stack` records the Java language, rule version and pattern, token offsets for loops/push/pop/peek, the one-push bound, removal bound, amortized argument, O(n) result, assumptions, and limitations. The argument is that each of n indices is pushed once and can be permanently popped at most once, including in the final drain. This is not a proof for arbitrary Java code; helper calls and aliases are not expanded.

## Case 18 diagnostic

The replay runner reads case `axioma-20261029-18` and its approved label from the existing packet, verifies both source hashes, invokes the normal Java analyzer, and writes a new result file without overwriting any earlier run. The frozen source uses `ArrayDeque`, pushes each index once, pops smaller top values during the scan, and drains the remainder after the scan.

Command:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/replay_monotonic_stack_diagnostic.py
```

The result is in `monotonic-stack-diagnostic-results-2026-10-29.json`. This is diagnostic development data, not holdout accuracy. It contains no runtime timing measurements.

## Verification

The Java complexity suite covers next-greater and previous-smaller comparisons, concrete and interface-typed `ArrayDeque` declarations, multi-pop iterations, final drains, single push/removal sites, and five adversarial near-misses. It also retains the Java binary-search and quicksort recurrence regressions.

The approved labels in `gold-reviewed-04.jsonl` were not edited. Python analysis, Mode 2, APIs, schemas, persistence, migrations, and dependencies are out of scope.
