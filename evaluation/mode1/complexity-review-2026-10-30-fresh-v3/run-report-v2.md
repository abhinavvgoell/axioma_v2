# Axioma external multifamily pilot v2 — corrected postprocessing

This is a corrected scoring pass over the saved raw output from the original five-case calibration pilot. Axioma was **not rerun**. The v1 artifacts remain unchanged and preserve the original scoring defect for auditability.

## Corrected metrics

| Dimension | Cases | Answered | Coverage | Exact accuracy | Exact among answered |
|---|---:|---:|---:|---:|---:|
| Worst-case time | 5 | 3 | 60% (3/5) | 40% (2/5) | 67% |
| Auxiliary space | 5 | 0 | 0% (0/5) | 0% (0/5) | Not defined |

## Why the score changed

The v1 normalizer removed whitespace from Axioma labels but compared them to canonical labels containing spaces. As a result, the valid analyzer estimate `O(log n)` became `unknown`. The v2 normalizer canonicalizes both sides and records `O(log n)` as a supported class.

The pilot remains a five-case calibration diagnostic, not an untouched holdout. Its small sample is not a broad accuracy claim. Auxiliary-space coverage remains zero because the current static analyzer did not emit that class.

See `predictions-v2.jsonl`, `joined-evaluation-v2.jsonl`, `evaluation-report-v2.json`, and `run-manifest-v2.json` for the corrected, hash-bound artifacts.
