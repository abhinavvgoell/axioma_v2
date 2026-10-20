# ADR 0002: Use Server-Sent Events for job progress

- Status: accepted
- Date: 2026-10-20

## Context

The first UI only needs progress updates from server to browser. The client does not need a bidirectional live channel.

## Decision

Expose job progress as Server-Sent Events with persistent event IDs and `Last-Event-ID` reconnect support.

## Consequences

- Browser clients can use a straightforward event stream for a live status indicator.
- Events can be replayed from PostgreSQL after reconnect.
- If a future feature needs sustained bidirectional messaging, revisit WebSockets then.

