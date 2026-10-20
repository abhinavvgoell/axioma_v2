# ADR 0010: Narrow, user-controlled optimization proposals

## Status

Accepted

## Context

Mode 1 should suggest improvements without silently changing a student's solution or making unsupported speedup claims. The project has no configured LLM provider or paid inference budget. General source rewriting is difficult to verify from a small set of examples, so broad transformations would create more risk than evidence.

## Decision

Add a deterministic API proposal route that recognizes one exact integer-array accumulation pattern in Python and Java. It returns a candidate source string with static evidence, low confidence, and explicit limitations. The route validates the problem specification but does not execute submitted code.

The UI requires the user to select “Use as optimization candidate.” The normal worker flow then checks the alternate against declared outputs and, when configured, user-reference differential inputs. Optional benchmark measurements are presented separately and can show no improvement. The original source remains intact. No LLM call is made.

## Consequences

- The behavior is reproducible and works without a key, model download, network access, or paid inference.
- Coverage is intentionally narrow. A static match is not a correctness or performance guarantee; full validation remains the user's configured run.
- Additional rules require dedicated match conditions, negative tests, explicit limitations, and measured evidence before they are described as useful optimizations.
- The project still needs curated, held-out data to evaluate proposal preservation and real speedup rates.
