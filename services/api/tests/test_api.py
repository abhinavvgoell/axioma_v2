from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axioma_api.database import get_session
from axioma_api.database import get_session_factory
from axioma_api.main import app
from axioma_api.models import (
    Base,
    ComplexityRecord,
    EvidenceClaimRecord,
    Job,
    TestCaseRecord as CaseRow,
    VerificationGateRecord,
)


@pytest.fixture
def test_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(test_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: test_session_factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_job_submission_is_idempotent_and_cancellation_is_streamable(
    client: TestClient,
) -> None:
    body = {"mode": "dsa_analysis", "language": "python", "input": {"code": "pass"}}
    first = client.post("/v1/jobs", json=body, headers={"Idempotency-Key": "request-1"})
    second = client.post("/v1/jobs", json=body, headers={"Idempotency-Key": "request-1"})
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    conflict = client.post(
        "/v1/jobs",
        json={"mode": "dsa_analysis", "language": "java", "input": {"code": "pass"}},
        headers={"Idempotency-Key": "request-1"},
    )
    assert conflict.status_code == 409

    job_id = first.json()["id"]
    cancelled = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    stream = client.get(f"/v1/jobs/{job_id}/events")
    assert "event: job_status" in stream.text
    assert '"status":"cancelled"' in stream.text


def test_report_counts_come_from_test_case_rows_and_gates_are_ordered(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
) -> None:
    response = client.post(
        "/v1/jobs",
        json={"mode": "repository_review", "language": "java", "input": {"commit": "abc123"}},
    )
    job_id = response.json()["id"]
    with test_session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.status = "completed"
        session.add_all(
            [
                EvidenceClaimRecord(
                    id="claim-1",
                    job_id=job_id,
                    evidence_type="executed",
                    confidence="high",
                    summary="14 of 15 tests passed",
                    provenance={"tool": "pytest"},
                    artifact_ids=[],
                ),
                CaseRow(id="test-1", job_id=job_id, name="example", outcome="passed", details={"origin": "catalog_sample", "stdout": "x" * 5000}),
                CaseRow(id="test-2", job_id=job_id, name="generated_1", outcome="failed", details={"failure_kind": "incorrect_output", "expected": 3, "actual": 2}),
                CaseRow(id="test-3", job_id=job_id, name="property/example", outcome="skipped", details={"reason": "property did not run"}),
                ComplexityRecord(
                    job_id=job_id,
                    method="static_loop_analysis",
                    estimate="O(n)",
                    confidence="medium",
                    methods_disagree=True,
                    details={"measurement_method": "executed_source_line_events", "points": []},
                ),
                VerificationGateRecord(
                    id="gate-2",
                    job_id=job_id,
                    gate_order=2,
                    name="tests_pass",
                    state="not_run",
                    evidence_claim_ids=[],
                ),
                VerificationGateRecord(
                    id="gate-1",
                    job_id=job_id,
                    gate_order=0,
                    name="patch_applies",
                    state="passed",
                    evidence_claim_ids=[],
                ),
            ]
        )
        session.commit()

    result = client.get(f"/v1/jobs/{job_id}/result").json()
    assert result["tests"] == {"total": 3, "passed": 1, "failed": 1, "skipped": 1}
    assert result["complexity"]["methods_disagree"] is True
    assert result["complexity"]["details"]["measurement_method"] == "executed_source_line_events"
    assert [gate["order"] for gate in result["verification_gates"]] == [0, 2]
    assert result["claims"][0]["type"] == "executed"
    assert [case["origin"] for case in result["test_cases"]] == [
        "catalog_sample", "generated_differential", "property_check"
    ]
    assert result["test_cases"][1]["details"]["failure_kind"] == "incorrect_output"
    assert result["test_cases"][0]["details"]["truncated"] is True


def test_problem_spec_validation_checks_function_samples(client: TestClient) -> None:
    response = client.post(
        "/v1/problem-specs/validate",
        json={
            "statement": "Return the sum.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [
                {"path": "args[0]", "minimum": 1, "maximum": 10},
                {"path": "kwargs.limit", "maximum": 5},
                {"path": "args.length", "minimum": 1},
            ],
            "samples": [
                {
                    "kind": "function",
                    "name": "valid",
                    "args": [7],
                    "kwargs": {"limit": 3},
                    "expected": 10,
                },
                {
                    "kind": "function",
                    "name": "invalid",
                    "args": [12],
                    "kwargs": {"limit": 8},
                    "expected": 20,
                },
            ],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is False
    assert result["samples_checked"] == 2
    assert [(issue["sample"], issue["path"]) for issue in result["issues"]] == [
        ("invalid", "args[0]"),
        ("invalid", "kwargs.limit"),
    ]


def test_stdin_constraints_can_check_input_length(client: TestClient) -> None:
    response = client.post(
        "/v1/problem-specs/validate",
        json={
            "statement": "Read one token.",
            "interface": {"kind": "stdin_stdout"},
            "constraints": [{"path": "stdin.length", "maximum": 8}],
            "samples": [
                {
                    "kind": "stdin_stdout",
                    "name": "too_long",
                    "stdin": "123456789",
                    "expected_stdout": "ok",
                }
            ],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is False
    assert result["issues"][0]["message"] == "sample value 9 exceeds maximum 8"


def test_python_function_job_submission_requires_valid_samples(client: TestClient) -> None:
    payload = {
        "language": "python",
        "code": "def solve(value): return value * 2",
        "problem": {
            "statement": "Double the input.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [{"path": "args[0]", "minimum": 1, "maximum": 5}],
            "samples": [{"kind": "function", "name": "small", "args": [2], "expected": 4}],
        },
    }
    response = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    payload["problem"]["samples"][0]["args"] = [9]
    invalid = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert invalid.status_code == 422


def test_python_complexity_benchmarks_require_three_increasing_sizes(client: TestClient) -> None:
    payload = {
        "language": "python",
        "code": "def solve(value): return value",
        "complexity_benchmarks": [
            {"size": size, "args": [size], "kwargs": {}} for size in (8, 16, 32, 64)
        ],
        "problem": {
            "statement": "Return the input.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "samples": [{"kind": "function", "name": "small", "args": [2], "expected": 2}],
        },
    }
    valid = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert valid.status_code == 202

    payload["complexity_benchmarks"] = payload["complexity_benchmarks"][:3]
    invalid = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert invalid.status_code == 422


def test_stdin_stdout_job_submission_accepts_python_and_java(client: TestClient) -> None:
    base_payload = {
        "code": "class Main {}",
        "problem": {
            "statement": "Echo the input.",
            "interface": {"kind": "stdin_stdout"},
            "samples": [
                {
                    "kind": "stdin_stdout",
                    "name": "echo",
                    "stdin": "hello\n",
                    "expected_stdout": "hello\n",
                }
            ],
        },
    }
    for language in ("python", "java"):
        response = client.post(
            "/v1/jobs/mode1/stdin-stdout", json={**base_payload, "language": language}
        )
        assert response.status_code == 202
        assert response.json()["language"] == language


def test_java_function_job_requires_a_class_method_entrypoint(client: TestClient) -> None:
    payload = {
        "language": "java",
        "code": "class Solution {}",
        "problem": {
            "statement": "Add values.",
            "interface": {"kind": "function", "entrypoint": "Solution.add"},
            "samples": [{"kind": "function", "name": "sum", "args": [1, 2], "expected": 3}],
        },
    }
    response = client.post("/v1/jobs/mode1/java-function", json=payload)
    assert response.status_code == 202
    assert response.json()["language"] == "java"


def test_java_function_jobs_accept_a_reference_and_generated_test_count(
    client: TestClient,
) -> None:
    payload = {
        "language": "java",
        "code": "class Solution { int solve(int value) { return value * 2; } }",
        "reference_code": "class Reference { int solve(int value) { return value * 2; } }",
        "generated_tests": 5,
        "seed": 17,
        "problem": {
            "statement": "Double an integer.",
            "interface": {"kind": "function", "entrypoint": "Solution.solve"},
            "constraints": [{"path": "args[0]", "minimum": 0, "maximum": 10}],
            "samples": [{"kind": "function", "name": "example", "args": [2], "expected": 4}],
        },
    }

    response = client.post("/v1/jobs/mode1/java-function", json=payload)

    assert response.status_code == 202
    job = client.get(f"/v1/jobs/{response.json()['id']}")
    assert job.status_code == 200


def test_java_function_jobs_accept_reference_mutation_testing(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/java-function",
        json={
            "language": "java",
            "code": "class Solution { int solve(int value) { return value + 1; } }",
            "reference_code": "class Reference { int solve(int value) { return value + 1; } }",
            "mutation_tests": 3,
            "problem": {
                "statement": "Add one.",
                "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                "samples": [
                    {"kind": "function", "name": "sample", "args": [2], "expected": 3}
                ],
            },
        },
    )

    assert response.status_code == 202
    queued_job = client.get(f"/v1/jobs/{response.json()['id']}")
    assert queued_job.status_code == 200
    assert queued_job.json()["status"] == "queued"


def test_function_jobs_accept_an_independent_reference(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(value): return value * 2",
            "reference_code": "def solve(value): return value * 2",
            "independent_reference_code": "def solve(value): return value + value",
            "problem": {
                "statement": "Double an integer.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "samples": [
                    {"kind": "function", "name": "example", "args": [2], "expected": 4}
                ],
            },
        },
    )

    assert response.status_code == 202


def test_independent_reference_requires_a_primary_reference(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(value): return value",
            "independent_reference_code": "def solve(value): return value",
            "problem": {
                "statement": "Return an integer.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "samples": [
                    {"kind": "function", "name": "example", "args": [2], "expected": 2}
                ],
            },
        },
    )

    assert response.status_code == 422


def test_java_reference_class_must_not_collide_with_submission_class(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/jobs/mode1/java-function",
        json={
            "language": "java",
            "code": "class Reference { int solve(int value) { return value; } }",
            "reference_code": "class Reference { int solve(int value) { return value; } }",
            "problem": {
                "statement": "Return the value.",
                "interface": {"kind": "function", "entrypoint": "Reference.solve"},
                "samples": [{"kind": "function", "name": "example", "args": [1], "expected": 1}],
            },
        },
    )

    assert response.status_code == 422


def test_generated_differential_jobs_require_a_reference_solution(client: TestClient) -> None:
    payload = {
        "language": "python",
        "code": "def solve(value): return value * 2",
        "generated_tests": 5,
        "problem": {
            "statement": "Double one number.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [{"path": "args[0]", "minimum": 1, "maximum": 10}],
            "samples": [{"kind": "function", "name": "sample", "args": [2], "expected": 4}],
        },
    }
    response = client.post("/v1/jobs/mode1/python-function", json=payload)

    assert response.status_code == 422


def test_python_job_accepts_exhaustive_small_scalar_differential_checks(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(left, right): return left + right",
            "reference_code": "def solve(left, right): return left + right",
            "exhaustive_tests": True,
            "problem": {
                "statement": "Add two small integers.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "constraints": [
                    {"path": "args[0]", "minimum": -2, "maximum": 2},
                    {"path": "args[1]", "minimum": 0, "maximum": 1},
                ],
                "samples": [
                    {"kind": "function", "name": "example", "args": [1, 1], "expected": 2}
                ],
            },
        },
    )

    assert response.status_code == 202


def test_java_job_accepts_exhaustive_small_scalar_differential_checks(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/jobs/mode1/java-function",
        json={
            "language": "java",
            "code": "class Solution { int solve(int value) { return value * 2; } }",
            "reference_code": "class Reference { int solve(int value) { return value * 2; } }",
            "exhaustive_tests": True,
            "problem": {
                "statement": "Double a small integer.",
                "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                "constraints": [{"path": "args[0]", "minimum": -1, "maximum": 1}],
                "samples": [
                    {"kind": "function", "name": "example", "args": [1], "expected": 2}
                ],
            },
        },
    )

    assert response.status_code == 202


def test_exhaustive_checks_reject_domains_above_the_case_cap(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(left, right): return left + right",
            "reference_code": "def solve(left, right): return left + right",
            "exhaustive_tests": True,
            "problem": {
                "statement": "Add two integers.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "constraints": [
                    {"path": "args[0]", "minimum": -100, "maximum": 100},
                    {"path": "args[1]", "minimum": 0, "maximum": 1},
                ],
                "samples": [
                    {"kind": "function", "name": "example", "args": [0, 0], "expected": 0}
                ],
            },
        },
    )

    assert response.status_code == 422
    assert "maximum is 256" in response.text


def test_mutation_testing_requires_a_python_reference_solution(client: TestClient) -> None:
    payload = {
        "language": "python",
        "code": "def solve(value): return value + 1",
        "mutation_tests": 4,
        "problem": {
            "statement": "Add one.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "samples": [{"kind": "function", "name": "sample", "args": [2], "expected": 3}],
        },
    }
    missing_reference = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert missing_reference.status_code == 422

    payload["reference_code"] = "def solve(value): return value + 1"
    accepted = client.post("/v1/jobs/mode1/python-function", json=payload)
    assert accepted.status_code == 202


def test_python_function_job_accepts_an_optimization_candidate(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(values): return sum(values)",
            "optimization_code": "def solve(values): return max(values) + min(values)",
            "optimization_notes": "Try a built-in reduction.",
            "problem": {
                "statement": "Return a value.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "samples": [
                    {"kind": "function", "name": "example", "args": [[1, 2]], "expected": 3}
                ],
            },
        },
    )

    assert response.status_code == 202


def test_java_function_job_accepts_an_optimization_and_benchmark_inputs(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/jobs/mode1/java-function",
        json={
            "language": "java",
            "code": "class Solution { int solve(int value) { return value; } }",
            "optimization_code": "class AxiomaOptimized { int solve(int value) { return value; } }",
            "complexity_benchmarks": [
                {"size": size, "args": [size]} for size in (10, 20, 40, 80)
            ],
            "problem": {
                "statement": "Return a value.",
                "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                "samples": [{"kind": "function", "name": "example", "args": [1], "expected": 1}],
            },
        },
    )

    assert response.status_code == 202


def test_python_function_job_accepts_a_user_supplied_property_checker(client: TestClient) -> None:
    payload = {
        "language": "python",
        "code": "def solve(value): return value * 2",
        "property_code": "def check(args, kwargs, result): return result == args[0] * 2",
        "property_tests": 5,
        "seed": 11,
        "problem": {
            "statement": "Double an integer.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [{"path": "args[0]", "minimum": 0, "maximum": 20}],
            "samples": [{"kind": "function", "name": "example", "args": [2], "expected": 4}],
        },
    }

    response = client.post("/v1/jobs/mode1/python-function", json=payload)

    assert response.status_code == 202


def test_java_function_job_accepts_a_separate_property_class(client: TestClient) -> None:
    response = client.post(
        "/v1/jobs/mode1/java-function",
        json={
            "language": "java",
            "code": "class Solution { int solve(int value) { return value * 2; } }",
            "property_code": (
                "class AxiomaProperties { static boolean check(Object[] args, Object result) "
                "{ return result.equals(((Number) args[0]).intValue() * 2); } }"
            ),
            "property_tests": 3,
            "problem": {
                "statement": "Double a value.",
                "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                "samples": [{"kind": "function", "name": "example", "args": [2], "expected": 4}],
            },
        },
    )

    assert response.status_code == 202


def test_generated_inputs_are_seeded_and_obey_numeric_and_length_constraints(
    client: TestClient,
) -> None:
    payload = {
        "problem": {
            "statement": "Work with a bounded list.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [
                {"path": "args[0].length", "minimum": 2, "maximum": 6},
                {"path": "args[0][0]", "minimum": -5, "maximum": 5},
            ],
            "samples": [
                {
                    "kind": "function",
                    "name": "base",
                    "args": [[1, 2]],
                    "expected": 3,
                }
            ],
        },
        "count": 11,
        "seed": 1234,
    }
    first = client.post("/v1/problem-specs/generate-inputs", json=payload)
    second = client.post("/v1/problem-specs/generate-inputs", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    assert result["generated"] == 11
    assert all(2 <= len(case["args"][0]) <= 6 for case in result["cases"])
    assert all(-5 <= case["args"][0][0] <= 5 for case in result["cases"])
    assert {case["strategy"] for case in result["cases"]} >= {
        "boundary_minimum_1",
        "boundary_minimum_adjacent_1",
        "boundary_maximum_1",
        "boundary_maximum_adjacent_1",
        "boundary_minimum_2",
        "boundary_maximum_2",
        "boundary_zero_2",
    }
    assert any(len(case["args"][0]) == 2 for case in result["cases"])
    assert any(len(case["args"][0]) == 6 for case in result["cases"])
    assert {case["args"][0][0] for case in result["cases"]} >= {-5, 0, 5}


def test_generated_inputs_include_adversarial_numeric_array_patterns(
    client: TestClient,
) -> None:
    payload = {
        "problem": {
            "statement": "Process a bounded numeric list.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [{"path": "args[0].length", "minimum": 3, "maximum": 5}],
            "samples": [
                {
                    "kind": "function",
                    "name": "base",
                    "args": [[3, 1, 2]],
                    "expected": 3,
                }
            ],
        },
        "count": 10,
        "seed": 7,
    }

    response = client.post("/v1/problem-specs/generate-inputs", json=payload)

    assert response.status_code == 200
    cases = response.json()["cases"]
    adversarial = {case["strategy"]: case["args"][0] for case in cases}
    ascending = adversarial["adversarial_ascending_1"]
    descending = adversarial["adversarial_descending_1"]
    all_equal = adversarial["adversarial_all_equal_1"]
    assert ascending == sorted(ascending)
    assert descending == sorted(descending, reverse=True)
    assert len(set(all_equal)) == 1
    assert any(strategy.startswith("adversarial_duplicate_heavy") for strategy in adversarial)
    assert any(strategy.startswith("adversarial_alternating_low_high") for strategy in adversarial)
    assert any(strategy.startswith("adversarial_nearly_sorted") for strategy in adversarial)
    for strategy, values in adversarial.items():
        if strategy.startswith("adversarial_duplicate_heavy"):
            assert len(set(values)) <= 2
        elif strategy.startswith("adversarial_alternating_low_high"):
            assert values[0] == min(values) and values[1] == max(values)
        elif strategy.startswith("adversarial_nearly_sorted"):
            assert sum(left > right for left, right in zip(values, values[1:])) == 1
    assert all(3 <= len(case["args"][0]) <= 5 for case in cases)


def test_complexity_benchmark_generator_returns_copyable_patterned_inputs(
    client: TestClient,
) -> None:
    payload = {
        "problem": {
            "statement": "Sort or search a bounded numeric list.",
            "interface": {"kind": "function", "entrypoint": "solve"},
            "constraints": [{"path": "args[0].length", "minimum": 2, "maximum": 32}],
            "samples": [
                {"kind": "function", "name": "base", "args": [[3, 1, 2]], "expected": 6}
            ],
        },
        "size_path": "args[0].length",
        "sizes": [4, 8, 16, 32],
        "pattern": "descending",
        "seed": 7,
    }

    first = client.post("/v1/problem-specs/generate-complexity-benchmarks", json=payload)
    second = client.post("/v1/problem-specs/generate-complexity-benchmarks", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    result = first.json()
    assert result["pattern"] == "descending"
    benchmarks = result["benchmarks"]
    assert all(item["strategy"] == "descending" for item in benchmarks)
    assert [item["size"] for item in benchmarks] == [4, 8, 16, 32]
    assert all(len(item["args"][0]) == item["size"] for item in benchmarks)
    assert all(item["args"][0] == sorted(item["args"][0], reverse=True) for item in benchmarks)
    assert "does not prove a worst case" in " ".join(result["limitations"])
    accepted = client.post(
        "/v1/jobs/mode1/python-function",
        json={
            "language": "python",
            "code": "def solve(values): return sum(values)",
            "problem": payload["problem"],
            "complexity_benchmarks": benchmarks,
        },
    )
    assert accepted.status_code == 202


def test_complexity_benchmark_generator_rejects_unsupported_sample_pattern(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/problem-specs/generate-complexity-benchmarks",
        json={
            "problem": {
                "statement": "Return a numeric list.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "constraints": [{"path": "args[0].length", "minimum": 2, "maximum": 10}],
                "samples": [
                    {"kind": "function", "name": "base", "args": [[1, 1, 1]], "expected": [1, 1, 1]}
                ],
            },
            "size_path": "args[0].length",
            "sizes": [2, 3, 4, 5],
            "pattern": "nearly_sorted",
        },
    )

    assert response.status_code == 422
    assert "could not generate the nearly_sorted pattern" in response.json()["detail"]


def test_complexity_benchmark_generator_supports_repeated_character_strings(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/problem-specs/generate-complexity-benchmarks",
        json={
            "problem": {
                "statement": "Return the longest substring without repeating characters.",
                "interface": {"kind": "function", "entrypoint": "Solution.lengthOfLongestSubstring"},
                "constraints": [{"path": "args[0].length", "minimum": 0, "maximum": 16}],
                "samples": [
                    {
                        "kind": "function",
                        "name": "base",
                        "args": ["abcabcbb"],
                        "expected": 3,
                    }
                ],
            },
            "size_path": "args[0].length",
            "sizes": [1, 4, 8, 16],
            "pattern": "repeated_characters",
            "seed": 0,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["pattern"] == "repeated_characters"
    assert [item["size"] for item in result["benchmarks"]] == [1, 4, 8, 16]
    assert [item["args"][0] for item in result["benchmarks"]] == ["a", "aaaa", "aaaaaaaa", "a" * 16]


def test_complexity_benchmark_scales_one_argument_and_preserves_other_inputs(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/problem-specs/generate-complexity-benchmarks",
        json={
            "problem": {
                "statement": "Check whether s2 contains a permutation of s1.",
                "interface": {"kind": "function", "entrypoint": "Solution.checkInclusion"},
                "constraints": [
                    {"path": "args[0].length", "minimum": 1, "maximum": 16},
                    {"path": "args[1].length", "minimum": 2, "maximum": 32},
                ],
                "samples": [
                    {
                        "kind": "function",
                        "name": "base",
                        "args": ["ab", "eidbaooo"],
                        "expected": True,
                    }
                ],
            },
            "size_path": "args[1].length",
            "sizes": [8, 16, 24, 32],
            "pattern": "repeated_characters",
            "seed": 0,
        },
    )

    assert response.status_code == 200, response.text
    benchmarks = response.json()["benchmarks"]
    assert [item["args"][0] for item in benchmarks] == ["ab"] * 4
    assert [item["args"][1] for item in benchmarks] == ["e" * size for size in (8, 16, 24, 32)]


def test_optimization_proposal_route_returns_static_unverified_candidate(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/optimization-proposals",
        json={
            "language": "python",
            "code": (
                "def solve(values):\n"
                "    total = 0\n"
                "    for value in values:\n"
                "        total += value\n"
                "    return total\n"
            ),
            "problem": {
                "statement": "Given an integer array, return its sum.",
                "interface": {"kind": "function", "entrypoint": "solve"},
                "constraints": [
                    {"path": "args[0].length", "minimum": 1, "maximum": 100}
                ],
                "samples": [
                    {
                        "kind": "function",
                        "name": "example",
                        "args": [[1, 2, 3]],
                        "kwargs": {},
                        "expected": 6,
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    proposal = response.json()["proposals"][0]
    assert proposal["evidence_type"] == "static"
    assert proposal["confidence"] == "low"
    assert "return sum(values)" in proposal["candidate_code"]
    assert "unverified" in response.json()["message"]


def test_optimization_proposals_reject_stdin_stdout_problems(client: TestClient) -> None:
    response = client.post(
        "/v1/optimization-proposals",
        json={
            "language": "python",
            "code": "print(1)",
            "problem": {
                "statement": "Print one.",
                "interface": {"kind": "stdin_stdout"},
                "samples": [
                    {"name": "example", "stdin": "", "expected_stdout": "1\n"}
                ],
            },
        },
    )

    assert response.status_code == 422
