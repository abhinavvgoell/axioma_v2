# Backend lifecycle and sandbox audit

Date: 2026-10-29  
Audited revision: `01b16dd`  
Scope: job creation, queueing, worker recovery, cancellation, Docker execution boundary, resource limits, and existing verification. This is a local-development audit, not a public-deployment security approval. No code, schema, or configuration was changed.

## Summary

The intended boundary is present: the API persists submissions; the separate worker invokes code in a fresh Docker container; the container has no network, no host bind mount, a read-only root filesystem, a non-root UID, and CPU/memory/PID/time/output limits. It fails closed if the required Docker image is absent and does not pull images while processing a job. The README explicitly warns against exposing the local service publicly.

The most significant lifecycle gap is the fixed 180-second worker lease with no heartbeat. The API accepts up to 100 stdin/stdout samples, and the worker starts a separate sandbox run for every sample, with each run allowed 10 seconds of submitted-code time. A sufficiently long stdin job can therefore outlive its lease. With multiple workers, another worker can reclaim and execute that still-running job. A stale worker is prevented from persisting after ownership changes, but duplicate execution and resource consumption remain possible.

Two additional critical boundaries are not proven by current tests: running-job cancellation is marked terminal before the worker confirms container termination, and cleanup errors from `docker rm -f` are silently suppressed. Public access is not safe: the API has no authentication/ownership enforcement, the worker requires Docker daemon access, and the development Compose file publishes PostgreSQL with a fixed password.

## Prioritized findings

| Priority | Finding | Evidence and impact |
|---|---|---|
| P1 | **Lease can expire during a valid long stdin job.** | `services/api/src/axioma_api/queue.py` sets a 180-second lease and has no renewal path. `services/api/src/axioma_api/contracts.py` permits 100 samples. `services/worker/src/axioma_worker/runtime.py` runs stdin samples sequentially, each through a new sandbox; `services/worker/src/axioma_worker/sandbox.py` allows 10 seconds per submitted-code run. `worker_iteration` reaps only when a worker returns to its loop. If another worker is running, it can reap/reclaim an active long job. The first worker later checks its lease owner and avoids writing stale results, but the job can run twice and consume resources. Existing lease tests expire a lease manually; no test covers a live job longer than its lease or heartbeat renewal. |
| P1 | **Cancellation completion is reported before termination is confirmed.** | `services/api/src/axioma_api/main.py:313-322` clears the lease and transitions a running job directly to `cancelled`. The sandbox polls for that status, kills its Docker CLI process, then asks Docker to kill/remove the container (`sandbox.py:111-118, 205-225`). The API response/SSE can therefore say `cancelled` before the container is known to be stopped. Current cancellation API coverage cancels a queued job; no test cancels a running container and verifies process/container termination before terminal state. This differs from the security specification's order: stop descendants/container, then mark cancellation complete. |
| P1 | **Container cleanup is best effort and its failure is hidden.** | `sandbox.py:143` calls `_try_docker(["rm", "-f", container_id])` in `finally`; `_try_docker` suppresses OS and subprocess failures (`sandbox.py:199-203`). A daemon or CLI failure during cleanup is invisible to the caller and there is no post-cleanup verification or stale-container reaper. `test_run_lifecycle_uses_prebuilt_image_and_cleans_up` and `test_timeout_kills_and_removes_the_container` assert that removal was attempted, not that it succeeded. Normally the explicit removal succeeds; under daemon failure the persistent `sleep infinity` container could remain. |
| P1 for any shared/public deployment | **API job endpoints have no authentication or per-user authorization.** | Job creation, reads, result, event stream, and cancellation in `services/api/src/axioma_api/main.py` do not authenticate callers; `create_job` assigns every request `owner_key="local"` (`jobs.py:38`). README states auth/user accounts are absent and warns not to expose this local code-execution setup. A caller with access to the API can submit work, inspect stored inputs/results, and cancel jobs. Do not deploy it as a shared or public service in this state. |
| P1 for network-reachable development hosts | **Compose publishes PostgreSQL with a known static development password.** | `compose.yaml:3-9` uses `POSTGRES_PASSWORD: axioma` and maps `5432:5432` without a loopback-only host binding. Anyone who can reach the host port may attempt database access. The Compose file currently starts only PostgreSQL; this is a development configuration, not a deployment stack. |
| P2 | **Concurrent idempotent job creation can surface a database error.** | `jobs.py:38-71` first queries the idempotency key, then inserts; the model has a unique constraint on `(owner_key, idempotency_key)`. Two concurrent same-key requests can both miss the initial query and race at insert. The uniqueness constraint prevents duplicate rows, but `main.py` catches `ValueError`, not `IntegrityError`; one request may get a 500 instead of the existing job response. Current tests only submit sequentially. |
| P2 | **Database-backed multi-worker claim behavior is not verified in this environment.** | `queue.py:14-40` uses `SELECT ... FOR UPDATE SKIP LOCKED`, appropriate for PostgreSQL workers. SQLite ignores row-level `FOR UPDATE` semantics, so the local SQLite mode should be treated as a single-worker development mode. The PostgreSQL concurrency test exists (`services/api/tests/test_postgres_queue.py`) but was skipped because `AXIOMA_TEST_DATABASE_URL` is unset. |
| P2 | **Runtime image tags are not immutable.** | `services/worker/src/axioma_worker/adapters.py` uses `python:3.13-slim` and `eclipse-temurin:21-jdk`, not image digests. The worker checks that a local image exists and does not pull it, which avoids implicit updates during job execution, but rebuilds on different hosts may resolve different image content. This affects reproducibility and supply-chain assurance. |
| P2 | **The limits are present, but some abuse paths are only partially tested.** | The sandbox sets 256 MiB memory, 1 CPU, 64 PIDs, a 10-second per-run timeout, 64 MiB `/work` tmpfs, 32 MiB `/tmp` tmpfs, a 1 MiB returned output cap, and a 64 KiB aggregate source-file limit (`sandbox.py:39-42, 76-77, 145-177, 227-234`). Existing Docker tests check timeout, network denial, read-only root, PID/memory values, and output truncation. The memory test reads the cgroup limit rather than exercising an allocation bomb; output flood uses 2 MB, below the 32 MB `/tmp` cap. There are no explicit tests for fork-bomb termination, filling tmpfs, or cleanup after daemon loss. |
| P2 | **Request bounds are field-level, not a total request-body cap.** | Pydantic limits source fields, statement, sample count, and some argument counts in `contracts.py`, but nested `Any` input/expected values can be large and there is no visible ASGI request-body size limit. This can cause avoidable API memory/validation load before the sandbox's 64 KiB aggregate source cap applies. |

## Verified controls and flow

- **Creation and idempotency:** `jobs.py:38-71` fingerprints mode/language/input, returns the prior job for an identical key, rejects key reuse with different input, and records the initial queued event. The database enforces unique `(owner_key, idempotency_key)`.
- **State transitions and streaming:** `jobs.py:13-35,74-86` defines legal states and emits events. `main.py:263-311` streams ordered events with `Last-Event-ID` replay and keep-alives; the stream closes after a terminal event is drained.
- **Claim and crash recovery:** `queue.py:14-68` claims the oldest queued row with a lease and requeues an expired lease once, then fails after two attempts. `worker/main.py:23-40` invokes the reaper during normal polling and after iteration exceptions. A dead worker's job is not permanently stuck if another worker remains active to run the reaper.
- **Stale-result protection:** `runtime.py:486-505` checks that the job is still running and that the finishing worker still owns the lease before persisting. Test/result records and terminal transition are written through the same session path; terminal jobs cannot transition back to running through `transition_job`.
- **Execution stays out of the API:** API routes validate and persist submitted code. `runtime.py` sends it to `DockerSandbox`; no submitted source is evaluated in the FastAPI process.
- **Sandbox setup and cleanup:** `sandbox.py:64-143` inspects prebuilt images, creates a unique named container, transfers source files through tar stdin, runs the fixed command, then attempts forced removal in `finally`. No host working directory or broad bind mount is passed to the container.
- **Container restrictions:** `sandbox.py:145-177` applies `--network none`, `--read-only`, drops capabilities, `no-new-privileges`, non-root UID/GID 65534, 64 PID limit, 256 MiB memory with swap equal to memory, 1 CPU, and bounded tmpfs mounts. Docker's default seccomp profile is left enabled; no custom profile is configured.
- **Timeout and output handling:** `sandbox.py:205-234` polls cancellation and a monotonic deadline, kills the container on timeout/cancel, reads only the configured output prefix, and records truncation. Docker operations themselves have short command timeouts. Image errors fail closed; the worker does not pull images.
- **Secrets/filesystem/network:** no host directory or Docker socket is mounted into the submitted-code container; no host environment variables are passed with `docker create`; rootfs is read-only and network mode is disabled. The trusted worker itself must have Docker daemon control, so compromise of the worker is outside the container boundary. The Docker daemon and host kernel remain trusted.

## Existing tests and reproducible commands

Run from repository root in PowerShell with the existing API virtual environment:

```powershell
.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py services/api/tests/test_jobs.py services/api/tests/test_queue.py services/api/tests/test_postgres_queue.py services/worker/tests/test_runtime.py services/worker/tests/test_sandbox.py services/worker/tests/test_sandbox_integration.py -ra
```

Audit run on 2026-10-29: **60 passed, 1 skipped in 31.74s**. The skip was `test_postgres_worker_skips_a_locked_queued_job` because `AXIOMA_TEST_DATABASE_URL` was not set. Docker-backed sandbox integration checks ran in this invocation and were not skipped.

Relevant coverage includes:

- `services/api/tests/test_api.py::test_job_submission_is_idempotent_and_cancellation_is_streamable` (sequential duplicate request, queued cancellation, event stream)
- `services/api/tests/test_jobs.py::test_job_creation_is_idempotent_and_records_initial_event`
- `services/api/tests/test_jobs.py::test_job_state_machine_rejects_terminal_transition`
- `services/api/tests/test_queue.py::test_worker_claims_job_with_a_lease_and_reaper_retries_once`
- `services/worker/tests/test_sandbox.py::test_container_profile_has_isolation_and_resource_limits`
- `services/worker/tests/test_sandbox.py::test_run_lifecycle_uses_prebuilt_image_and_cleans_up`
- `services/worker/tests/test_sandbox.py::test_timeout_kills_and_removes_the_container`
- `services/worker/tests/test_sandbox_integration.py` (network/read-only root, timeout, output truncation, cgroup memory/PID values, Java runtime/harness)
- `services/worker/tests/test_runtime.py` (normal result persistence and language/interface paths)

For PostgreSQL queue-lock verification, set `AXIOMA_TEST_DATABASE_URL` to a disposable PostgreSQL test database and rerun `services/api/tests/test_postgres_queue.py`. Do not point that test at a database containing user data: it creates temporary test jobs and deletes those test rows.

## Recommended next fix order

1. Resolve lease ownership for jobs that can exceed the fixed lease: heartbeat/renewal or a bounded job deadline that is strictly shorter than the lease. Add a test with a live worker and a competing reaper/worker before changing queue behavior.
2. Make cancellation state reflect confirmed sandbox termination, and test cancellation during execution. Preserve the terminal state machine/API contract unless approved otherwise.
3. Surface and verify cleanup failure rather than silently claiming cleanup succeeded; add a test where Docker removal fails.
4. Close deployment-only risks before any shared exposure: authenticate/authorize all job routes, protect the worker/daemon boundary, and bind Compose PostgreSQL to loopback/use non-default secrets.
5. Add concurrent idempotency and PostgreSQL multi-worker tests, then consider immutable runtime image digests and a request-body size limit.

Per the M6 specification, this audit does not implement these fixes. The highest-priority implementation candidate is the lease/long-job race, followed by cancellation/cleanup verification.
