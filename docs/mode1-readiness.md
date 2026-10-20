# Mode 1 readiness and completion gates

Updated: 2026-10-20

This checklist tracks the original Mode 1 scope. “Implemented” means the code path exists; it does not mean the runtime or an evaluation claim has been verified. Mode 2 stays out of scope until the Gate 1 evidence below exists.

| Area | Current state | Evidence | Remaining completion evidence |
|---|---|---|---|
| API contract and report structure | Implemented; local checks pass | `docs/api-contract.md`, API contract tests, frontend production build | Confirm the hosted CI run once repository Actions results are accessible |
| Problem validation and harnesses | Implemented for Python/Java function and stdin/stdout jobs | `services/api/src/axioma_api/problem_validation.py`, `services/worker/src/axioma_worker/*_harness.py`, API/worker tests | Run real submissions inside both preloaded Docker images |
| Generated inputs | Boundaries, seeded values, and adversarial integer-array patterns are implemented | `services/api/src/axioma_api/problem_generation.py`, generation tests | Broaden typed adversarial families and connect them to repeatable complexity benchmarks |
| Correctness oracle | Partial by design: declared samples, user references, optional independent reference, properties, exhaustive small integer domains, differential checks | API contract and worker harness tests | No general trusted oracle; curated independent expected outputs are still needed for broad claims |
| Complexity and constraint signals | Static heuristics, Python line/opcode counts, Java JVM timing, memory proxies, model fit, disagreement flag, and constraint scale exist | `services/worker/src/axioma_worker/python_complexity.py`, `java_complexity.py`, tests, API contract | Validate measurements in Docker on Java and Python; collect controlled benchmark inputs and report the limitations |
| Optimization | Equivalence checks and measurements are implemented; proposal rules recognize one narrow pattern | `services/api/src/axioma_api/optimization_proposals.py`, worker tests, optimization evaluator | Broaden proposal coverage only with safe transformations; collect independently selected paired runs before claiming improvement |
| Test-quality measurement | Bounded Python/Java mutation generation and scoring tools exist | Worker mutation tests and `evaluation/mode1/evaluate_detection.py` | Label known-correct controls and mutants independently; run and report recall and false-positive rate |
| Dashboard | Browser-local history, topic tags, complexity summaries, report export, and local-history clearing exist | `frontend/src/App.tsx`, frontend build | User accounts, server-side ownership, account deletion, and cross-device data are not in the local-only scope; share final visual designs before visual polish |
| Job pipeline | Durable job states, idempotency, cancellation, lease recovery, event stream, and persisted reports exist | API/queue tests and `docs/api-contract.md` | Verify with PostgreSQL and real worker/container execution; dead-letter semantics remain limited to terminal failure after retry |
| Sandbox security | Docker profile config has resource limits, no network, non-root execution, read-only root, and no host mounts | `services/worker/src/axioma_worker/sandbox.py`, unit tests, threat model | Run the Docker-backed abuse suite; its checks currently skip because Docker/images are unavailable here |
| Evaluation | Complexity, detection, optimization, and latency evaluators exist; complexity output now distinguishes rows from unique solutions | `evaluation/mode1/` tests and guides | Supply at least 50 independently human-reviewed solutions, labeled controls/mutants, selected optimization runs, and enough real jobs for descriptive latency percentiles |
| CI and release evidence | GitHub Actions workflow and local checks are configured | `.github/workflows/ci.yml`; local test/lint/build commands pass | Confirm a successful hosted Actions run; no public deployment is configured because arbitrary-code execution is not safe on a generic free host |

## Gate 1 exit criteria

Do not start Mode 2 until all of these are supported by artifacts and recorded commands:

1. Python and Java sample submissions complete in the Docker sandbox, including function and stdin/stdout paths.
2. The Docker-backed abuse checks pass on the intended local Linux-container runtime; skipped checks do not count.
3. At least 50 distinct solutions have independently reviewed complexity labels, with source/problem provenance and a held-out evaluation partition where calibration is reported.
4. Correct controls and mutants are labeled independently, and the detection report includes denominators and uncertainty intervals.
5. Optimization candidates are preselected, equivalence checked, and paired measurements preserved with their source reports; work-count changes are not described as speedup.
6. Latency data comes from actual completed jobs and is reported with sample counts. It remains a local descriptive measurement, not an SLO.
7. API/worker/evaluator tests, lint, frontend lint/build, database migration, and the hosted CI run pass.
8. The user supplies the final frontend visual design and signs off on the local demo flow.

The current repository has working implementation paths and reproducible evaluator tools, but the external evidence in this gate is not complete. The 50-solution indicator in the evaluator is only a count check; it cannot verify that labels are independent or correct.
