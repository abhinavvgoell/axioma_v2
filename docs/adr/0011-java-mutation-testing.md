# ADR 0011: Bounded Java reference mutation testing

## Status

Accepted for Mode 1.

## Context

Java function jobs already support reference-guided differential checks. Mode 1 also needs a way to check whether those finite examples distinguish simple faulty variants. The existing Python mutation runner cannot safely mutate Java source.

## Decision

Generate deterministic, single-operator Java mutants only inside the selected method of a top-level `Reference` class. The first implementation changes a bounded set of arithmetic, comparison, and boolean operators, and caps requested mutants at 20. Each mutant receives a unique class name and is compiled by the sandbox JDK into a separate output directory at runtime. A mutant is killed when it differs from the validated reference or throws on a checked input; it survives when all checked inputs agree. Compilation or reference execution failures are invalid, and work without validated reference samples is not run.

Mutation outcomes create a separate low-confidence statistical evidence claim. The score is `killed / (killed + survived)`; invalid and not-run mutants are excluded. Mutation results do not change the ordinary sample pass/fail totals.

## Consequences

- Java function jobs can opt in with `mutation_tests` when a `reference_code` is supplied.
- Unsupported source shapes can yield zero generated mutants; the report preserves requested, generated, and not-run counts.
- The method covers only these deterministic operators and finite inputs. It does not estimate general test quality or establish the reference as correct.
- Execution requires a sandbox image with a JDK compiler. Local container execution could not be verified when this decision was implemented.
