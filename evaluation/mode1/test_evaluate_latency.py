"""Tests for database-backed Mode 1 latency summaries."""

import sqlite3

from evaluation.mode1.evaluate_latency import extract_records, score


def _database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, language TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE job_events (
                id INTEGER PRIMARY KEY, job_id TEXT, status TEXT, created_at TEXT
            );
            """
        )
        connection.executemany(
            "INSERT INTO jobs VALUES (?, ?, ?, ?)",
            [
                ("ok-1", "python", "completed", "2026-01-01T00:00:00+00:00"),
                ("ok-2", "python", "completed", "2026-01-01T00:01:00+00:00"),
                ("failed", "java", "failed", "2026-01-01T00:02:00+00:00"),
                ("requeued", "python", "completed", "2026-01-01T00:03:00+00:00"),
                ("bad-time", "python", "completed", "2026-01-01T00:04:00+00:00"),
            ],
        )
        connection.executemany(
            "INSERT INTO job_events VALUES (?, ?, ?, ?)",
            [
                (1, "ok-1", "running", "2026-01-01T00:00:01+00:00"),
                (2, "ok-1", "completed", "2026-01-01T00:00:04+00:00"),
                (3, "ok-2", "running", "2026-01-01T00:01:02+00:00"),
                (4, "ok-2", "completed", "2026-01-01T00:01:12+00:00"),
                (5, "failed", "running", "2026-01-01T00:02:01+00:00"),
                (6, "failed", "failed", "2026-01-01T00:02:02+00:00"),
                (7, "requeued", "running", "2026-01-01T00:03:01+00:00"),
                (8, "requeued", "queued", "2026-01-01T00:03:02+00:00"),
                (9, "requeued", "running", "2026-01-01T00:03:04+00:00"),
                (10, "requeued", "completed", "2026-01-01T00:03:07+00:00"),
                (11, "bad-time", "running", "2026-01-01T00:04:01+00:00"),
                (12, "bad-time", "completed", "2026-01-01T00:04:00+00:00"),
                # Stale terminal records must not override the job's current state.
                (13, "failed", "completed", "2026-01-01T00:02:03+00:00"),
            ],
        )


def test_extracts_current_terminal_and_retry_timing(tmp_path):
    database = tmp_path / "latency.sqlite"
    _database(database)

    records = extract_records(f"sqlite:///{database.as_posix()}")
    by_id = {record["id"]: record for record in records}

    assert by_id["requeued"]["first_started_at"] == "2026-01-01T00:03:01+00:00"
    assert by_id["requeued"]["last_started_at"] == "2026-01-01T00:03:04+00:00"
    assert by_id["requeued"]["terminal_at"] == "2026-01-01T00:03:07+00:00"
    assert by_id["failed"]["terminal_at"] == "2026-01-01T00:02:02+00:00"


def test_scores_success_latency_and_excludes_non_completed_or_invalid_rows(tmp_path):
    database = tmp_path / "latency.sqlite"
    _database(database)

    report = score(extract_records(f"sqlite:///{database.as_posix()}"))

    assert report["jobs_seen"] == 5
    assert report["job_status_counts"] == {"completed": 4, "failed": 1}
    assert report["completed_jobs_with_valid_timing"] == 3
    assert report["completed_jobs_excluded_for_missing_or_invalid_timing"] == 1
    python = report["by_language"]["python"]
    assert python["queue_to_first_start"] == {
        "n": 3, "p50_ms": 1000.0, "p95_ms": 2000.0, "min_ms": 1000.0, "max_ms": 2000.0
    }
    assert python["last_worker_lifecycle"]["p50_ms"] == 3000.0
    assert python["end_to_end"]["p50_ms"] == 7000.0
    assert report["source_sha256"]


def test_percentiles_use_nearest_rank_for_small_samples():
    summary = score([
        {
            "id": str(index), "language": "java", "status": "completed",
            "submitted_at": f"2026-01-01T00:00:0{index}+00:00",
            "first_started_at": f"2026-01-01T00:00:0{index}+00:00",
            "last_started_at": f"2026-01-01T00:00:0{index}+00:00",
            "terminal_at": f"2026-01-01T00:00:0{index + 1}+00:00",
        }
        for index in range(1, 4)
    ])
    assert summary["by_language"]["java"]["end_to_end"]["p50_ms"] == 1000.0
    assert summary["by_language"]["java"]["end_to_end"]["p95_ms"] == 1000.0

