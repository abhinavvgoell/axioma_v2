# Packet 02 baseline notes

Dataset: `axioma-20261029-review-packet-02`  
Analyzer commit: `5afb193f6bda0020039e90cdd15b0bfa28481b3b`  
Partition: calibration; labels were frozen before the baseline run.

## Result

The analyzer returned the expected time class on 3 of 5 cases (60% end-to-end exact accuracy) and produced an estimate on 3 of 5 (60% coverage). Its selective accuracy was 3 of 3 (100%). Both misses are Java patterns, and both were explicit abstentions (`unknown`) rather than incorrect complexity claims.

## Error taxonomy

- **Case 7 — insertion sort:** The generic Java path treats any `while` loop as unknown unless a narrow recognizer proves a supported pattern. Existing special handling covers common binary search and a specific forward-only sliding-window scan; it does not bound an inner shifting loop from the outer loop's iteration count. The result is a conservative abstention on a familiar quadratic algorithm.
- **Case 9 — adjacency-list BFS:** The analyzer recognizes a narrower BFS shape that uses `visited.add(neighbor)` as its enqueue guard. This case uses a `boolean[]` and explicit `seen[neighbor] = true`, so it misses the recognizer and falls through to the generic `while` abstention. This is a recognizer coverage gap, not evidence that the overall BFS complexity is misunderstood.

## Follow-up after the baseline

These are two useful failure examples, not evidence of broad Java or algorithm-family accuracy: the packet has one example per family and is calibration data.

The insertion-sort failure category has since been addressed by a narrow Java structural recognizer for an outer array pass plus a backward, element-shifting inner loop. A synthetic positive fixture predicts `O(n^2)` and a near-miss backward loop remains inconclusive. The pre-change baseline above is preserved; the five-case packet was not rescored after this change and must not be described as an untouched holdout.

The array-backed visited-state BFS gap remains open. Its next implementation should recognize the `boolean[]` visited-guard form with positive and near-miss tests. Any broader performance claim requires a fresh, untouched evaluation packet.

The follow-up changed only the Java static analyzer, its regression tests, and this evaluation note. No catalog, database, or API schema changes were made.
