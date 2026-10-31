# Axioma external multifamily pilot v1 — run report

## Scope and provenance

- Dataset: `axioma-20261030-external-multifamily-pilot-v1` (5 distinct solutions; calibration partition).
- Labels: owner-reviewed and frozen before analysis in `gold-reviewed-v1.jsonl`.
- Analysis: current static Python/Java complexity analyzers. Submitted programs were **not executed**, and benchmark measurements were not run.
- Analyzer revision: `55ba24c3edac23a83ebbf610be63ee3e3b30e15f` on `main`.
- Recorded environment: Python 3.14.3, Windows 11, AMD64, 16 logical CPUs; run time `2026-10-30T16:54:08.365912+00:00`.
- Provenance: `run-manifest-v1.json` records SHA-256 hashes for the frozen manifest, labels, packet, decisions, analyzer inputs, runner, and all four result files.

## Results

| Dimension | Cases | Answered | Coverage | Exact accuracy | Exact among answered |
|---|---:|---:|---:|---:|---:|
| Worst-case time | 5 | 2 | 40% (2/5) | 20% (1/5) | 50% (1/2) |
| Auxiliary space | 5 | 0 | 0% (0/5) | 0% (0/5) | Not defined |

The evaluator marks both dimensions `below_minimum`; its minimum is 50 distinct solutions. The small sample makes these pilot observations only. In particular, the 50% selective time accuracy is based on two answered cases and should not be read as a stable accuracy estimate.

## Case-level time predictions

| Case | Expected | Predicted | Analyzer method | Outcome |
|---|---|---|---|---|
| `axioma-20261030-v3-01` | `O(log n)` | `unknown` | `static_ast_binary_search` | Abstained |
| `axioma-20261030-v3-02` | `O(n^2)` | `unknown` | `static_ast_loop_depth` | Abstained |
| `axioma-20261030-v3-03` | `O(n^2)` | `O(n)` | `static_ast_tree_recursion` | Incorrect answered estimate |
| `axioma-20261030-v3-04` | `O(n^2)` | `O(n^2)` | `static_java_token_loop_depth` | Exact |
| `axioma-20261030-v3-05` | `O(n)` | `unknown` | `static_java_token_loop_depth` | Abstained |

For auxiliary space, all five predictions are `unknown` with method `not_emitted_by_current_static_analyzer`; the analyzer currently provides no auxiliary-space class to score.

## Interpretation and next step

The run shows limited time-analysis coverage on this small cross-family pilot, one exact time prediction, one incorrect answered prediction, and three abstentions. The recursive generator case (`v3-03`) is the concrete incorrect estimate: the reviewed label accounts for `yield from` delegation and is `O(n^2)` in the worst case, while the analyzer returned `O(n)`. The Java dynamic-programming case (`v3-04`) was exact. The remaining three time cases were not classified.

Treat this pilot as calibration evidence. The evaluation plan calls for expanding to roughly 30–50 distinct, independently reviewed solutions across algorithm families, followed by a separate untouched set after any tuning. Do not tune against this pilot and then report it as held-out performance. Auxiliary-space analysis needs a distinct implementation milestone before its coverage can improve.

## Integrity checks

At report preparation, hashes in `run-manifest-v1.json` matched all four output files; the frozen case, label, decision, runner, analyzer, and evaluator source hashes also matched their manifests. `validate_proposed_packet.py` passed for the preserved original proposal artifacts. Its `analyzer_run: false` field describes that original pending proposal packet; it does not describe the separate frozen-label pilot run.

The runner's final console-summary formatting has a post-write bug (`.name` is accessed on output filename strings). The analysis outputs and run manifest were written before that formatting step. Integrity validation confirms the recorded files; the analyzer was not rerun to work around the display error.
