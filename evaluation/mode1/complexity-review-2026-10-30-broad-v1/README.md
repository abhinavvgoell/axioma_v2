# Broad complexity calibration candidates

This folder contains the proposed 30-case calibration review set, assembled in six batches of five. It is separate from the completed five-case v3 pilot. Owner review is incomplete, and no Axioma analysis has been run on these candidates.

Batch 01 contains five exact source files from pinned MIT-licensed upstream commits. Labels are proposals and remain pending owner confirmation. The file `candidate-cases-batch-01-v1.jsonl` stores source, hashes, proposed time and auxiliary-space labels, rationale, assumptions, and provenance. `review-batch-01.md` is the human review worksheet. `manifest-v1.json` records the current batch and explicitly marks the gold labels unfrozen and analyzer unrun.

The older 2026-10-22 and 2026-10-29 sets, BFS development/evaluation packets, and v3 pilot cases are excluded from this candidate set. This set shares upstream repositories with the v3 pilot and is intended for calibration only. The eventual untouched evaluation must use different repositories or a later time slice and must be frozen before analysis.

Review the cases before any Axioma run. Build subsequent batches only after preserving all existing artifacts; freeze a consolidated manifest and labels after all owner decisions.

## Revised proposal

The files review-batch-01-v2.md, candidate-cases-batch-01-v2.jsonl, and manifest-v2.json preserve the original v1 files and correct case axioma-20261030-broad-002: bottom-up edit distance fills boundary cells even when either input is empty, so its complete time and auxiliary-space bounds are O((m+1)(k+1)). The proposed partition uses the evaluator-supported value calibration.

The project owner confirmed all five batch-01 labels against the exact source on 2026-10-31. The separate owner-decision file and gold-reviewed-batch-01-v2.jsonl preserve that review. The latter is frozen only as a partial batch; the full 30-case calibration set remains unfrozen and no analyzer run has been performed. Its SHA-256 is recorded in gold-reviewed-batch-01-v2.manifest.json.

The guarded freeze helper requires an explicit `approve` or `revise` decision, source hash, reviewer ID, review date, and rationale for every case. An `approve` must keep the proposed scoring classes. A `revise` must include the final scoring classes, exact time and space expressions, and updated assumptions; the owner's rationale is preserved with the frozen label. The helper writes a new evaluator-compatible gold file and a SHA-256 freeze record, rejects pending decisions, and never overwrites artifacts. The current batch-01 freeze was produced from `owner-decisions-batch-01-v2.jsonl`. Do not use it as a full-set evaluation until the remaining batches are reviewed and the consolidated set is frozen.

Validate the original v1 proposal or revised v2 proposal from the repository root:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json
```

## Batch 02 proposal (2026-10-31)

`review-batch-02-v1.md` presents cases 006–010 with the complete pinned source code, proposed time and auxiliary-space labels, assumptions, rationales, and source hashes. `candidate-cases-batch-02-v1.jsonl` and `manifest-batch-02-v1.json` store the machine-readable candidate packet and provenance. All five labels are pending owner confirmation; Axioma has not been run on this batch. Batch 01 remains the only owner-confirmed/frozen partial batch (5/30 labels). The full 30-case calibration set remains unfrozen. Review is presented in batches of five; only run Axioma after all labels are reviewed and the full calibration set is frozen.

Validate the new proposal:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json
```

On 2026-10-31, the exact source bytes for all ten cases in batch 01 v2 and batch 02 v1 were fetched from their pinned GitHub commits and matched the local snapshots and embedded candidate source. Reproduce that provenance check with:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json
```

## Batch 03 proposal (2026-10-31)

Cases 011–015 are prepared in `review-batch-03-v1.md`, `candidate-cases-batch-03-v1.jsonl`, and `manifest-batch-03-v1.json`. This packet is prepared ahead, but the human review flow remains five cases at a time; review batch 02 before moving on to batch 03. All five labels remain proposed and unfrozen. Axioma has not been run on these cases. The source verifier checked the pinned upstream bytes for batch 03 along with batches 01 and 02; all 15 source records matched.

Validate batch 03 and its source provenance:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json
```

## Batch 04 proposal (2026-10-31)

Cases 016–020 are in `review-batch-04-v1.md`, `candidate-cases-batch-04-v1.jsonl`, and `manifest-batch-04-v1.json`. All labels remain pending. Axioma has not been run on these cases. `prepare_batch_04.py` regenerates the packet from the saved pinned source snapshots and refuses a source hash already used in batches 01–03.

Validate the proposal, its generator style, and all 20 source records:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_04.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json
```

## Batch 05 proposal (2026-10-31)

Cases 021–025 are in `review-batch-05-v1.md`, `candidate-cases-batch-05-v1.jsonl`, and `manifest-batch-05-v1.json`. The packet includes graph search, ternary search, substring dynamic programming, knapsack tabulation, and graph topological sorting. All five labels remain pending owner confirmation; Axioma has not been run. `prepare_batch_05.py` regenerates the packet and checks source-hash uniqueness against batches 01–04.

## Batch 06 proposal (2026-10-31)

Cases 026–030 are in `review-batch-06-v1.md`, `candidate-cases-batch-06-v1.jsonl`, and `manifest-batch-06-v1.json`. This completes the 30-case **candidate preparation** set. All labels remain proposed; only batch 01 (5 cases) has owner-confirmed partial labels. The full set is not frozen, and Axioma has not been run against these candidates. `prepare_batch_06.py` regenerates the packet and checks source-hash uniqueness against batches 01–05.

## Full candidate-set preparation status

All 30 candidates are now present across six five-case packets. The 30 IDs and source hashes are unique; every source file matches its pinned upstream commit byte-for-byte. All six packet validators pass. The owner-confirmed count is 5/30: cases 001–005 are frozen as a partial batch, while cases 006–030 remain proposed and pending owner review. The full set is not frozen, and the analyzer has not been run on these candidates.

Use `review-batch-02-v1.md` through `review-batch-06-v1.md` for the remaining five-case reviews. Do not analyze candidate labels until all owner decisions are recorded and the consolidated gold-label artifact is frozen.

Validate the last two batches, all six packets, and all pinned upstream source bytes:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_05.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/prepare_batch_06.py
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-05-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/validate_candidate_batch.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-06-v1.json
services/api/.venv/Scripts/python.exe evaluation/mode1/complexity-review-2026-10-30-broad-v1/verify_pinned_sources.py --manifest evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-v2.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-02-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-03-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-04-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-05-v1.json evaluation/mode1/complexity-review-2026-10-30-broad-v1/manifest-batch-06-v1.json
```
