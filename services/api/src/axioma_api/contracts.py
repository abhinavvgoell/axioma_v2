import math
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobMode(StrEnum):
    DSA_ANALYSIS = "dsa_analysis"
    REPOSITORY_REVIEW = "repository_review"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceType(StrEnum):
    EXECUTED = "executed"
    STATIC = "static"
    STATISTICAL = "statistical"
    MODEL = "model"
    UNVERIFIED = "unverified"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GateState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class ClaimProvenance(BaseModel):
    tool: str | None = None
    tool_version: str | None = None
    input_hash: str | None = None
    observed_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceClaim(BaseModel):
    id: str
    type: EvidenceType
    confidence: Confidence
    summary: str
    provenance: ClaimProvenance = Field(default_factory=ClaimProvenance)
    artifact_ids: list[str] = Field(default_factory=list)


class ComplexityResult(BaseModel):
    method: str
    estimate: str
    confidence: Confidence
    methods_disagree: bool
    explanation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TestResultSummary(BaseModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)

    model_config = ConfigDict(validate_assignment=True)

    def model_post_init(self, __context: Any) -> None:
        if self.total != self.passed + self.failed + self.skipped:
            raise ValueError("total must equal passed + failed + skipped")


class VerificationGate(BaseModel):
    order: int = Field(ge=0)
    name: str
    state: GateState
    evidence_claim_ids: list[str] = Field(default_factory=list)


class JobCreate(BaseModel):
    mode: JobMode
    language: str = Field(pattern="^(java|python)$")
    input: dict[str, Any]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class JobView(BaseModel):
    id: str
    mode: JobMode
    language: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress_message: str | None = None
    error_code: str | None = None


class JobEventView(BaseModel):
    id: int
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class TestCaseView(BaseModel):
    name: str
    outcome: Literal["passed", "failed", "skipped"]
    origin: Literal[
        "catalog_sample",
        "generated_differential",
        "reference_validation",
        "property_check",
        "program_execution",
        "unknown",
    ] = "unknown"
    duration_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    job_id: str
    claims: list[EvidenceClaim] = Field(default_factory=list)
    complexity: ComplexityResult | None = None
    tests: TestResultSummary = Field(
        default_factory=lambda: TestResultSummary(total=0, passed=0, failed=0, skipped=0)
    )
    test_cases: list[TestCaseView] = Field(default_factory=list)
    verification_gates: list[VerificationGate] = Field(default_factory=list)


class FunctionSample(BaseModel):
    kind: Literal["function"] = "function"
    name: str = Field(min_length=1, max_length=100)
    args: list[Any] = Field(default_factory=list, max_length=64)
    kwargs: dict[str, Any] = Field(default_factory=dict, max_length=64)
    expected: Any


class ComplexityBenchmarkSample(BaseModel):
    size: int = Field(ge=1, le=1_000_000_000)
    args: list[Any] = Field(default_factory=list, max_length=64)
    kwargs: dict[str, Any] = Field(default_factory=dict, max_length=64)
    strategy: Literal[
        "ascending",
        "descending",
        "all_equal",
        "duplicate_heavy",
        "alternating_low_high",
        "nearly_sorted",
        "repeated_characters",
    ] | None = None


class StdinStdoutSample(BaseModel):
    kind: Literal["stdin_stdout"] = "stdin_stdout"
    name: str = Field(min_length=1, max_length=100)
    stdin: str = Field(max_length=65536)
    expected_stdout: str = Field(max_length=65536)


SampleCase = Annotated[FunctionSample | StdinStdoutSample, Field(discriminator="kind")]


class FunctionInterface(BaseModel):
    kind: Literal["function"] = "function"
    entrypoint: str = Field(pattern=r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$", max_length=120)


class StdinStdoutInterface(BaseModel):
    kind: Literal["stdin_stdout"] = "stdin_stdout"


ProblemInterface = Annotated[
    FunctionInterface | StdinStdoutInterface,
    Field(discriminator="kind"),
]


class ConstraintRange(BaseModel):
    path: str = Field(
        pattern=r"^(args|kwargs|stdin)(\.[A-Za-z_]\w*|\[\d+\]|\.length)*$", max_length=120
    )
    minimum: int | float | None = None
    maximum: int | float | None = None
    description: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ConstraintRange":
        if self.minimum is None and self.maximum is None:
            raise ValueError("at least one of minimum or maximum is required")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot be greater than maximum")
        if isinstance(self.minimum, bool) or isinstance(self.maximum, bool):
            raise ValueError("boolean values are not valid numeric bounds")
        return self


class ProblemSpec(BaseModel):
    statement: str = Field(min_length=1, max_length=20000)
    interface: ProblemInterface
    constraints: list[ConstraintRange] = Field(default_factory=list, max_length=100)
    samples: list[SampleCase] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_sample_kinds(self) -> "ProblemSpec":
        if any(sample.kind != self.interface.kind for sample in self.samples):
            raise ValueError("sample kind must match the selected interface kind")
        return self


class ProblemCatalogMatchRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=20000)


class ProblemCatalogMatchResponse(BaseModel):
    recognized: bool
    match_state: Literal["matched", "not_found", "ambiguous"] = "not_found"
    candidate_titles: list[str] = Field(default_factory=list)
    slug: str | None = None
    title: str | None = None
    topics: list[str] = Field(default_factory=list)
    test_count: int = Field(default=0, ge=0)
    test_source: str | None = None
    problem: ProblemSpec | None = None


def exhaustive_argument_domains(problem: ProblemSpec, max_cases: int = 256) -> list[range]:
    """Validate and return bounded domains for exhaustive scalar positional checks."""
    if problem.interface.kind != "function" or not isinstance(problem.samples[0], FunctionSample):
        raise ValueError("exhaustive checks require a function interface")
    arity = len(problem.samples[0].args)
    if arity == 0 or any(
        not isinstance(sample, FunctionSample)
        or len(sample.args) != arity
        or sample.kwargs
        for sample in problem.samples
    ):
        raise ValueError("exhaustive checks require samples with the same positional scalar arguments and no kwargs")

    domains: dict[int, range] = {}
    for constraint in problem.constraints:
        match = re.fullmatch(r"args\[(\d+)\]", constraint.path)
        if match is None:
            raise ValueError("exhaustive checks support only direct positional integer arguments")
        index = int(match.group(1))
        if index in domains or index >= arity:
            raise ValueError("each exhaustive argument needs exactly one constraint")
        if type(constraint.minimum) is not int or type(constraint.maximum) is not int:
            raise ValueError("exhaustive argument constraints require integer minimum and maximum bounds")
        domains[index] = range(constraint.minimum, constraint.maximum + 1)

    if sorted(domains) != list(range(arity)):
        raise ValueError("each exhaustive argument needs exactly one integer range constraint")
    if any(type(value) is not int for sample in problem.samples for value in sample.args):
        raise ValueError("exhaustive samples must use integer positional arguments")
    domain_list = [domains[index] for index in range(arity)]
    total = math.prod(len(domain) for domain in domain_list)
    if total > max_cases:
        raise ValueError(f"exhaustive input space has {total} cases; maximum is {max_cases}")
    return domain_list


class Mode1JobCreate(BaseModel):
    language: str = Field(pattern="^(java|python)$")
    code: str = Field(min_length=1, max_length=65536)
    optimization_code: str | None = Field(default=None, min_length=1, max_length=65536)
    optimization_notes: str | None = Field(default=None, max_length=2000)
    property_code: str | None = Field(default=None, min_length=1, max_length=65536)
    property_tests: int = Field(default=0, ge=0, le=50)
    problem: ProblemSpec
    reference_code: str | None = Field(default=None, min_length=1, max_length=65536)
    independent_reference_code: str | None = Field(default=None, min_length=1, max_length=65536)
    generated_tests: int = Field(default=0, ge=0, le=50)
    exhaustive_tests: bool = False
    mutation_tests: int = Field(default=0, ge=0, le=20)
    complexity_benchmarks: list[ComplexityBenchmarkSample] = Field(
        default_factory=list, max_length=6
    )
    seed: int = Field(default=0, ge=0, le=4_294_967_295)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_reference_settings(self) -> "Mode1JobCreate":
        if self.generated_tests and not self.reference_code:
            raise ValueError("generated_tests requires a reference_code")
        if self.exhaustive_tests:
            if not self.reference_code:
                raise ValueError("exhaustive_tests requires a reference_code")
            if self.generated_tests:
                raise ValueError("exhaustive_tests cannot be combined with generated_tests")
            exhaustive_argument_domains(self.problem)
        if self.mutation_tests and not self.reference_code:
            raise ValueError("mutation_tests requires a reference_code")
        if self.independent_reference_code and not self.reference_code:
            raise ValueError("independent_reference_code requires a reference_code")
        if self.independent_reference_code == self.reference_code and self.reference_code:
            raise ValueError("independent_reference_code must differ from reference_code")
        if self.reference_code and self.problem.interface.kind != "function":
            raise ValueError("reference_code currently requires a function interface")
        if self.independent_reference_code and self.problem.interface.kind != "function":
            raise ValueError("independent_reference_code currently requires a function interface")
        if self.optimization_code and self.problem.interface.kind != "function":
            raise ValueError("optimization_code currently requires a function interface")
        if self.optimization_notes and not self.optimization_code:
            raise ValueError("optimization_notes requires optimization_code")
        if bool(self.property_code) != bool(self.property_tests):
            raise ValueError("property_code and property_tests must be provided together")
        if self.property_code and (self.problem.interface.kind != "function"):
            raise ValueError("property checks currently require a function interface")
        if self.language == "java" and self.property_code:
            entrypoint_class = self.problem.interface.entrypoint.split(".", maxsplit=1)[0]
            if entrypoint_class == "AxiomaProperties":
                raise ValueError(
                    "Java submission class name cannot be AxiomaProperties when using properties"
                )
        if self.language == "java" and self.optimization_code:
            entrypoint_class = self.problem.interface.entrypoint.split(".", maxsplit=1)[0]
            if entrypoint_class == "AxiomaOptimized":
                raise ValueError(
                    "Java submission class name cannot be AxiomaOptimized when using an optimization"
                )
        if self.mutation_tests and self.problem.interface.kind != "function":
            raise ValueError("mutation_tests currently require a function job")
        if self.language == "java" and self.reference_code:
            entrypoint_class = self.problem.interface.entrypoint.split(".", maxsplit=1)[0]
            if entrypoint_class == "Reference":
                raise ValueError(
                    "Java submission class name cannot be Reference when using a reference"
                )
        if self.language == "java" and self.independent_reference_code:
            entrypoint_class = self.problem.interface.entrypoint.split(".", maxsplit=1)[0]
            if entrypoint_class == "ReferenceIndependent":
                raise ValueError(
                    "Java submission class name cannot be ReferenceIndependent when using an independent reference"
                )
            if not self.reference_code:
                raise ValueError("independent_reference_code requires reference_code")
        if self.complexity_benchmarks:
            if self.problem.interface.kind != "function":
                raise ValueError("complexity benchmarks currently require a function job")
            sizes = [sample.size for sample in self.complexity_benchmarks]
            if len(sizes) < 4 or sizes != sorted(set(sizes)):
                raise ValueError(
                    "complexity benchmarks require at least four increasing unique sizes"
                )
            if self.language == "java" and any(sample.kwargs for sample in self.complexity_benchmarks):
                raise ValueError("Java complexity benchmarks currently support positional arguments only")
        return self


class OptimizationProposalRequest(BaseModel):
    language: Literal["python", "java"]
    code: str = Field(min_length=1, max_length=65536)
    problem: ProblemSpec


class OptimizationProposal(BaseModel):
    rule_id: str
    title: str
    summary: str
    evidence_type: Literal["static"] = "static"
    confidence: Confidence = Confidence.LOW
    candidate_code: str
    limitations: list[str]


class OptimizationProposalResponse(BaseModel):
    proposals: list[OptimizationProposal] = Field(default_factory=list)
    message: str


class ProblemSpecIssue(BaseModel):
    sample: str
    path: str
    message: str


class ProblemSpecValidation(BaseModel):
    valid: bool
    samples_checked: int = Field(ge=0)
    issues: list[ProblemSpecIssue] = Field(default_factory=list)


class ProblemInputGenerationRequest(BaseModel):
    problem: ProblemSpec
    count: int = Field(default=10, ge=1, le=100)
    seed: int = Field(default=0, ge=0, le=4_294_967_295)


class GeneratedInputCase(BaseModel):
    name: str
    kind: Literal["function", "stdin_stdout"]
    strategy: str = "random_constraint_sample"
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    stdin: str | None = None


class ProblemInputGenerationResult(BaseModel):
    seed: int
    requested: int = Field(ge=1)
    generated: int = Field(ge=0)
    cases: list[GeneratedInputCase] = Field(default_factory=list)


class ComplexityBenchmarkGenerationRequest(BaseModel):
    problem: ProblemSpec
    size_path: str = Field(pattern=r"^(args|kwargs)(\.[A-Za-z_]\w*|\[\d+\])*\.length$", max_length=120)
    sizes: list[int] = Field(min_length=4, max_length=6)
    pattern: Literal[
        "ascending",
        "descending",
        "all_equal",
        "duplicate_heavy",
        "alternating_low_high",
        "nearly_sorted",
        "repeated_characters",
    ]
    seed: int = Field(default=0, ge=0, le=4_294_967_295)

    @model_validator(mode="after")
    def validate_benchmark_request(self) -> "ComplexityBenchmarkGenerationRequest":
        if not isinstance(self.problem.interface, FunctionInterface):
            raise ValueError("complexity benchmark generation requires a function interface")
        if self.sizes != sorted(set(self.sizes)):
            raise ValueError("benchmark sizes must be unique and strictly increasing")
        if any(size < 1 or size > 10_000 for size in self.sizes):
            raise ValueError("generated benchmark sizes must be between 1 and 10000")
        length_constraints = [
            constraint
            for constraint in self.problem.constraints
            if constraint.path == self.size_path
        ]
        if len(length_constraints) != 1:
            raise ValueError("size_path must have exactly one matching collection-length constraint")
        constraint = length_constraints[0]
        if any(
            type(bound) is not int
            for bound in (constraint.minimum, constraint.maximum)
            if bound is not None
        ):
            raise ValueError("generated benchmark sizes require integer length bounds")
        if any(
            (constraint.minimum is not None and size < constraint.minimum)
            or (constraint.maximum is not None and size > constraint.maximum)
            for size in self.sizes
        ):
            raise ValueError("every benchmark size must fit the declared length constraint")
        return self


class ComplexityBenchmarkGenerationResult(BaseModel):
    seed: int
    size_path: str
    pattern: str
    benchmarks: list[ComplexityBenchmarkSample]
    limitations: list[str]
