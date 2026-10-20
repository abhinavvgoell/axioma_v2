# ADR 0005: Add a CPython opcode-count signal

## Status

Accepted

## Context

Python source-line events can hide repeated work when several operations share one line. Wall-clock measurements are noisy on shared machines. Mode 1 needs a reproducible executed-work signal that complements static analysis and line events.

## Decision

During optional Python complexity benchmarks, count `opcode` trace events only in the selected target function code object. Take the median of three executions per input size and fit the same coarse growth candidates used for line-event counts. Keep raw line and opcode measurements and their fitted models separately in complexity details. Set `methods_disagree` when the static, line-event, or opcode-count coarse buckets differ.

## Consequences

- Counts are deterministic for a particular Python execution and can reveal repeated operations on one source line.
- The signal represents CPython bytecode dispatches, not CPU instructions or total program work.
- Calls to helper functions and native-library work are outside the measured target frame.
- Submitted code can disable tracing; instrumentation adds overhead and is suitable for relative operation counts, not timing comparisons.
- Java continues to report reflective wall-time measurements until a comparable portable operation counter is available.
