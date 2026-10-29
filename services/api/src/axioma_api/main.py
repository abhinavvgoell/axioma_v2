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
from axioma_api.jobs import create_job, transition_job
from axioma_api.models import (
    ComplexityRecord,
    EvidenceClaimRecord,
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


app = FastAPI(title="Axioma API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/problem-specs/match", response_model=ProblemCatalogMatchResponse)
def match_problem(payload: ProblemCatalogMatchRequest) -> ProblemCatalogMatchResponse:
    return match_problem_statement(payload.statement)


def catalog_source_for_problem(problem: ProblemSpec) -> str | None:
    match = match_problem_statement(problem.statement)
    if not match.recognized or match.problem is None:
        return None
    if match.problem.model_dump(mode="json") != problem.model_dump(mode="json"):
        return None
    return match.test_source


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
    test_pack_source = catalog_source_for_problem(payload.problem)
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
    test_pack_source = catalog_source_for_problem(payload.problem)
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language="java",
        input={
            "code": payload.code,
            "optimization_code": payload.optimization_code,
            "optimization_notes": payload.optimization_notes,
            "problem": payload.problem.model_dump(mode="json"),
            "test_pack_source": test_pack_source,
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
    request = JobCreate(
        mode=JobMode.DSA_ANALYSIS,
        language=payload.language,
        input={"code": payload.code, "problem": payload.problem.model_dump(mode="json")},
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
                details=complexity_row.details or {},
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
