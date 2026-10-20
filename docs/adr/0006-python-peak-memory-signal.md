# ADR 0006: Measure Python-traced peak allocation growth

## Status

Accepted

## Context

Mode 1 reports time-growth signals, but the project brief also calls for peak-memory evidence. Process RSS is noisy and includes interpreter, worker, and container memory that is not attributable to the selected function. Python's `tracemalloc` can provide a bounded signal for Python-managed allocations during a target call.

## Decision

When a Python function job supplies complexity benchmarks and passes its configured checks, prepare fresh inputs before tracing and measure the peak traced allocation delta for three separate target calls at each size. Report the median bytes and, with at least four valid sizes, fit the same coarse growth candidates used by the time signals. Return this under `complexity.details.space_measurement`; keep it out of the time estimate and `methods_disagree` calculation.

## Consequences

- The estimate is low-confidence and describes traced Python allocations, not process RSS or all memory used by the program.
- Native allocations may be omitted, harness overhead remains, and submitted code can interfere with `tracemalloc`.
- The traced peak includes memory retained by the function's returned value during measurement.
- Java reports a separate heap-pool peak-increase proxy; see ADR 0007 for its different limitations.
