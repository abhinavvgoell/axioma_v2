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

The next fixes should be handled one category at a time with positive and near-miss regression tests. The most useful next category is Python branching-recursion inference, because it directly covers common backtracking algorithms. The Java two-pointer and matrix-BFS gaps remain separate follow-up categories. Do not tune on the final evaluation partition.

No application code changed while analyzing this packet.
