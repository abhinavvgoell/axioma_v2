from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axioma_api.contracts import JobCreate, JobMode, JobStatus
from axioma_api.jobs import create_job
from axioma_api.models import (
    Base,
    ComplexityRecord,
    EvidenceClaimRecord,
    Job,
    TestCaseRecord as CaseRow,
)
from axioma_api.queue import claim_next_job
from axioma_worker.runtime import run_claimed_job
from axioma_worker.sandbox import SandboxResult


class FakeSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert source == "print(42)"
        assert cancellation_requested is not None
        return SandboxResult(exit_code=0, stdout="42\n", stderr="")


class FakeHarnessTimeoutSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        return SandboxResult(
            exit_code=None,
            stdout="",
            stderr="",
            timed_out=True,
            failure_kind="timeout",
        )


class FakeHarnessSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert source == "def solve(value): return value * 2"
        assert kwargs["source_filename"] == "submission.py"
        assert "AXIOMA_RESULT" in kwargs["extra_files"]["main.py"].decode()
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample-1","outcome":"passed","details":{}},'
                '{"name":"sample-2","outcome":"failed","details":{"actual":5,"expected":6}}]\n'
            ),
            stderr="",
        )


class FakeBenchmarkSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        harness = kwargs["extra_files"]["main.py"].decode()
        assert '"size":10' in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}}]\n'
                'AXIOMA_COMPLEXITY:{"measurements":[{"size":10,"line_events":30,"opcode_events":90},'
                '{"size":20,"line_events":60,"opcode_events":180},'
                '{"size":40,"line_events":120,"opcode_events":360},'
                '{"size":80,"line_events":240,"opcode_events":720}],'
                '"skipped_reason":null}\n'
            ),
            stderr="",
        )


class FakeMutationSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert "mutant_1.py" in kwargs["extra_files"]
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}},'
                '{"name":"reference/sample","outcome":"passed","details":{}}]\n'
                'AXIOMA_COMPLEXITY:{"measurements":[],"skipped_reason":null}\n'
                'AXIOMA_MUTATION:{"requested":1,"generated":1,"outcomes":[{"id":"mutant_1",'
                '"label":"BinOp_Sub_line_1","state":"killed","cases_checked":1}]}\n'
            ),
            stderr="",
        )


class FakeStdinSandbox:
    def __init__(self):
        self.inputs = []

    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language in {"python", "java"}
        assert "< /work/input.txt" in kwargs["execute_script"]
        sample_input = kwargs["extra_files"]["input.txt"].decode()
        self.inputs.append(sample_input)
        output = "HELLO\n" if sample_input == "hello\n" else "WRONG\n"
        return SandboxResult(exit_code=0, stdout=output, stderr="")


class FakeJavaFunctionSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        assert kwargs["source_filename"] == "Solution.java"
        assert "javac -d /work /work/Solution.java" in kwargs["execute_script"]
        harness = kwargs["extra_files"]["Harness.java"].decode()
        assert 'invokeQuietly("Solution", "add"' in harness
        return SandboxResult(
            exit_code=0,
            stdout='AXIOMA_RESULT:[{"name":"sum","outcome":"passed","details":{"reason":""}}]\n',
            stderr="",
        )


class FakeJavaReferenceSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        assert "Reference.java" in kwargs["extra_files"]
        assert "/work/Reference.java" in kwargs["execute_script"]
        harness = kwargs["extra_files"]["Harness.java"].decode()
        assert 'invokeQuietly("Reference", "solve"' in harness
        assert "candidate differs from user-supplied reference" in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"example","outcome":"passed","details":{}},'
                '{"name":"reference/example","outcome":"passed","details":{}},'
                '{"name":"generated_1","outcome":"passed","details":{}},'
                '{"name":"generated_2","outcome":"failed","details":{}}]\n'
            ),
            stderr="",
        )


class FakeJavaMutationSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        assert "AxiomaMutant1.java" in kwargs["extra_files"]
        harness = kwargs["extra_files"]["Harness.java"].decode()
        assert "ToolProvider.getSystemJavaCompiler()" in harness
        assert "AXIOMA_MUTATION:" in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}},'
                '{"name":"reference/sample","outcome":"passed","details":{}}]\n'
                'AXIOMA_MUTATION:{"requested":1,"generated":1,"outcomes":'
                '[{"id":"mutant_1","label":"operator_+_to_-_offset_48",'
                '"state":"killed","cases_checked":1}],"reason":""}\n'
            ),
            stderr="",
        )


class FakeJavaExhaustiveSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        harness = kwargs["extra_files"]["Harness.java"].decode()
        assert '"exhaustive_integer_domain"' in harness
        assert 'result(test.name(), outcome, reason, test.strategy(),' in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"example","outcome":"passed","details":{}},'
                '{"name":"reference/example","outcome":"passed","details":{}},'
                '{"name":"exhaustive_1","outcome":"passed","details":{}},'
                '{"name":"exhaustive_2","outcome":"passed","details":{}}]\n'
            ),
            stderr="",
        )


class FakeJavaCompileFailureSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        return SandboxResult(
            exit_code=1,
            stdout="",
            stderr="Solution.java:1: error: illegal start of expression",
            failure_kind="compile_error",
        )


class FakeJavaPropertySandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "java"
        assert "AxiomaProperties.java" in kwargs["extra_files"]
        assert "/work/AxiomaProperties.java" in kwargs["execute_script"]
        harness = kwargs["extra_files"]["Harness.java"].decode()
        assert 'Class.forName("AxiomaProperties")' in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"example","outcome":"passed","details":{}}]\n'
                'AXIOMA_PROPERTY:{"example_checks":[{"name":"property/example",'
                '"outcome":"passed","details":{}}],"generated_checks":['
                '{"name":"property_generated_1","outcome":"passed","details":{}}],'
                '"requested":1,"generated":1,"property_validated_on_examples":true}\n'
            ),
            stderr="",
        )


class FakeReferenceSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert "reference.py" in kwargs["extra_files"]
        harness = kwargs["extra_files"]["main.py"].decode()
        assert "candidate against user-supplied reference" in harness
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}},'
                '{"name":"reference/sample","outcome":"passed","details":{}},'
                '{"name":"generated_1","outcome":"passed","details":{"comparison":"candidate against user-supplied reference"}}]\n'
            ),
            stderr="",
        )


class FakeExhaustiveSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        harness = kwargs["extra_files"]["main.py"].decode()
        assert "exhaustive_integer_domain" in harness
        assert '"args":[-2]' in harness and '"args":[2]' in harness
        outcomes = [
            {"name": "sample", "outcome": "passed", "details": {}},
            {"name": "reference/sample", "outcome": "passed", "details": {}},
            *[
                {"name": f"exhaustive_{index}", "outcome": "passed", "details": {}}
                for index in range(1, 6)
            ],
        ]
        import json

        return SandboxResult(
            exit_code=0,
            stdout="AXIOMA_RESULT:" + json.dumps(outcomes) + "\n",
            stderr="",
        )


class FakeOptimizationSandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert "optimized.py" in kwargs["extra_files"]
        assert "AXIOMA_OPTIMIZATION:" in kwargs["extra_files"]["main.py"].decode()
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}}]\n'
                'AXIOMA_OPTIMIZATION:{"checks":[{"name":"optimization/sample",'
                '"outcome":"passed","details":{}}],"requested":1,"checked":1}\n'
                'AXIOMA_COMPLEXITY:{"measurements":[{"size":10,"line_events":42,"opcode_events":84},'
                '{"size":20,"line_events":82,"opcode_events":164},'
                '{"size":40,"line_events":162,"opcode_events":324},'
                '{"size":80,"line_events":322,"opcode_events":644}],"optimized_measurements":['
                '{"size":10,"line_events":42,"optimized_line_events":2,"opcode_events":84,"optimized_opcode_events":4},'
                '{"size":20,"line_events":82,"optimized_line_events":2,"opcode_events":164,"optimized_opcode_events":4},'
                '{"size":40,"line_events":162,"optimized_line_events":2,"opcode_events":324,"optimized_opcode_events":4},'
                '{"size":80,"line_events":322,"optimized_line_events":2,"opcode_events":644,"optimized_opcode_events":4}],'
                '"skipped_reason":null,"optimized_skipped_reason":null}\n'
            ),
            stderr="",
        )


class FakePropertySandbox:
    def run(self, adapter, source, cancellation_requested=None, **kwargs):
        assert adapter.language == "python"
        assert "properties.py" in kwargs["extra_files"]
        assert '"requested_property_tests":2' in kwargs["extra_files"]["main.py"].decode()
        return SandboxResult(
            exit_code=0,
            stdout=(
                'AXIOMA_RESULT:[{"name":"sample","outcome":"passed","details":{}}]\n'
                'AXIOMA_PROPERTY:{"example_checks":[{"name":"property/sample",'
                '"outcome":"passed","details":{}}],"generated_checks":['
                '{"name":"generated_1","outcome":"passed","details":{}},'
                '{"name":"generated_2","outcome":"passed","details":{}}],'
                '"requested":2,"generated":2,"property_validated_on_examples":true,'
                '"property_code":"def check(args, kwargs, result): return True",'
                '"limit":"Finite checks are not a universal proof."}\n'
            ),
            stderr="",
        )


def make_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_claimed_job_runs_and_persists_execution_evidence() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={"code": "print(42)"},
            ),
        )
        job_id = job.id
        claimed = claim_next_job(session, "worker-test")
        assert claimed is not None
        assert claimed.status == JobStatus.RUNNING.value

    run_claimed_job(session_factory, job_id, "worker-test", FakeSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED.value
        case = session.query(CaseRow).filter_by(job_id=job_id).one()
        assert case.outcome == "passed"
        assert case.details["stdout"] == "42\n"
        claim = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).one()
        assert claim.evidence_type == "executed"
        assert claim.confidence == "high"


def test_function_harness_persists_one_result_per_sample() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value * 2",
                    "test_pack_source": "Axioma test pack",
                    "problem": {
                        "statement": "Double the input.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "sample-1", "args": [2], "expected": 4},
                            {"kind": "function", "name": "sample-2", "args": [3], "expected": 6},
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", FakeHarnessSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None and job.status == JobStatus.COMPLETED.value
        cases = session.query(CaseRow).filter_by(job_id=job_id).order_by(CaseRow.name).all()
        assert [(case.name, case.outcome) for case in cases] == [
            ("sample-1", "passed"),
            ("sample-2", "failed"),
        ]
        assert all(case.details["origin"] == "catalog_sample" for case in cases)
        claim = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).one()
        assert claim.summary == "1 of 2 sample tests passed; 1 failed, 0 skipped"
        complexity = session.get(ComplexityRecord, job_id)
        assert complexity is not None
        assert complexity.method == "static_ast_loop_depth"
        assert complexity.estimate == "O(1) (loop-free target)"
        assert complexity.confidence == "low"
        assert complexity.details["code_analysis"]["language"] == "python"
        assert complexity.details["constraint_scalability"]["state"] == "not_estimated"


def test_python_benchmark_fit_and_measurements_are_persisted() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value",
                    "complexity_benchmarks": [
                        {
                            "size": size,
                            "args": [size],
                            "kwargs": {},
                            "generator_version": "problem-input-generator-v1",
                            "seed": 42,
                            "size_path": "args[0]",
                            "strategy": "descending",
                        }
                        for size in (10, 20, 40, 80)
                    ],
                    "problem": {
                        "statement": "Return the input.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [1], "expected": 1}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", FakeBenchmarkSandbox())

    with session_factory() as session:
        complexity = session.get(ComplexityRecord, job_id)
        assert complexity is not None
        assert complexity.method.endswith("+dynamic_line_event_fit+dynamic_opcode_count_fit")
        assert complexity.details["measurement_method"] == "executed_source_line_events"
        assert complexity.details["signals"]["opcode_count_fit"]["estimate"] == "O(n)"
        assert [point["size"] for point in complexity.details["points"]] == [10, 20, 40, 80]
        assert complexity.details["benchmark_provenance"] == {
            "state": "declared_generated",
            "metadata_source": "job_request",
            "generator_version": "problem-input-generator-v1",
            "seed": 42,
            "size_path": "args[0]",
            "sizes": [10, 20, 40, 80],
            "strategies": ["descending", "descending", "descending", "descending"],
            "runtime_image": "python:3.13-slim",
        }


def test_exhaustive_differential_results_share_the_normal_test_ledger() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value * 2",
                    "reference_code": "def solve(value): return value * 2",
                    "exhaustive_tests": True,
                    "problem": {
                        "statement": "Double a small integer.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "constraints": [{"path": "args[0]", "minimum": -2, "maximum": 2}],
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [1], "expected": 2}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-exhaustive-test")

    run_claimed_job(session_factory, job_id, "worker-exhaustive-test", FakeExhaustiveSandbox())

    with session_factory() as session:
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert len(cases) == 7
        assert all(case.outcome == "passed" for case in cases)
        claims = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).all()
        summary = next(claim for claim in claims if "checks passed" in claim.summary)
        assert summary.summary == "7 of 7 checks passed; 0 failed, 0 skipped"
        assert summary.provenance["details"]["generated_tests_requested"] == 5
        assert summary.provenance["details"]["exhaustive_tests"] is True
        assert "not been independently established" in summary.provenance["details"]["reference_limit"]


def test_java_exhaustive_differential_checks_use_the_shared_test_ledger() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { int solve(int value) { return value * 2; } }",
                    "reference_code": "class Reference { int solve(int value) { return value * 2; } }",
                    "exhaustive_tests": True,
                    "problem": {
                        "statement": "Double a small integer.",
                        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                        "constraints": [{"path": "args[0]", "minimum": 0, "maximum": 1}],
                        "samples": [
                            {"kind": "function", "name": "example", "args": [1], "expected": 2}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-java-exhaustive-test")

    run_claimed_job(
        session_factory, job_id, "worker-java-exhaustive-test", FakeJavaExhaustiveSandbox()
    )

    with session_factory() as session:
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert len(cases) == 4
        assert all(case.outcome == "passed" for case in cases)


def test_java_compile_failure_is_a_failed_check_not_a_worker_failure() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { int solve(int value) { return value; } }",
                    "problem": {
                        "statement": "Return the integer.",
                        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                        "samples": [{"kind": "function", "name": "example", "args": [1], "expected": 1}],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-java-compile-test")

    run_claimed_job(session_factory, job_id, "worker-java-compile-test", FakeJavaCompileFailureSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert job is not None and job.status == "completed"
        assert len(cases) == 1
        assert cases[0].outcome == "failed"
        assert cases[0].details["failure_kind"] == "compile_error"
        assert "illegal start" in cases[0].details["stderr"]


def test_function_harness_timeout_does_not_claim_unobserved_samples_failed() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value",
                    "problem": {
                        "statement": "Return the integer.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "one", "args": [1], "expected": 1},
                            {"kind": "function", "name": "two", "args": [2], "expected": 2},
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-timeout-test")

    run_claimed_job(session_factory, job_id, "worker-timeout-test", FakeHarnessTimeoutSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert job is not None and job.status == "completed"
        assert job.progress_message == "Analysis timed out before per-case outcomes were recorded"
        assert len(cases) == 2
        assert all(case.outcome == "skipped" for case in cases)
        assert all(case.details["failure_kind"] == "timeout" for case in cases)


def test_optimization_evidence_stores_both_versions_without_changing_test_totals() -> None:
    session_factory = make_session_factory()
    original = "def solve(value):\n    return value + 1\n"
    optimized = "def solve(value):\n    return 1 + value\n"
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": original,
                    "optimization_code": optimized,
                    "optimization_notes": "Equivalent arithmetic form.",
                    "complexity_benchmarks": [
                        {"size": size, "args": [size], "kwargs": {}} for size in (10, 20, 40, 80)
                    ],
                    "problem": {
                        "statement": "Add one.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [1], "expected": 2}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-opt-test")

    run_claimed_job(session_factory, job_id, "worker-opt-test", FakeOptimizationSandbox())

    with session_factory() as session:
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert len(cases) == 1
        assert cases[0].outcome == "passed"
        claims = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).all()
        equivalent_claim = next(
            claim for claim in claims if "Optimization candidate passed" in claim.summary
        )
        details = equivalent_claim.provenance["details"]
        assert details["state"] == "passed"
        assert details["original_code"] == original
        assert details["optimized_code"] == optimized
        statistical_claim = next(claim for claim in claims if claim.evidence_type == "statistical")
        assert statistical_claim.provenance["details"]["fewer_events_at_every_size"] is True
        assert statistical_claim.provenance["details"]["fewer_opcodes_at_every_size"] is True


def test_property_claim_is_separate_from_correctness_test_records() -> None:
    session_factory = make_session_factory()
    property_code = "def check(args, kwargs, result): return True"
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value * 2",
                    "property_code": property_code,
                    "property_tests": 2,
                    "problem": {
                        "statement": "Double the value.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [2], "expected": 4}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-property-test")

    run_claimed_job(session_factory, job_id, "worker-property-test", FakePropertySandbox())

    with session_factory() as session:
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert len(cases) == 1
        assert cases[0].name == "sample"
        claims = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).all()
        property_claim = next(
            claim for claim in claims if claim.provenance["tool"] == "axioma-python-property-runner"
        )
        assert property_claim.confidence == "low"
        assert property_claim.provenance["details"]["state"] == "passed"
        assert property_claim.provenance["details"]["property_code"] == property_code


def test_mutation_score_is_saved_as_separate_statistical_evidence() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value + 1",
                    "reference_code": "def solve(value): return value + 1",
                    "mutation_tests": 1,
                    "problem": {
                        "statement": "Add one.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [2], "expected": 3}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", FakeMutationSandbox())

    with session_factory() as session:
        claims = (
            session.query(EvidenceClaimRecord)
            .filter_by(job_id=job_id)
            .order_by(EvidenceClaimRecord.evidence_type)
            .all()
        )
        mutation_claim = next(claim for claim in claims if claim.evidence_type == "statistical")
        details = mutation_claim.provenance["details"]
        assert mutation_claim.confidence == "low"
        assert details["killed"] == 1
        assert details["mutation_score"] == 1.0


def test_java_mutation_score_is_saved_as_low_confidence_evidence() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { int solve(int value) { return value + 1; } }",
                    "reference_code": "class Reference { int solve(int value) { return value + 1; } }",
                    "mutation_tests": 1,
                    "problem": {
                        "statement": "Add one.",
                        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                        "samples": [
                            {"kind": "function", "name": "sample", "args": [2], "expected": 3}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-java-mutation-test")

    run_claimed_job(
        session_factory, job_id, "worker-java-mutation-test", FakeJavaMutationSandbox()
    )

    with session_factory() as session:
        mutation_claim = next(
            claim
            for claim in session.query(EvidenceClaimRecord).filter_by(job_id=job_id).all()
            if claim.evidence_type == "statistical"
        )
        details = mutation_claim.provenance["details"]
        assert mutation_claim.confidence == "low"
        assert mutation_claim.provenance["tool"] == "axioma-java-mutation-runner"
        assert details["killed"] == 1
        assert details["mutation_score"] == 1.0


def test_stdin_stdout_harness_runs_each_case_with_a_fresh_sandbox() -> None:
    session_factory = make_session_factory()
    sandbox = FakeStdinSandbox()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "public class Main {}",
                    "problem": {
                        "statement": "Echo each input.",
                        "interface": {"kind": "stdin_stdout"},
                        "samples": [
                            {
                                "kind": "stdin_stdout",
                                "name": "echo",
                                "stdin": "hello\n",
                                "expected_stdout": "HELLO\n",
                            },
                            {
                                "kind": "stdin_stdout",
                                "name": "not_echo",
                                "stdin": "other\n",
                                "expected_stdout": "OTHER\n",
                            },
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", sandbox)

    assert sandbox.inputs == ["hello\n", "other\n"]
    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None and job.status == JobStatus.COMPLETED.value
        cases = session.query(CaseRow).filter_by(job_id=job_id).order_by(CaseRow.name).all()
        assert [(case.name, case.outcome) for case in cases] == [
            ("echo", "passed"),
            ("not_echo", "failed"),
        ]


def test_java_function_harness_records_sample_results() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { public int add(int a, int b) { for (int i=0; i<a; i++) { for (int j=0; j<b; j++) {} } return a + b; } }",
                    "problem": {
                        "statement": "Add both values.",
                        "interface": {"kind": "function", "entrypoint": "Solution.add"},
                        "samples": [
                            {
                                "kind": "function",
                                "name": "sum",
                                "args": [2, 3],
                                "expected": 5,
                            }
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", FakeJavaFunctionSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None and job.status == JobStatus.COMPLETED.value
        case = session.query(CaseRow).filter_by(job_id=job_id).one()
        assert case.name == "sum" and case.outcome == "passed"
        complexity = session.get(ComplexityRecord, job_id)
        assert complexity is not None
        assert complexity.method == "static_java_token_loop_depth"
        assert complexity.estimate == "O(n^2)"
        assert complexity.confidence == "low"
        assert complexity.details["code_analysis"]["language"] == "java"


def test_java_reference_generated_checks_are_persisted() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { public int solve(int value) { return value * 2; } }",
                    "reference_code": "class Reference { public int solve(int value) { return value * 2; } }",
                    "generated_tests": 2,
                    "seed": 12,
                    "problem": {
                        "statement": "Double a bounded integer.",
                        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                        "constraints": [{"path": "args[0]", "minimum": 1, "maximum": 5}],
                        "samples": [
                            {"kind": "function", "name": "example", "args": [2], "expected": 4}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-java-reference")

    run_claimed_job(session_factory, job_id, "worker-java-reference", FakeJavaReferenceSandbox())

    with session_factory() as session:
        job = session.get(Job, job_id)
        assert job is not None and job.status == JobStatus.COMPLETED.value
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert {case.name: case.outcome for case in cases} == {
            "example": "passed",
            "reference/example": "passed",
            "generated_1": "passed",
            "generated_2": "failed",
        }


def test_java_property_evidence_is_saved_without_adding_test_case_rows() -> None:
    session_factory = make_session_factory()
    property_code = (
        "class AxiomaProperties { static boolean check(Object[] args, Object result) "
        "{ return result.equals(((Number) args[0]).intValue() * 2); } }"
    )
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="java",
                input={
                    "code": "class Solution { int solve(int value) { return value * 2; } }",
                    "property_code": property_code,
                    "property_tests": 1,
                    "problem": {
                        "statement": "Double a value.",
                        "interface": {"kind": "function", "entrypoint": "Solution.solve"},
                        "samples": [
                            {"kind": "function", "name": "example", "args": [2], "expected": 4}
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-java-property")

    run_claimed_job(session_factory, job_id, "worker-java-property", FakeJavaPropertySandbox())

    with session_factory() as session:
        cases = session.query(CaseRow).filter_by(job_id=job_id).all()
        assert len(cases) == 1
        claims = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).all()
        property_claim = next(
            claim for claim in claims if claim.provenance["tool"] == "axioma-java-property-runner"
        )
        assert property_claim.provenance["details"]["state"] == "passed"
        assert property_claim.provenance["details"]["property_code"] == property_code


def test_reference_guided_cases_are_persisted_separately() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        job, _ = create_job(
            session,
            JobCreate(
                mode=JobMode.DSA_ANALYSIS,
                language="python",
                input={
                    "code": "def solve(value): return value * 2",
                    "reference_code": "def solve(value): return value * 2",
                    "generated_tests": 1,
                    "seed": 42,
                    "problem": {
                        "statement": "Double one number.",
                        "interface": {"kind": "function", "entrypoint": "solve"},
                        "constraints": [{"path": "args[0]", "minimum": 1, "maximum": 10}],
                        "samples": [
                            {
                                "kind": "function",
                                "name": "sample",
                                "args": [2],
                                "expected": 4,
                            }
                        ],
                    },
                },
            ),
        )
        job_id = job.id
        claim_next_job(session, "worker-test")

    run_claimed_job(session_factory, job_id, "worker-test", FakeReferenceSandbox())

    with session_factory() as session:
        rows = session.query(CaseRow).filter_by(job_id=job_id).order_by(CaseRow.name).all()
        assert [(row.name, row.outcome) for row in rows] == [
            ("generated_1", "passed"),
            ("reference/sample", "passed"),
            ("sample", "passed"),
        ]
        claim = session.query(EvidenceClaimRecord).filter_by(job_id=job_id).one()
        assert claim.provenance["details"]["seed"] == 42
        assert claim.provenance["details"]["generator_version"] == "problem-input-generator-v1"
        assert claim.provenance["details"]["generated_tests_actual"] == 1
