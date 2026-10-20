# ADR 0007: Measure Java heap-pool peak increases

## Status

Accepted

## Context

Mode 1 needs a space signal for Java as well as Python. Java does not provide a portable per-invocation peak-allocation counter through the APIs used by this project. The standard management beans expose peak usage per heap memory pool, which can be reset immediately before a target call.

## Decision

During optional Java complexity benchmarks, warm the target, capture each supported heap pool's current usage, reset its peak, invoke the target, and sum each pool's positive peak increase. Take the median of nine observations at each size and fit the same coarse growth candidates when at least four valid sizes are available. Report this under `complexity.details.space_measurement`, separate from time complexity and `methods_disagree`.

## Consequences

- The result is a low-confidence heap-pool proxy, not process RSS or exact live memory.
- It excludes off-heap/native allocations, includes JVM/reflection overhead, and may overcount objects that move between pools.
- Small allocations may produce zero increase at the memory-pool reporting granularity; if all sizes read zero, Axioma reports no space growth fit.
- Activity on other Java threads can affect the measurement.
- The measurement requires JVM memory-pool peak reset support; unavailable support yields no raw memory point for that run.
