"""Summarize Mode 1 job latency from the application database's status events."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("database contains a missing or invalid timestamp")
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def extract_records(database_url: str) -> list[dict[str, Any]]:
    """Read job/event timestamps only; source code and report payloads are not selected."""
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            jobs = connection.execute(text(
                "SELECT id, language, status, created_at FROM jobs ORDER BY created_at, id"
            )).mappings().all()
            events = connection.execute(text(
                "SELECT job_id, status, created_at, id FROM job_events ORDER BY job_id, id"
            )).mappings().all()
    except Exception as exc:
        raise ValueError(
            "could not read jobs and job_events from the configured database "
            f"({type(exc).__name__})"
        ) from exc
    finally:
        if "engine" in locals():
            engine.dispose()

    events_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_job[event["job_id"]].append(dict(event))

    records: list[dict[str, Any]] = []
    for job in jobs:
        timeline = events_by_job[job["id"]]
        terminal_events = [
            event for event in timeline
            if event["status"] == job["status"]
            and event["status"] in {"completed", "failed", "cancelled"}
        ]
        terminal = terminal_events[-1] if terminal_events else None
        running_events = [event for event in timeline if event["status"] == "running"]
        if terminal is not None:
            running_before_terminal = [
                event for event in running_events if event["id"] < terminal["id"]
            ]
        else:
            running_before_terminal = running_events
        records.append({
            "id": job["id"],
            "language": job["language"],
            "status": job["status"],
            "submitted_at": _timestamp(job["created_at"]).isoformat(),
            "first_started_at": (
                _timestamp(running_before_terminal[0]["created_at"]).isoformat()
                if running_before_terminal else None
            ),
            "last_started_at": (
                _timestamp(running_before_terminal[-1]["created_at"]).isoformat()
                if running_before_terminal else None
            ),
            "terminal_at": _timestamp(terminal["created_at"]).isoformat() if terminal else None,
        })
    return records


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def _duration_ms(start: str | None, end: str | None) -> float | None:
    if start is None or end is None:
        return None
    try:
        elapsed = (_timestamp(end) - _timestamp(start)).total_seconds() * 1000
    except (OverflowError, TypeError, ValueError):
        return None
    if elapsed < 0:
        return None
    return elapsed


def _distribution(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None,
    }


def score(records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(record["status"] for record in records)
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"queue_to_first_start": [], "last_worker_lifecycle": [], "end_to_end": []}
    )
    malformed_timing = 0
    for record in records:
        if record["status"] != "completed":
            continue
        queue = _duration_ms(record["submitted_at"], record["first_started_at"])
        worker = _duration_ms(record["last_started_at"], record["terminal_at"])
        total = _duration_ms(record["submitted_at"], record["terminal_at"])
        if queue is None or worker is None or total is None:
            malformed_timing += 1
            continue
        metrics = grouped[record["language"]]
        metrics["queue_to_first_start"].append(queue)
        metrics["last_worker_lifecycle"].append(worker)
        metrics["end_to_end"].append(total)

    by_language = {
        language: {metric: _distribution(values) for metric, values in sorted(metrics.items())}
        for language, metrics in sorted(grouped.items())
    }
    canonical_input = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "jobs_seen": len(records),
        "job_status_counts": dict(sorted(status_counts.items())),
        "completed_jobs_with_valid_timing": sum(
            len(counts["end_to_end"]) for counts in grouped.values()
        ),
        "completed_jobs_excluded_for_missing_or_invalid_timing": malformed_timing,
        "by_language": by_language,
        "percentile_method": "nearest-rank empirical percentile (ceil(p*n), one-based)",
        "source_sha256": hashlib.sha256(canonical_input).hexdigest(),
        "limitations": [
            "Only completed jobs with submitted, running, and terminal status events are included in latency distributions.",
            "End-to-end latency uses persisted wall-clock event timestamps and includes queueing and retries.",
            "Last worker lifecycle is the latest running-to-terminal span; it may include worker recovery time and is not CPU time.",
            "Percentiles are descriptive. Small samples, host load, and wall-clock adjustments can make p95 unstable.",
            "This summarizes observed local jobs; it is not a controlled load test or a public service SLO measurement.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "sqlite:///services/api/axioma.db"),
        help="SQLAlchemy URL (defaults to DATABASE_URL or the local SQLite database)",
    )
    parser.add_argument("--output", help="write the JSON report to this path")
    args = parser.parse_args()
    try:
        report = score(extract_records(args.database_url))
        report["evaluator_version"] = "0.1.0"
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as destination:
            destination.write(output)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
