# ADR 0009: Held-out confidence calibration and uncertainty intervals

## Status

Accepted

## Context

Mode 1 evaluation needs uncertainty around accuracy and a way to check whether its categorical confidence labels track observed correctness. Assigning fixed numeric probabilities to `high`, `medium`, or `low` would invent calibration. Measuring reliability on the same records used to assign probabilities would also overstate performance.

## Decision

The complexity evaluator accepts `calibration` and `evaluation` partitions. Every row for one solution ID must stay in the same partition. For each method and confidence category, exact-class accuracy on calibration IDs becomes an empirical probability. Brier score, log loss, and expected calibration error are then calculated only on held-out evaluation IDs. Categories absent from calibration are excluded from these metrics and counted.

Accuracy, detection recall, false-positive rate, and precision include two-sided 95% Wilson score intervals. Reports identify these as record-level intervals. The detection evaluator does not assume mutants from one source solution are independent, so its intervals can understate uncertainty when mutants are related.

## Consequences

- Existing complexity JSONL remains valid; records without a partition default to `evaluation`, and calibration metrics remain unavailable without both partitions.
- The evaluator prevents the same solution ID from appearing in both partitions, including across different complexity methods.
- Calibration values are learned from the supplied calibration set and are not universal probabilities. No gold set or measured project accuracy is bundled.
- Small sets produce wide intervals and potentially unstable calibration. The evaluator reports these values without claiming that the project target of 50 solutions ensures adequate precision.
