import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from axioma_api.config import get_settings
from axioma_api.contracts import (
    AnalysisReport,
    ClaimProvenance,
    ComplexityResult,
    EvidenceClaim,
    EvidenceType,
    Confidence,
    ProblemInputGenerationRequest,
    ProblemInputGenerationResult,
    ProblemCatalogMatchRequest,
    ProblemCatalogMatchResponse,
    ComplexityBenchmarkGenerationRequest,
    ComplexityBenchmarkGenerationResult,
    OptimizationProposalRequest,
    OptimizationProposalResponse,
    GemmaReviewRequest,
    GemmaReviewResponse,
    GateState,
    JobCreate,
    JobEventView,
    JobMode,
    Mode1JobCreate,
    ProblemSpec,
    ProblemSpecValidation,
    JobStatus,
    JobView,
    TestResultSummary,
    TestCaseView,
    VerificationGate,
)
from axioma_api.database import get_session, get_session_factory
from axioma_api.jobs import canonical_hash, create_job, transition_job
from axioma_api.models import (
    ComplexityRecord,
    EvidenceClaimRecord,
    InputSnapshotRecord,
    Job,
    JobEvent,
    TestCaseRecord,
    VerificationGateRecord,
)
from axioma_api.problem_validation import validate_problem_spec
from axioma_api.problem_generation import (
    generate_complexity_benchmarks,
    generate_problem_inputs,
)
from axioma_api.problem_catalog import match_problem_statement
from axioma_api.optimization_proposals import propose_optimizations
from axioma_api.gemma_review import GemmaReviewError, generate_gemma_review
from uuid import uuid4


app = FastAPI(title="Axioma API", version="0.1.0")


def _expected_benchmark_snapshot_keys(benchmark_inputs: object) -> list[str] | None:
    if not isinstance(benchmark_inputs, list) or not benchmark_inputs:
        return None
    keys = []
    for index, benchmark in enumerate(benchmark_inputs):
        if not isinstance(benchmark, dict) or type(benchmark.get("size")) is not int:
            return None
        keys.append(f"benchmark/{index:03d}/{benchmark['size']}")
    return keys


def _benchmark_snapshots_match(
    benchmark_inputs: object, snapshots: list[InputSnapshotRecord]
) -> bool:
    expected_keys = _expected_benchmark_snapshot_keys(benchmark_inputs)
    if (
        expected_keys is None
        or not isinstance(benchmark_inputs, list)
        or len(snapshots) != len(expected_keys)
    ):
        return False
    snapshots_by_key = {snapshot.snapshot_key: snapshot for snapshot in snapshots}
    if set(snapshots_by_key) != set(expected_keys):
        return False
    if any(not isinstance(snapshot.input_snapshot, dict) for snapshot in snapshots):
        return False
    if any(
        canonical_hash(snapshot.input_snapshot) != snapshot.input_sha256
        for snapshot in snapshots
    ):
        return False
    return all(
        snapshots_by_key[key].input_snapshot.get("size") == benchmark["size"]
        for key, benchmark in zip(expected_keys, benchmark_inputs, strict=True)
    )


def _test_input_preview(
    case_name: str, snapshots: list[InputSnapshotRecord]
) -> dict[str, object] | None:
    base_name = case_name
    for prefix in ("reference/", "optimization/"):
        if base_name.startswith(prefix):
            base_name = base_name[len(prefix) :]
            break

    exact_keys = {f"generated/{base_name}", f"property/{base_name}"}
    if base_name.startswith("property/"):
        exact_keys.add(base_name)
    matches = [
        snapshot
        for snapshot in snapshots
        if snapshot.snapshot_key in exact_keys
        or (
            snapshot.snapshot_key.startswith("sample/")
            and snapshot.snapshot_key.endswith(f"/{base_name}")
        )
    ]
    if len(matches) != 1:
        return None

    snapshot = matches[0]
    if (
        not isinstance(snapshot.input_snapshot, dict)
        or canonical_hash(snapshot.input_snapshot) != snapshot.input_sha256
    ):
        return None
    data = {
        key: snapshot.input_snapshot[key]
        for key in ("args", "kwargs", "stdin")
        if key in snapshot.input_snapshot
    }
    if not data:
        return None

    serialized = json.dumps(data, ensure_ascii=True, separators=(",", ":"), default=str)
    truncated = len(serialized) > 2048
    if truncated:
        data = {"preview": serialized[:2000] + "…"}
    return {"data": data, "sha256": snapshot.input_sha256, "truncated": truncated}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/problem-specs/match", response_model=ProblemCatalogMatchResponse)
def match_problem(payload: ProblemCatalogMatchRequest) -> ProblemCatalogMatchResponse:
    return match_problem_statement(payload.statement)


def catalog_source_for_problem(problem: ProblemSpec) -> str | None:
    identity = catalog_identity_for_problem(problem)
    return str(identity["source"]) if identity else None


def catalog_identity_for_problem(problem: ProblemSpec) -> dict[str, str] | None:
    match = match_problem_statement(problem.statement)
    if not match.recognized or match.problem is None:
        return None
    if match.problem.model_dump(mode="json") != problem.model_dump(mode="json"):
        return None
    return {
        "slug": match.slug or "",
        "title": match.title or "",
        "source": match.test_source or "",
    }


@app.post("/v1/problem-specs/validate", response_model=ProblemSpecValidation)
def validate_problem(payload: ProblemSpec) -> ProblemSpecValidation:
    return validate_problem_spec(payload)


@app.post("/v1/problem-specs/generate-inputs", response_model=ProblemInputGenerationResult)
def generate_problem_input_cases(
    payload: ProblemInputGenerationRequest,
) -> ProblemInputGenerationResult:
    return generate_problem_inputs(payload)


@app.post(
    "/v1/problem-specs/generate-complexity-benchmarks",
    response_model=ComplexityBenchmarkGenerationResult,
)
def generate_complexity_benchmark_inputs(
    payload: ComplexityBenchmarkGenerationRequest,
) -> ComplexityBenchmarkGenerationResult:
    validation = validate_problem_spec(payload.problem)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump(mode="json"))
    try:
        return generate_complexity_benchmarks(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/v1/optimization-proposals",
    response_model=OptimizationProposalResponse,
)
def propose_mode1_optimization(
    payload: OptimizationProposalRequest,
) -> OptimizationProposalResponse:
    if payload.problem.interface.kind != "function":
        raise HTTPException(
            status_code=422,
            detail="Rule-based optimization proposals currently require a function interface",
        )
    validation = validate_problem_spec(payload.problem)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump(mode="json"))
    return propose_optimizations(payload.language, payload.code, payload.problem)


@app.post("/v1/gemma-review", response_model=GemmaReviewResponse)
def review_with_gemma(
    payload: GemmaReviewRequest, session: Session = Depends(get_session)
) -> GemmaReviewResponse:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemma 4 is not configured. Set GEMINI_API_KEY in the API environment.",
        )
    job = session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if job.mode != JobMode.DSA_ANALYSIS.value:
        raise HTTPException(status_code=409, detail="Gemma review requires a Mode 1 analysis")
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Run Axioma analysis before asking Gemma to review")
    problem = job.input_payload.get("problem")
    code = job.input_payload.get("code")
    if not isinstance(problem, dict) or not isinstance(code, str):
        raise HTTPException(status_code=409, detail="This run does not contain reviewable source")
    problem_statement = problem.get("statement")
    if not isinstance(problem_statement, str):
        raise HTTPException(status_code=409, detail="This run does not contain a problem statement")
    if payload.language != job.language or payload.code != code:
        raise HTTPException(
            status_code=409,
            detail="The current language or code differs from this saved run. Run Axioma again before asking Gemma.",
        )
    current_match = match_problem_statement(payload.problem_statement)
    saved_identity = job.input_payload.get("problem_pack_identity")
    saved_slug = saved_identity.get("slug") if isinstance(saved_identity, dict) else None
    saved_title = problem.get("title")
    same_problem = (
        bool(current_match.recognized and current_match.slug == saved_slug)
        if saved_slug
        else payload.problem_statement.strip().casefold()
        in {problem_statement.strip().casefold(), str(saved_title or "").strip().casefold()}
    )
    if not same_problem:
        raise HTTPException(
            status_code=409,
            detail="The current problem differs from this saved run. Run Axioma again before asking Gemma.",
        )
    report = get_job_result(payload.job_id, session)
    complexity = report.complexity
    analysis_details = complexity.details.get("code_analysis", {}) if complexity else {}
    signals = analysis_details.get("signals", []) if isinstance(analysis_details, dict) else []
    limitations = analysis_details.get("limitations", []) if isinstance(analysis_details, dict) else []
    failed_cases = []

    def bounded_value(value: object, limit: int = 500) -> object:
        serialized = json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)
        if len(serialized) <= limit:
            return value
        return serialized[: limit - 1] + "…"

    for case in report.test_cases:
        if case.outcome != "failed" or len(failed_cases) >= 5:
            continue
        details = case.details if isinstance(case.details, dict) else {}
        diagnostic = next(
            (
                details.get(key)
                for key in ("error", "reason", "stderr", "message")
                if isinstance(details.get(key), str) and details.get(key).strip()
            ),
            None,
        )
        failed_cases.append(
            {
                "name": case.name,
                "failure_kind": details.get("failure_kind", "unknown"),
                "expected": bounded_value(details.get("expected", details.get("expected_stdout"))),
                "observed": bounded_value(
                    details.get("actual", details.get("observed", details.get("actual_stdout")))
                ),
                "input": bounded_value(case.input_preview.data, 800) if case.input_preview else None,
                "diagnostic": bounded_value(diagnostic, 800) if diagnostic else None,
                "source_location": bounded_value(details.get("source_location"))
                if details.get("source_location")
                else None,
            }
        )
    axioma_evidence = {
        "test_counts": report.tests.model_dump(),
        "complexity_estimate": (
            {
                "estimate": complexity.estimate,
                "method": complexity.method,
                "confidence": complexity.confidence.value,
                "methods_disagree": complexity.methods_disagree,
                "explanation": complexity.explanation,
            }
            if complexity
            else None
        ),
        "code_signals": [
            {key: signal[key] for key in ("kind", "label", "line") if key in signal}
            for signal in signals[:8]
            if isinstance(signal, dict)
        ],
        "failed_cases": failed_cases,
        "sample_passed_names": [
            case.name for case in report.test_cases if case.outcome == "passed"
        ][:3],
        "analysis_limitations": [str(item)[:240] for item in limitations[:5]],
    }
    try:
        advisory = generate_gemma_review(
            api_key=settings.gemini_api_key,
            model=settings.gemma_model,
            language=job.language,
            code=code,
            problem_statement=problem_statement,
            axioma_evidence=axioma_evidence,
        )
    except GemmaReviewError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GemmaReviewResponse(
        model=settings.gemma_model,
        advisory=advisory,
        axioma_evidence=axioma_evidence,
        limitations=[
            "Gemma's comments are model advice and are not independently verified.",
            "Test outcomes and the complexity estimate come from this saved Axioma run.",
        ],
    )


@app.post("/v1/jobs/mode1/python-function", response_model=JobView, status_code=202)
def submit_python_function_job(
    payload: Mode1JobCreate,
    response: Response,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Job:
    if payload.language != "python":
        raise HTTPException(status_code=422, detail="This route currently supports Python only")
    if payload.problem.interface.kind != "function":
        raise HTTPException(status_code=422, detail="This route requires a function interface")
    validation = validate_problem_spec(payload.problem)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump(mode="json"))
    problem_pack_identity = catalog_identity_for_problem(payload.problem)
    test_pack_source = problem_pack_identity["source"] if problem_pack_identity else None
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language="python",
        input={
            "code": payload.code,
            "optimization_code": payload.optimization_code,
            "optimization_notes": payload.optimization_notes,
            "property_code": payload.property_code,
            "property_tests": payload.property_tests,
            "problem": payload.problem.model_dump(mode="json"),
            "test_pack_source": test_pack_source,
            "problem_pack_identity": problem_pack_identity,
            "reference_code": payload.reference_code,
            "independent_reference_code": payload.independent_reference_code,
            "generated_tests": payload.generated_tests,
            "exhaustive_tests": payload.exhaustive_tests,
            "mutation_tests": payload.mutation_tests,
            "complexity_benchmarks": [
                sample.model_dump(mode="json") for sample in payload.complexity_benchmarks
            ],
            "seed": payload.seed,
        },
        idempotency_key=idempotency_header or payload.idempotency_key,
    )
    try:
        job, created = create_job(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@app.post("/v1/jobs/mode1/java-function", response_model=JobView, status_code=202)
def submit_java_function_job(
    payload: Mode1JobCreate,
    response: Response,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Job:
    if payload.language != "java":
        raise HTTPException(status_code=422, detail="This route requires Java")
    if payload.problem.interface.kind != "function":
        raise HTTPException(status_code=422, detail="This route requires a function interface")
    if "." not in payload.problem.interface.entrypoint:
        raise HTTPException(
            status_code=422, detail="Java function entrypoints must use ClassName.methodName"
        )
    validation = validate_problem_spec(payload.problem)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump(mode="json"))
    problem_pack_identity = catalog_identity_for_problem(payload.problem)
    test_pack_source = problem_pack_identity["source"] if problem_pack_identity else None
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language="java",
        input={
            "code": payload.code,
            "optimization_code": payload.optimization_code,
            "optimization_notes": payload.optimization_notes,
            "problem": payload.problem.model_dump(mode="json"),
            "test_pack_source": test_pack_source,
            "problem_pack_identity": problem_pack_identity,
            "reference_code": payload.reference_code,
            "independent_reference_code": payload.independent_reference_code,
            "generated_tests": payload.generated_tests,
            "exhaustive_tests": payload.exhaustive_tests,
            "seed": payload.seed,
            "property_code": payload.property_code,
            "property_tests": payload.property_tests,
            "mutation_tests": payload.mutation_tests,
            "complexity_benchmarks": [
                sample.model_dump(mode="json") for sample in payload.complexity_benchmarks
            ],
        },
        idempotency_key=idempotency_header or payload.idempotency_key,
    )
    try:
        job, created = create_job(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@app.post("/v1/jobs/mode1/stdin-stdout", response_model=JobView, status_code=202)
def submit_stdin_stdout_job(
    payload: Mode1JobCreate,
    response: Response,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Job:
    if payload.problem.interface.kind != "stdin_stdout":
        raise HTTPException(status_code=422, detail="This route requires a stdin/stdout interface")
    validation = validate_problem_spec(payload.problem)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump(mode="json"))
    problem_pack_identity = catalog_identity_for_problem(payload.problem)
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language=payload.language,
        input={
            "code": payload.code,
            "problem": payload.problem.model_dump(mode="json"),
            "test_pack_source": problem_pack_identity["source"] if problem_pack_identity else None,
            "problem_pack_identity": problem_pack_identity,
        },
        idempotency_key=idempotency_header or payload.idempotency_key,
    )
    try:
        job, created = create_job(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@app.post("/v1/jobs", response_model=JobView, status_code=status.HTTP_202_ACCEPTED)
def submit_job(
    payload: JobCreate,
    response: Response,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Job:
    if idempotency_header:
        payload = payload.model_copy(update={"idempotency_key": idempotency_header})
    try:
        job, created = create_job(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@app.get("/v1/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/v1/jobs/{job_id}/benchmarks/replay", response_model=JobView, status_code=202)
def replay_job_benchmarks(
    job_id: str,
    response: Response,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> Job:
    source_job = session.get(Job, job_id)
    if source_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if source_job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Only completed analysis jobs can be replayed")

    snapshots = session.scalars(
        select(InputSnapshotRecord)
        .where(
            InputSnapshotRecord.job_id == job_id,
            InputSnapshotRecord.origin.in_(
                {"generated_benchmark", "user_benchmark", "benchmark_replay"}
            ),
        )
        .order_by(InputSnapshotRecord.snapshot_key)
    ).all()
    if not snapshots:
        raise HTTPException(
            status_code=409,
            detail="This historical job has no persisted benchmark inputs and is non-replayable.",
        )
    for snapshot in snapshots:
        if canonical_hash(snapshot.input_snapshot) != snapshot.input_sha256:
            raise HTTPException(
                status_code=409,
                detail=f"Stored benchmark input {snapshot.snapshot_key} failed its integrity check.",
            )
    benchmark_inputs = source_job.input_payload.get("complexity_benchmarks", [])
    if not _benchmark_snapshots_match(benchmark_inputs, snapshots):
        raise HTTPException(
            status_code=409,
            detail=(
                "Persisted benchmark snapshots do not exactly match the declared benchmark inputs; "
                "this job is non-replayable."
            ),
        )
    snapshots_by_key = {snapshot.snapshot_key: snapshot for snapshot in snapshots}
    snapshots = [
        snapshots_by_key[key]
        for key in _expected_benchmark_snapshot_keys(benchmark_inputs) or []
    ]

    replay_benchmarks: list[dict] = []
    replay_sources: list[dict] = []
    for snapshot in snapshots:
        replay_benchmarks.append(
            {
                "size": snapshot.input_snapshot["size"],
                "args": snapshot.input_snapshot.get("args", []),
                "kwargs": snapshot.input_snapshot.get("kwargs", {}),
                "generator_version": snapshot.generator_version,
                "generator_artifact_sha256": snapshot.generator_artifact_sha256,
                "seed": snapshot.seed,
                "size_path": snapshot.size_path,
                "strategy": snapshot.strategy,
            }
        )
        replay_sources.append(
            {
                "snapshot_id": snapshot.id,
                "snapshot_key": snapshot.snapshot_key,
                "origin": snapshot.origin,
                "input_sha256": snapshot.input_sha256,
                "original_runtime_configuration": snapshot.runtime_configuration,
            }
        )

    replay_input = dict(source_job.input_payload)
    replay_input.update(
        {
            "complexity_benchmarks": replay_benchmarks,
            "generated_tests": 0,
            "exhaustive_tests": False,
            "property_code": None,
            "property_tests": 0,
            "mutation_tests": 0,
            "optimization_code": None,
            "optimization_notes": None,
            "benchmark_replay": {
                "source_job_id": source_job.id,
                "snapshots": replay_sources,
                "timing_note": (
                    "Inputs were replayed exactly; elapsed timings can differ across runs, machines, "
                    "and runtime environments."
                ),
            },
        }
    )
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language=source_job.language,
        input=replay_input,
        idempotency_key=idempotency_header or f"benchmark-replay-{uuid4()}",
    )
    try:
        replay_job, created = create_job(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return replay_job


@app.get("/v1/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> StreamingResponse:
    with session_factory() as session:
        if session.get(Job, job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
    try:
        after_id = max(0, int(last_event_id or 0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer") from exc

    async def events() -> AsyncIterator[str]:
        nonlocal after_id
        while not await request.is_disconnected():
            with session_factory() as session:
                rows = session.scalars(
                    select(JobEvent)
                    .where(JobEvent.job_id == job_id, JobEvent.id > after_id)
                    .order_by(JobEvent.id)
                    .limit(100)
                ).all()
                current_job = session.get(Job, job_id)
                terminal = current_job and JobStatus(current_job.status) in {
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                }
                for row in rows:
                    event = JobEventView(
                        id=row.id,
                        job_id=row.job_id,
                        status=row.status,
                        message=row.message,
                        created_at=row.created_at,
                    )
                    yield f"id: {row.id}\nevent: job_status\ndata: {event.model_dump_json()}\n\n"
                    after_id = row.id
                if terminal and not rows:
                    return
            yield ": keep-alive\n\n"
            await asyncio.sleep(get_settings().job_event_poll_seconds)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.post("/v1/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        job.lease_owner = None
        job.lease_expires_at = None
        return transition_job(session, job, JobStatus.CANCELLED, "Cancellation requested")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/jobs/{job_id}/result", response_model=AnalysisReport)
def get_job_result(job_id: str, session: Session = Depends(get_session)) -> AnalysisReport:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Job has no completed result")
    claim_rows = session.scalars(
        select(EvidenceClaimRecord)
        .where(EvidenceClaimRecord.job_id == job_id)
        .order_by(EvidenceClaimRecord.id)
    ).all()
    complexity_row = session.get(ComplexityRecord, job_id)
    complexity_details = dict(complexity_row.details or {}) if complexity_row else {}
    benchmark_inputs = job.input_payload.get("complexity_benchmarks", [])
    if complexity_row and benchmark_inputs:
        benchmark_snapshots = session.scalars(
            select(InputSnapshotRecord).where(
                InputSnapshotRecord.job_id == job_id,
                InputSnapshotRecord.origin.in_(
                    {"generated_benchmark", "user_benchmark", "benchmark_replay"}
                ),
            )
        ).all()
        snapshot_count = len(benchmark_snapshots)
        benchmark_provenance = dict(complexity_details.get("benchmark_provenance") or {})
        benchmark_provenance["replay_state"] = (
            "replayable"
            if _benchmark_snapshots_match(benchmark_inputs, benchmark_snapshots)
            else "non_replayable"
        )
        benchmark_provenance["snapshot_count"] = snapshot_count
        complexity_details["benchmark_provenance"] = benchmark_provenance
    gate_rows = session.scalars(
        select(VerificationGateRecord)
        .where(VerificationGateRecord.job_id == job_id)
        .order_by(VerificationGateRecord.gate_order)
    ).all()
    case_counts = dict(
        session.execute(
            select(TestCaseRecord.outcome, func.count())
            .where(TestCaseRecord.job_id == job_id)
            .group_by(TestCaseRecord.outcome)
        ).all()
    )
    passed = case_counts.get("passed", 0)
    failed = case_counts.get("failed", 0)
    skipped = case_counts.get("skipped", 0)
    test_case_rows = session.scalars(
        select(TestCaseRecord)
        .where(TestCaseRecord.job_id == job_id)
        .order_by(TestCaseRecord.name, TestCaseRecord.id)
    ).all()
    test_input_snapshots = session.scalars(
        select(InputSnapshotRecord).where(
            InputSnapshotRecord.job_id == job_id,
            InputSnapshotRecord.origin.in_(
                {
                    "imported_sample",
                    "user_sample",
                    "generated_differential",
                    "exhaustive_generated",
                    "generated_property",
                }
            ),
        )
    ).all()

    def test_case_origin(name: str, details: dict) -> str:
        recorded_origin = details.get("origin")
        if recorded_origin in {
            "catalog_sample",
            "generated_differential",
            "reference_validation",
            "property_check",
            "program_execution",
            "unknown",
        }:
            return recorded_origin
        if name.startswith("reference/"):
            return "reference_validation"
        if name.startswith("generated_"):
            return "generated_differential"
        if name.startswith("property/"):
            return "property_check"
        if name == "program_exit":
            return "program_execution"
        return "unknown"

    def safe_case_details(details: dict) -> dict:
        serialized = json.dumps(details, ensure_ascii=True, separators=(",", ":"), default=str)
        if len(serialized) <= 4096:
            return details
        return {"truncated": True, "preview": serialized[:4000]}

    return AnalysisReport(
        job_id=job_id,
        claims=[
            EvidenceClaim(
                id=row.id,
                type=EvidenceType(row.evidence_type),
                confidence=Confidence(row.confidence),
                summary=row.summary,
                provenance=ClaimProvenance.model_validate(row.provenance),
                artifact_ids=row.artifact_ids,
            )
            for row in claim_rows
        ],
        complexity=(
            ComplexityResult(
                method=complexity_row.method,
                estimate=complexity_row.estimate,
                confidence=Confidence(complexity_row.confidence),
                methods_disagree=complexity_row.methods_disagree,
                explanation=complexity_row.explanation,
                details=complexity_details,
            )
            if complexity_row
            else None
        ),
        tests=TestResultSummary(
            total=passed + failed + skipped,
            passed=passed,
            failed=failed,
            skipped=skipped,
        ),
        test_cases=[
            TestCaseView(
                name=row.name,
                outcome=row.outcome,
                origin=test_case_origin(row.name, row.details or {}),
                duration_ms=row.duration_ms,
                details=safe_case_details(row.details or {}),
                input_preview=_test_input_preview(row.name, test_input_snapshots),
            )
            for row in test_case_rows
        ],
        verification_gates=[
            VerificationGate(
                order=row.gate_order,
                name=row.name,
                state=GateState(row.state),
                evidence_claim_ids=row.evidence_claim_ids,
            )
            for row in gate_rows
        ],
    )
