# API contract, version 1

This document is the backend/frontend agreement. The UI can render the supplied objects directly; it should not infer evidence, recalculate totals, or invent verification states.

## Evidence claim

Each claim contains a stable ID, a user-readable summary, an evidence type, categorical confidence, provenance, and optional artifact references. Evidence types are `executed`, `static`, `statistical`, `model`, and `unverified`. Confidence is `high`, `medium`, or `low`; it is not a numeric probability. A future calibrated probability must be represented as a separately named and documented measurement.

## Complexity result

Every complexity result has `method`, `estimate`, `confidence`, and `methods_disagree`; optional structured `details` contain raw measurements. Method names identify the signal (for example, `static_loop_analysis`, `operation_count_fit`, or `wall_time_fit`). Empirical measurements support a complexity estimate but do not prove an asymptotic bound.

Python function jobs record `static_ast_loop_depth` estimates. They inspect the selected function for loop/comprehension nesting, built-in sorting, iterable-consuming built-ins, membership checks, collection-style method calls, and direct recursion. Java function jobs record `static_java_token_loop_depth` estimates, based on tokenized loop nesting, common sorting calls, collection-style calls, indexing, and direct recursion. The report includes `complexity.details.code_analysis` with detected signals and source lines where available. A common closed-interval binary search is recognized when the loop computes a midpoint from both bounds and updates the lower and upper bounds to midpoint + 1 and midpoint - 1; it is estimated as O(log n) with low confidence. Other unrecognized data-dependent `while` loops return an unknown static estimate rather than assuming linear work; benchmarks may still provide a separate low-confidence observed fit. These are syntax-level clues: they do not establish the runtime cost of an unknown collection, solve recurrences, expand called helpers, or recognize every algorithm. Java tokenization currently cannot provide signal line numbers. The amortized forward-scan pattern has medium confidence and remains a heuristic, not a proof.

Function jobs can optionally provide four to six `complexity_benchmarks`, each with an increasing user-declared `size` and function `args`; Python also supports `kwargs`. After configured correctness and property checks pass, Python records median target-function source-line and CPython opcode events over three runs, plus median traced peak-allocation deltas over three separate runs. Java records median reflective JVM wall time and median heap-pool peak-increase estimates after five warmups and nine trials per measurement. The memory signal is returned as `complexity.details.space_measurement`, with raw per-size byte values and a coarse fitted growth class when at least four valid sizes have a positive observed increase. Python measures traced Python allocations, not process RSS; native allocations may be omitted, input preparation is excluded, and harness overhead remains. Java sums positive per-pool peak usage increases; it is not process RSS, excludes off-heap/native memory, includes JVM and reflection overhead, pool migration can overcount, and small allocations may read as zero at the pool reporting granularity. Submitted code can disable or interfere with Python tracing, and can allocate on other Java threads during measurement. If all observations are zero, the space growth class is not estimated. The space estimate is separate from time-complexity `methods_disagree`, because time and space growth can differ. Opcode events count interpreter bytecode dispatches in the selected function frame; they are deterministic for a given execution but are not CPU instructions or total program work. The signals fit candidate growth models (`O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, and `O(2^n)`) using least-squares fit. Raw measurements and per-signal fits are returned in `complexity.details`; time `methods_disagree` is true when the coarse static, line-event, or opcode-count buckets differ. These are low-confidence statistical observations: Axioma does not verify that declared sizes match the data; Python tracing can be disabled by submitted code and omits helpers/native work; Java timing includes reflection overhead and JVM/host noise. Neither is an asymptotic proof. Benchmarks are not correctness test cases and do not change the test summary.

When constraints declare a maximum collection length, `complexity.details.constraint_scalability` reports a rough growth scale for that bound. It assumes the largest declared collection is `n` and one abstract growth unit per operation. Scalar bounds without a collection length do not produce a scale estimate. This is a low-confidence context estimate, not measured work, a time-limit prediction, or a guarantee that all input dimensions are represented.

## Test summary

The source of truth will be individual test-case records. A response summary has `total`, `passed`, `failed`, and `skipped`; `total` must equal the sum of the other three. Counts are derived on read from those records, not incremented independently in multiple services.

## Verification gates

Mode 2 gates are returned as an ordered array. Each gate has `order`, `name`, `state`, and references to supporting evidence claims. States are `passed`, `failed`, and `not_run`.

## Job state and events

Jobs have one of five states: `queued`, `running`, `completed`, `failed`, or `cancelled`. The API persists every state change and emits it through Server-Sent Events. Clients can reconnect using the last event ID. Terminal jobs stop emitting events. Reusing an idempotency key for the same mode, language, and input returns the original job; reusing it for a different request returns a conflict.

## Initial routes

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/v1/jobs` | Create an analysis job; accepts optional `Idempotency-Key` |
| `GET` | `/v1/jobs/{job_id}` | Read current job status |
| `GET` | `/v1/jobs/{job_id}/events` | Stream status events |
| `POST` | `/v1/jobs/{job_id}/cancel` | Cancel a queued or running job |
| `GET` | `/v1/jobs/{job_id}/result` | Read the completed report |
| `POST` | `/v1/problem-specs/validate` | Validate a Mode 1 problem definition and its sample inputs |
| `POST` | `/v1/problem-specs/generate-inputs` | Generate deterministic input candidates within declared numeric and length constraints |
| `POST` | `/v1/problem-specs/generate-complexity-benchmarks` | Generate four to six adversarial function inputs that can be copied into a Mode 1 job |
| `POST` | `/v1/optimization-proposals` | Return low-confidence, static candidates for supported Mode 1 patterns |
| `POST` | `/v1/jobs/mode1/python-function` | Queue Python function-style sample execution |
| `POST` | `/v1/jobs/mode1/java-function` | Queue Java class-method sample execution |
| `POST` | `/v1/jobs/mode1/stdin-stdout` | Queue Python or Java stdin/stdout sample execution |

## Mode 1 problem specification

Mode 1 problem definitions use a tagged `interface` (`function` or `stdin_stdout`) and tagged sample cases of the matching kind. A function sample supplies JSON-compatible `args`, `kwargs`, and `expected`; an stdin/stdout sample supplies `stdin` and `expected_stdout`. Constraint paths address numeric sample values such as `args[0]`, `kwargs.limit`, or lengths such as `args.length` and `stdin.length`. The validate route checks every declared constraint against every sample and returns `valid`, `samples_checked`, and per-sample issues. This checks the problem data only; it does not execute a submitted solution.

The input-generation route accepts `{problem, count, seed}` and returns reproducible candidate inputs. It includes declared minimum and maximum values, the adjacent representable integer/float values when in range, zero and negative one when in range, and (for numeric arrays with a length constraint) ascending, descending, all-equal, duplicate-heavy, alternating low/high, and nearly-sorted patterns. When the request can accommodate both all declared bound candidates and adversarial patterns, it reserves up to three result slots for adversarial patterns; remaining capacity is filled with seeded random samples. Each case includes a `strategy` label, and the API rechecks candidates against the declared constraints before returning them. Duplicate inputs are removed, so `requested` and `generated` can differ when paths or constraints cannot produce enough distinct cases. These are input candidates only; without an oracle they do not indicate correctness or pass/fail results.

The complexity-benchmark generation route accepts `{problem, size_path, sizes, pattern, seed}`. It requires a numeric list in the first function example for numeric patterns, or a string in the first example for `repeated_characters`, plus a matching integer collection-length constraint. `sizes` must contain four to six increasing unique values from 1 to 10,000, each inside that constraint. Numeric `pattern` values are `ascending`, `descending`, `all_equal`, `duplicate_heavy`, `alternating_low_high`, or `nearly_sorted`; string inputs support `repeated_characters`. The response includes benchmark objects directly compatible with `complexity_benchmarks` on a function-job request. The pattern travels with each benchmark and appears as `input_strategy` beside its measurements; manually entered benchmarks are marked `user_supplied`. Inspect the generated values and their associated sizes before running; a generated pattern is not a worst-case proof or an oracle, and the reported fit remains a low-confidence measurement.

The Mode 1 UI requests four growth benchmarks automatically when the matched pack has at least one supported numeric-array or string-length constraint and four distinct sizes fit between the selected example value's length (or the constraint minimum) and 32. When a problem has multiple scalable arguments, the UI varies only the highest-index eligible argument and the generator preserves the other values from the first example. Numeric arrays use ascending values; strings use a repeated-character pattern. This adds growth measurements to the normal report without asking the user to enter benchmark cases. Packs with unsupported or too-narrow constraints still run their configured checks, but do not receive automatic complexity benchmarks. Generated benchmarks are measurements, not correctness test cases; the UI reports estimates with the same low-confidence limitations described above.

The Python and Java function job routes accept `language`, `code`, `problem`, and an optional `idempotency_key`. They run each declared sample against a top-level Python function, a one-level Python class method, or a Java `ClassName.methodName`, then store one test-case record per sample. Solution output is redirected away from the harness response so its result remains parseable. Java samples support JSON-compatible primitives, lists/arrays, and maps; the harness converts arguments to the reflected method's parameter types.

Python and Java function jobs accept optional `reference_code`, `independent_reference_code`, `generated_tests` (0–50), `mutation_tests` (0–20), and `seed`. A reference implementation is first checked against every provided sample. When a second implementation is supplied, both must match every provided sample and each other before generated differential checks run. On generated inputs, disagreement between the two references marks that existing check as skipped and does not compare the candidate against either answer. For Java, the supplied sources must declare top-level classes named `Reference` and `ReferenceIndependent`; the submitted solution class must have a different name. This is corroboration, not proof: independently written references can share the same misconception. The second source is optional, and the existing single-reference behavior remains available.

For small scalar-input problems, `exhaustive_tests: true` replaces randomized differential generation with every combination in the declared integer ranges. It requires a user-supplied `reference_code`, one exact integer `args[i]` range per positional argument, equal-arity positional-only examples, no keyword arguments, and at most 256 combinations. It is available for both languages and is mutually exclusive with `generated_tests`. Exhaustive comparison means only that the candidate matched the supplied reference for every enumerated input; it does not validate the reference or prove semantic correctness.

Python and Java function jobs may include `optimization_code` and optional `optimization_notes`. The worker keeps the original `code`, runs both versions on the same provided samples, and compares both outputs with declared expected outputs. If a user reference is supplied and passes the samples, it also checks both versions on the generated differential inputs. Java optimization source must declare top-level class `AxiomaOptimized` with the same method name as the submitted entrypoint. Optimization checks appear as separate executed evidence claims and do not change the ordinary test summary. The report details retain both source versions, notes, check counts, and complexity estimates before and after. With four to six benchmark inputs, timings are collected only when configured correctness and property checks pass and the optimized version passes every equivalence check. Java timing uses five warmups and nine `System.nanoTime()` trials per size, returning median nanoseconds for both variants. A separate low-confidence statistical claim says whether the candidate had a lower measured median at every size. Java measurements include reflection overhead and host/JVM timing noise; Python source-line events omit native-library work. Neither measurement establishes a general speedup or asymptotic improvement.

`POST /v1/optimization-proposals` accepts `{language, code, problem}` and only performs static pattern matching; it never executes submitted source. It recognizes a narrow integer-array accumulation-loop pattern and one Two Sum nested-pair-search pattern in Python and Java. The Two Sum proposal uses a reverse hash-map scan to preserve the first pair returned by the recognized loop order while reducing expected time from O(n²) to O(n) at the cost of O(n) auxiliary space. In the Mode 1 UI, the user can inspect the candidate and choose to verify it; Axioma runs original and candidate against the same test pack and four no-solution benchmark inputs at increasing sizes. A proposal is not a correctness or speedup claim until those configured checks run, and the estimates remain limited to the supplied inputs. No LLM provider is called.

Python and Java function jobs may include `property_code` and `property_tests` (1–50) together. Python source must define `check(args, kwargs, result) -> bool`. Java source must define top-level class `AxiomaProperties` with static `boolean check(Object[] args, Object result)`; the submitted solution class must have a different name. Both run in the worker sandbox. Axioma first requires the solution to pass each provided sample and the property to return `True` for that sample; only then are seeded generated inputs checked. A non-boolean return, exception, or `False` is a failed property check. Property checks are reported as a separate low-confidence executed claim and do not change ordinary test totals. Passing examples only checks that the supplied predicate is consistent with those examples; it does not prove the predicate is a valid specification. Inputs come from Axioma's constraint-aware generator, and this version does not shrink failing inputs.

Python or Java function jobs may request `mutation_tests` (0–20), which requires `reference_code`. Python uses deterministic single-operator AST mutants from a bounded set of arithmetic, comparison, and unary operators. Java creates deterministic single-operator mutants inside the selected reference method, renames the reference class for each mutant, and compiles each mutant in an isolated output directory at runtime. Java mutation generation is intentionally limited to arithmetic, comparison, and boolean operators; unsupported source shapes produce no mutants, which are reported as not run. Mutants are run against provided samples and generated inputs for which the reference executes. The worker adds a low-confidence `statistical` evidence claim with killed, survived, invalid, and not-run counts and a mutation score `killed / (killed + survived)`. Invalid or unrun mutants are excluded from that denominator. This evaluates only this mutant set and the supplied reference; it does not measure all bug-finding ability or prove the reference correct. Mutation results are evidence claims, not correctness test cases, so they do not change the test summary.

The stdin/stdout job route runs each sample in a fresh sandbox for either Python or Java. Input is delivered through a sandbox file rather than interpolated into a shell command. Output comparison normalizes CRLF to LF and ignores trailing newline characters; other whitespace remains significant. After a timed-out case, later cases are recorded as skipped.

## Example report

```json
{
  "job_id": "job-id",
  "claims": [
    {
      "id": "claim-id",
      "type": "executed",
      "confidence": "high",
      "summary": "14 of 15 generated tests passed",
      "provenance": {"tool": "axioma-harness", "tool_version": "0.1.0"},
      "artifact_ids": []
    }
  ],
  "complexity": {
    "method": "operation_count_fit",
    "estimate": "O(n log n)",
    "confidence": "medium",
    "methods_disagree": false
  },
  "tests": {"total": 15, "passed": 14, "failed": 1, "skipped": 0},
  "verification_gates": [
    {"order": 0, "name": "patch_applies", "state": "passed", "evidence_claim_ids": []},
    {"order": 1, "name": "compile", "state": "not_run", "evidence_claim_ids": []}
  ]
}
```

