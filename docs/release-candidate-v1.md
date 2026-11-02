# Mode 1 release-candidate validation

This is a local validation record and reproducible demo guide. It does not declare Axioma production-safe or ready for public code execution.

## Reproduce a local setup

From a clean clone on Windows, install the API and worker dependencies using the commands in the root README. Use a fresh database filename so an existing local database is never migrated by accident:

```powershell
py -3.14 -m venv services/api/.venv
services/api/.venv/Scripts/python -m pip install -r services/api/requirements.lock
services/api/.venv/Scripts/python -m pip install -e services/api --no-deps
services/api/.venv/Scripts/python -m pip install -e services/worker --no-deps
$env:DATABASE_URL = "sqlite:///./axioma-release-demo.db"
Set-Location services/api
.\.venv\Scripts\alembic upgrade head
```

In a second terminal, use the same `DATABASE_URL` and start the API and worker from `services/api`:

```powershell
$env:DATABASE_URL = "sqlite:///./axioma-release-demo.db"
Set-Location services/api
.\.venv\Scripts\uvicorn axioma_api.main:app --host 127.0.0.1 --port 8000
```

```powershell
$env:DATABASE_URL = "sqlite:///./axioma-release-demo.db"
Set-Location services/api
.\.venv\Scripts\axioma-worker
```

The local catalog is intentionally excluded from Git. Rebuild it from the pinned source before running the demo:

```powershell
Set-Location <repository-root>
services/api/.venv/Scripts/python services/api/scripts/import_problem_catalog.py --limit 1000
```

Pull the pinned runtime images once if they are not already present:

```powershell
docker pull python:3.13-slim
docker pull eclipse-temurin:21-jdk
```

## Run the deterministic Mode 1 demo

With the API, worker, and Docker sandbox running, from the repository root:

```powershell
services/api/.venv/Scripts/python services/api/scripts/run_release_demo.py
```

The script checks six scenarios and exits nonzero on any mismatch: successful Python and Java samples, ambiguous match rejection, Java compilation failure, a Python timeout, and an inconclusive complexity estimate. It creates local job records; rerunning it creates additional records. It does not clear or reset the database.

To use a different local API URL, set `AXIOMA_API_BASE_URL` or pass `--base-url`. Increase `--timeout-seconds` only when the worker needs longer to process a job.

## Automated checks

Run from the repository root after installing the API environment and frontend dependencies:

```powershell
services/api/.venv/Scripts/python -m pytest services/api/tests services/worker/tests -q
services/api/.venv/Scripts/python -m pytest evaluation/mode1 -q
services/api/.venv/Scripts/ruff check services/api/src services/api/tests services/api/migrations services/worker/src services/worker/tests evaluation/mode1
Set-Location frontend
npm ci
npm test
npm run lint
npm run build
```

For PostgreSQL, use an isolated disposable database and set `AXIOMA_TEST_DATABASE_URL` when running the queue integration tests. The CI workflow starts a fresh PostgreSQL service and runs migrations before the tests. Do not point validation commands at an existing database you need to preserve.

## Complexity evaluation snapshot

The current post-fix replay combines three user-reviewed **calibration** packets with 15 distinct cases. It answered and exactly matched all 15 (15/15; 100% calibration coverage and exact accuracy). The cases were used to diagnose or verify analyzer patterns, so this is not held-out evidence and must not be presented as general accuracy. The evaluator marks it below the 50-solution minimum; no untouched post-fix evaluation partition or confidence calibration is available. The exact outputs, label/source hashes, analyzer commit, and evaluator report are recorded in `evaluation/mode1/complexity-review-2026-10-29/`.

The older packet-03 report is a **pre-fix baseline**: 2/5 answered and 2/5 exact. It remains unchanged for traceability. Do not combine it with the post-fix replay or describe either result as a final held-out test-set score.

The independent BFS v2 packet was also run once and scored on 2026-10-30, before the later BFS recognizer changes. It contains 28 cases (14 Java, 14 Python): response agreement was 23/28 (82.1%), while the analyzer emitted estimates for only 3/28 (10.7%). All three emitted estimates were exact (3/3), and it abstained unexpectedly on five cases whose reviewed response was `estimate`. This is a targeted diagnostic baseline only; the packet was subsequently used during analyzer development and is not an untouched post-change holdout. See the [saved v2 report](../evaluation/mode1/bfs-fresh-v2-results-2026-10-30/evaluation-report-v2.md) and [post-evaluation development note](../evaluation/mode1/bfs-fresh-v2-results-2026-10-30/post-evaluation-development-note.md). Do not combine it with the older 49-scorable evaluation or the 15-case calibration replay.

A subsequent development replay on the same 28 BFS cases reached 28/28 response agreement, with 8/8 expected estimates emitted and exact; 20 cases were correctly left unknown. This remains development evidence because these cases informed the changes. It is not an independent accuracy result and does not generalize beyond this BFS packet. The targeted changes add Java deque `removeFirst()` recognition, bounded accounting for nested unbraced full-grid loops, and Python tuple-assignment recognition for an initialized visited set. The [development report](../evaluation/mode1/bfs-fresh-v2-development-2026-10-30-run-02/development-report-v2.md) and its manifest preserve the results and hashes.

No new wall-clock or memory benchmark is claimed by this release-candidate check. Runtime measurements from an individual workstation are observations, not proof of asymptotic complexity.

## Known limitations and security boundary

- Mode 1 has no trained ML model or LLM. Complexity analysis uses syntax-pattern heuristics and may abstain on valid algorithms it does not recognize.
- Imported examples are not LeetCode hidden tests and have not been independently verified against the original judge. Passing them is not proof of correctness.
- Generated differential checks need a valid reference implementation; generated inputs without an oracle are not correctness evidence.
- Worker-generated checks and benchmark cases are persisted as input snapshots with their exact arguments, origin, problem identity, generator source hash/version when applicable, seed/size/strategy, and configured sandbox runtime. Completed jobs with retained benchmark snapshots can be replayed through `POST /v1/jobs/{job_id}/benchmarks/replay`; old jobs without them are explicitly non-replayable. Replay reuses inputs, not identical timing results.
- Complexity estimates describe the supported static rules. Optional line/opcode counts, JVM timings, and memory signals are environment- and input-dependent observations, not asymptotic proofs.
- The imported dataset is local-only. The source repository's MIT license does not settle rights for embedded third-party problem statements or test cases; review redistribution rights before sharing the catalog.
- This is a local student project, not a public arbitrary-code execution service. Docker containers share the host kernel, the worker controls the Docker daemon, and the application has no account-level authorization. A separate security review is required before exposing execution to untrusted public traffic.
- Authentication, hosted deployment, repository ingestion/repair, and Mode 2 are not part of this release candidate.

## Validation record

Clean-checkout validation ran against commit `a97d19fae3ef43cb243c420939802b35bd351748` on Windows 11 Home, build 26200, with Python 3.14.3, Node 24.20.0, npm 11.19.0, Docker Engine 29.9.1, and Eclipse Temurin 21.0.12 in the Java sandbox image.

| Check | Result |
|---|---|
| Clean setup | Shallow clone from GitHub at the commit above; a new Python 3.14.3 virtual environment installed `requirements.lock` and both editable packages. `npm ci` installed 98 packages and reported 0 vulnerabilities. |
| API and worker suite, including Docker-backed sandbox tests | `173 passed, 1 skipped` in 39.38s from the clean clone. The skip was the PostgreSQL queue-lock test because the SQLite run had no `AXIOMA_TEST_DATABASE_URL`. |
| Mode 1 evaluator suite | `27 passed` in 0.61s. |
| Python lint | Ruff passed across API, worker, and evaluator sources/tests. |
| PostgreSQL migration and queue-lock integration | Passed from the clean clone on a new disposable `postgres:17.11` container bound to `127.0.0.1:55433`; Alembic applied both migrations and `test_postgres_worker_skips_a_locked_queued_job` passed. The container used no persistent volume and was removed afterward. |
| Frontend | `npm test`: 7 passed; `npm run lint`: passed; `npm run build`: passed. |
| SQLite setup, live demo, and persistence | Both Alembic migrations applied to a new scratch DB. All six demo scenarios passed: ambiguous match rejection, Python sample, Java sample, Java compile failure, Python timeout, and inconclusive complexity. Five submitted jobs were persisted with completed status; after stopping the original API and worker and starting a new API process on the same DB, all five jobs and reports remained readable. The timeout job retained its timeout message and skipped case outcomes. |
| Catalog import reproducibility | Two fresh imports from the clean clone each selected 1,000 packs from 2,448 eligible packs at pinned revision `182cd19fd53161efd70a1ef074fe1056b659bfa3`. Catalog JSON SHA-256 matched across imports: `9fe1dfef3c257cc0409c7eaabbcbdc1564a60bdb6647a7645c355018724c5a6b`. License and source metadata artifacts also matched byte-for-byte. The demo used a local ignored catalog import; catalog data remains excluded from Git. |
| Complexity replay | The replay script ran from the clean clone and matched 15/15 calibration cases (15/15 answered). This is not held-out evidence. |

The PostgreSQL check is a single concurrency test on a disposable local server, not a broad PostgreSQL compatibility guarantee. The catalog hash result verifies deterministic output for this pinned importer/runtime, not dataset licensing for redistribution. No performance benchmark or public deployment claim is made.

Follow-up local check on 2026-11-02: against a newly created scratch SQLite database (the existing local databases were not used), `services/api/.venv/Scripts/python.exe services/api/scripts/run_release_demo.py --timeout-seconds 120` passed all six scenarios. `GET http://127.0.0.1:8000/health` returned `{"status":"ok"}`, the frontend at `http://127.0.0.1:5173/` returned HTTP 200, and `/analyzer` loaded in the in-app browser. The current local suites also passed: `services/api/.venv/Scripts/python.exe -m pytest services/api/tests services/worker/tests evaluation/mode1 -o addopts='' -q` reported 348 passed and 1 skipped in 34.03 seconds; the skip was the PostgreSQL integration test because `AXIOMA_TEST_DATABASE_URL` was unset. Ruff passed across API, worker, and evaluation code; in `frontend/`, `npm test` reported 15 passed, `npm run lint` passed, and `npm run build` passed. The test run exposed a Python 3.14 exception-message wording difference; commit `dac44c3` made the assertion check the stable exception type/message meaning while retaining the source-location assertion. These are local checks, not an independent clean-clone reproduction.

### Remaining release gate

- Have someone other than the implementer reproduce the documented install/test/demo path from a clean checkout; this independent reproduction remains unverified.
- Collect and review additional calibration cases, then freeze a separate untouched post-fix evaluation set before making broader complexity claims. The current 15-case result is below the evaluator minimum and all cases are calibration data.
- Do not tag or advertise a public release until those checks and the separate sandbox security review are complete.
