# Mode 1 complexity review — 2026-10-22

This is the first blinded human-label comparison for Axioma's Python static complexity estimate. The owner reviewed 50 preselected solutions and wrote an expected class and rationale before seeing Axioma's predictions. The initial partition assignment was preserved (calibration/evaluation). Saved per-solution reports and hashes support traceability.

## Result

- 50 reviewed source solutions; 49 were scorable. One graph traversal never adds visited nodes and can recurse indefinitely on valid input, so it has no finite complexity class and is listed in `excluded-cases.jsonl`.
- Calibration: 25 solutions. Held-out evaluation: 24 solutions. Because one case was excluded, the evaluator's 50-distinct-solution minimum is not met.
- All methods combined: exact class accuracy 20/49 (40.8%); coverage 33/49 (67.3%); selective accuracy among answered cases 20/33 (60.6%). Within-one-class accuracy is 25/49 (51.0%).
- Held-out: exact accuracy 8/24 (33.3%); coverage 15/24 (62.5%); selective accuracy 8/15 (53.3%). Within-one-class accuracy is 9/24 (37.5%). The 95% Wilson intervals are wide; see `evaluation-report.json`.
- 16/49 predictions abstained. Results combine the `static_ast_loop_depth` method (48 rows) and one `static_ast_amortized_pointer_scan` row. No dynamic benchmark estimate was scored.

## What the held-out results show

The strongest gaps are recognizing algorithm structure beyond loop nesting:

- Binary search does not receive a usable logarithmic estimate in these samples: the rotated-array search and square-root search abstain; median of two sorted arrays is called O(1).
- Recursion/DP is not modeled reliably: regular-expression matching is called O(1), Word Break II O(n), and Word Break O(n²) despite the reviewed implementation's higher worst-case cost.
- Nested loops over fixed domains are confused with input-sized loops: Binary Watch is called O(n²), though it always checks 720 times.
- Graph/tree structure and amortized multi-pointer work often produce `unknown` or an incorrect class.

The small set indicates that loop-depth heuristics are insufficient as a general analyzer. It does not justify a population-wide accuracy claim or training a model. Use the calibration cases for targeted improvements, then create a new held-out set before evaluating those changes; this current held-out set has now been inspected.

## Reproduction and files

- `gold-reviewed.jsonl`: frozen human labels, rationales, partitions, original complexity wording, and normalized class buckets.
- `predictions-source.jsonl`: Axioma's original per-solution estimate classes and report hashes.
- `predictions-normalized.jsonl`: evaluator-ready static estimates, with abstentions normalized to `unknown`.
- `reports/`: all 50 original Axioma reports, including the excluded non-terminating sample.
- `joined-evaluation.jsonl`: provenance-checked, scorable rows.
- `evaluation-report.json`: evaluator output with exact/within-one scores, coverage, confusion matrix, partitions, and uncertainty intervals.
- `normalization.md`: mapping rules for multi-parameter and exponential classes.
- `excluded-cases.jsonl`: the graph solution omitted from complexity scoring, with its reason.

The 3Sum review prompt shown in chat was abbreviated and omitted pointer advances. The scoring uses the source file identified by its preserved source hash; that source advances both pointers after a match. All reports are static-only. Confidence calibration numbers are descriptive and too small to treat as reliable probabilities.
