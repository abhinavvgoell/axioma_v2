# Exact benchmark input replay

Mode 1 stores each test input snapshot in `input_snapshots`, linked to its analysis job. The snapshot contains the exact arguments (or stdin), a canonical SHA-256 hash, the input origin, language, problem-pack identity where available, generator version and source artifact hash where applicable, seed/size path/strategy, and the sandbox configuration used for the original analysis.

Input origins distinguish imported examples (`imported_sample`), user examples (`user_sample`), worker-generated differential and property checks, generated benchmarks (`generated_benchmark`), user-provided benchmarks (`user_benchmark`), and replayed benchmarks (`benchmark_replay`). Worker inserts are idempotent by job and snapshot key. A conflicting retry fails integrity validation rather than replacing the recorded value.

## Replay a completed benchmark

```http
POST /v1/jobs/{job_id}/benchmarks/replay
```

The endpoint creates a separate queued analysis job, which runs under the existing worker sandbox and its limits. The worker consumes the stored benchmark argument values; it does not call the current generator to recreate them. The replay report records source snapshot IDs and hashes, the original generator/runtime provenance, and the actual runtime configuration used by the replay. The job's usual event stream remains available at `/v1/jobs/{replay_job_id}/events`.

Replay requires a one-to-one match between the source job's declared benchmarks and stored snapshot keys (`benchmark/{index}/{size}`). A partial set, an unexpected key, or a key whose stored size differs from the declaration is non-replayable and returns `409`; matching counts alone do not establish complete coverage.

The result API labels benchmark provenance `replay_state: replayable` only when every requested benchmark has its matching stored snapshot and each input hash verifies; otherwise it reports `non_replayable`. The endpoint returns `409` when the source job is not complete, has no retained benchmark snapshots, has incomplete or mismatched snapshot coverage, or a stored snapshot fails its hash check. Pre-migration jobs without snapshots remain explicitly non-replayable; metadata such as seed and generator version is insufficient to reconstruct exact values.

Replay guarantees input reuse, not identical performance measurements. Timing and memory observations can vary with the host, container/runtime environment, JVM state, and scheduling.
