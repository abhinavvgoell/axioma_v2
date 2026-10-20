from __future__ import annotations

import re

from axioma_worker.python_complexity import ComplexityEstimate
from axioma_worker.python_complexity import add_line_event_fit

_TOKEN = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[A-Za-z_$][\w$]*|\d+|[^\s]"
)


def _tokens(source: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(source)
        if not token.startswith("//")
        and not token.startswith("/*")
        and not token.startswith('"')
        and not token.startswith("'")
    ]


def _matching(tokens: list[str], start: int, opening: str, closing: str) -> int | None:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == opening:
            depth += 1
        elif tokens[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _class_body(tokens: list[str], class_name: str) -> tuple[int, int] | None:
    for index, token in enumerate(tokens[:-1]):
        if token == "class" and tokens[index + 1] == class_name:
            opening = next((i for i in range(index + 2, len(tokens)) if tokens[i] == "{"), None)
            if opening is None:
                return None
            closing = _matching(tokens, opening, "{", "}")
            return (opening, closing) if closing is not None else None
    return None


def _method_body(
    tokens: list[str], class_range: tuple[int, int], method_name: str
) -> list[str] | None:
    class_start, class_end = class_range
    for index in range(class_start + 1, class_end - 1):
        if tokens[index] != method_name or tokens[index + 1] != "(":
            continue
        args_end = _matching(tokens, index + 1, "(", ")")
        if args_end is None:
            continue
        body_open = next(
            (i for i in range(args_end + 1, class_end) if tokens[i] in {"{", ";"}), None
        )
        if body_open is None or tokens[body_open] == ";":
            continue
        body_close = _matching(tokens, body_open, "{", "}")
        if body_close is not None:
            return tokens[body_open + 1 : body_close]
    return None


def _loop_spans(tokens: list[str]) -> tuple[list[tuple[int, int]], bool]:
    spans: list[tuple[int, int]] = []
    incomplete = False
    for index, token in enumerate(tokens):
        if token in {"for", "while"}:
            paren_open = next(
                (i for i in range(index + 1, len(tokens)) if tokens[i] in {"(", "{", ";"}),
                None,
            )
            if paren_open is None or tokens[paren_open] != "(":
                incomplete = True
                continue
            paren_close = _matching(tokens, paren_open, "(", ")")
            if paren_close is None:
                incomplete = True
                continue
            body = paren_close + 1
        elif token == "do":
            body = index + 1
        else:
            continue

        if body < len(tokens) and tokens[body] == "{":
            end = _matching(tokens, body, "{", "}")
            if end is None:
                incomplete = True
                continue
            spans.append((index, end))
        else:
            incomplete = True
            spans.append((index, body))
    return spans, incomplete


def analyze_java_complexity(code: str, entrypoint: str) -> ComplexityEstimate:
    method = "static_java_token_loop_depth"
    explanation = "Heuristic from Java loop nesting, direct recursion, and common sorting calls."
    parts = entrypoint.split(".")
    if len(parts) != 2:
        return ComplexityEstimate(
            method,
            "unknown (Java entrypoint must be ClassName.methodName)",
            "low",
            False,
            "A class and method are required for static Java analysis.",
        )
    tokens = _tokens(code)
    class_range = _class_body(tokens, parts[0])
    if class_range is None:
        return ComplexityEstimate(
            method,
            "unknown (class not found)",
            "low",
            False,
            f"Could not locate class {parts[0]} in the source.",
        )
    body = _method_body(tokens, class_range, parts[1])
    if body is None:
        return ComplexityEstimate(
            method,
            "unknown (method not found)",
            "low",
            False,
            f"Could not locate method {parts[1]} in class {parts[0]}.",
        )

    spans, incomplete_loop = _loop_spans(body)
    loop_indices = [start for start, _ in spans]
    maximum_depth = max(
        (sum(start <= index <= end for start, end in spans) for index in loop_indices),
        default=0,
    )
    recursive = any(
        token == parts[1] and index + 1 < len(body) and body[index + 1] == "("
        for index, token in enumerate(body)
    )
    has_sort = any(
        token in {"sort", "parallelSort"} and index + 1 < len(body) and body[index + 1] == "("
        for index, token in enumerate(body)
    )
    has_while = any(token == "while" for token in body)

    if recursive:
        estimate = "unknown (recursion detected)"
        explanation += " Recurrence behavior is not inferred by this analyzer."
    elif maximum_depth >= 2:
        estimate = f"O(n^{maximum_depth})"
        explanation += f" Maximum detected braced loop nesting depth: {maximum_depth}."
    elif maximum_depth == 1 and has_sort:
        estimate = "O(n log n)"
        explanation += " One braced loop level and a common sort call were detected."
    elif maximum_depth == 1:
        estimate = "O(n)"
        explanation += " One braced loop level was detected."
    elif has_sort:
        estimate = "O(n log n)"
        explanation += " A common sort call was detected."
    else:
        estimate = "O(1) (no detected loops or sorting)"
        explanation += " No loops or common sort calls were detected."

    if has_while or incomplete_loop:
        explanation += " A while-loop bound or an unbraced loop may change the estimate."
    explanation += " Called helpers, library costs, and complex control flow are not analyzed; this is not a proof."
    return ComplexityEstimate(method, estimate, "low", False, explanation)


def add_java_wall_time_fit(
    static: ComplexityEstimate, measurements: list[dict[str, int]], value_key: str = "elapsed_ns"
) -> ComplexityEstimate:
    """Fit coarse growth models to JVM timings while retaining their measurement provenance."""
    normalized = [
        {"size": point["size"], "line_events": point[value_key]}
        for point in measurements
        if isinstance(point.get("size"), int) and isinstance(point.get(value_key), int)
    ]
    if len(normalized) < 4 or any(point["line_events"] < 1 for point in normalized):
        return static
    fitted = add_line_event_fit(static, normalized)
    details = dict(fitted.details)
    details["measurement_method"] = "jvm_reflective_wall_time"
    details["points"] = measurements
    details["fit_value"] = value_key
    return ComplexityEstimate(
        method=fitted.method.replace("dynamic_line_event_fit", "dynamic_jvm_wall_time_fit"),
        estimate=fitted.estimate.replace("measured line-event fit", "measured JVM wall-time fit"),
        confidence="low",
        methods_disagree=fitted.methods_disagree,
        explanation=(
            static.explanation
            + " The measured fit uses median JVM reflective wall time over user-declared input sizes; "
            "reflection overhead, JVM warmup, scheduling noise, and unchecked input scaling limit "
            "this low-confidence observation, which is not an asymptotic proof."
        ),
        details=details,
    )
