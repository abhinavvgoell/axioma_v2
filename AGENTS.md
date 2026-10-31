# Axioma — Repository Instructions for Codex

These instructions apply to every task in this repository. Follow them together with the current PRD, TRD, UX specification, backend schema/API contract, implementation plan, AI/ML evaluation plan, and sandbox security/testing specification. The repository's actual code and migrations are the source of truth for what exists today; the documents define intended behavior. When they conflict, stop and report the exact conflict rather than silently overwriting existing behavior.

## 1. Product and current implementation

Axioma is a code intelligence and DSA analysis platform. Its current Mode 1 accepts a coding problem and Java or Python solution, matches the problem against a locally imported problem catalog, runs catalog sample tests in an isolated Docker sandbox, and reports test evidence, complexity estimates, and optional benchmark evidence. The catalog dataset is imported locally and must not be committed to Git.

Current stack as reported by the product owner:
- Frontend: React, TypeScript, Vite.
- API: Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Persistence / queue: SQLite locally or PostgreSQL; database-backed worker queue; streamed job updates.
- Execution: Docker sandbox with separate Java and Python runtimes.
- Problem data: local catalog of 1,000 compatible packs from a pinned public dataset; recent importer retained at least one supported numeric constraint in 534 packs. Dataset itself is not committed.
- Analysis: title/description catalog matching with ambiguous-match rejection; imported examples; bounded seeded input generation; pattern-based language-specific static heuristics; optional empirical benchmarking; narrow rule-based optimization suggestions.

There is currently **no trained ML model or LLM in Mode 1**. Do not describe its current analysis as ML-powered. Static inference, heuristic estimates, benchmark measurements, and any future ML/LLM output must be separately identified. Historical diagnostic evaluation reported 33.3% exact complexity accuracy at 62.5% coverage; it was not a final untouched evaluation. Five fresh cases were prepared but had not yet been analyzed according to the latest status. Treat this as open work; do not claim new results unless reproduced by running the current code.

Latest reported code milestone included commit `885a5d9`, which updated constraint extraction/mapping and generated benchmark inputs for Binary Search at sizes 8, 16, 32, and 64. The supplied status says 20/20 imported checks passed and static, line-event, and opcode estimates agreed on `O(log n)` for that case. These are reported existing results, not permission to assume the current checkout is at that commit. Verify the actual Git status and code.

## 2. Required task workflow

For each task:
1. Inspect the repository before editing: `git status`, recent commits, project tree, README, dependency/lock files, environment examples, tests, current API routes, SQLAlchemy models, Alembic migrations, worker implementation, sandbox configuration, and relevant analysis code.
2. Summarize what exists, what is already working, and the smallest task that meets the request. Do not re-scaffold the application or replace the stack without a specific, evidence-backed reason.
3. Read the relevant project documents. If files are available in the repository, use their latest version. When documents differ, identify the mismatch and defer to actual runtime contracts for preserving existing data and routes until the product owner approves a change.
4. Make a short plan with files expected to change and tests to run.
5. Implement one bounded milestone. Avoid unrelated refactors and dependency additions.
6. Run the most relevant tests, then broader tests when practical. Report exact commands, pass/fail results, and tests not run.
7. Update docs, API examples, configuration examples, and migration notes if behavior changes.
8. Finish with: files changed, behavior changed, test evidence, known limitations, migration/recovery notes, and next safe step.

## 3. Change safety and repository preservation

- Never delete or rewrite a working feature simply because a cleaner architecture is imaginable.
- Never drop, recreate, or reset the user's database as a convenience. Do not run destructive migration/reset commands without explicit approval and a verified backup plan.
- Never overwrite local uncommitted changes. Inspect `git status` and preserve them.
- Do not commit, push, rebase, force-push, change branches, or alter remote history unless explicitly asked.
- Do not commit datasets, generated catalog files that are intentionally local-only, private source code, model weights, credentials, `.env` files, or large generated artifacts. Follow the existing `.gitignore` and update it carefully if needed.
- Keep migrations additive where possible; explain and test any data migration.
- Preserve existing API behavior unless a requested change requires otherwise. Add compatibility or migration handling for breaking changes.
- Do not claim work was completed if files were not changed or tests were not executed.

## 4. Axioma analysis correctness principles

- Separate facts from estimates. Use distinct result fields or evidence labels for compilation, test execution, static findings, complexity estimates, benchmark measurements, optimization proposals, and future ML/LLM output.
- Never present runtime benchmarks as proof of asymptotic complexity. Benchmarks are machine-, runtime-, input-, and environment-dependent observations.
- Complexity estimates must include the best-supported class, reasoning, assumptions, and confidence/coverage state. If the analyzer cannot infer a reliable class, it should return inconclusive/unsupported rather than invent a result.
- Correctness is not established merely because code runs or imported examples pass. Show which tests ran, their expected outputs and source, and which checks were not possible.
- Seeded generated tests must be reproducible and must be valid for the problem's stated constraints. Test generation without an expected-output oracle can test robustness, but cannot independently prove correctness.
- Problem matching must reject ambiguous or low-confidence catalog matches; do not silently choose an unrelated problem pack.
- Optimization recommendations are proposals. Do not mutate the user's code silently. Validate the candidate against the same relevant tests and benchmark sizes before describing a measured improvement.
- Do not generate fake confidence scores, accuracy numbers, runtime improvements, or model capabilities.
- The model is not trained in Mode 1. Do not add an ML dependency/model merely to satisfy a label. A future ML component must have a defined task, data provenance, a leakage-resistant split, a baseline, evaluation, model versioning, and documented limitations.

## 5. Execution sandbox and security rules

- Never execute submitted code inside the FastAPI request process or on the host outside the intended sandbox.
- Treat code, filenames, problem text, test output, catalog content, and generated suggestions as untrusted.
- Do not run privileged containers. Do not expose the host Docker socket to submitted code. Do not mount host credentials or broad host directories into workers.
- Enforce time, CPU, memory, process, output-size, temporary-disk, and wall-clock limits. Ensure cancellation/timeouts terminate the whole process tree and clean up temporary artifacts.
- Disable outbound network access by default. Do not allow submitted code to access internal services, cloud metadata endpoints, or credentials.
- Use fixed runtime images/versions where practical. Avoid shell-string interpolation; pass arguments safely and validate identifiers and paths.
- Keep API worker and sandbox worker privileges separate. Log job IDs and structured outcomes, but avoid logging source code or secrets unnecessarily.
- If the current environment cannot provide adequate isolation, do not weaken the boundary to make tests pass. Implement a safe interface or report the blocker.

## 6. Backend, jobs, and database rules

- Maintain clear job states and valid state transitions; a worker crash must not leave a job permanently marked running without detection/recovery.
- Treat queue delivery as potentially duplicated. Use idempotent updates and unique job/run identifiers where appropriate.
- Keep database transactions short; do not hold a transaction open while compiling or running user code.
- Use SQLAlchemy models and Alembic migrations consistent with existing project conventions. Do not edit deployed schema only in model code.
- Avoid blocking network, compilation, or long benchmark calls inside API handlers. Use the established worker/job mechanism.
- Streamed job updates must be authorized, tied to the correct job, and closed cleanly on completion, failure, or cancellation.
- Keep SQLite compatibility for local development if the project currently supports it; use migrations and queries compatible with the supported dialects or clearly document any PostgreSQL-only path.
- Validate request shape and size at the API boundary. Return stable, documented error codes; do not leak stack traces or host paths to clients.

## 7. Frontend and UX rules

- Keep existing React/TypeScript/Vite patterns and component conventions after inspecting the repository.
- Represent queued, running, completed, failed, timed-out, cancelled, and inconclusive states accurately.
- Never use fabricated progress, dummy result metrics, or hard-coded successful reports as production behavior.
- Display the origin of evidence: imported sample, generated test, compiler, static heuristic, benchmark, optimization rule, or future model output.
- Distinguish static complexity estimate from measured runtime trend and disclose limitations.
- Make error, empty, loading, and partial-result states explicit. Keep the original submitted code unchanged when showing a candidate optimization.
- Ensure frontend types match actual Pydantic API schemas. Prefer generated/shared contract tests or documented examples where feasible.

## 8. Testing and evaluation standards

- Add tests for behavior and failure paths, not only happy paths.
- Test complexity categories across multiple algorithm families and both supported languages where a rule claims to support them.
- Maintain a genuinely fresh evaluation set for final performance claims. Do not keep tuning against the final holdout; keep development and final evaluation data separate.
- Split by repository, bug, problem family, or time where appropriate to limit near-duplicate leakage. Document the split unit.
- Report coverage and conditional accuracy separately. State the denominator and how inconclusive cases are scored.
- Benchmark with documented hardware, runtime versions, input generation method, warm-up/repetition policy, and variability where relevant.
- Test matching ambiguity, malformed submissions, compilation errors, runtime errors, timeouts, memory limits, output floods, cancellation, worker restart, and DB persistence.
- For optimization, verify semantic equivalence with tests; benchmark on the same input family and report no improvement when evidence is inconclusive.
- A test passing is evidence for the tested cases, not a general correctness proof.

## 9. Dependencies and design scope

- Prefer the existing dependency set. Add a dependency only when it materially enables a required feature and is maintainable.
- Do not introduce microservices, Kubernetes, Kafka, or a second database merely because they are common in production systems.
- Keep language-specific analysis behind adapters/interfaces where it reduces coupling, but avoid speculative abstraction.
- Keep deterministic analysis available if an optional external service fails.
- Never make a paid provider mandatory for the local Mode 1 workflow unless the product owner explicitly changes that requirement.

## 10. Required completion report

At the end of every task, report:
- Summary of changes and user-visible impact.
- Files added, modified, and removed.
- Actual tests run, exact commands, pass/fail counts, and skipped tests.
- Migration/data compatibility notes.
- Security implications and limitations.
- Measured results with environment and sample-size context; do not infer beyond data.
- Remaining work and one recommended next step.

## 11. Default first response for a new Codex session

Before writing code, respond with:
1. Current branch and clean/dirty working-tree status.
2. Current relevant architecture and test commands discovered from the repository.
3. The state of the specific feature requested, backed by files/tests/commits.
4. Conflicts between request, docs, and implementation.
5. A small milestone plan and the tests that will be used as the completion gate.

Then proceed with the smallest safe milestone unless a truly blocking question exists.
