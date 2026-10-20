# Threat model, version 1

## Assets

- Submitted source code and repositories
- Host CPU, memory, process table, filesystem, and network
- User data, API credentials, database contents, and any future LLM credentials
- Integrity of evidence claims, test results, and audit history

## Trust boundaries

1. Browser or API client to the API.
2. API process to PostgreSQL.
3. API/queue to the isolated worker.
4. Worker to the untrusted execution sandbox.
5. Repository content and build scripts to analysis tools and any future LLM.

## Threats and planned controls

| Threat | Planned control |
|---|---|
| Infinite loop, fork bomb, memory bomb, or huge output | Worker wall-clock timeout, CPU/memory/PID/output limits, cancellation |
| Code reads host files or secrets | Separate worker; non-root container; read-only root filesystem; temporary workdir; no secrets mounted |
| Code writes outside the intended scratch directory | No host bind mounts; source copied into a bounded tmpfs; container root filesystem is read-only |
| Network exfiltration or dependency download during execution | Network disabled for test execution; dependency preparation handled separately and narrowly |
| Build scripts execute arbitrary commands | Build only inside the sandbox, never in the API process |
| Malicious repository instructions affect an LLM | Treat repository content as data; patch scope guard; schema-validated model output |
| Duplicate queue delivery creates duplicate reports | Idempotency key, unique constraint, deterministic input hash, idempotent worker design |
| Fabricated or overconfident UI claim | Evidence type, categorical confidence, provenance, executed-only verification rule |

## Residual risk and limits

Containers share a host kernel and are not a complete security boundary. The worker talks to the local Docker daemon, so a compromised worker could control that daemon; keep it local and trusted. Docker execution has not been run in this workspace because Docker Desktop/CLI is unavailable. Phase 2 has no public submission or authentication. A public execution service requires a separately isolated worker host, stronger isolation review, and abuse controls before launch. Resource limits and seccomp support depend on the runtime and operating system and must be verified in the actual deployment environment.

The executable runtime checks are in `services/worker/tests/test_sandbox_integration.py`. The GitHub Actions sandbox job pulls both prebuilt images and runs them on a Linux runner. To repeat locally, install Docker Desktop with Linux containers and preload both images from the run instructions, then execute `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_sandbox_integration.py -q` from the repository root. They verify an outbound network attempt fails, root filesystem writes are denied, wall-clock termination, output truncation, observed cgroup memory/process limits, a Java JDK-container smoke run, and Java benchmark strategy reporting. Pytest skips each language's checks when its daemon or image is unavailable; a skipped run is not a security verification.

