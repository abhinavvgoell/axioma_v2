# Broad complexity calibration candidates

This folder contains the 30-case calibration review set, assembled in six batches of five. The owner reviewed all labels, and the consolidated calibration set is frozen. The preparation notes below preserve historical checkpoints; current run status is recorded first.

## Calibration runs (2026-11-02)

Both runs analyzed the frozen 30-case set with the static Java and Python analyzers. Each runner reads only the six source candidate packets while making analyzer calls; labels are loaded afterward for scoring. Each run produced 60 predictions: one time and one auxiliary-space record per case. No submission execution or benchmark timing was performed.

| Run | Dimension | Answered | Coverage | Exact accuracy across all cases | Exact accuracy among answered |
|---|---|---:|---:|---:|---:|
| v1 | Time complexity | 15/30 | 50.0% | 36.7% (11/30) | 73.3% (11/15) |
| v2 | Time complexity | 15/30 | 50.0% | 40.0% (12/30) | 80.0% (12/15) |
| v3 | Time complexity | 15/30 | 50.0% | 43.3% (13/30) | 86.7% (13/15) |
| v1, v2, and v3 | Auxiliary space | 4/30 | 13.3% | 13.3% (4/30) | 100% (4/4) |

The v2 replay adds the bounded Python `sort_before_binary_search` rule: a top-level sort completed before a binary-search call now estimates `O(n log n)`, while a plain binary search remains `O(log n)`. The fractional-knapsack case 017 is corrected. V3 adds recognition for a wrapper that only returns a recursive Java binary-search helper; the bounded helper analysis recognizes the two mutually exclusive half-interval branches in case 008 as `O(log n)`. Time coverage remains 50%. The two remaining time misclassifications are case 007 (custom heap sort) and case 020 (counting-sort helpers); auxiliary-space output is unchanged. These are calibration diagnostics, not held-out performance. The sample is under 50 distinct solutions, shares upstream repositories with prior work, and has significant abstention; the auxiliary-space selective score is based on only four answered cases. Reports include family/language/method breakdowns and confidence intervals.

Outputs for each run are in `calibration-run-v1/`, `calibration-run-v2/`, and `calibration-run-v3/`: raw analyzer output, prediction JSONL, joined evaluator input, evaluation report, and run manifest. The frozen gold file and manifest remain unchanged. V1 used analyzer commit `624b5e0532a94f7fc4f4b35621d8b1ea9b241531`; v2 used `fb617f6e641ac22a15f44ff9b77675829c99b2dc`; v3 used `ea7bb8230ae8e0431d1e33b69741acbaf0c48561`. Each run manifest records source and output hashes.

Batch 01 contains five exact source files from pinned MIT-licensed upstream commits. The original proposals are preserved in `candidate-cases-batch-01-v1.jsonl` and `review-batch-01.md`; the owner-approved revised packet is preserved separately in `candidate-cases-batch-01-v2.jsonl` and its owner-decision/freeze artifacts. Its partial freeze does not freeze the full calibration set.

The older 2026-10-22 and 2026-10-29 sets, BFS development/evaluation packets, and v3 pilot cases are excluded from this candidate set. This set shares upstream repositories with the v3 pilot and is intended for calibration only. The eventual untouched evaluation must use different repositories or a later time slice and must be frozen before analysis.

Review the cases before any Axioma run. Build subsequent batches only after preserving all existing artifacts; freeze a consolidated manifest and labels after all owner decisions.

## Revised proposal

The files review-batch-01-v2.md, candidate-cases-batch-01-v2.jsonl, and manifest-v2.json preserve the original v1 files and correct case axioma-20261030-broad-002: bottom-up edit distance fills boundary cells even when either input is empty, so its complete time and auxiliary-space bounds are O((m+1)(k+1)). The proposed partition uses the evaluator-supported value calibration.

The project owner confirmed batch 01 against the exact source on 2026-10-31 and reviewed batches 02–06 on 2026-11-02. Separate decision and partial-freeze files preserve each review. Case 010 was revised to O(1) auxiliary space by excluding the two returned O(d²) tables. These were partial freezes before the consolidated set was frozen and analyzed.

The guarded freeze helper requires an explicit `approve` or `revise` decision, source hash, reviewer ID, review date, and rationale for every case. An `approve` must keep the proposed scoring classes. A `revise` must include the final scoring classes, exact time and space expressions, and updated assumptions; the owner's rationale is preserved with the frozen label. The helper writes a new evaluator-compatible gold file and a SHA-256 freeze record, rejects pending decisions, and never overwrites artifacts. The current batch-01 freeze was produced from `owner-decisions-batch-01-v2.jsonl`; the six partial freezes were later consolidated into the full calibration file described below.

After all six batches have their own partial gold files and freeze manifests, consolidate and freeze the complete calibration set without running Axioma:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/consolidate_reviewed_calibration.py `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-01-v2.manifest.json `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-02-v1.manifest.json `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-03-v1.manifest.json `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-04-v1.manifest.json `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-05-v1.manifest.json `
  evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-batch-06-v1.manifest.json `
  --output evaluation/mode1/complexity-review-2026-10-30-broad-v1/gold-reviewed-calibration-v1.jsonl
```

The consolidator refuses missing or duplicate batches, altered source/packet/manifest/gold hashes, non-calibration rows, incomplete owner metadata, and existing output paths. Its manifest records the input hashes and leaves `analyzer_run` false. The frozen set is calibration data only; it is not the untouched final evaluation set.

Validate the original v1 proposal or revised v2 proposal from the repository root:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json
```

## Batch 02 proposal (2026-10-31)

`review-batch-02-v1.md` and `candidate-cases-batch-02-v1.jsonl` preserve the original five proposals and pinned sources. The owner decisions and partial gold artifact are stored separately in `owner-decisions-batch-02-v1.jsonl`, `gold-reviewed-batch-02-v1.jsonl`, and `gold-reviewed-batch-02-v1.manifest.json`. The corrected case 010 label excludes its two returned tables from auxiliary space: O(1) auxiliary, O(d²) output.

Validate the new proposal:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json
```

On 2026-10-31, the exact source bytes for all ten cases in batch 01 v2 and batch 02 v1 were fetched from their pinned GitHub commits and matched the local snapshots and embedded candidate source. Reproduce that provenance check with:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json
```

## Batch 03 owner review (2026-11-02)

Cases 011–015 are in `review-batch-03-v1.md`, `candidate-cases-batch-03-v1.jsonl`, and `manifest-batch-03-v1.json`. The owner reviewed all five against the pinned source. `owner-decisions-batch-03-v1.jsonl`, `gold-reviewed-batch-03-v1.jsonl`, and its freeze manifest preserve this partial batch review. Case 013 keeps its proposed scoring labels but corrects the rationale to Θ(n²) time for every input order and O(n) auxiliary space excluding input and output. Case 014 keeps its approved labels with a corrected StringBuilder rationale and a duplicate-source flag linking it to `axioma-20261030-v3-04`. Both records remain in the calibration partition.

Validate batch 03 and its source provenance:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json
```

## Batch 04 owner review (2026-11-02)

Cases 016–020 are in `review-batch-04-v1.md`, `candidate-cases-batch-04-v1.jsonl`, and `manifest-batch-04-v1.json`. The owner reviewed all five against pinned source. `owner-decisions-batch-04-v1.jsonl`, `gold-reviewed-batch-04-v1.jsonl`, and its freeze manifest preserve this partial batch review. Case 020's exact auxiliary-space label is O(k), excluding the returned output; its coarse class remains O(n) when k=O(n). `prepare_batch_04.py` regenerates the proposal from saved pinned snapshots and refuses a source hash already used in batches 01–03.

Validate the proposal, its generator style, and all 20 source records:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_04.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json
```

## Batch 05 owner review (2026-11-02)

Cases 021–025 are preserved in the review sheet, candidate packet, and manifest. The owner confirmed all five against pinned source; the separate owner-decision file and partial gold artifact preserve the decisions. The candidate packet and manifest remain unchanged.

## Batch 06 owner review (2026-11-02)

Cases 026–030 are preserved in the review sheet, candidate packet, and manifest. The owner confirmed all five against pinned source, revising only case 028's coarse time class to O(n²) for n=V+E. The separate owner-decision file and partial gold artifact preserve the decisions. Candidate packet and manifest remain unchanged.

## Full candidate-set preparation status

All 30 candidates are present across six five-case packets. The 30 IDs and source hashes are unique; every source file matches its pinned upstream commit byte-for-byte. All six packet validators pass. Owner-reviewed partial freezes cover 30/30 cases and are consolidated in `gold-reviewed-calibration-v1.jsonl`. Its manifest records SHA-256 `c5d016c2cc6dbb57c9e3039d5ba820dd3cdc76ad3b757f81f883162c90cd9ca3`. The full calibration set is frozen and the recorded run is summarized above.

The calibration run is complete. The next evaluation gate is to use these results for targeted development, then freeze and score a separately selected untouched holdout. Do not use these calibration results as final-evaluation performance.

Validate the last two batches, all six packets, and all pinned upstream source bytes:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_05.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_06.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-05-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-06-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-05-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-06-v1.json
```
