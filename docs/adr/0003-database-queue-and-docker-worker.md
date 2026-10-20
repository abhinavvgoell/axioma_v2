# ADR 0003: Use PostgreSQL leases and a separate Docker worker

- Status: accepted
- Date: 2026-10-20

## Context

The project needs durable asynchronous jobs and must never execute submitted source in the API process. The available time and budget favor a small local architecture before introducing a broker.

## Decision

The worker claims queued jobs in a database transaction using row locks with `SKIP LOCKED`, records a 3-minute lease, and emits job events. A lease reaper retries one expired job and then marks it failed. The worker starts isolated, disposable Docker containers with network disabled and hard resource limits. Runtime images are prepared before jobs are accepted; the worker never pulls an image for a submission.

## Consequences

- The API and executor run as separate processes and share durable PostgreSQL state.
- The database is the initial queue; Redis/Celery remain optional until measured need appears.
- Worker leases recover jobs after process failure, but multi-worker behavior still needs PostgreSQL integration testing.
- Access to the Docker daemon is highly privileged; the worker must remain trusted and separate from public API deployments.
- Local SQLite supports development tests but does not exercise PostgreSQL row-lock semantics.

