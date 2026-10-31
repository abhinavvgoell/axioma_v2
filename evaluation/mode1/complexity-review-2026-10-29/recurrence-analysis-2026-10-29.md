# Recurrence analysis milestone — 2026-10-29

## Scope

This change adds bounded, heuristic recurrence recognition to the existing Java token analyzer and Python AST analyzer. It addresses the three recurrence-related failures in packet 04. The approved labels in gold-reviewed-04.jsonl were read-only and remain unchanged. Packet 04 is calibration/development data and is not an untouched holdout.

No auxiliary-space analysis, front-end, API, database, queue, benchmark generator, problem catalog, or user-code execution behavior changed.

## Diagnosed failures

| Case | Saved analyzer result | Cause |
|---|---|---|
| 16 — Java recursive binary search | unknown (recursion detected) | The Java analyzer detected self-calls but did not relate middle ± 1 updates to the inclusive [low, high] search interval. |
| 17 — Python cached Fibonacci | unknown (recursion detected) | The Python analyzer only modeled cached local recursive helpers. This case decorates a top-level direct-recursive function with lru_cache(maxsize=None), so its two recursive branches were not reduced to the number of distinct cached states. |
| 20 — Java last-pivot quicksort | unknown (recursion detected) | The Java analyzer did not combine the two pivot-bounded recursive calls with the linear partition pass to derive worst-case work. It also mistook the method's recursive sort(...) calls for library sorting calls. |

## Implementation

The new shared recurrence helper in services/worker/src/axioma_worker/recurrence.py solves only these forms:

| Recurrence | Result |
|---|---|
| T(n) = T(n - c) + O(1) | O(n) |
| T(n) = T(n - c) + O(n) | O(n²) |
| T(n) = T(n / 2) + O(1) | O(log n) |
| T(n) = T(n / 2) + O(n) | O(n) |
| T(n) = 2T(n / 2) + O(1) | O(n) |
| T(n) = 2T(n / 2) + O(n) | O(n log n) |

Both language analyzers recognize simple scalar recurrences with a parameter-guarded base case, constant decrement or halving, and either constant local work or one linear scan outside the recursive calls. A two-call recurrence is accepted only when both calls occur in the same returned expression, avoiding the addition of mutually exclusive branches.

Additional narrow patterns cover:

- Java recursive binary search whose midpoint is calculated from the interval bounds and whose two recursive returns select opposite halves. It records T(n) = T(n / 2) + O(1); the two syntactic calls are mutually exclusive, so the recurrence has one call per level.
- Python direct recursion on one non-negative integer state with an unbounded cache/lru_cache decorator and strictly decreasing constant offsets. It counts distinct cached states, not recursive call paths. Bounded caches, multiple state dimensions, loops, and other uncertain cases are not accepted by this rule.
- Java quicksort using a last-element pivot, a linear range scan in partition, a returned pivot index, and the usual two pivot-bounded recursive ranges. Under the requested worst-case model, the pivot may be at an endpoint, giving T(n) = T(n - 1) + O(n) = O(n²). The self-recursive method calls are no longer recorded as library sort calls.

Each accepted estimate adds details.code_analysis.recurrence with rule version, function and source line where available, recursive-call count, input-size reduction, non-recursive work, recurrence, solving rule, result, assumptions, and heuristic_pattern_match. Java token analysis does not retain line numbers, so its evidence names the selected method and reports line: null. Confidence remains low because these are structural heuristics, not proofs.

The worker already keeps the static estimate separate, then optionally applies Python line/opcode growth fits or Java wall-time fits when benchmark samples exist. Those measured fits can annotate or disagree with the static result; they do not replace the recurrence evidence. The existing worker result path passes the estimate's details through to the report, so recurrence evidence uses the established contract without a schema or API change. This milestone ran no benchmark samples.

Irregular size changes, unsupported call counts, ambiguous branches, recursive calls inside loops, and bounded-cache recurrences remain unknown. The generic solver is not a full recurrence engine and does not infer auxiliary space.

## Diagnostic re-evaluation

The reproducible runner is evaluation/mode1/replay_recurrence_diagnostics.py. It verifies the frozen case and label source hashes, invokes the same static analyzer entrypoints, and writes a new result file without replacing the earlier run or changing approved labels.

Command:

\`\`\`powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/replay_recurrence_diagnostics.py
\`\`\`

Result: 3/3 exact time labels, 0 mismatches, 0 unsupported on these three diagnostic cases. The full predictions and structured evidence are in [recurrence-diagnostic-results-2026-10-29-final.json](recurrence-diagnostic-results-2026-10-29-final.json).

Earlier iterative smoke runs are retained in recurrence-diagnostic-results-2026-10-29-initial.json and recurrence-diagnostic-results-2026-10-29-iterative.json. The final result above records hashes for the tested analyzer sources after the matcher refinements.

| Case | Approved label | New estimate | Evidence |
|---|---:|---:|---|
| 16 — Recursive binary search | O(log n) | O(log n) | T(n) = T(n / 2) + O(1); one selected recursive branch per call. |
| 17 — Memoized Fibonacci | O(n) | O(n) | At most n + 1 distinct cached scalar states, each with average O(1) cache access and constant modeled work. |
| 20 — Last-pivot quicksort | O(n²) worst case | O(n²) worst case | T(n) = T(n - 1) + O(n) when the last-element pivot lands at an endpoint. |

These cases were used to develop and verify the rules. Their results are diagnostic only and must not be reported as independent holdout accuracy. Case 17 uses the approved usual unit-cost arithmetic model; Python big-integer bit costs are not represented. No benchmarks were run and no timing-based complexity conclusion was made.

The two non-recurrence cases remain outside the change: Java monotonic-stack case 18 still returns unknown (data-dependent or incomplete loop), and Python grid-BFS case 19 still returns unknown (data-dependent loop bound). Their amortized traversal gaps are unresolved.

## Verification

Pre-change analyzer baseline: 66 passed across the Java and Python complexity test files.

Post-change commands and results:

\`\`\`powershell
services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py -v
# 73 passed

services/api/.venv/Scripts/python.exe -m pytest services/worker/tests -x -vv
# 125 passed

services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1 -q
# 31 passed

services/api/.venv/Scripts/ruff.exe check services/worker/src/axioma_worker/python_complexity.py services/worker/src/axioma_worker/java_complexity.py services/worker/src/axioma_worker/recurrence.py services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py evaluation/mode1/replay_recurrence_diagnostics.py
# All checks passed

git diff --check
# Passed
\`\`\`

The full worker suite includes sandbox integration tests and passed in this environment. No PostgreSQL database test was run; this analyzer-only change does not touch persistence. No database migration or new dependency was added. No commit or push was made.

## Next technical milestone

Add a separate bounded rule for amortized monotonic-stack scans, beginning with Java diagnostic case 18 and adversarial near-misses. Keep the grid-BFS case separate so a stack-rule result cannot be mistaken for graph-traversal coverage.
