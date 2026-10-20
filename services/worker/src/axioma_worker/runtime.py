from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from axioma_api.contracts import (
    Confidence,
    ComplexityBenchmarkSample,
    EvidenceType,
    FunctionInterface,
    FunctionSample,
    JobStatus,
    ProblemInputGenerationRequest,
    ProblemSpec,
    StdinStdoutSample,
)
from axioma_api.jobs import transition_job
from axioma_api.models import ComplexityRecord, EvidenceClaimRecord, Job, TestCaseRecord
from axioma_api.problem_validation import validate_problem_spec
from axioma_api.problem_generation import generate_exhaustive_inputs, generate_problem_inputs
from axioma_api.queue import claim_next_job, reap_expired_jobs
from axioma_worker.adapters import get_adapter
from axioma_worker.java_harness import build_java_function_harness
from axioma_worker.java_mutation_testing import generate_java_mutants
from axioma_worker.python_complexity import (
    ComplexityEstimate,
    analyze_python_complexity,
    estimate_constraint_scale,
    triangulate_python_complexity,
)
from axioma_worker.java_complexity import (
    add_java_wall_time_fit,
    analyze_java_complexity,
    estimate_java_heap_pool_peak_growth,
)
from axioma_worker.python_complexity import estimate_python_peak_memory
from axioma_worker.mutation_testing import generate_mutants
from axioma_worker.python_harness import build_function_harness
from axioma_worker.sandbox import DockerSandbox, SandboxUnavailable


def is_cancelled(session_factory: sessionmaker, job_id: str) -> bool:
    with session_factory() as session:
        job = session.get(Job, job_id)
        return job is None or job.status == JobStatus.CANCELLED.value


def _stdin_execute_script(language: str) -> str:
    if language == "python":
        command = "python -I /work/main.py < /work/input.txt"
    elif language == "java":
        command = (
            "javac -d /work /work/Main.java > /tmp/stdout 2> /tmp/stderr; code=$?; "
            'if [ "$code" -eq 0 ]; then java -cp /work Main < /work/input.txt >> /tmp/stdout 2>> /tmp/stderr; code=$?; fi; '
            "printf '%s' \"$code\" > /tmp/exit-code; exit 0"
        )
        return f"umask 077; {command}"
    else:
        raise ValueError(f"Unsupported stdin/stdout language: {language}")
    return (
        f"umask 077; {command} > /tmp/stdout 2> /tmp/stderr; "
        "code=$?; printf '%s' \"$code\" > /tmp/exit-code; exit 0"
    )


def run_claimed_job(
    session_factory: sessionmaker,
    job_id: str,
    worker_id: str,
    sandbox: DockerSandbox,
) -> None:
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status != JobStatus.RUNNING.value or job.lease_owner != worker_id:
            return
        mode = job.mode
        language = job.language
        input_payload = dict(job.input_payload)
        input_hash = job.input_hash

    started = time.monotonic()
    sample_results: list[dict] | None = None
    complexity_report: dict = {}
    mutation_report: dict = {}
    optimization_report: dict = {}
    property_report: dict = {}
    generated_count_effective = 0
    problem: ProblemSpec | None = None
    try:
        if mode != "dsa_analysis":
            raise ValueError("Repository review execution is not available in this phase")
        if input_payload.get("code") is None:
            raise ValueError("This worker phase requires a single source file in input.code")
        if not isinstance(input_payload["code"], str):
            raise ValueError("input.code must be a string")
        adapter = get_adapter(language)
        if "problem" in input_payload:
            problem = ProblemSpec.model_validate(input_payload["problem"])
            if not validate_problem_spec(problem).valid:
                raise ValueError("Problem samples do not satisfy the declared constraints")
            requested_mutants = int(input_payload.get("mutation_tests", 0))
            generated_count = int(input_payload.get("generated_tests", 0))
            exhaustive_mode = input_payload.get("exhaustive_tests", False)
            if not isinstance(exhaustive_mode, bool):
                raise ValueError("exhaustive_tests must be a boolean")
            if requested_mutants < 0 or requested_mutants > 20:
                raise ValueError("mutation_tests must be between 0 and 20")
            if generated_count < 0 or generated_count > 50:
                raise ValueError("generated_tests must be between 0 and 50")
            if exhaustive_mode and generated_count:
                raise ValueError("exhaustive_tests cannot be combined with generated_tests")
            if exhaustive_mode and not input_payload.get("reference_code"):
                raise ValueError("exhaustive_tests requires a reference_code")
            optimization_code = input_payload.get("optimization_code")
            property_code = input_payload.get("property_code")
            property_count = int(input_payload.get("property_tests", 0))
            if property_count < 0 or property_count > 50:
                raise ValueError("property_tests must be between 0 and 50")
            if bool(property_code) != bool(property_count):
                raise ValueError("property_code and property_tests must be provided together")
            if input_payload.get("optimization_notes") and not optimization_code:
                raise ValueError("optimization_notes requires optimization_code")
            if optimization_code and not isinstance(problem.interface, FunctionInterface):
                raise ValueError("Optimization verification currently requires a function interface")
            if property_code and (not isinstance(problem.interface, FunctionInterface)):
                raise ValueError("Property checks currently require a function interface")
            if not isinstance(problem.interface, FunctionInterface) and (
                input_payload.get("reference_code") or generated_count or requested_mutants
            ):
                raise ValueError("Reference-guided checks require a function interface")
            if requested_mutants and not isinstance(problem.interface, FunctionInterface):
                raise ValueError("Mutation testing currently requires a function job")
            if isinstance(problem.interface, FunctionInterface):
                benchmark_samples = [
                    ComplexityBenchmarkSample.model_validate(item)
                    for item in input_payload.get("complexity_benchmarks", [])
                ]
                if benchmark_samples and (
                    len(benchmark_samples) < 4
                    or len(benchmark_samples) > 6
                    or [sample.size for sample in benchmark_samples]
                    != sorted({sample.size for sample in benchmark_samples})
                    or (
                        language == "java"
                        and any(sample.kwargs for sample in benchmark_samples)
                    )
                ):
                    raise ValueError(
                        "Complexity benchmarks require four to six increasing unique function sizes; Java currently supports positional arguments only"
                    )
                if any(not isinstance(sample, FunctionSample) for sample in problem.samples):
                    raise ValueError("Function interfaces require function-style samples")
                reference_code = input_payload.get("reference_code")
                independent_reference_code = input_payload.get("independent_reference_code")
                if requested_mutants and not reference_code:
                    raise ValueError("Mutation testing requires reference_code")
                if independent_reference_code and not reference_code:
                    raise ValueError("independent_reference_code requires reference_code")
                if independent_reference_code and independent_reference_code == reference_code:
                    raise ValueError("independent_reference_code must differ from reference_code")
                generated_samples: list[dict] = []
                if exhaustive_mode:
                    generated_samples = generate_exhaustive_inputs(problem)
                    generated_count = len(generated_samples)
                elif reference_code and generated_count:
                    generated_inputs = generate_problem_inputs(
                        ProblemInputGenerationRequest(
                            problem=problem,
                            count=generated_count,
                            seed=int(input_payload.get("seed", 0)),
                        )
                    )
                    generated_samples = [
                        case.model_dump(mode="json", exclude_none=True)
                        for case in generated_inputs.cases
                    ]
                    generated_count = len(generated_samples)
                generated_count_effective = generated_count
                if language == "python":
                    mutation_count = int(input_payload.get("mutation_tests", 0))
                    seed = int(input_payload.get("seed", 0))
                    if generated_count and not reference_code:
                        raise ValueError("Generated differential tests require reference_code")
                    if mutation_count and not reference_code:
                        raise ValueError("Mutation testing requires reference_code")
                    property_samples: list[dict] = []
                    if property_code and property_count:
                        property_inputs = generate_problem_inputs(
                            ProblemInputGenerationRequest(
                                problem=problem, count=property_count, seed=seed
                            )
                        )
                        property_samples = [
                            case.model_dump(mode="json", exclude_none=True)
                            for case in property_inputs.cases
                        ]
                    harness = build_function_harness(
                        problem.interface.entrypoint,
                        [sample.model_dump(mode="json") for sample in problem.samples],
                        reference_code=reference_code,
                        optimization_code=optimization_code,
                        property_code=property_code,
                        property_samples=property_samples,
                        requested_property_tests=property_count,
                        generated_samples=generated_samples,
                        requested_generated=generated_count,
                        complexity_benchmarks=[
                            sample.model_dump(mode="json") for sample in benchmark_samples
                        ],
                        mutations=[
                            {
                                "id": mutant.id,
                                "label": mutant.label,
                                "path": f"{mutant.id}.py",
                            }
                            for mutant in generate_mutants(reference_code or "", mutation_count)
                        ],
                        mutation_tests_requested=mutation_count,
                        independent_reference_code=independent_reference_code,
                    )
                    harness_files = {"main.py": harness.encode("utf-8")}
                    if reference_code:
                        harness_files["reference.py"] = reference_code.encode("utf-8")
                    if independent_reference_code:
                        harness_files["independent_reference.py"] = independent_reference_code.encode("utf-8")
                    if optimization_code:
                        harness_files["optimized.py"] = optimization_code.encode("utf-8")
                    if property_code:
                        harness_files["properties.py"] = property_code.encode("utf-8")
                    for mutant in generate_mutants(reference_code or "", mutation_count):
                        harness_files[f"{mutant.id}.py"] = mutant.code.encode("utf-8")
                    run_options = {
                        "source_filename": "submission.py",
                        "extra_files": harness_files,
                        "execute_script": "umask 077; python -I /work/main.py > /tmp/stdout 2> /tmp/stderr; code=$?; printf '%s' \"$code\" > /tmp/exit-code; exit 0",
                    }
                elif language == "java":
                    if "." not in problem.interface.entrypoint:
                        raise ValueError("Java function entrypoints must use ClassName.methodName")
                    class_name = problem.interface.entrypoint.split(".", maxsplit=1)[0]
                    if property_code and class_name == "AxiomaProperties":
                        raise ValueError(
                            "Java submission class name cannot be AxiomaProperties when using properties"
                        )
                    java_mutants = generate_java_mutants(
                        reference_code or "",
                        problem.interface.entrypoint.split(".", maxsplit=1)[1],
                        requested_mutants,
                    )
                    if optimization_code and class_name == "AxiomaOptimized":
                        raise ValueError(
                            "Java submission class name cannot be AxiomaOptimized when using an optimization"
                        )
                    property_samples: list[dict] = []
                    if property_code and property_count:
                        property_inputs = generate_problem_inputs(
                            ProblemInputGenerationRequest(
                                problem=problem,
                                count=property_count,
                                seed=int(input_payload.get("seed", 0)),
                            )
                        )
                        property_samples = [
                            case.model_dump(mode="json", exclude_none=True)
                            for case in property_inputs.cases
                        ]
                    harness = build_java_function_harness(
                        problem.interface.entrypoint,
                        [sample.model_dump(mode="json") for sample in problem.samples],
                        reference_samples=(
                            [sample.model_dump(mode="json") for sample in problem.samples]
                            if reference_code
                            else None
                        ),
                        generated_samples=generated_samples,
                        requested_generated=generated_count if reference_code else 0,
                        property_samples=property_samples,
                        requested_property_tests=property_count,
                        optimization_enabled=bool(optimization_code),
                        complexity_benchmarks=[
                            sample.model_dump(mode="json") for sample in benchmark_samples
                        ],
                        independent_reference_enabled=bool(independent_reference_code),
                        mutations=[
                            {
                                "id": mutant.id,
                                "label": mutant.label,
                                "class_name": mutant.class_name,
                            }
                            for mutant in java_mutants
                        ],
                        mutation_tests_requested=requested_mutants,
                    )
                    extra_files = {"Harness.java": harness.encode("utf-8")}
                    source_paths = [f"/work/{class_name}.java"]
                    if reference_code:
                        if class_name == "Reference":
                            raise ValueError(
                                "Java submission class name cannot be Reference when using a reference"
                            )
                        extra_files["Reference.java"] = reference_code.encode("utf-8")
                        source_paths.append("/work/Reference.java")
                    for mutant in java_mutants:
                        extra_files[f"{mutant.class_name}.java"] = mutant.code.encode("utf-8")
                    if independent_reference_code:
                        if class_name == "ReferenceIndependent":
                            raise ValueError(
                                "Java submission class name cannot be ReferenceIndependent when using an independent reference"
                            )
                        extra_files["ReferenceIndependent.java"] = independent_reference_code.encode("utf-8")
                        source_paths.append("/work/ReferenceIndependent.java")
                    if property_code:
                        extra_files["AxiomaProperties.java"] = property_code.encode("utf-8")
                        source_paths.append("/work/AxiomaProperties.java")
                    if optimization_code:
                        extra_files["AxiomaOptimized.java"] = optimization_code.encode("utf-8")
                        source_paths.append("/work/AxiomaOptimized.java")
                    source_paths.append("/work/Harness.java")
                    run_options = {
                        "source_filename": f"{class_name}.java",
                        "extra_files": extra_files,
                        "execute_script": (
                            f"umask 077; javac -d /work {' '.join(source_paths)} "
                            "> /tmp/stdout 2> /tmp/stderr; code=$?; "
                            'if [ "$code" -eq 0 ]; then java -cp /work Harness >> /tmp/stdout 2>> /tmp/stderr; code=$?; fi; '
                            "printf '%s' \"$code\" > /tmp/exit-code; exit 0"
                        ),
                    }
                else:
                    raise ValueError(f"Unsupported function language: {language}")
                result = sandbox.run(
                    adapter,
                    input_payload["code"],
                    cancellation_requested=lambda: is_cancelled(session_factory, job_id),
                    **run_options,
                )
                if not result.timed_out and result.exit_code == 0:
                    marker = "AXIOMA_RESULT:"
                    report_line = next(
                        line for line in result.stdout.splitlines() if line.startswith(marker)
                    )
                    sample_results = json.loads(report_line[len(marker) :])
                    complexity_marker = "AXIOMA_COMPLEXITY:"
                    complexity_line = next(
                        (
                            line
                            for line in result.stdout.splitlines()
                            if line.startswith(complexity_marker)
                        ),
                        None,
                    )
                    if complexity_line is not None:
                        complexity_report = json.loads(complexity_line[len(complexity_marker) :])
                    optimization_marker = "AXIOMA_OPTIMIZATION:"
                    optimization_line = next(
                        (
                            line
                            for line in result.stdout.splitlines()
                            if line.startswith(optimization_marker)
                        ),
                        None,
                    )
                    if optimization_line is not None:
                        optimization_report = json.loads(
                            optimization_line[len(optimization_marker) :]
                        )
                    elif optimization_code:
                        optimization_report = {
                            "checks": [],
                            "requested": len(problem.samples) + generated_count,
                            "checked": 0,
                            "reason": "Harness did not return optimization checks",
                        }
                    property_marker = "AXIOMA_PROPERTY:"
                    property_line = next(
                        (
                            line
                            for line in result.stdout.splitlines()
                            if line.startswith(property_marker)
                        ),
                        None,
                    )
                    if property_line is not None:
                        property_report = json.loads(property_line[len(property_marker) :])
                    elif property_code:
                        property_report = {
                            "example_checks": [],
                            "generated_checks": [],
                            "requested": property_count,
                            "generated": 0,
                            "property_validated_on_examples": False,
                            "property_code": property_code,
                            "reason": "Harness did not return property checks",
                        }
                    if (
                        not isinstance(sample_results, list)
                        or len(sample_results)
                        != len(problem.samples)
                        + (
                            len(problem.samples) + generated_count
                            if input_payload.get("reference_code")
                            else 0
                        )
                        or any(not isinstance(item, dict) for item in sample_results)
                    ):
                        raise ValueError("Harness returned an incomplete sample report")
                    mutation_marker = "AXIOMA_MUTATION:"
                    mutation_line = next(
                        (
                            line
                            for line in result.stdout.splitlines()
                            if line.startswith(mutation_marker)
                        ),
                        None,
                    )
                    if mutation_line is not None:
                        mutation_report = json.loads(mutation_line[len(mutation_marker) :])
                    if int(input_payload.get("mutation_tests", 0)) and not mutation_report:
                        mutation_report = {
                            "requested": int(input_payload.get("mutation_tests", 0)),
                            "generated": 0,
                            "outcomes": [],
                            "reason": "Harness did not complete the mutation run",
                        }
                    if mutation_report and not isinstance(mutation_report.get("outcomes"), list):
                        raise ValueError("Harness returned invalid mutation results")
            else:
                if any(not isinstance(sample, StdinStdoutSample) for sample in problem.samples):
                    raise ValueError("stdin/stdout interfaces require stdin/stdout samples")
                sample_results = []
                for index, sample in enumerate(problem.samples):
                    script = _stdin_execute_script(language)
                    result = sandbox.run(
                        adapter,
                        input_payload["code"],
                        cancellation_requested=lambda: is_cancelled(session_factory, job_id),
                        extra_files={"input.txt": sample.stdin.encode("utf-8")},
                        execute_script=script,
                    )
                    if result.cancelled:
                        break
                    actual = result.stdout.replace("\r\n", "\n").rstrip("\n")
                    expected = sample.expected_stdout.replace("\r\n", "\n").rstrip("\n")
                    outcome = (
                        "passed"
                        if result.exit_code == 0 and not result.timed_out and actual == expected
                        else "failed"
                    )
                    sample_results.append(
                        {
                            "name": sample.name,
                            "outcome": outcome,
                            "details": {
                                "expected_stdout": expected,
                                "actual_stdout": actual,
                                "exit_code": result.exit_code,
                                "stderr": result.stderr,
                                "timed_out": result.timed_out,
                                "output_limited": result.output_limited,
                            },
                        }
                    )
                    if result.timed_out:
                        sample_results.extend(
                            {
                                "name": remaining.name,
                                "outcome": "skipped",
                                "details": {"reason": "An earlier sample timed out"},
                            }
                            for remaining in problem.samples[index + 1 :]
                        )
                        break
        else:
            result = sandbox.run(
                adapter,
                input_payload["code"],
                cancellation_requested=lambda: is_cancelled(session_factory, job_id),
            )
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, job_id)
            if job is None or job.status != JobStatus.RUNNING.value or job.lease_owner != worker_id:
                return
            job.lease_owner = None
            job.lease_expires_at = None
            job.error_code = (
                "sandbox_unavailable" if isinstance(exc, SandboxUnavailable) else "worker_error"
            )
            job.error_message = str(exc)[:1000]
            transition_job(
                session, job, JobStatus.FAILED, "The analysis worker could not run this submission"
            )
        return

    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None or job.status == JobStatus.CANCELLED.value:
            return
        if job.status != JobStatus.RUNNING.value or job.lease_owner != worker_id:
            return
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if result.cancelled:
            job.lease_owner = None
            job.lease_expires_at = None
            transition_job(session, job, JobStatus.CANCELLED, "Execution cancelled")
            return

        if input_payload.get("optimization_code") and not optimization_report:
            optimization_report = {
                "requested": len(problem.samples) + generated_count_effective if problem else 0,
                "checked": 0,
                "checks": [],
                "reason": "Sandbox did not return optimization checks",
            }
        if input_payload.get("property_code") and not property_report:
            property_report = {
                "example_checks": [
                    {
                        "name": "property/" + sample.name,
                        "outcome": "skipped",
                        "details": {"reason": "Sandbox did not return property checks"},
                    }
                    for sample in problem.samples
                ]
                if problem
                else [],
                "generated_checks": [
                    {
                        "name": f"property/generated_{index + 1}",
                        "outcome": "skipped",
                        "details": {"reason": "Sandbox did not return property checks"},
                    }
                    for index in range(int(input_payload.get("property_tests", 0)))
                ],
                "requested": int(input_payload.get("property_tests", 0)),
                "generated": 0,
                "property_validated_on_examples": False,
                "property_code": input_payload["property_code"],
                "reason": "Sandbox did not return property checks",
            }

        if problem is not None and sample_results is None:
            sample_results = [
                {
                    "name": sample.name,
                    "outcome": "failed",
                    "details": {
                        "timed_out": result.timed_out,
                        "exit_code": result.exit_code,
                        "stderr": result.stderr,
                        "output_limited": result.output_limited,
                    },
                }
                for sample in problem.samples
            ]

        if sample_results is not None:
            if result.cancelled:
                job.lease_owner = None
                job.lease_expires_at = None
                transition_job(session, job, JobStatus.CANCELLED, "Execution cancelled")
                return
            passed_count = 0
            failed_count = 0
            skipped_count = 0
            for sample_result in sample_results:
                outcome = sample_result.get("outcome")
                if outcome not in {"passed", "failed", "skipped"}:
                    raise ValueError("Harness returned an invalid sample outcome")
                details = sample_result.get("details", {})
                if not isinstance(details, dict):
                    details = {"message": str(details)[:500]}
                passed_count += outcome == "passed"
                failed_count += outcome == "failed"
                skipped_count += outcome == "skipped"
                session.add(
                    TestCaseRecord(
                        id=str(uuid4()),
                        job_id=job_id,
                        name=str(sample_result.get("name", "unnamed sample"))[:200],
                        outcome=outcome,
                        duration_ms=elapsed_ms,
                        details=details,
                    )
                )
            check_label = "checks" if input_payload.get("reference_code") else "sample tests"
            summary = (
                f"{passed_count} of {len(sample_results)} {check_label} passed; "
                f"{failed_count} failed, {skipped_count} skipped"
            )
            session.add(
                EvidenceClaimRecord(
                    id=str(uuid4()),
                    job_id=job_id,
                    evidence_type=EvidenceType.EXECUTED.value,
                    confidence=Confidence.HIGH.value,
                    summary=summary,
                    provenance={
                        "tool": (
                            "axioma-python-harness"
                            if isinstance(problem.interface, FunctionInterface)
                            and language == "python"
                            else "axioma-java-harness"
                            if isinstance(problem.interface, FunctionInterface)
                            else "axioma-stdin-worker"
                        ),
                        "tool_version": "0.1.0",
                        "input_hash": input_hash,
                        "observed_at": datetime.now(UTC).isoformat(),
                        "details": {
                            "language": language,
                            "elapsed_ms": elapsed_ms,
                            "reference_code_provided": bool(input_payload.get("reference_code")),
                            "independent_reference_code_provided": bool(
                                input_payload.get("independent_reference_code")
                            ),
                            "generated_tests_requested": generated_count_effective,
                            "exhaustive_tests": exhaustive_mode,
                            "reference_limit": (
                                (
                                    "Two user-supplied references agreed with each other and matched the "
                                    "declared examples; shared errors remain possible."
                                    if input_payload.get("independent_reference_code")
                                    else "A user-supplied reference matched the declared examples; its "
                                    "correctness has not been independently established."
                                )
                                if input_payload.get("reference_code")
                                else None
                            ),
                            "seed": int(input_payload.get("seed", 0)),
                        },
                    },
                    artifact_ids=[],
                )
            )
            if input_payload.get("property_code"):
                example_checks = property_report.get("example_checks", [])
                generated_checks = property_report.get("generated_checks", [])
                all_property_checks = [*example_checks, *generated_checks]
                property_passed = sum(
                    isinstance(item, dict) and item.get("outcome") == "passed"
                    for item in all_property_checks
                )
                property_failed = sum(
                    isinstance(item, dict) and item.get("outcome") == "failed"
                    for item in all_property_checks
                )
                property_skipped = sum(
                    isinstance(item, dict) and item.get("outcome") == "skipped"
                    for item in all_property_checks
                )
                if property_failed:
                    property_state = "failed"
                elif (
                    property_report.get("property_validated_on_examples")
                    and len(generated_checks) == int(property_report.get("requested", 0))
                    and all(item.get("outcome") == "passed" for item in generated_checks)
                ):
                    property_state = "passed"
                else:
                    property_state = "inconclusive"
                session.add(
                    EvidenceClaimRecord(
                        id=str(uuid4()),
                        job_id=job_id,
                        evidence_type=EvidenceType.EXECUTED.value,
                        confidence=Confidence.LOW.value,
                        summary=(
                            f"User-supplied property checks {property_state}: {property_passed} passed, "
                            f"{property_failed} failed, {property_skipped} skipped across examples and generated inputs"
                        ),
                        provenance={
                            "tool": (
                                "axioma-python-property-runner"
                                if language == "python"
                                else "axioma-java-property-runner"
                            ),
                            "tool_version": "0.1.0",
                            "input_hash": input_hash,
                            "observed_at": datetime.now(UTC).isoformat(),
                            "details": {
                                "state": property_state,
                                "property_code": property_report.get(
                                    "property_code", input_payload["property_code"]
                                ),
                                "property_signature": "check(args, kwargs, result) -> bool",
                                "property_validated_on_examples": property_report.get(
                                    "property_validated_on_examples", False
                                ),
                                "requested_generated": property_report.get("requested", 0),
                                "generated": property_report.get("generated", 0),
                                "example_checks": example_checks,
                                "generated_checks": generated_checks,
                                "passed": property_passed,
                                "failed": property_failed,
                                "skipped": property_skipped,
                                "limitation": property_report.get(
                                    "limit",
                                    "A user-supplied property passing finite examples does not prove it universally valid.",
                                ),
                                "runner_note": property_report.get("reason"),
                            },
                        },
                        artifact_ids=[],
                    )
                )
            if int(input_payload.get("mutation_tests", 0)):
                outcomes = mutation_report.get("outcomes", [])
                states = [item.get("state") for item in outcomes if isinstance(item, dict)]
                killed = states.count("killed")
                survived = states.count("survived")
                invalid = states.count("invalid")
                not_run = states.count("not_run") + max(
                    int(mutation_report.get("requested", 0))
                    - int(mutation_report.get("generated", 0)),
                    0,
                )
                valid_mutants = killed + survived
                score = killed / valid_mutants if valid_mutants else None
                score_text = (
                    f" ({score:.1%} mutation score)"
                    if score is not None
                    else " (score unavailable)"
                )
                session.add(
                    EvidenceClaimRecord(
                        id=str(uuid4()),
                        job_id=job_id,
                        evidence_type=EvidenceType.STATISTICAL.value,
                        confidence=Confidence.LOW.value,
                        summary=(
                            f"Mutation analysis killed {killed} of {valid_mutants} valid mutants"
                            f"{score_text}; {survived} survived, {invalid} invalid, {not_run} not run"
                        ),
                        provenance={
                            "tool": f"axioma-{language}-mutation-runner",
                            "tool_version": "0.1.0",
                            "input_hash": input_hash,
                            "observed_at": datetime.now(UTC).isoformat(),
                            "details": {
                                "requested": mutation_report.get("requested", 0),
                                "generated": mutation_report.get("generated", 0),
                                "killed": killed,
                                "survived": survived,
                                "invalid": invalid,
                                "not_run": not_run,
                                "mutation_score": score,
                                "mutants": outcomes,
                                "analysis_note": mutation_report.get("reason"),
                                "reference_limit": (
                                    "The supplied reference set passed its sample checks; this does not "
                                    "establish correctness for every input or exclude shared errors."
                                ),
                            },
                        },
                        artifact_ids=[],
                    )
                )
            if (
                problem is not None
                and isinstance(problem.interface, FunctionInterface)
                and language == "python"
            ):
                complexity = analyze_python_complexity(
                    input_payload["code"], problem.interface.entrypoint
                )
                measured_points = complexity_report.get("measurements", [])
                if measured_points:
                    complexity = triangulate_python_complexity(complexity, measured_points)
                elif complexity_report.get("skipped_reason"):
                    complexity = ComplexityEstimate(
                        method=complexity.method,
                        estimate=complexity.estimate,
                        confidence=complexity.confidence,
                        methods_disagree=complexity.methods_disagree,
                        explanation=(
                            complexity.explanation
                            + " Benchmark was skipped: "
                            + str(complexity_report["skipped_reason"])[:300]
                        ),
                        details={
                            "measurement_method": "executed_source_line_events",
                            "points": [],
                            "skipped_reason": str(complexity_report["skipped_reason"])[:300],
                        },
                    )
                complexity = replace(
                    complexity,
                    details={
                        **complexity.details,
                        "space_measurement": estimate_python_peak_memory(measured_points),
                        "constraint_scalability": estimate_constraint_scale(
                            problem.constraints, complexity.estimate
                        ),
                    },
                )
                session.add(
                    ComplexityRecord(
                        job_id=job_id,
                        method=complexity.method,
                        estimate=complexity.estimate,
                        confidence=complexity.confidence,
                        methods_disagree=complexity.methods_disagree,
                        explanation=complexity.explanation,
                        details=complexity.details,
                    )
                )
                optimization_code = input_payload.get("optimization_code")
                if optimization_code:
                    checks = optimization_report.get("checks", [])
                    passed_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "passed"
                        for item in checks
                    )
                    failed_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "failed"
                        for item in checks
                    )
                    skipped_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "skipped"
                        for item in checks
                    )
                    requested_checks = int(
                        optimization_report.get("requested", len(problem.samples))
                    )
                    if passed_checks == requested_checks and len(checks) == requested_checks:
                        optimization_state = "passed"
                    elif failed_checks:
                        optimization_state = "failed"
                    else:
                        optimization_state = "inconclusive"
                    optimized_static = analyze_python_complexity(
                        optimization_code, problem.interface.entrypoint
                    )
                    optimization_points = complexity_report.get("optimized_measurements", [])
                    optimized_complexity = optimized_static
                    if optimization_points:
                        optimized_complexity = triangulate_python_complexity(
                            optimized_static,
                            [
                                {
                                    "size": point["size"],
                                    "line_events": point["optimized_line_events"],
                                    "opcode_events": point.get("optimized_opcode_events"),
                                }
                                for point in optimization_points
                            ],
                        )
                    optimized_space_measurement = estimate_python_peak_memory(
                        optimization_points, "optimized_peak_traced_bytes"
                    )
                    optimized_complexity = replace(
                        optimized_complexity,
                        details={
                            **optimized_complexity.details,
                            "space_measurement": optimized_space_measurement,
                        },
                    )

                    def complexity_view(value: ComplexityEstimate) -> dict:
                        return {
                            "method": value.method,
                            "estimate": value.estimate,
                            "confidence": value.confidence,
                            "methods_disagree": value.methods_disagree,
                            "details": value.details,
                        }

                    verification_details = {
                        "state": optimization_state,
                        "checks": {
                            "requested": requested_checks,
                            "checked": len(checks),
                            "passed": passed_checks,
                            "failed": failed_checks,
                            "skipped": skipped_checks,
                            "cases": checks,
                        },
                        "original_code": input_payload["code"],
                        "optimized_code": optimization_code,
                        "optimization_notes": input_payload.get("optimization_notes"),
                        "complexity_before": complexity_view(complexity),
                        "complexity_after": complexity_view(optimized_complexity),
                        "measurement_method": "executed_source_line_events",
                        "measurements": optimization_points,
                        "measurement_skipped_reason": complexity_report.get(
                            "optimized_skipped_reason"
                        ),
                        "measurement_limit": (
                            "Line events are a work proxy, not wall-clock speed. Native library work "
                            "is not counted, and these measurements do not prove an asymptotic bound."
                        ),
                    }
                    session.add(
                        EvidenceClaimRecord(
                            id=str(uuid4()),
                            job_id=job_id,
                            evidence_type=EvidenceType.EXECUTED.value,
                            confidence=Confidence.HIGH.value,
                            summary=(
                                f"Optimization candidate {optimization_state}: "
                                f"{passed_checks} of {requested_checks} output-equivalence checks passed; "
                                f"{failed_checks} failed, {skipped_checks} skipped"
                            ),
                            provenance={
                                "tool": "axioma-python-optimization-checker",
                                "tool_version": "0.1.0",
                                "input_hash": input_hash,
                                "observed_at": datetime.now(UTC).isoformat(),
                                "details": verification_details,
                            },
                            artifact_ids=[],
                        )
                    )
                    if optimization_points:
                        lower_at_every_size = all(
                            point["optimized_line_events"] < point["line_events"]
                            for point in optimization_points
                        )
                        fewer_opcodes_at_every_size = (
                            all(
                                point["optimized_opcode_events"] < point["opcode_events"]
                                for point in optimization_points
                            )
                            if all(
                                "optimized_opcode_events" in point and "opcode_events" in point
                                for point in optimization_points
                            )
                            else None
                        )
                        session.add(
                            EvidenceClaimRecord(
                                id=str(uuid4()),
                                job_id=job_id,
                                evidence_type=EvidenceType.STATISTICAL.value,
                                confidence=Confidence.LOW.value,
                                summary=(
                                    "Optimization candidate used fewer source-line events at every "
                                    f"one of {len(optimization_points)} benchmark sizes"
                                    if lower_at_every_size
                                    else "Optimization candidate did not use fewer source-line events "
                                    "at every benchmark size"
                                ),
                                provenance={
                                    "tool": "axioma-python-line-event-benchmark",
                                    "tool_version": "0.1.0",
                                    "input_hash": input_hash,
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "details": {
                                        "measurement_method": "executed_source_line_events",
                                        "points": optimization_points,
                                        "fewer_events_at_every_size": lower_at_every_size,
                                        "fewer_opcodes_at_every_size": fewer_opcodes_at_every_size,
                                        "equivalence_state": optimization_state,
                                        "limitation": verification_details["measurement_limit"],
                                    },
                                },
                                artifact_ids=[],
                            )
                        )
            elif (
                problem is not None
                and isinstance(problem.interface, FunctionInterface)
                and language == "java"
            ):
                complexity = analyze_java_complexity(
                    input_payload["code"], problem.interface.entrypoint
                )
                measured_points = complexity_report.get("measurements", [])
                if measured_points:
                    complexity = add_java_wall_time_fit(complexity, measured_points)
                elif complexity_report.get("skipped_reason") not in (None, "none"):
                    complexity = replace(
                        complexity,
                        details={
                            **complexity.details,
                            "measurement_method": "jvm_reflective_wall_time",
                            "points": [],
                            "skipped_reason": str(complexity_report["skipped_reason"])[:300],
                        },
                    )
                complexity = replace(
                    complexity,
                    details={
                        **complexity.details,
                        "space_measurement": estimate_java_heap_pool_peak_growth(measured_points),
                        "constraint_scalability": estimate_constraint_scale(
                            problem.constraints, complexity.estimate
                        ),
                    },
                )
                session.add(
                    ComplexityRecord(
                        job_id=job_id,
                        method=complexity.method,
                        estimate=complexity.estimate,
                        confidence=complexity.confidence,
                        methods_disagree=complexity.methods_disagree,
                        explanation=complexity.explanation,
                        details=complexity.details,
                    )
                )
                optimization_code = input_payload.get("optimization_code")
                if optimization_code:
                    checks = optimization_report.get("checks", [])
                    passed_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "passed"
                        for item in checks
                    )
                    failed_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "failed"
                        for item in checks
                    )
                    skipped_checks = sum(
                        isinstance(item, dict) and item.get("outcome") == "skipped"
                        for item in checks
                    )
                    requested_checks = int(optimization_report.get("requested", len(problem.samples)))
                    if passed_checks == requested_checks and len(checks) == requested_checks:
                        optimization_state = "passed"
                    elif failed_checks:
                        optimization_state = "failed"
                    else:
                        optimization_state = "inconclusive"
                    optimized_static = analyze_java_complexity(
                        optimization_code, problem.interface.entrypoint
                    )
                    optimization_points = complexity_report.get("optimized_measurements", [])
                    optimized_complexity = (
                        add_java_wall_time_fit(optimized_static, optimization_points, "optimized_elapsed_ns")
                        if optimization_points
                        else optimized_static
                    )
                    optimized_complexity = replace(
                        optimized_complexity,
                        details={
                            **optimized_complexity.details,
                            "space_measurement": estimate_java_heap_pool_peak_growth(
                                optimization_points, "optimized_heap_pool_peak_increase_bytes"
                            ),
                        },
                    )

                    def java_complexity_view(value: ComplexityEstimate) -> dict:
                        return {
                            "method": value.method,
                            "estimate": value.estimate,
                            "confidence": value.confidence,
                            "methods_disagree": value.methods_disagree,
                            "details": value.details,
                        }

                    limitation = (
                        "Measurements use reflective invocation and include reflection overhead. JVM "
                        "warmup and host scheduling add noise; lower observed time on these inputs "
                        "does not establish general speedup or an asymptotic improvement."
                    )
                    verification_details = {
                        "state": optimization_state,
                        "checks": {
                            "requested": requested_checks,
                            "checked": len(checks),
                            "passed": passed_checks,
                            "failed": failed_checks,
                            "skipped": skipped_checks,
                            "cases": checks,
                        },
                        "original_code": input_payload["code"],
                        "optimized_code": optimization_code,
                        "optimization_notes": input_payload.get("optimization_notes"),
                        "complexity_before": java_complexity_view(complexity),
                        "complexity_after": java_complexity_view(optimized_complexity),
                        "measurement_method": complexity_report.get(
                            "measurement_method", "jvm_reflective_wall_time"
                        ),
                        "measurements": optimization_points,
                        "warmups": complexity_report.get("warmups", 5),
                        "trials": complexity_report.get("trials", 9),
                        "measurement_skipped_reason": complexity_report.get(
                            "optimized_skipped_reason"
                        ),
                        "measurement_limit": limitation,
                    }
                    session.add(
                        EvidenceClaimRecord(
                            id=str(uuid4()),
                            job_id=job_id,
                            evidence_type=EvidenceType.EXECUTED.value,
                            confidence=Confidence.HIGH.value,
                            summary=(
                                f"Java optimization candidate {optimization_state}: "
                                f"{passed_checks} of {requested_checks} output-equivalence checks passed; "
                                f"{failed_checks} failed, {skipped_checks} skipped"
                            ),
                            provenance={
                                "tool": "axioma-java-optimization-checker",
                                "tool_version": "0.1.0",
                                "input_hash": input_hash,
                                "observed_at": datetime.now(UTC).isoformat(),
                                "details": verification_details,
                            },
                            artifact_ids=[],
                        )
                    )
                    if optimization_points:
                        faster_at_every_size = all(
                            point.get("optimized_elapsed_ns", 0) < point.get("elapsed_ns", 0)
                            for point in optimization_points
                        )
                        session.add(
                            EvidenceClaimRecord(
                                id=str(uuid4()),
                                job_id=job_id,
                                evidence_type=EvidenceType.STATISTICAL.value,
                                confidence=Confidence.LOW.value,
                                summary=(
                                    "Java optimization candidate had lower measured median time at every "
                                    f"one of {len(optimization_points)} benchmark sizes"
                                    if faster_at_every_size
                                    else "Java optimization candidate did not have lower measured median time "
                                    "at every benchmark size"
                                ),
                                provenance={
                                    "tool": "axioma-java-wall-time-benchmark",
                                    "tool_version": "0.1.0",
                                    "input_hash": input_hash,
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "details": {
                                        "measurement_method": "jvm_reflective_wall_time",
                                        "points": optimization_points,
                                        "lower_median_at_every_size": faster_at_every_size,
                                        "equivalence_state": optimization_state,
                                        "warmups": complexity_report.get("warmups", 5),
                                        "trials": complexity_report.get("trials", 9),
                                        "limitation": limitation,
                                    },
                                },
                                artifact_ids=[],
                            )
                        )
            job.lease_owner = None
            job.lease_expires_at = None
            transition_job(session, job, JobStatus.COMPLETED, "Sample tests finished")
            return

        outcome = "passed" if result.exit_code == 0 and not result.timed_out else "failed"
        if result.timed_out:
            summary = "Execution exceeded the wall-clock limit"
        elif result.exit_code == 0:
            summary = "Program exited successfully"
        else:
            summary = f"Program exited with code {result.exit_code}"
        session.add(
            TestCaseRecord(
                id=str(uuid4()),
                job_id=job_id,
                name="program_exit",
                outcome=outcome,
                duration_ms=elapsed_ms,
                details={
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "output_limited": result.output_limited,
                },
            )
        )
        session.add(
            EvidenceClaimRecord(
                id=str(uuid4()),
                job_id=job_id,
                evidence_type=EvidenceType.EXECUTED.value,
                confidence=Confidence.HIGH.value,
                summary=summary,
                provenance={
                    "tool": "axioma-docker-worker",
                    "tool_version": "0.1.0",
                    "input_hash": input_hash,
                    "observed_at": datetime.now(UTC).isoformat(),
                    "details": {"language": language, "elapsed_ms": elapsed_ms},
                },
                artifact_ids=[],
            )
        )
        job.lease_owner = None
        job.lease_expires_at = None
        transition_job(
            session, job, JobStatus.COMPLETED, "Execution finished; inspect the evidence report"
        )


def worker_iteration(session_factory: sessionmaker, worker_id: str, sandbox: DockerSandbox) -> bool:
    with session_factory() as session:
        reap_expired_jobs(session)
        job = claim_next_job(session, worker_id)
        job_id = job.id if job else None
    if job_id is None:
        return False
    run_claimed_job(session_factory, job_id, worker_id, sandbox)
    return True
