from __future__ import annotations

import copy
import itertools
import json
import math
import random
import re
from typing import Any

from axioma_api.contracts import (
    ConstraintRange,
    ComplexityBenchmarkGenerationRequest,
    ComplexityBenchmarkGenerationResult,
    ComplexityBenchmarkSample,
    FunctionSample,
    GeneratedInputCase,
    ProblemInputGenerationRequest,
    ProblemInputGenerationResult,
    ProblemSpec,
    StdinStdoutSample,
    exhaustive_argument_domains,
)
from axioma_api.problem_validation import validate_problem_spec

_PATH_PART = re.compile(r"\.([A-Za-z_]\w*)|\[(\d+)\]")
_ROOT = re.compile(r"^(args|kwargs|stdin)")


def _path_parts(path: str) -> tuple[str, list[str | int]]:
    root_match = _ROOT.match(path)
    if root_match is None:
        raise ValueError(f"Unsupported constraint path: {path}")
    root = root_match.group(1)
    offset = len(root)
    parts: list[str | int] = []
    while offset < len(path):
        match = _PATH_PART.match(path, offset)
        if match is None:
            raise ValueError(f"Unsupported constraint path: {path}")
        parts.append(match.group(1) if match.group(1) is not None else int(match.group(2)))
        offset = match.end()
    return root, parts


def _get_child(parent: Any, part: str | int) -> Any:
    if part == "length":
        if not isinstance(parent, (str, list, dict)):
            raise ValueError("length constraint requires a string, list, or object")
        return len(parent)
    if isinstance(part, int):
        if not isinstance(parent, list) or part >= len(parent):
            raise ValueError("sample does not contain the constrained index")
        return parent[part]
    if not isinstance(parent, dict) or part not in parent:
        raise ValueError(f"sample does not contain the constrained field {part!r}")
    return parent[part]


def _get_value(case: dict[str, Any], path: str) -> Any:
    root, parts = _path_parts(path)
    value: Any = case.get(root)
    if value is None:
        raise ValueError(f"sample does not contain {root}")
    for part in parts:
        value = _get_child(value, part)
    return value


def _replace_length(value: Any, length: int, rng: random.Random) -> Any:
    if isinstance(value, str):
        unit = value[:1] or "x"
        return unit * length
    if isinstance(value, list):
        unit = value[0] if value else 0
        return [copy.deepcopy(rng.choice(value)) if value else unit for _ in range(length)]
    if isinstance(value, dict):
        items = list(value.values())
        unit = items[0] if items else 0
        return {
            (list(value.keys())[index] if index < len(value) else f"item_{index}"): copy.deepcopy(
                items[index % len(items)] if items else unit
            )
            for index in range(length)
        }
    raise ValueError("length constraint requires a string, list, or object")


def _set_path(parent: Any, parts: list[str | int], value: Any, rng: random.Random) -> Any:
    if not parts:
        return value
    part, *remaining = parts
    if part == "length":
        if remaining:
            raise ValueError("length must be the final part of a constraint path")
        return _replace_length(parent, value, rng)
    if isinstance(part, int):
        if not isinstance(parent, list):
            raise ValueError("index constraint requires a list")
        while len(parent) <= part:
            parent.append("" if remaining and remaining[0] == "length" else {})
        parent[part] = _set_path(parent[part], remaining, value, rng)
        return parent
    if not isinstance(parent, dict):
        raise ValueError("field constraint requires an object")
    if remaining:
        default: Any = (
            "" if remaining == ["length"] else {} if isinstance(remaining[0], str) else []
        )
        child = parent.setdefault(part, default)
        parent[part] = _set_path(child, remaining, value, rng)
    else:
        parent[part] = value
    return parent


def _set_value(case: dict[str, Any], path: str, value: Any, rng: random.Random) -> None:
    root, parts = _path_parts(path)
    if root not in case or case[root] is None:
        case[root] = [] if root == "args" else {} if root == "kwargs" else ""
    case[root] = _set_path(case[root], parts, value, rng)


def _collection_for_length_path(case: dict[str, Any], path: str) -> Any:
    root, parts = _path_parts(path)
    if not parts or parts[-1] != "length":
        return None
    value: Any = case.get(root)
    for part in parts[:-1]:
        value = _get_child(value, part)
    return value


def _random_numeric_value(
    current: Any, minimum: int | float | None, maximum: int | float | None, rng: random.Random
) -> int | float:
    if minimum is None and maximum is None:
        raise ValueError("numeric generation requires at least one bound")
    pivot = current if isinstance(current, (int, float)) and not isinstance(current, bool) else 0
    low = minimum if minimum is not None else min(pivot - 100, maximum - 100)  # type: ignore[operator]
    high = maximum if maximum is not None else max(pivot + 100, minimum + 100)  # type: ignore[operator]
    if low > high:
        raise ValueError("constraint bounds do not contain a value")
    if isinstance(low, float) or isinstance(high, float) or isinstance(pivot, float):
        return rng.uniform(float(low), float(high))
    return rng.randint(math.ceil(low), math.floor(high))


def _candidate_case(
    problem: ProblemSpec,
    sample: FunctionSample | StdinStdoutSample,
    constraints: list[ConstraintRange],
    rng: random.Random,
    focus: tuple[str, int | float] | None = None,
    pattern: tuple[str, str] | None = None,
) -> dict[str, Any] | None:
    case = sample.model_dump(mode="json")
    try:
        for constraint in constraints:
            current = _get_value(case, constraint.path)
            value = _random_numeric_value(current, constraint.minimum, constraint.maximum, rng)
            if constraint.path.endswith(".length"):
                value = int(value)
                if value < 0:
                    raise ValueError("generated collection lengths cannot be negative")
            _set_value(case, constraint.path, value, rng)
        if focus is not None:
            path, value = focus
            if path.endswith(".length"):
                value = int(value)
            _set_value(case, path, value, rng)
        if pattern is not None:
            path, name = pattern
            collection = _collection_for_length_path(case, path)
            if not isinstance(collection, list):
                return None
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in collection
            ):
                return None
            try:
                ordered = sorted(collection)
            except TypeError:
                return None
            if name == "ascending":
                collection[:] = ordered
            elif name == "descending":
                collection[:] = reversed(ordered)
            elif name == "all_equal" and collection:
                collection[:] = [collection[0] for _ in collection]
            elif name == "duplicate_heavy" and collection:
                collection[:] = [ordered[0] for _ in collection]
                if len(collection) > 1:
                    collection[-1] = ordered[-1]
            elif name == "alternating_low_high" and collection:
                alternating: list[int | float] = []
                low, high = 0, len(ordered) - 1
                while low <= high:
                    alternating.append(ordered[low])
                    low += 1
                    if low <= high:
                        alternating.append(ordered[high])
                        high -= 1
                collection[:] = alternating
            elif name == "nearly_sorted" and len(ordered) > 1:
                swap_index = next(
                    (index for index in range(len(ordered) - 1) if ordered[index] != ordered[index + 1]),
                    None,
                )
                if swap_index is None:
                    return None
                ordered[swap_index], ordered[swap_index + 1] = (
                    ordered[swap_index + 1],
                    ordered[swap_index],
                )
                collection[:] = ordered
            else:
                return None
        candidate = ProblemSpec.model_validate(
            {**problem.model_dump(mode="json"), "samples": [case]}
        )
        if not validate_problem_spec(candidate).valid:
            return None
    except (ValueError, TypeError):
        return None
    return case


def _boundary_values(constraint: ConstraintRange) -> list[tuple[str, int | float]]:
    values: list[tuple[str, int | float]] = []
    if constraint.minimum is not None:
        values.append(("minimum", constraint.minimum))
        adjacent = (
            math.nextafter(float(constraint.minimum), math.inf)
            if isinstance(constraint.minimum, float)
            else constraint.minimum + 1
        )
        if constraint.maximum is None or adjacent <= constraint.maximum:
            values.append(("minimum_adjacent", adjacent))
    if constraint.maximum is not None and constraint.maximum != constraint.minimum:
        values.append(("maximum", constraint.maximum))
        adjacent = (
            math.nextafter(float(constraint.maximum), -math.inf)
            if isinstance(constraint.maximum, float)
            else constraint.maximum - 1
        )
        if constraint.minimum is None or adjacent >= constraint.minimum:
            values.append(("maximum_adjacent", adjacent))
    low = constraint.minimum if constraint.minimum is not None else -1
    high = constraint.maximum if constraint.maximum is not None else 1
    for label, value in (("zero", 0), ("negative_one", -1)):
        if low <= value <= high and all(existing != value for _, existing in values):
            values.append((label, value))
    return values


def generate_problem_inputs(
    request: ProblemInputGenerationRequest,
) -> ProblemInputGenerationResult:
    rng = random.Random(request.seed)
    cases: list[GeneratedInputCase] = []
    seen: set[str] = set()
    max_attempts = max(request.count * 20, 20)
    ordered_constraints = sorted(
        request.problem.constraints,
        key=lambda item: ("length" not in item.path, len(item.path)),
    )
    has_numeric_length = any(
        constraint.path.endswith(".length")
        and any(
            isinstance(collection := _collection_for_length_path(
                sample.model_dump(mode="json"), constraint.path
            ), list)
            and all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in collection
            )
            for sample in request.problem.samples
        )
        for constraint in ordered_constraints
    )
    boundary_candidate_count = sum(len(_boundary_values(item)) for item in ordered_constraints)
    adversarial_reserve = (
        min(3, request.count // 2)
        if has_numeric_length and request.count >= boundary_candidate_count + 3
        else 0
    )

    def append_case(sample: FunctionSample | StdinStdoutSample, case: dict, strategy: str) -> None:
        identity_data = {
            "kind": sample.kind,
            "args": case.get("args"),
            "kwargs": case.get("kwargs"),
            "stdin": case.get("stdin"),
        }
        identity = json.dumps(identity_data, sort_keys=True, separators=(",", ":"))
        if identity in seen:
            return
        seen.add(identity)
        if isinstance(sample, FunctionSample):
            generated = GeneratedInputCase(
                name=f"generated_{len(cases) + 1}",
                kind="function",
                strategy=strategy,
                args=case["args"],
                kwargs=case["kwargs"],
            )
        else:
            generated = GeneratedInputCase(
                name=f"generated_{len(cases) + 1}",
                kind="stdin_stdout",
                strategy=strategy,
                stdin=case["stdin"],
            )
        cases.append(generated)

    for sample in request.problem.samples:
        for constraint_index, constraint in enumerate(ordered_constraints, start=1):
            for label, value in _boundary_values(constraint):
                if len(cases) >= request.count - adversarial_reserve:
                    break
                case = _candidate_case(
                    request.problem,
                    sample,
                    ordered_constraints,
                    rng,
                    focus=(constraint.path, value),
                )
                if case is not None:
                    append_case(sample, case, f"boundary_{label}_{constraint_index}")
            if len(cases) >= request.count - adversarial_reserve:
                break
        if len(cases) >= request.count:
            break

    for sample in request.problem.samples:
        for constraint_index, constraint in enumerate(ordered_constraints, start=1):
            if not constraint.path.endswith(".length"):
                continue
            for pattern_name in (
                "ascending",
                "descending",
                "all_equal",
                "duplicate_heavy",
                "alternating_low_high",
                "nearly_sorted",
            ):
                if len(cases) >= request.count:
                    break
                case = _candidate_case(
                    request.problem,
                    sample,
                    ordered_constraints,
                    rng,
                    pattern=(constraint.path, pattern_name),
                )
                if case is not None:
                    append_case(sample, case, f"adversarial_{pattern_name}_{constraint_index}")
            if len(cases) >= request.count:
                break
        if len(cases) >= request.count:
            break

    for attempt in range(max_attempts):
        if len(cases) >= request.count:
            break
        sample = rng.choice(request.problem.samples)
        case = _candidate_case(request.problem, sample, ordered_constraints, rng)
        if case is not None:
            append_case(sample, case, "random_constraint_sample")
    return ProblemInputGenerationResult(
        seed=request.seed,
        requested=request.count,
        generated=len(cases),
        cases=cases,
    )


def generate_complexity_benchmarks(
    request: ComplexityBenchmarkGenerationRequest,
) -> ComplexityBenchmarkGenerationResult:
    """Create repeatable, adversarial function inputs at declared collection sizes."""
    sample = request.problem.samples[0]
    if not isinstance(sample, FunctionSample):
        raise ValueError("complexity benchmark generation requires function samples")
    sample_data = sample.model_dump(mode="json")
    collection = _collection_for_length_path(sample_data, request.size_path)
    if not isinstance(collection, list) or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in collection
    ):
        raise ValueError("size_path must point to a numeric array in the first example")

    rng = random.Random(request.seed)
    constraints = sorted(
        request.problem.constraints,
        key=lambda item: ("length" not in item.path, len(item.path)),
    )
    benchmarks: list[ComplexityBenchmarkSample] = []
    for size in request.sizes:
        case = _candidate_case(
            request.problem,
            sample,
            constraints,
            rng,
            focus=(request.size_path, size),
            pattern=(request.size_path, request.pattern),
        )
        if case is None:
            raise ValueError(
                f"could not generate the {request.pattern} pattern at size {size}; "
                "check the sample values and constraints"
            )
        args = case.get("args")
        kwargs = case.get("kwargs")
        generated_collection = _collection_for_length_path(case, request.size_path)
        if not isinstance(generated_collection, list) or len(generated_collection) != size:
            raise ValueError("generated benchmark did not match its declared size")
        benchmarks.append(
            ComplexityBenchmarkSample(
                size=size,
                args=args,
                kwargs=kwargs,
                strategy=request.pattern,
            )
        )

    return ComplexityBenchmarkGenerationResult(
        seed=request.seed,
        size_path=request.size_path,
        pattern=request.pattern,
        benchmarks=benchmarks,
        limitations=[
            "Inputs are generated from the first example and declared constraints; inspect them before execution.",
            "The selected pattern may expose some input-sensitive cases but does not prove a worst case for the submitted algorithm.",
            "Generated sizes are user-selected and results remain low-confidence empirical observations.",
        ],
    )


def generate_exhaustive_inputs(problem: ProblemSpec, max_cases: int = 256) -> list[dict[str, Any]]:
    """Enumerate every case in a small, explicitly bounded integer argument space."""
    domains = exhaustive_argument_domains(problem, max_cases=max_cases)
    return [
        {
            "name": f"exhaustive_{index}",
            "kind": "function",
            "args": list(values),
            "kwargs": {},
            "strategy": "exhaustive_integer_domain",
        }
        for index, values in enumerate(itertools.product(*domains), start=1)
    ]
