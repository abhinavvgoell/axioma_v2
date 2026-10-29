# Packet 03 calibration analysis

Dataset: `axioma-20261029-review-packet-03`  
Analyzer commit: `adb20e30c6c5d35ec2f932060cbcad7817d31438`  
Partition: calibration; labels were frozen before analysis.  
Scored dimension: worst-case time complexity.

## Result

The analyzer returned the expected class on 2/5 cases (40% end-to-end exact accuracy) and answered 2/5 (40% coverage). Both answered cases were correct, so selective exact accuracy was 2/2 (100%). The three other cases were explicit `unknown` abstentions. The evaluator reports 95% Wilson intervals, but this five-case sample is too small for broad claims and is not held-out evaluation data.

## Per-case outcome and failure taxonomy

| Case | Family | Expected | Actual | Category and likely cause |
|---|---|---|---|---|
| 11 | Stack | O(n) | O(n) | Correct. The Python analyzer sees one input-dependent loop. |
| 12 | Two pointers | O(n) | unknown | Java loop-inference coverage gap. The loop uses two pointers moving inward under `left < right`; current Java recognition handles selected binary search and nested amortized scans, not this convergence pattern. Diagnosis confidence: high. |
| 13 | Backtracking | O(2^n) | unknown | Recurrence-analysis limitation. Python detects self-recursion but does not infer this take/skip branching recurrence, so it abstains. Diagnosis confidence: high. |
| 14 | Matrix graph traversal | O(n^2), normalized from O(V²) | unknown | Java pattern/representation gap. The existing BFS recognizer targets adjacency-list neighbor iteration; it does not account for scanning a full matrix row for each dequeued vertex. Diagnosis confidence: high. |
| 15 | Dynamic programming | O(n²) | O(n²) | Correct. The Python analyzer detects two nested loops over the square grid. |

## Interpretation and next step

These results describe five calibration fixtures only. Do not combine them with the earlier packet scores as an independent accuracy claim; the analyzer has been tuned using earlier calibration cases, and there is not yet a fresh untouched holdout report for the current version.

The next fixes should be handled one category at a time with positive and near-miss regression tests. Python branching-recursion inference has now been addressed for top-level functions as well as local helpers. Synthetic regressions cover direct branching, mutually exclusive single-call branches, and memoized recursion. The original packet03 outcome above remains the pre-fix calibration baseline and was not rescored after this change. The Java two-pointer and matrix-BFS gaps remain separate follow-up categories. Do not tune on the final evaluation partition.

## Reproduction of remaining Java abstentions

Reproduced on the current analyzer after the Python-only fix using the frozen packet03 calibration source:

```powershell
$env:PYTHONPATH='services/worker/src;services/api/src'
@'
import json
from pathlib import Path
from axioma_worker.java_complexity import analyze_java_complexity
for line in Path('evaluation/mode1/complexity-review-2026-10-29/review-set-03.jsonl').read_text(encoding='utf-8').splitlines():
    item = json.loads(line)
    if item['id'] in {'axioma-20261029-12', 'axioma-20261029-14'}:
        result = analyze_java_complexity(item['source'], item['entrypoint'])
        print(item['id'], item['expected'], result.estimate, result.method)
'@ | python -
```

The output reproduces `axioma-20261029-12: O(n) → unknown (data-dependent or incomplete loop)` and `axioma-20261029-14: O(n^2) → unknown (data-dependent or incomplete loop)`. Both are analyzer abstentions, not label ambiguities: the source and assumptions are explicit, and the independent rationale follows directly from the bounded scan.

| Case | Root cause | Frequency / severity | Proposed action |
|---|---|---|---|
| 12, inward two-pointer scan | `_is_binary_search_loop` recognizes interval halving and `_amortized_forward_scan` recognizes a forward-only inner pointer, but neither recognizes two cursors moving inward. The generic `has_while` fallback therefore abstains. | 1/5 in this calibration packet; high product priority because this is a common linear DSA pattern. The sample is too small to estimate prevalence. | Add a narrow Java convergence-loop recognizer requiring a sequence-sized interval, opposing cursor updates, and a guard that shrinks that interval; retain unknown for unproven `while` loops. Test a positive and non-converging near miss. |
| 14, adjacency-matrix BFS | `_is_adjacency_list_bfs` specifically expects enhanced-for iteration over `graph.get(node)`. It does not model scanning `V` matrix columns for every dequeued vertex; the generic `has_while` fallback masks the nested scan bound. | 1/5 in this calibration packet; medium-high product priority because matrix representation is a common graph variant. The sample is too small to estimate prevalence. | Add a separate matrix-BFS recognizer requiring queue progress, visited marking before enqueue, and a full row scan bounded by the matrix size; retain unknown when a visited guard or matrix bound is missing. |

## Follow-up: Python branching-recursion fix

The original case 13 used a top-level function with two progressing recursive calls in one boolean expression. The recognizer previously inspected only local helper functions, which caused an avoidable abstention. The entrypoint is now included, and the recognizer requires two progressing calls in the same `BinOp` or `BoolOp` expression. This avoids treating mutually exclusive branches as exponential. Functions with unbounded memoization remain excluded from this exponential classification.

This is a targeted calibration-driven change. No packet03 post-fix score is claimed; the fixture informed the change and is not an independent evaluation set.

## Follow-up: Java inward two-pointer fix

Approved category: Java inward-moving two-pointer scans. The analyzer now recognizes one braced `while` loop whose condition compares two cursors, whose lower bound was last initialized to zero, and whose upper bound was last initialized from a `.length` expression. Each cursor must have exactly one unit step in the expected direction; cursor resets, conditional cursor progress, nested loops, and `continue` reject the pattern. A recognized case is reported as a low-confidence static `O(n)` estimate, with an `inward_two_pointer_scan` signal. Other unbounded while-loops retain the existing inconclusive result.

Development regressions use a synthetic string scan with an early mismatch return, plus near misses with a missing cursor update and conditional cursor progress. The original packet03 calibration was not rescored after the fix, and no post-fix accuracy claim is made.
