# ADR 0008: Optional independent reference corroboration

## Status

Accepted

## Context

A user-supplied reference can be wrong while still matching the declared examples. Differential checks can then report false candidate failures or false passes. A second implementation can expose disagreements, but it cannot establish correctness because both sources may share the same mistaken interpretation.

## Decision

Python and Java function-job requests may include `independent_reference_code` alongside the existing `reference_code`. When supplied, both references must load, match every declared sample, and agree with each other before generated or exhaustive differential checks are considered. On generated inputs, a disagreement skips the existing comparison row rather than labeling the candidate wrong. The optional field is included in queued job input; Java uses the reserved top-level class name `ReferenceIndependent`.

The default remains one reference for compatibility. No extra test rows are added, so existing count formulas remain stable. Reports continue to describe these results as comparisons against user-supplied references.

## Consequences

- A reference bug visible only on generated inputs is surfaced as a skipped comparison when the two references disagree.
- When the references agree, the candidate is compared against their shared output.
- A shared misunderstanding remains possible; consensus is corroboration, not an oracle guarantee.
- Reference-source execution increases sandbox work and code volume, but remains within the existing source-size limits and test caps.
