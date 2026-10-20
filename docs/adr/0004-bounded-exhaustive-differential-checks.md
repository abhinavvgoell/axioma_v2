# ADR 0004: Bounded exhaustive differential checks

## Status

Accepted

## Context

Random generated inputs can miss errors in small input domains. Axioma already supports comparing a candidate with a user-supplied reference, but it must not imply that the reference itself is trusted or correct.

## Decision

Add an opt-in `exhaustive_tests` flag for function jobs in both supported languages. The first implementation enumerates positional integer arguments only, where every argument has one inclusive `args[i]` range. It requires examples with the same arity and no keyword arguments, and rejects a Cartesian product larger than 256 cases. It cannot be combined with randomized `generated_tests`.

All enumerated comparisons use the existing harness result marker and persisted test-case records. The report therefore derives totals from the same test ledger as examples and other differential checks. The source remains labeled as a user-supplied reference; exhaustive agreement is finite evidence, not a proof of reference correctness.

## Consequences

- Tiny scalar domains get complete, reproducible input coverage without a random seed.
- The fixed cap bounds CPU use in the worker and keeps the report manageable.
- Arrays, nested structures, keyword arguments, and larger domains remain on the existing generated-test path.
- A future independently validated oracle can use this mode, but this ADR does not create or certify one.
