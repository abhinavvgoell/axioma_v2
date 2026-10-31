# Fresh v3 complexity review and pilot

## Original review packet

- `review-packet-v1.jsonl`: five source snapshots, proposed time labels, assumptions, rationale, source attribution, per-case SHA-256, and pending owner decisions.
- `review-sheet-v1.md`: human-readable case-level review.
- `review-sheet-v1-with-source.md`: combined review worksheet with the exact relevant Python entrypoint or complete Java source beside both proposed time and auxiliary-space labels.
- `manifest-v1.json`: pinned repositories/commits, packet hash, label status, and evaluation-run status.
- `space-review-v1.md` and `space-review-v1.jsonl`: separate proposed auxiliary-space labels for the same source snapshots; exact expressions are preserved alongside coarse scoring classes.
- `space-review-manifest-v1.json`: parent packet hash, space-label artifact hash, per-case source hashes, and pending review state.
- `validate_proposed_packet.py`: repeatable integrity check for the original packet, both label artifacts, source snapshots, review-sheet code excerpts, and pending state.
- `sources/`: exact source blobs copied from those commits.
- `LICENSE-TheAlgorithms-Python.md` and `LICENSE-TheAlgorithms-Java.md`: included upstream MIT notices.

The original proposal artifacts remain unchanged. Their provisional labels are preserved in `review-sheet-v1.md`, `review-packet-v1.jsonl`, `space-review-v1.md`, and `space-review-v1.jsonl`. They are not the frozen gold-label artifact.

## Frozen diagnostic run

The owner-reviewed labels were frozen separately in `gold-reviewed-v1.jsonl` and `manifest-approved-v1.json`; Axioma was then run on those five cases. The predictions and evaluation are recorded in `predictions-v1.jsonl`, `analysis-output-v1.json`, `joined-evaluation-v1.jsonl`, and `evaluation-report-v1.json`. `run-manifest-v1.json` binds these outputs to their hashes, the frozen labels, the source packet, and the analyzer revision. See `run-report-v1.md` for the case-level results and interpretation.

This is a five-case **calibration/diagnostic pilot**, not an untouched holdout and not evidence of broad analyzer accuracy. The evaluation reports time-complexity coverage of 2/5 (40%) and exact accuracy of 1/5 (20%; 1/2, or 50%, among answered cases). Auxiliary-space coverage is 0/5 because the current static analyzer does not emit an auxiliary-space estimate. Both dimensions are marked below the evaluator's 50-distinct-solution minimum. Do not use this pilot as a final performance claim or tune on it and continue calling it held out.

### Corrected scoring pass

The original v1 score had a label-normalization defect: it removed spaces from estimates before comparing them with canonical class labels, so `O(log n)` became `unknown`. The raw analyzer output itself contained `O(log n)`. A corrected v2 scoring pass reuses that saved output without rerunning Axioma and preserves every v1 file. The corrected time metrics are 3/5 answered (60% coverage), 2/5 exact overall (40%), and 2/3 exact among answered cases (about 67%). Auxiliary-space coverage remains 0/5. See `run-report-v2.md`, `predictions-v2.jsonl`, `joined-evaluation-v2.jsonl`, `evaluation-report-v2.json`, and `run-manifest-v2.json`.

`complexity_normalization.py` contains the tested canonical label normalizer. `reprocess_saved_outputs_v2.py` verifies the frozen inputs and saved raw report hashes, then creates the corrected postprocessing artifacts exclusively. This is still a five-case calibration diagnostic, not a held-out result.

Validate the review artifacts from the repository root with:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-fresh-v3/validate_proposed_packet.py
```

That validator checks the **original proposal artifacts** and will continue to report their historical `analyzer_run: false` state. It does not invalidate the separate frozen-label run artifacts listed above.
