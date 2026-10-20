from __future__ import annotations

import re
from typing import Any

from axioma_api.contracts import (
    FunctionSample,
    ProblemSpec,
    ProblemSpecIssue,
    ProblemSpecValidation,
    StdinStdoutSample,
)

_PATH_PART = re.compile(r"\.([A-Za-z_]\w*)|\[(\d+)\]")
_ROOT = re.compile(r"^(args|kwargs|stdin)")


def _resolve_sample_path(sample: FunctionSample | StdinStdoutSample, path: str) -> Any:
    root_match = _ROOT.match(path)
    if root_match is None:
        raise ValueError("malformed path")
    root = root_match.group(1)
    segments: list[str | int] = [root]
    offset = len(root)
    while offset < len(path):
        match = _PATH_PART.match(path, offset)
        if match is None:
            raise ValueError("malformed path")
        segments.append(match.group(1) if match.group(1) is not None else int(match.group(2)))
        offset = match.end()

    if isinstance(sample, FunctionSample):
        value: Any = {"args": sample.args, "kwargs": sample.kwargs}.get(root)
    else:
        value = {"stdin": sample.stdin}.get(root)
    if value is None:
        raise ValueError(f"{root} is not available for this sample")

    for segment in segments[1:]:
        if segment == "length":
            if not isinstance(value, (str, list, dict, tuple)):
                raise ValueError("length is only defined for strings, lists, and objects")
            value = len(value)
        elif isinstance(segment, int):
            if not isinstance(value, (list, tuple)) or segment >= len(value):
                raise ValueError("index does not exist in the sample")
            value = value[segment]
        elif isinstance(value, dict):
            if segment not in value:
                raise ValueError(f"field {segment!r} does not exist in the sample")
            value = value[segment]
        else:
            raise ValueError(f"field {segment!r} cannot be resolved")
    return value


def validate_problem_spec(spec: ProblemSpec) -> ProblemSpecValidation:
    issues: list[ProblemSpecIssue] = []
    for sample in spec.samples:
        for constraint in spec.constraints:
            try:
                value = _resolve_sample_path(sample, constraint.path)
            except ValueError as exc:
                issues.append(
                    ProblemSpecIssue(sample=sample.name, path=constraint.path, message=str(exc))
                )
                continue

            if not isinstance(value, (int, float)) or isinstance(value, bool):
                issues.append(
                    ProblemSpecIssue(
                        sample=sample.name,
                        path=constraint.path,
                        message="constraint value must resolve to a number",
                    )
                )
                continue
            if constraint.minimum is not None and value < constraint.minimum:
                issues.append(
                    ProblemSpecIssue(
                        sample=sample.name,
                        path=constraint.path,
                        message=f"sample value {value} is below minimum {constraint.minimum}",
                    )
                )
            if constraint.maximum is not None and value > constraint.maximum:
                issues.append(
                    ProblemSpecIssue(
                        sample=sample.name,
                        path=constraint.path,
                        message=f"sample value {value} exceeds maximum {constraint.maximum}",
                    )
                )
    return ProblemSpecValidation(
        valid=not issues,
        samples_checked=len(spec.samples),
        issues=issues,
    )
