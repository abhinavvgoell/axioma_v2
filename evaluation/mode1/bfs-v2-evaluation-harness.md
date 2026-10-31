# BFS v2 evaluation harness

This versioned harness adds packet prediction and symbolic-expression comparison without changing the legacy `evaluate_complexity.py` or `run_reviewed_packet_04.py` behavior. The legacy evaluator accepts only its documented canonical classes; BFS v2 uses independent size variables such as `V`, `E`, `R`, and `C`, so it uses a separate parser and scorer.

## Prediction runner

`run_bfs_v2_predictions.py` reads only the source packet. It verifies the whole-packet hash when supplied, validates unique case IDs and each source SHA-256, and derives the required entrypoint from code syntax. The Java/Python analyzer call receives only `(source, entrypoint)`. Expected complexity, expected response, review disposition, rationale, and other gold fields are not passed to it.

The runner writes one JSON object per input case to a new JSONL path. The schema is `axioma.bfs-v2.prediction.v1`:

```json
{
  "schema_version": "axioma.bfs-v2.prediction.v1",
  "case_id": "axioma-bfs-v2-j01",
  "language": "java",
  "pattern": "adjacency_list_single_source",
  "source_sha256": "<sha256>",
  "entrypoint": "ReachA.count",
  "execution_status": "completed",
  "actual_response": "estimate",
  "analyzer_output": {
    "method": "<raw method>",
    "estimate": "<raw estimate>",
    "confidence": "low",
    "methods_disagree": false,
    "explanation": "<raw explanation>",
    "details": {"<raw evidence and rule metadata>": "..."}
  },
  "error": null
}
```

For an analyzer or entrypoint error, `execution_status` is `error`, `actual_response` is `error`, `analyzer_output` is null, and `error` records stage, exception type, and message. Errors are never rewritten as `unknown`. A completed result is `unknown` only when the raw estimate starts with `unknown`; otherwise its response type is `estimate`.

Example invocation for a future, separately authorized evaluation:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/run_bfs_v2_predictions.py `
  evaluation/mode1/bfs-fresh-v2-review-2026-10-30/review-packet.jsonl `
  --packet-sha256 d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1 `
  --output evaluation/mode1/bfs-fresh-v2-results-2026-10-30/predictions-v2.jsonl
```

The runner refuses a packet/source hash mismatch, duplicate IDs, and output overwrite. It does not create the output parent directory.

## Complexity parser and comparator

`bfs_v2_complexity.py` uses a bounded tokenizer and recursive-descent parser. It never evaluates input text. It supports outer `O(...)` labels; variables `V`, `E`, `R`, `C`, `Q`, `N`, and `S` (the packet uses `S` for start entries); addition; multiplication; non-negative integer powers up to 8; parentheses; and `log(expr)` or the common unary form `log V`. It accepts whitespace and harmless formatting changes, `²`, `×`, `·`, implicit multiplication such as `VE` and `V(E+1)`, and an equality chain such as J08’s two equal Big-O forms.

Comparison results are:

- `exact_match`: same normalized ordered expression after formatting normalization.
- `mathematically_equivalent`: expanded symbolic polynomial forms are identical up to a positive constant factor. Addition and multiplication order and distributive expansion are normalized.
- `mismatch`: a positive independent-parameter growth ray proves different asymptotic orders.
- `unscorable`: syntax is unsupported/malformed, an equality chain is inconsistent, or the bounded comparator cannot prove equivalence or a mismatch. It is not converted to `unknown`.

The comparator does not assume relationships between parameters such as `E <= V`, `Q <= V`, or `R = C`. It does not use finite numeric samples as proof. Logarithms are retained as symbolic factors; only log arguments with the same normalized algebraic form are treated alike. It intentionally returns `unscorable` for log identities or other comparisons it cannot prove safely. Unsupported syntax includes subtraction, division, arbitrary functions, non-integer powers, unknown variable names, and unbounded expressions beyond parser limits. The original and normalized forms are both retained in each comparison.

## Scorer

`evaluate_bfs_v2.py` joins predictions to the frozen artifact strictly by case ID, checks source hashes and languages, and reports response behavior separately from complexity correctness. It reports coverage over all cases, expected-estimate-subset coverage, correct and unexpected abstentions, execution errors, exact/equivalent/mismatch/unscorable complexity comparisons, and both all-emitted and scorable-only selective-accuracy denominators. Unknown responses and execution errors are not complexity estimates.

The scorer emits a JSON report with case-level evidence summaries and can optionally write a CSV comparison table. It refuses missing/extra/duplicate IDs, source mismatches, and overwriting output files. Example invocation for a future evaluation:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_bfs_v2.py `
  evaluation/mode1/bfs-fresh-v2-review-2026-10-30/gold-labels-v2.json `
  evaluation/mode1/bfs-fresh-v2-results-2026-10-30/predictions-v2.jsonl `
  --output evaluation/mode1/bfs-fresh-v2-results-2026-10-30/score-v2.json `
  --csv evaluation/mode1/bfs-fresh-v2-results-2026-10-30/case-results-v2.csv
```

The existing evaluators remain unchanged. This task’s tests use synthetic packets and stub analyzers; they do not invoke the analyzer on frozen BFS v2 sources.
