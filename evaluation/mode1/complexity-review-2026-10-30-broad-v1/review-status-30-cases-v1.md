# Axioma broad complexity calibration — 30-case review status

**Candidate preparation is complete. Label review and analyzer evaluation are not.**

## Current counts

- Candidate source implementations: 30 across six batches of five.
- Owner-reviewed labels: 30 (cases 001–030), frozen as six partial batches only.
- Labels awaiting owner review: 0.
- Full-set gold labels frozen: no.
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

- Candidate packets remain unchanged, with five unique cases per batch, matching source hashes, and no analyzer run. Batches 01–06 have separate owner-reviewed partial gold freezes; candidate manifests intentionally remain unfrozen.
- Structural audit: exactly 30 unique case IDs (`axioma-20261030-broad-001` through `...030`), 30 distinct source hashes, no missing time/space labels, and every embedded/local snapshot matches its hash.
- Pinned-source audit: all 30 source files match byte-for-byte with the corresponding GitHub files at the recorded commits.
- Ruff passed on the source-verification and batch-preparation scripts.
- Batch freeze helper tests passed (8/8); batch 05 and 06 source verification matched all ten pinned sources, and both candidate validators confirmed five unique cases with matching hashes. `git diff --check` is run for this update before completion.

The source repositories are pinned TheAlgorithms/Python and TheAlgorithms/Java MIT commits recorded in each manifest. This is a **calibration** set that shares upstream repositories with earlier development work; it is not the untouched final evaluation. Keep a separate repository- or time-held-out set for final performance claims.

## Gate before analyzer execution

All 30 cases now have owner-reviewed partial gold freezes. The next gate is to consolidate the six partial freezes into one 30-case calibration gold artifact, verify its SHA-256 and source integrity, and only then run Axioma and compute evaluation metrics. The analyzer has not been run on this set.
