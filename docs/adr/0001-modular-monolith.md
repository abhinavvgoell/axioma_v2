# ADR 0001: Start with a modular monolith and separate worker process

- Status: accepted
- Date: 2026-10-20

## Context

The project has a 16-week schedule with six hours available each week and no hosting budget. The API, database, and analysis worker need clear boundaries, while operating many distributed services would add setup and deployment cost.

## Decision

Use one FastAPI service and one separately runnable worker package in a monorepo. Keep PostgreSQL as the shared durable job/result store. Start the local development queue using persisted jobs and add a dedicated broker only if worker throughput or coordination needs justify it.

## Consequences

- The API and untrusted code execution remain separate trust domains.
- Local development can run with SQLite; PostgreSQL is the deployment target.
- A database-backed queue is simpler to explain and operate initially, but needs careful locking and leases before multiple workers are used.
- The design can add Redis/Celery later without changing report contracts.

