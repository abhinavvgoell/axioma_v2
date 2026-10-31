# Independent BFS complexity evaluation — 2026-10-29

- Dataset: `axioma-independent-bfs-2026-10-29-v1` (22 cases; Java 11, Python 11)
- Label status: **provisional_not_human_reviewed**
- Frozen label SHA-256: `9bda67401a794613b4ac01fd351af8f4e0e3904f0c9464d4254efef930d95298`
- Analyzer commit: `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`; analyzer source SHA-256 values are in `run-manifest.json`.
- Rule version: `bounded_bfs_traversal_v1`
- No submitted code was compiled or executed; this was static analysis only.

## Overall metrics

| Measure | Result |
|---|---:|
| Scorable cases | 20 |
| Concrete predictions | 6 |
| Exact accuracy among answered | 83.3% |
| Coverage | 30.0% |
| Selective accuracy (paired with coverage) | 83.3% |
| All-case exact rate | 25.0% |
| Supported-pattern candidates | 10 |
| Supported-pattern coverage | 50.0% |
| Expected-unknown cases / correct abstention agreement | 12 / 91.7% |
| Unsupported-case concrete predictions | 1 (truth-matching 0, mismatching 1) |
| Execution failures | 0 |

## Results by language

| Language | Scorable | Answered | Exact accuracy | Coverage | Unsupported-case estimates |
|---|---:|---:|---:|---:|---:|
| java | 10 | 3 | 66.7% | 30.0% | 1 |
| python | 10 | 3 | 100.0% | 30.0% | 0 |

## Results by pattern

| Pattern | Cases | Answered | Exact accuracy | Coverage | Expected unknown | False positives |
|---|---:|---:|---:|---:|---:|---:|
| adjacency_list_boolean_visited | 1 | 1 | 100.0% | 100.0% | 0 | 0 |
| adjacency_list_mark_on_dequeue | 1 | 0 | undefined | 0.0% | 0 | 0 |
| adjacency_list_multi_source | 2 | 1 | 100.0% | 50.0% | 0 | 0 |
| adjacency_list_single_source | 2 | 1 | 100.0% | 50.0% | 0 | 0 |
| adjacency_matrix | 1 | 0 | undefined | 0.0% | 0 | 0 |
| adjacency_matrix_bfs | 1 | 0 | undefined | 0.0% | 1 | 0 |
| grid_bfs_with_extra_full_scan | 2 | 1 | 0.0% | 50.0% | 2 | 1 |
| grid_eight_direction | 2 | 0 | undefined | 0.0% | 1 | 0 |
| grid_four_direction | 1 | 1 | 100.0% | 100.0% | 0 | 0 |
| grid_four_direction_rectangular | 1 | 1 | 100.0% | 100.0% | 0 | 0 |
| grid_neighbor_helper_representation | 1 | 0 | undefined | 0.0% | 1 | 0 |
| missing_visited_bound | 2 | 0 | undefined | undefined | 2 | 0 |
| queue_worklist_not_graph | 2 | 0 | undefined | 0.0% | 2 | 0 |
| repeated_adjacency_list_bfs | 2 | 0 | undefined | 0.0% | 2 | 0 |
| unfamiliar_neighbor_api | 1 | 0 | undefined | 0.0% | 1 | 0 |

## Unsupported-pattern estimates and evidence review

- `bfs-ind-010` (grid_bfs_with_extra_full_scan): predicted `O(R*C)`; disagrees with provisional truth. Review method `static_java_grid_bfs_v1`, evidence signals, and assumptions in `predictions.jsonl`.

## Supported-pattern abstentions

- `bfs-ind-001` (adjacency_list_single_source): expected `O(V + E)`, analyzer abstained. See source and evidence in `predictions.jsonl`.
- `bfs-ind-003` (adjacency_list_multi_source): expected `O(V + E)`, analyzer abstained. See source and evidence in `predictions.jsonl`.
- `bfs-ind-004` (adjacency_matrix): expected `O(V^2)`, analyzer abstained. See source and evidence in `predictions.jsonl`.
- `bfs-ind-009` (grid_eight_direction): expected `O(R * C)`, analyzer abstained. See source and evidence in `predictions.jsonl`.
- `bfs-ind-014` (adjacency_list_mark_on_dequeue): expected `O(V + E)`, analyzer abstained. See source and evidence in `predictions.jsonl`.

## Method, limitations, and interpretation

The evaluator checked the pre-run manifest hashes, each source hash, Git HEAD, and the working-tree hashes of both analyzer files before invoking the existing Java/Python analyzer. It records one prediction per case, including complete structured evidence, or a separate execution-failure record. It does not alter analyzer configuration or rules.

Labels were authored before the analyzer run but were not reviewed by a second human; all are provisional. Therefore these results are exploratory and must not be reported as human-approved accuracy. There are two intentionally non-finite/nonterminating cases (one per language), excluded from complexity accuracy and coverage. Unsupported-case estimates are reviewed against both the provisional mathematical label and the preregistered expectation to abstain.

## Evidence-based follow-up priorities

1. **Fix the Java grid false positive first.** Case `bfs-ind-010` was reported as `O(R*C)` by `static_java_grid_bfs_v1`, although it performs a full `R*C` scan inside the neighbor loop for every dequeued cell. The extra work makes the dominant term `O((R*C)^2)`. The rule recognized the surrounding grid BFS but did not account for nested full-grid work. Add a near-miss regression before changing the detector.
2. **Improve Java adjacency-list BFS coverage without weakening abstention.** Cases `bfs-ind-001` and `bfs-ind-003` use set-based `add` as the visited test and a multi-source queue; both abstained despite finite adjacency-list work. The returned fallback evidence has only token/loop-depth signals. Add structurally distinct positive fixtures before generalizing.
3. **Resolve the Java matrix BFS gap.** Case `bfs-ind-004` is a recognizable adjacency-matrix traversal with an `n`-wide row scan per reached vertex, so provisional truth is `O(V^2)`, but the analyzer abstained. Add a positive matrix case and negative list-graph contrast.
4. **Broaden Java grid directions carefully.** Case `bfs-ind-009` uses eight offsets in a fixed-size loop and correctly remains `O(R*C)`, but the current rule abstained. Ensure any extension still accounts for dimension-dependent inner scans, as case 010 demonstrates.
5. **Evaluate alternate visitation timing in Python.** Case `bfs-ind-014` marks nodes visited on dequeue and skips duplicate dequeues; each vertex expands once, so provisional truth is `O(V+E)`. It abstained. Verify the bound with cycles and converging paths before deciding whether to support the form.

The Python results show 3/3 concrete predictions exact, but only 30% overall coverage; this small provisional set is not evidence of broad language-level accuracy. Java answered 3/10 scorable cases (2 exact) and produced the single unsupported-pattern false positive.

No runtime benchmarks, auxiliary-space estimates, API tests, database tests, or submitted-code execution were performed. The evaluation set must not be used to tune rules and still be called independent; after examining errors it becomes development data.

## Reproduction

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/bfs-independent-2026-10-29-v1/run_independent_bfs_eval.py
```

Raw predictions/evidence: `predictions.jsonl`. Machine-readable metrics: `results.json`. Run provenance: `run-manifest.json`.
