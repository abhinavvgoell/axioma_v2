# Axioma broad complexity calibration — 30-case review status

**Candidate preparation, owner label review, and calibration gold freeze are complete. Axioma evaluation remains unrun.**

## Current counts

- Candidate source implementations: 30 across six batches of five.
- Owner-reviewed labels: 30 (cases 001–030), frozen in six partial batches and one consolidated calibration artifact.
- Labels awaiting owner review: 0.
- Full-set gold labels frozen: yes. SHA-256: `c5d016c2cc6dbb57c9e3039d5ba820dd3cdc76ad3b757f81f883162c90cd9ca3`.
- Axioma run against these candidates: no.

## Review sequence

All six five-case packets now have owner-reviewed partial freezes:

| Cases | Human review sheet | Proposed packet | State |
|---|---|---|---|
| 001–005 | `review-batch-01-v2.md` | `candidate-cases-batch-01-v2.jsonl` | Owner-confirmed; partial freeze only |
| 006–010 | `review-batch-02-v1.md` | `candidate-cases-batch-02-v1.jsonl` | Owner-reviewed; partial freeze. Case 010 space revised to O(1) excluding returned tables |
| 011–015 | `review-batch-03-v1.md` | `candidate-cases-batch-03-v1.jsonl` | Owner-reviewed; partial freeze. 013 rationale/assumptions revised, labels unchanged; 014 duplicate source flagged |
| 016–020 | `review-batch-04-v1.md` | `candidate-cases-batch-04-v1.jsonl` | Owner-reviewed; partial freeze. 020 auxiliary space revised to O(k), coarse O(n) |
| 021–025 | `review-batch-05-v1.md` | `candidate-cases-batch-05-v1.jsonl` | Owner-reviewed; partial freeze |
| 026–030 | `review-batch-06-v1.md` | `candidate-cases-batch-06-v1.jsonl` | Owner-reviewed; partial freeze. 028 coarse time class revised to O(n²) |

Each worksheet contains the exact source code used for its proposed labels, source URL pinned to a commit, SHA-256, input assumptions, and time/space rationale. Some cases show both the exact multi-parameter bound and a coarser supported scoring class; the assumptions explain when that coarse class applies.

## Validation evidence

- Candidate packets remain unchanged, with five unique cases per batch and matching source hashes. Batches 01–06 have separate partial gold freezes, consolidated into `gold-reviewed-calibration-v1.jsonl`; the candidate manifests remain unfrozen. Axioma has not been run.
- Structural audit: exactly 30 unique case IDs (`axioma-20261030-broad-001` through `...030`), 30 distinct source hashes, no missing time/space labels, and every embedded/local snapshot matches its hash.
- Pinned-source audit: all 30 source files match byte-for-byte with the corresponding GitHub files at the recorded commits.
- Ruff passed on the source-verification and batch-preparation scripts.
- Batch freeze helper tests passed (8/8), consolidation tests passed (3/3), batches 05 and 06 each matched all five pinned sources, and their candidate validators confirmed five unique cases with matching hashes. The consolidated artifact contains 30 unique IDs and passes the gold loader; `git diff --check` is run for this update before completion.

The source repositories are pinned TheAlgorithms/Python and TheAlgorithms/Java MIT commits recorded in each manifest. This is a **calibration** set that shares upstream repositories with earlier development work; it is not the untouched final evaluation. Keep a separate repository- or time-held-out set for final performance claims.

## Gate before analyzer execution

The six partial freezes are consolidated and frozen in `gold-reviewed-calibration-v1.jsonl`; its recorded SHA-256 is `c5d016c2cc6dbb57c9e3039d5ba820dd3cdc76ad3b757f81f883162c90cd9ca3`. The next gate is to run Axioma against this calibration artifact and compute evaluation metrics. This remains calibration data, not the untouched final evaluation set.
