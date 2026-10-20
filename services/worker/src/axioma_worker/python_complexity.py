from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field

from axioma_api.contracts import ConstraintRange


@dataclass(frozen=True)
class ComplexityEstimate:
    method: str
    estimate: str
    confidence: str
    methods_disagree: bool
    explanation: str
    details: dict = field(default_factory=dict)


def add_line_event_fit(
    static: ComplexityEstimate, measurements: list[dict[str, int]]
) -> ComplexityEstimate:
    """Combine a static estimate with a coarse fit over user-supplied benchmark sizes."""
    if len(measurements) < 4:
        return static
    points = sorted(measurements, key=lambda point: point["size"])
    if any(point["line_events"] < 1 for point in points):
        return static

    sizes = [point["size"] for point in points]
    ys = [float(point["line_events"]) for point in points]
    log_two = math.log(2)
    exponential_logs = [size * log_two for size in sizes]
    max_exponential_log = max(exponential_logs)
    model_inputs = [
        ("O(1)", [1.0 for _ in sizes]),
        ("O(log n)", [math.log2(size) for size in sizes]),
        ("O(n)", [float(size) for size in sizes]),
        ("O(n log n)", [size * math.log2(max(size, 2)) for size in sizes]),
        ("O(n^2)", [float(size**2) for size in sizes]),
        ("O(n^3)", [float(size**3) for size in sizes]),
        (
            "O(2^n)",
            [math.exp(value - max_exponential_log) for value in exponential_logs],
        ),
    ]
    y_mean = sum(ys) / len(ys)
    total_sum_squares = sum((value - y_mean) ** 2 for value in ys)
    fits: list[tuple[float, str]] = []
    for model, raw_xs in model_inputs:
        maximum = max(raw_xs)
        xs = [value / maximum if maximum else 0.0 for value in raw_xs]
        x_mean = sum(xs) / len(xs)
        denominator = sum((value - x_mean) ** 2 for value in xs)
        slope = (
            sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
            if denominator
            else 0.0
        )
        intercept = y_mean - slope * x_mean
        residual_sum_squares = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        goodness = 1.0 - residual_sum_squares / total_sum_squares if total_sum_squares else 1.0
        fits.append((goodness, model))
    goodness, measured = max(fits, key=lambda item: item[0])

    measured_bucket = {
        "O(1)": "flat_or_logarithmic",
        "O(log n)": "flat_or_logarithmic",
        "O(n)": "linear",
        "O(n log n)": "n_log_n_or_mildly_superlinear",
        "O(n^2)": "quadratic",
        "O(n^3)": "superquadratic",
        "O(2^n)": "superquadratic",
    }[measured]

    static_bucket = _static_growth_bucket(static.estimate)
    disagrees = static_bucket is not None and static_bucket != measured_bucket
    estimate = (
        f"static {static.estimate}; measured line-event fit {measured}"
        if disagrees
        else f"{static.estimate} (measured line-event fit: {measured})"
    )
    return ComplexityEstimate(
        method=f"{static.method}+dynamic_line_event_fit",
        estimate=estimate,
        confidence="low",
        methods_disagree=disagrees,
        explanation=(
            static.explanation
            + " The measured fit uses executed source-line events over user-declared input sizes; "
            "input scaling is not independently checked, line events are only a proxy for work, "
            "submitted code can interfere with tracing, and this low-confidence observation is "
            "not an asymptotic proof."
        ),
        details={
            "measurement_method": "executed_source_line_events",
            "points": points,
            "input_sizes_are_user_declared": True,
            "fit": measured,
            "goodness_of_fit_r2": round(goodness, 3),
            "fit_quality": "strong" if goodness >= 0.9 else "weak",
            "candidate_models": [model for model, _ in model_inputs],
        },
    )


def _static_growth_bucket(estimate: str) -> str | None:
    if estimate.startswith("O(1)"):
        return "flat_or_logarithmic"
    if estimate == "O(n)":
        return "linear"
    if estimate == "O(n log n)":
        return "n_log_n_or_mildly_superlinear"
    if estimate == "O(n^2)":
        return "quadratic"
    if estimate.startswith("O(n^"):
        return "superquadratic"
    return None


def _fitted_growth_bucket(model: str | None) -> str | None:
    return {
        "O(1)": "flat_or_logarithmic",
        "O(log n)": "flat_or_logarithmic",
        "O(n)": "linear",
        "O(n log n)": "n_log_n_or_mildly_superlinear",
        "O(n^2)": "quadratic",
        "O(n^3)": "superquadratic",
        "O(2^n)": "superquadratic",
    }.get(model)


def add_opcode_count_fit(
    static: ComplexityEstimate, measurements: list[dict[str, int]]
) -> ComplexityEstimate:
    """Fit coarse growth models to executed CPython opcode dispatch counts."""
    normalized = [
        {"size": point["size"], "line_events": point["opcode_events"]}
        for point in measurements
        if isinstance(point.get("size"), int)
        and isinstance(point.get("opcode_events"), int)
    ]
    if len(normalized) < 4 or any(point["line_events"] < 1 for point in normalized):
        return static
    fitted = add_line_event_fit(static, normalized)
    details = dict(fitted.details)
    details["measurement_method"] = "executed_python_opcode_count"
    details["points"] = measurements
    details["fit_value"] = "opcode_events"
    return ComplexityEstimate(
        method=fitted.method.replace("dynamic_line_event_fit", "dynamic_opcode_count_fit"),
        estimate=fitted.estimate.replace("measured line-event fit", "measured opcode-count fit"),
        confidence="low",
        methods_disagree=fitted.methods_disagree,
        explanation=(
            static.explanation
            + " The measured fit uses target-function Python opcode dispatch counts over user-declared "
            "input sizes. It omits work in called helpers and native code, tracing can be disabled by "
            "submitted code, and this low-confidence observation is not an asymptotic proof."
        ),
        details=details,
    )


def triangulate_python_complexity(
    static: ComplexityEstimate, measurements: list[dict[str, int]]
) -> ComplexityEstimate:
    """Combine static analysis, line events, and opcode counts when each is available."""
    line_fit = add_line_event_fit(static, measurements)
    opcode_fit = add_opcode_count_fit(static, measurements)
    has_line_fit = line_fit.method.endswith("+dynamic_line_event_fit")
    has_opcode_fit = opcode_fit.method.endswith("+dynamic_opcode_count_fit")
    if not has_line_fit:
        return opcode_fit
    if not has_opcode_fit:
        return line_fit

    line_model = line_fit.details.get("fit")
    opcode_model = opcode_fit.details.get("fit")
    line_bucket = _fitted_growth_bucket(line_model)
    opcode_bucket = _fitted_growth_bucket(opcode_model)
    methods_disagree = (
        line_fit.methods_disagree
        or opcode_fit.methods_disagree
        or (line_bucket is not None and opcode_bucket is not None and line_bucket != opcode_bucket)
    )
    return ComplexityEstimate(
        method=f"{line_fit.method}+dynamic_opcode_count_fit",
        estimate=(
            f"static {static.estimate}; line-event fit {line_model}; opcode-count fit {opcode_model}"
        ),
        confidence="low",
        methods_disagree=methods_disagree,
        explanation=(
            static.explanation
            + " Complexity signals include static loop analysis, executed source-line events, and "
            "target-function opcode dispatch counts. Dynamic fits use user-declared input sizes; "
            "helpers and native-library work are omitted, tracing can be disabled by submitted code, "
            "and none of these observations proves an asymptotic bound."
        ),
        details={
            **line_fit.details,
            "signals": {
                "static": {"method": static.method, "estimate": static.estimate},
                "line_event_fit": {
                    "estimate": line_model,
                    "goodness_of_fit_r2": line_fit.details.get("goodness_of_fit_r2"),
                },
                "opcode_count_fit": {
                    "estimate": opcode_model,
                    "goodness_of_fit_r2": opcode_fit.details.get("goodness_of_fit_r2"),
                },
            },
        },
    )


def estimate_constraint_scale(
    constraints: list[ConstraintRange], estimate: str
) -> dict[str, object]:
    """Relate a complexity class to the largest declared collection bound, cautiously."""
    length_bounds = [
        constraint
        for constraint in constraints
        if constraint.path.endswith(".length") and constraint.maximum is not None
    ]
    if not length_bounds:
        return {
            "state": "not_estimated",
            "reason": "No maximum collection-length constraint was declared.",
            "confidence": "low",
        }

    bound = max(length_bounds, key=lambda item: item.maximum or 0)
    size = max(0, int(bound.maximum or 0))
    model_match = re.search(r"O\([^)]*\)", estimate)
    model = model_match.group(0) if model_match else "unknown"
    if model == "O(1)":
        scale = "about 1 growth unit"
    elif model == "O(log n)":
        scale = f"about {max(1, math.ceil(math.log2(max(size, 2))))} growth units"
    elif model == "O(n)":
        scale = f"about {size} growth units"
    elif model == "O(n log n)":
        units = math.ceil(size * math.log2(max(size, 2)))
        scale = f"about {units} growth units"
    elif (power_match := re.fullmatch(r"O\(n\^(\d+)\)", model)) is not None:
        power = int(power_match.group(1))
        scale = (
            f"about {size**power} growth units" if power <= 6 else "very large; exponent omitted"
        )
    elif model == "O(2^n)":
        log10_units = size * math.log10(2)
        scale = f"roughly 1e{math.floor(log10_units)} growth units"
    else:
        return {
            "state": "not_estimated",
            "reason": "The available complexity estimate cannot be mapped to a growth model.",
            "declared_collection_bound": {"path": bound.path, "maximum": size},
            "confidence": "low",
        }

    return {
        "state": "estimated",
        "complexity_model": model,
        "declared_collection_bound": {"path": bound.path, "maximum": size},
        "rough_growth_scale": scale,
        "confidence": "low",
        "assumption": (
            "Assumes the largest declared collection is n and one abstract growth unit per "
            "operation; this is not a runtime or time-limit prediction."
        ),
    }


def _find_function(
    tree: ast.Module, entrypoint: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parts = entrypoint.split(".")
    body: list[ast.stmt] = tree.body
    if len(parts) == 2:
        owner = next(
            (node for node in body if isinstance(node, ast.ClassDef) and node.name == parts[0]),
            None,
        )
        if owner is None:
            return None
        body = owner.body
    return next(
        (
            node
            for node in body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[-1]
        ),
        None,
    )


def analyze_python_complexity(code: str, entrypoint: str) -> ComplexityEstimate:
    method = "static_ast_loop_depth"
    explanation = "Heuristic from the target function's loop nesting and built-in sorting calls."
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return ComplexityEstimate(
            method, "unknown (syntax error)", "low", False, f"Could not parse Python: {exc.msg}."
        )

    function = _find_function(tree, entrypoint)
    if function is None:
        return ComplexityEstimate(
            method,
            "unknown (entrypoint not found)",
            "low",
            False,
            "Static analysis could not locate the declared function entrypoint.",
        )

    maximum_depth = 0
    has_while = False
    has_sort = False
    recursive = False
    stack: list[tuple[ast.AST, int]] = [(node, 0) for node in function.body]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            depth += 1
            maximum_depth = max(maximum_depth, depth)
            has_while = has_while or isinstance(node, ast.While)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            depth += len(node.generators)
            maximum_depth = max(maximum_depth, depth)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == function.name:
                recursive = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr == function.name:
                recursive = True
            if (isinstance(node.func, ast.Name) and node.func.id == "sorted") or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "sort"
            ):
                has_sort = True
        stack.extend((child, depth) for child in ast.iter_child_nodes(node))

    if recursive:
        estimate = "unknown (recursion detected)"
        explanation += " Recurrence behavior is not inferred by this analyzer."
    elif maximum_depth >= 2:
        estimate = f"O(n^{maximum_depth})"
        explanation += f" Maximum detected loop or comprehension nesting depth: {maximum_depth}."
    elif maximum_depth == 1 and has_sort:
        estimate = "O(n log n)"
        explanation += (
            " One loop level and a built-in sort were detected; sort cost is treated as O(n log n)."
        )
    elif maximum_depth == 1:
        estimate = "O(n)"
        explanation += " Maximum detected loop or comprehension nesting depth: 1."
    elif has_sort:
        estimate = "O(n log n)"
        explanation += " A built-in sort was detected."
    else:
        estimate = "O(1) (loop-free target)"
        explanation += " No loops or built-in sorting calls were detected in the target function."

    if has_while:
        explanation += " A while-loop bound is data-dependent and may change this estimate."
    explanation += " Called helper functions are not included; this estimate is not a proof."
    return ComplexityEstimate(method, estimate, "low", False, explanation)
