from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            decoded = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500] if isinstance(exc, HTTPError) else str(exc)
        raise RuntimeError(f"API request {path} failed: {detail}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"API request {path} returned an unexpected response")
    return decoded


def wait_for_report(base_url: str, job_id: str, timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = request_json(base_url, f"/v1/jobs/{job_id}")
        if job.get("status") in {"completed", "failed", "cancelled"}:
            if job.get("status") != "completed":
                raise RuntimeError(
                    f"Job {job_id[:8]} ended {job.get('status')}: "
                    f"{job.get('error_code') or job.get('progress_message') or 'no details'}"
                )
            report = request_json(base_url, f"/v1/jobs/{job_id}/result")
            return job, report
        time.sleep(0.25)
    raise RuntimeError(f"Job {job_id[:8]} did not finish within {timeout_seconds} seconds")


def submit_and_wait(
    base_url: str,
    language: str,
    code: str,
    problem: dict[str, Any],
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    route = "java-function" if language == "java" else "python-function"
    job = request_json(
        base_url,
        f"/v1/jobs/mode1/{route}",
        {"language": language, "code": code, "problem": problem},
    )
    job_id = job.get("id")
    if not isinstance(job_id, str):
        raise RuntimeError("Job submission did not return a job ID")
    return wait_for_report(base_url, job_id, timeout_seconds)


def assert_one_passed(report: dict[str, Any], label: str) -> None:
    tests = report.get("tests", {})
    if tests.get("total") != 1 or tests.get("passed") != 1 or tests.get("failed") != 0:
        raise RuntimeError(f"{label} did not pass its declared sample: {tests}")


def run_demo(base_url: str, timeout_seconds: int) -> list[str]:
    outcomes: list[str] = []

    ambiguous = request_json(
        base_url,
        "/v1/problem-specs/match",
        {
            "statement": (
                "Given an integer array nums and a target value, find the maximum length of a "
                "contiguous subarray whose sum equals the target. Return the length of that subarray."
            )
        },
    )
    if ambiguous.get("match_state") != "ambiguous" or ambiguous.get("recognized") is not False:
        raise RuntimeError(f"Ambiguous match was not rejected: {ambiguous}")
    if len(ambiguous.get("candidate_titles", [])) < 2:
        raise RuntimeError("Ambiguous match response did not include multiple candidate titles")
    outcomes.append("Ambiguous problem match: rejected with candidate titles")

    base_problem = {
        "statement": "Return the input integer plus one.",
        "interface": {"kind": "function", "entrypoint": "solve"},
        "constraints": [],
        "samples": [{"kind": "function", "name": "demo", "args": [2], "kwargs": {}, "expected": 3}],
    }
    _, python_report = submit_and_wait(
        base_url, "python", "def solve(value):\n    return value + 1\n", base_problem, timeout_seconds
    )
    assert_one_passed(python_report, "Python smoke case")
    outcomes.append("Python function: sample passed")

    java_problem = {
        **base_problem,
        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
    }
    java_code = "class Solution { public int solve(int value) { return value + 1; } }"
    _, java_report = submit_and_wait(base_url, "java", java_code, java_problem, timeout_seconds)
    assert_one_passed(java_report, "Java smoke case")
    outcomes.append("Java function: sample passed")

    compile_code = "class Solution { public int solve(int value) { return value + ; } }"
    _, compile_report = submit_and_wait(
        base_url, "java", compile_code, java_problem, timeout_seconds
    )
    compile_cases = compile_report.get("test_cases", [])
    if not compile_cases or not any(
        case.get("details", {}).get("failure_kind") == "compile_error" for case in compile_cases
    ):
        raise RuntimeError("Java compile failure was not reported as compile_error")
    outcomes.append("Java compiler failure: distinguished from runtime/test failure")

    timeout_code = "def solve(value):\n    while True:\n        pass\n"
    timeout_job, timeout_report = submit_and_wait(
        base_url, "python", timeout_code, base_problem, timeout_seconds
    )
    timeout_cases = timeout_report.get("test_cases", [])
    if not timeout_cases or not all(
        case.get("details", {}).get("failure_kind") == "timeout"
        and case.get("outcome") == "skipped"
        for case in timeout_cases
    ):
        raise RuntimeError("Timed-out harness outcomes were not marked as skipped/timeout")
    if "timed out" not in str(timeout_job.get("progress_message", "")).casefold():
        raise RuntimeError("Timed-out run did not expose its timeout state in job status")
    outcomes.append("Python timeout: unobserved cases marked skipped with timeout evidence")

    inconclusive_problem = {
        **base_problem,
        "samples": [{"kind": "function", "name": "demo", "args": [3], "kwargs": {}, "expected": 3}],
    }
    inconclusive_code = (
        "def solve(value):\n"
        "    index = 0\n"
        "    while index < value:\n"
        "        index += 1\n"
        "    return index\n"
    )
    _, inconclusive_report = submit_and_wait(
        base_url, "python", inconclusive_code, inconclusive_problem, timeout_seconds
    )
    complexity = inconclusive_report.get("complexity") or {}
    if not str(complexity.get("estimate", "")).startswith("unknown"):
        raise RuntimeError(f"Expected an inconclusive complexity result, got {complexity}")
    outcomes.append("Complexity analysis: unsupported loop bound reported as inconclusive")
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Axioma's deterministic local Mode 1 release-candidate demo."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("AXIOMA_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the local Axioma API",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.timeout_seconds < 10:
        parser.error("--timeout-seconds must be at least 10")
    try:
        for outcome in run_demo(args.base_url, args.timeout_seconds):
            print(f"PASS  {outcome}")
    except RuntimeError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1
    print("All six Mode 1 release-demo scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
