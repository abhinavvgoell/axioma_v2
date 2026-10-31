# Mode 1 test and benchmark evidence audit

Date: 2026-10-29

Scope: Mode 1 evidence behavior, updated for exact benchmark input snapshots.

Purpose: describe the evidence the existing workflow supports; this audit does not change analyzer behavior, scoring thresholds, or evaluation labels.

## Findings

| Workflow / evidence label | Oracle or invariant | What a passing result establishes | What it does not establish |
|---|---|---|---|
| Imported problem examples (`executed`) | Expected output stored in the locally imported problem pack; function harness compares values, stdin harness compares normalized output. | The candidate matched those expected outputs on the listed examples. | Correctness on hidden or untested inputs, or that upstream expected outputs are error-free. The local pack is not the LeetCode hidden judge. |
| Generated differential checks (`executed`) | A supplied reference implementation; when a second reference is supplied, both are checked against examples and each other first. | Candidate output agreed with the accepted reference output on the generated inputs. | Independent correctness when only one reference exists, or correctness beyond the finite generated set. A reference may share a bug with the candidate. |
| Bounded exhaustive checks (`executed`) | Supplied reference implementation over the explicitly enumerated small integer domain (maximum 256 cases). | Agreement with that reference for every generated value in the bounded domain. | Agreement outside that domain or independent correctness of the reference. |
| User property checks (`executed`, low confidence) | User-provided boolean predicate, first checked against provided examples, then on generated inputs. | The submitted predicate returned true on those finite examples and generated inputs. | That the predicate itself fully or correctly describes the problem, or that the candidate is universally correct. |
| Mutation analysis (`statistical`, low confidence) | Generated single-operator mutants are compared against a supplied reference over sample/generated inputs. | The test set distinguished some generated reference mutants from the reference. | General test quality or correctness. Mutants are a limited deterministic subset, not a representative sample of all defects. |
| Optimization output-equivalence (`executed`) | Both original and candidate outputs are checked against the supplied reference on configured examples/generated inputs. | The two versions matched the reference on each completed check. | Universal semantic equivalence or correctness of a shared reference. |
| Static complexity (`static`) | Language-specific pattern/heuristic analysis; no runtime oracle. | The listed code shape supports the reported estimate under the stated assumptions. For bounded BFS rules, structured evidence records queue traversal, visited-state behavior, adjacency-list versus matrix or grid representation, and the V/E or R/C work argument. The Java monotonic-stack rule separately records its one-push bound and amortized O(n) argument. | A proof of asymptotic behavior, especially for unsupported control flow or callees. BFS and monotonic-stack recognizers are intentionally narrow and remain low-confidence. |
| Python work benchmark (`statistical`, low confidence) | Counts executed source-line events and CPython opcode events; optional traced peak Python allocation. | Relative work/allocation observations for those exact inputs and interpreter. | Wall-clock speed, asymptotic proof, native/JVM memory, or stable results across environments. |
| Java benchmark (`statistical`, low confidence) | Reflective invocation elapsed nanoseconds and JVM heap-pool peak growth. | Median observations for those exact inputs and JVM process. | Asymptotic proof or a portable speed/memory comparison. Reflection, JIT/GC state, and host scheduling affect observations. |
| Job latency evaluator (`statistical`) | Persisted job/event timestamps; nearest-rank empirical percentiles over completed jobs with valid timing events. | Descriptive local queue, worker-lifecycle, and end-to-end latencies for included jobs. | A controlled load test, CPU time, production SLO, or stable tail-latency estimate from a small sample. |
| Plain stdin program exit (`executed`) | Process exit status and timeout state only. | The process exited with status 0 within the sandbox limits. | That output is correct. This path has no expected-output oracle unless it is run through a configured problem pack. |

The worker writes test counts from the same recorded per-case results. For function jobs, the main claim is high-confidence execution evidence; a passing count is still bounded by the cases and oracle described above. The worker's plain stdin fallback records `program_exit` with `Program exited successfully`; consumers must present that as execution success, not as a correctness pass.

## Generation and reproducibility

- Generated inputs use `random.Random(seed)`, deterministic boundary/adversarial construction, duplicate removal, and a final `validate_problem_spec` check. Numeric ranges and collection lengths are checked against the constraints that the problem schema actually represents. This is not validation of omitted, misunderstood, or semantically relational constraints.
- Generation starts from a stored example and mutates supported paths. For arrays, values are copied from the example; several adversarial patterns reorder or repeat those values. A requested count can be only partially fulfilled when no further distinct valid case is generated; skipped cases are reported.
- Benchmark inputs start from the first function example, use a requested size path/pattern, verify the generated collection length equals the requested size, and validate against declared constraints. They do not establish that the pattern is a worst case. Sizes are user-selected (API limits the list to 4–6 increasing sizes).
- Each job now stores immutable-by-worker input snapshots in `input_snapshots`: generated differential/property cases, imported or user examples, generated benchmarks, user-supplied benchmarks, and replayed benchmarks have distinct origins. Snapshots include exact argument values and SHA-256, job/language/problem-pack identity, generator version and source artifact hash when applicable, seed, size path, strategy, and configured sandbox runtime. A unique `(job_id, snapshot_key)` plus insert-on-conflict-do-nothing and post-insert content verification prevents retried/concurrent workers from overwriting or mixing cases.
- `POST /v1/jobs/{job_id}/benchmarks/replay` queues a new job from the source job's persisted benchmark snapshot values. It verifies each snapshot hash and never invokes the current input generator for replay inputs. The new report includes source snapshot IDs and hashes, original generator/runtime provenance, and the actual replay runtime configuration. Result reports label a benchmark set `replayable` only when all requested snapshots exist; a historical job without retained snapshots is labeled `non_replayable`, and replay returns `409`. A generator version string or benchmark metadata by itself is not treated as exact inputs.
- Replay reproduces the recorded inputs, not timing. Measurements can vary across runs, machines, container/runtime versions, JVM state, and host scheduling. The captured Docker configuration is not a complete hardware/OS/JVM fingerprint, and analyzer source revision is not currently attached to every runtime claim.
- Python work counts and traced allocation use three repetitions and the median, with no explicit warm-up. Java wall time and heap-pool peak increase use five warm-ups and nine measured trials, taking the median. Java invocation is reflective; report metadata contains method, sizes, warmups/trials, and measurements, but not a complete machine/runtime/JVM fingerprint.
- Python line/opcode counters measure interpreter events, not elapsed time. Both benchmark approaches are sensitive to runtime, input shape, JIT/GC, process state, and host scheduling. The current limitation text acknowledges this; comparisons remain low-confidence observations.

## Mutation accounting

The runtime mutation score is `killed / (killed + survived)`. Invalid mutants and mutants not run are excluded from the denominator and separately reported; requested-but-not-generated mutants are included in `not_run`. Individual mutant IDs, labels, states, checked-case counts, and reasons are retained. A score is unavailable if there are no valid mutants. This denominator is internally consistent, but the score describes only generated valid mutants and supplied reference cases, not a general percentage of bugs detected.

The offline detection evaluator separately treats any failed check as a detection, excludes records with skipped checks and no failure, and reports denominators and confidence intervals. The optimization evaluator requires every requested equivalence check to pass before a candidate is eligible for benchmark comparison, and requires at least four distinct sizes for aggregate comparisons.

## Current gaps and next priority

1. Attach the analyzer source revision to each runtime evidence claim and consider capturing a fuller OS/architecture/runtime/JVM fingerprint. These improve provenance, but will not make timing portable or deterministic.
2. Ensure the UI/API never renders the plain `program_exit` success outcome as correctness. Existing wording is “Program exited successfully,” but generic outcome fields still use `passed` in that fallback.
3. Keep benchmark and mutation summaries qualified as evidence on this recorded input/mutant set, not proof or a universal quality score.

This milestone adds the `input_snapshots` table with an additive migration and the benchmark replay endpoint. Existing historical rows remain untouched and are non-replayable when their argument values were not retained. No thresholds or complexity scoring behavior changed.

## Source paths inspected

- `services/api/src/axioma_api/problem_generation.py`
- `services/api/src/axioma_api/contracts.py`
- `services/worker/src/axioma_worker/runtime.py`
- `services/worker/src/axioma_worker/python_harness.py`
- `services/worker/src/axioma_worker/java_harness.py`
- `services/worker/src/axioma_worker/mutation_testing.py`
- `services/worker/src/axioma_worker/java_mutation_testing.py`
- `evaluation/mode1/evaluate_detection.py`
- `evaluation/mode1/evaluate_optimization.py`
- `evaluation/mode1/evaluate_latency.py`


## Fresh independent BFS v2 packet preparation — 2026-10-30

A 28-case candidate packet (14 Java, 14 Python) is awaiting human label review in `evaluation/mode1/bfs-fresh-v2-review-2026-10-30/`. Candidate packet SHA-256: `d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1`. All 28 per-case source hashes were verified. The readable review sheet contains the source, proposed mathematical complexity, rationale, assumptions, expected response category, and blank reviewer fields. No analyzer predictions/evidence are included and no analyzer was run on the packet. The previous BFS evaluation, diagnostic cases, analyzer tests used for rule development, and relevant stack/recurrence/graph calibration cases are listed as exclusions in the packet directory.

This is a candidate review packet, not an approved gold set or evaluation result. The analyzer must not be run against it until each retained case has an explicit human decision and any ambiguous labels have been corrected or excluded. Analyzer source hashes and rule versions at packet preparation are recorded separately in its manifest. See the packet's `evidence-audit-entry.md` for the phase details.
