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

    measured, goodness = fit_growth_model(points, "line_events")

    measured_bucket = _fitted_growth_bucket(measured)
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
            "code_analysis": static.details.get("code_analysis"),
            "measurement_method": "executed_source_line_events",
            "points": points,
            "input_sizes_are_user_declared": True,
            "fit": measured,
            "goodness_of_fit_r2": round(goodness, 3),
            "fit_quality": "strong" if goodness >= 0.9 else "weak",
            "candidate_models": ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"],
        },
    )


def fit_growth_model(points: list[dict[str, int]], value_key: str) -> tuple[str, float]:
    sizes = [point["size"] for point in points]
    ys = [float(point[value_key]) for point in points]
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
    return measured, goodness


def estimate_python_peak_memory(measurements: list[dict[str, int]], value_key: str = "peak_traced_bytes") -> dict:
    """Fit a low-confidence growth class to Python-traced peak allocation deltas."""
    points = sorted(
        [
            {"size": point["size"], value_key: point[value_key]}
            for point in measurements
            if isinstance(point.get("size"), int)
            and isinstance(point.get(value_key), int)
            and point["size"] > 0
            and point[value_key] >= 0
        ],
        key=lambda point: point["size"],
    )
    result = {
        "method": "python_tracemalloc_peak_fit",
        "confidence": "low",
        "points": measurements,
        "measurement": "peak traced Python allocation delta in bytes",
        "limitations": (
            "Not process RSS; native allocations may be omitted; includes harness overhead; "
            "submitted code may interfere with tracing; input sizes are user-declared."
        ),
    }
    if len(points) < 4:
        return {**result, "state": "not_estimated", "reason": "At least four valid sizes are required."}
    if not any(point[value_key] > 0 for point in points):
        return {
            **result,
            "state": "not_estimated",
            "reason": "No positive traced allocation increase was observed at the measured sizes.",
        }
    first_observation = points[0][value_key]
    last_observation = points[-1][value_key]
    minimum_increase = max(1, math.ceil(first_observation * 0.2))
    if last_observation <= first_observation or last_observation - first_observation < minimum_increase:
        return {
            **result,
            "state": "not_estimated",
            "reason": (
                "Observed peak allocations did not increase enough across the supplied sizes "
                "to distinguish growth from measurement noise."
            ),
        }
    normalized = [
        {"size": point["size"], "line_events": max(1, point[value_key])} for point in points
    ]
    model, goodness = fit_growth_model(normalized, "line_events")
    return {
        **result,
        "state": "estimated",
        "estimate": model,
        "goodness_of_fit_r2": round(goodness, 3),
        "fit_quality": "strong" if goodness >= 0.9 else "weak",
        "candidate_models": ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"],
    }


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


def _pointer_step(node: ast.stmt, variable: str) -> bool:
    if (
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == variable
        and isinstance(node.op, ast.Add)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
        and node.value.value > 0
    ):
        return True
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == variable
        and isinstance(node.value, ast.BinOp)
        and isinstance(node.value.left, ast.Name)
        and node.value.left.id == variable
        and isinstance(node.value.op, ast.Add)
        and isinstance(node.value.right, ast.Constant)
        and isinstance(node.value.right.value, int)
        and node.value.right.value > 0
    )


def _assigned_name(node: ast.stmt, variable: str) -> bool:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(
            isinstance(target, ast.Name) and target.id == variable for target in targets
        )
    return False


def _initialized_to_zero_before(function: ast.FunctionDef | ast.AsyncFunctionDef, loop: ast.For, variable: str) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or getattr(node, "lineno", 0) >= loop.lineno:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if (
            any(isinstance(target, ast.Name) and target.id == variable for target in targets)
            and isinstance(value, ast.Constant)
            and value.value == 0
        ):
            return True
    return False


def _fixed_iterable(node: ast.AST) -> bool:
    """Return whether an iterable has a source-level fixed number of elements."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "range":
            return bool(node.args) and all(isinstance(arg, ast.Constant) for arg in node.args)
        if node.func.id == "pairwise" and len(node.args) == 1:
            node = node.args[0]
    return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and all(
        isinstance(item, ast.Constant) for item in node.elts
    )


def _dynamic_loop_nesting(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count only loops whose iteration count can grow with the input."""
    maximum_depth = 0
    stack: list[tuple[ast.AST, int]] = [(node, 0) for node in function.body]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.For, ast.AsyncFor)) and not _fixed_iterable(node.iter):
            depth += 1
        elif isinstance(node, ast.While):
            depth += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            depth += sum(not _fixed_iterable(generator.iter) for generator in node.generators)
        maximum_depth = max(maximum_depth, depth)
        stack.extend((child, depth) for child in ast.iter_child_nodes(node))
    return maximum_depth


def _amortized_forward_scan(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Recognize a for-loop with an outer-initialized pointer advanced only forward in a while."""
    for outer in ast.walk(function):
        if not isinstance(outer, ast.For):
            continue
        inner_loops = [node for node in ast.walk(outer) if isinstance(node, ast.While)]
        if len(inner_loops) != 1:
            continue
        inner = inner_loops[0]
        if any(
            isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try,
                              ast.Break, ast.Continue, ast.Return))
            for statement in inner.body
            for node in ast.walk(statement)
        ):
            continue
        # Find only unconditional, top-level pointer updates; nested or conditional updates
        # are intentionally outside this simple amortized-analysis rule.
        update_candidates = [
            statement
            for statement in inner.body
            if isinstance(statement, (ast.AugAssign, ast.Assign))
        ]
        for update in update_candidates:
            if isinstance(update, ast.AugAssign) and isinstance(update.target, ast.Name):
                variable = update.target.id
            elif (
                isinstance(update, ast.Assign)
                and len(update.targets) == 1
                and isinstance(update.targets[0], ast.Name)
            ):
                variable = update.targets[0].id
            else:
                continue
            if not _pointer_step(update, variable):
                continue
            if not any(
                isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Name)
                and node.slice.id == variable
                for statement in inner.body
                for node in ast.walk(statement)
            ):
                continue
            if not _initialized_to_zero_before(function, outer, variable):
                continue

            writes = [node for node in ast.walk(outer) if _assigned_name(node, variable)]
            if any(not _pointer_step(node, variable) for node in writes):
                continue
            return True
    return False


def _is_binary_search_loop(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize common interval-halving searches, including lower-bound variants."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        bounds = None
        for comparison in ast.walk(loop.test):
            if not isinstance(comparison, ast.Compare) or not comparison.comparators:
                continue
            left, right = comparison.left, comparison.comparators[0]
            if not isinstance(left, ast.Name) or not isinstance(right, ast.Name):
                continue
            operator = comparison.ops[0]
            if isinstance(operator, (ast.Lt, ast.LtE)):
                bounds = [left.id, right.id]
                break
            if isinstance(operator, (ast.Gt, ast.GtE)):
                bounds = [right.id, left.id]
                break
        if bounds is None:
            continue
        midpoint_names: set[str] = set()
        for node in ast.walk(loop):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not any(
                isinstance(part, ast.BinOp)
                and isinstance(part.op, (ast.FloorDiv, ast.Div))
                and isinstance(part.right, ast.Constant)
                and part.right.value == 2
                and all(any(isinstance(child, ast.Name) and child.id == bound for child in ast.walk(part.left)) for bound in bounds)
                for part in ast.walk(value)
            ) and not any(
                isinstance(part, ast.BinOp)
                and isinstance(part.op, ast.RShift)
                and isinstance(part.right, ast.Constant)
                and part.right.value == 1
                and all(any(isinstance(child, ast.Name) and child.id == bound for child in ast.walk(part.left)) for bound in bounds)
                for part in ast.walk(value)
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            midpoint_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
        if not midpoint_names:
            continue

        assignments = [
            node for node in ast.walk(loop)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and len(node.targets if isinstance(node, ast.Assign) else [node.target]) == 1
            and isinstance((node.targets if isinstance(node, ast.Assign) else [node.target])[0], ast.Name)
        ]
        advanced: set[str] = set()
        for assignment in assignments:
            targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
            bound = targets[0].id
            if bound not in bounds:
                continue
            value = assignment.value
            is_midpoint = isinstance(value, ast.Name) and value.id in midpoint_names
            is_midpoint_step = (
                isinstance(value, ast.BinOp)
                and isinstance(value.left, ast.Name)
                and value.left.id in midpoint_names
                and isinstance(value.right, ast.Constant)
                and value.right.value == 1
                and (
                    (bound == bounds[0] and isinstance(value.op, ast.Add))
                    or (bound == bounds[1] and isinstance(value.op, ast.Sub))
                )
            )
            if is_midpoint or is_midpoint_step:
                advanced.add(bound)
        if len(advanced) == 2:
            return getattr(loop, "lineno", 0)
    return None


def _has_bisect_call(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute)
            else ""
        )
        if name in {"bisect", "bisect_left", "bisect_right"}:
            return getattr(node, "lineno", 0)
    return None


def _amortized_stack_scan(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize one push-per-item stacks with pop-only inner while loops."""
    for outer in (node for node in ast.walk(function) if isinstance(node, (ast.For, ast.AsyncFor))):
        for inner in (node for node in ast.walk(outer) if isinstance(node, ast.While)):
            stack_names = {
                node.id for node in ast.walk(inner.test)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            }
            for stack_name in stack_names:
                pops = [
                    node for node in ast.walk(inner)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == stack_name
                    and node.func.attr == "pop"
                ]
                pushes = [
                    node for node in ast.walk(outer)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == stack_name
                    and node.func.attr == "append"
                ]
                if pops and pushes:
                    return getattr(inner, "lineno", 0)
    return None


def _is_kahn_topological_sort(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize an indegree queue that scans each adjacency list once."""
    for assignment in (node for node in ast.walk(function) if isinstance(node, (ast.Assign, ast.AnnAssign))):
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        queue_name = targets[0].id
        value = assignment.value
        generator = None
        if isinstance(value, ast.ListComp):
            generator = value.generators[0] if value.generators else None
        elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "deque":
            generator = next((arg.generators[0] for arg in value.args if isinstance(arg, ast.GeneratorExp) and arg.generators), None)
        if generator is None or not isinstance(generator.iter, ast.Call):
            continue
        if not isinstance(generator.iter.func, ast.Name) or generator.iter.func.id != "enumerate":
            continue
        if not any(
            isinstance(node, ast.Compare)
            and any(isinstance(item, ast.Constant) and item.value == 0 for item in node.comparators)
            for node in ast.walk(value)
        ):
            continue
        for loop in (node for node in ast.walk(function) if isinstance(node, (ast.For, ast.While))):
            consumes_queue = (
                isinstance(loop, ast.For) and isinstance(loop.iter, ast.Name) and loop.iter.id == queue_name
            ) or (
                isinstance(loop, ast.While) and isinstance(loop.test, ast.Name) and loop.test.id == queue_name
            )
            if not consumes_queue:
                continue
            body = list(ast.walk(loop))
            scans_adjacency = any(
                isinstance(node, ast.For) and isinstance(node.iter, ast.Subscript)
                and isinstance(node.iter.value, ast.Name)
                for node in body
            )
            decrements_indegree = any(
                isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Sub)
                and isinstance(node.target, ast.Subscript)
                for node in body
            )
            appends_queue = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == queue_name
                and node.func.attr == "append"
                for node in body
            )
            if scans_adjacency and decrements_indegree and appends_queue:
                return getattr(loop, "lineno", 0)
    return None


def _is_sort_then_two_pointer_scan(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize a two-ended scan after an in-place or built-in sort."""
    has_sort = any(
        isinstance(node, ast.Call)
        and ((isinstance(node.func, ast.Name) and node.func.id == "sorted")
             or (isinstance(node.func, ast.Attribute) and node.func.attr == "sort"))
        for node in ast.walk(function)
    )
    if not has_sort:
        return None
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        names = {
            node.id for node in ast.walk(loop.test) if isinstance(node, ast.Name)
        }
        updates = {
            node.target.id
            for node in ast.walk(loop)
            if isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in names
            and isinstance(node.op, (ast.Add, ast.Sub))
            and isinstance(node.value, ast.Constant)
            and node.value.value == 1
        }
        if len(updates) >= 2:
            return loop.lineno
    return None


def _is_floyd_cycle_detection(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize slow/fast pointer traversal over a linked-list next link."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        next_assignments: dict[str, int] = {}
        for node in ast.walk(loop):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            if not isinstance(node.targets[0], ast.Name):
                continue
            depth = 0
            value = node.value
            while isinstance(value, ast.Attribute) and value.attr == "next":
                depth += 1
                value = value.value
            if depth:
                next_assignments[node.targets[0].id] = depth
        if sorted(next_assignments.values())[-2:] == [1, 2]:
            return loop.lineno
    return None


def _is_matrix_staircase_search(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize top-right/bottom-left matrix searches that move one axis per step."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        updates = {
            (node.target.id, node.op)
            for node in ast.walk(loop)
            if isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.op, (ast.Add, ast.Sub))
            and isinstance(node.value, ast.Constant)
            and node.value.value == 1
        }
        has_row_and_column_motion = any(isinstance(op, ast.Add) for _, op in updates) and any(
            isinstance(op, ast.Sub) for _, op in updates
        )
        nested_subscript = any(
            isinstance(node, ast.Subscript) and isinstance(node.value, ast.Subscript)
            for node in ast.walk(loop)
        )
        if has_row_and_column_motion and nested_subscript:
            return loop.lineno
    return None


def _is_heap_pop_scan(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize heap construction followed by an input-sized sequence of pops."""
    has_heapify = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "heapify"
        for node in ast.walk(function)
    )
    if not has_heapify:
        return None
    for loop in (node for node in ast.walk(function) if isinstance(node, (ast.For, ast.AsyncFor))):
        if _fixed_iterable(loop.iter):
            continue
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"heappop", "heappush"}
            for node in ast.walk(loop)
        ):
            return loop.lineno
    return None


def _is_character_trie_build(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize nested word/character loops that build a trie node by node."""
    for outer in (node for node in ast.walk(function) if isinstance(node, ast.For)):
        if not isinstance(outer.target, ast.Name):
            continue
        for inner in (node for node in ast.walk(outer) if isinstance(node, ast.For)):
            if not isinstance(inner.iter, ast.Name) or inner.iter.id != outer.target.id:
                continue
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setdefault"
                for node in ast.walk(inner)
            ):
                return inner.lineno
    return None


def _is_ternary_search_loop(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize a three-way interval search that retains two thirds each step."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        third_names = {
            target.id
            for node in ast.walk(loop)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.BinOp)
            and isinstance(node.value.op, ast.FloorDiv)
            and isinstance(node.value.right, ast.Constant)
            and node.value.right.value == 3
            for target in node.targets
        }
        if not third_names:
            continue
        updates = {
            node.targets[0].id
            for node in ast.walk(loop)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
        }
        if len(updates) >= 2:
            return loop.lineno
    return None


def _is_dijkstra_heap_traversal(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize lazy-deletion Dijkstra traversal over an adjacency list and heap."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        has_pop = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "heappop"
            for node in ast.walk(loop)
        )
        has_push = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "heappush"
            for node in ast.walk(loop)
        )
        scans_neighbors = any(
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Subscript)
            and isinstance(node.iter.value, ast.Name)
            for node in ast.walk(loop)
        )
        if has_pop and has_push and scans_neighbors:
            return loop.lineno
    return None


def _is_fenwick_prefix_loop(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize index -= index & -index prefix traversal in a Fenwick tree."""
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        for update in ast.walk(loop):
            if not isinstance(update, ast.AugAssign) or not isinstance(update.target, ast.Name):
                continue
            if not isinstance(update.op, ast.Sub) or not isinstance(update.value, ast.BinOp):
                continue
            if not isinstance(update.value.op, ast.BitAnd):
                continue
            if not (
                isinstance(update.value.left, ast.Name)
                and update.value.left.id == update.target.id
                and isinstance(update.value.right, ast.UnaryOp)
                and isinstance(update.value.right.op, ast.USub)
                and isinstance(update.value.right.operand, ast.Name)
                and update.value.right.operand.id == update.target.id
            ):
                continue
            return loop.lineno
    return None


def _is_z_algorithm(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize the standard Z-array scan with a right boundary that only advances."""
    for outer in (node for node in ast.walk(function) if isinstance(node, ast.For)):
        if not isinstance(outer.target, ast.Name):
            continue
        index_name = outer.target.id
        for inner in (node for node in ast.walk(outer) if isinstance(node, ast.While)):
            grows_z_value = any(
                isinstance(node, ast.AugAssign)
                and isinstance(node.op, ast.Add)
                and isinstance(node.value, ast.Constant)
                and node.value.value == 1
                and isinstance(node.target, ast.Subscript)
                and isinstance(node.target.slice, ast.Name)
                and node.target.slice.id == index_name
                for node in ast.walk(inner)
            )
            has_boundary_update = any(
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], (ast.Tuple, ast.List))
                and len(node.targets[0].elts) == 2
                for node in ast.walk(outer)
            )
            if grows_z_value and has_boundary_update:
                return outer.lineno
    return None


def _is_adjacency_list_bfs(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize a queue traversal over adjacency lists with a visited guard."""
    for outer in ast.walk(function):
        if not isinstance(outer, ast.While) or not isinstance(outer.test, ast.Name):
            continue
        queue_name = outer.test.id
        initialized = any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == queue_name
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
            and (
                isinstance(node.value, (ast.List, ast.ListComp))
                or (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "deque"
                )
            )
            and getattr(node, "lineno", 0) < outer.lineno
            for node in ast.walk(function)
        )
        if not initialized:
            continue

        dequeue_assignments = [
            node
            for node in ast.walk(outer)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ]
        dequeue_assignments = [
            node for node in dequeue_assignments
            if isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == queue_name
            and node.value.func.attr in {"popleft", "pop"}
        ]
        current_node_names = {node.targets[0].id for node in dequeue_assignments}
        if not current_node_names:
            continue

        for neighbors in (node for node in ast.walk(outer) if isinstance(node, ast.For)):
            iterable = neighbors.iter
            if not (
                isinstance(iterable, ast.Subscript)
                and isinstance(iterable.value, ast.Name)
                and isinstance(iterable.slice, ast.Name)
                and iterable.slice.id in current_node_names
            ):
                continue
            neighbor_name = neighbors.target.id if isinstance(neighbors.target, ast.Name) else None
            if neighbor_name is None:
                continue
            for guard in (node for node in ast.walk(neighbors) if isinstance(node, ast.If)):
                test = guard.test
                if not (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == neighbor_name
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.NotIn)
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Name)
                ):
                    continue
                visited_name = test.comparators[0].id
                adds_to_visited = any(
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == visited_name
                    and call.func.attr == "add"
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == neighbor_name
                    for call in ast.walk(guard)
                    if isinstance(call, ast.Call)
                )
                enqueues_neighbor = any(
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == queue_name
                    and call.func.attr == "append"
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == neighbor_name
                    for call in ast.walk(guard)
                    if isinstance(call, ast.Call)
                )
                if adds_to_visited and enqueues_neighbor:
                    return getattr(outer, "lineno", 0)
    return None


def _recursive_call_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == function.name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == function.name)
        )
    ]


def _local_recursive_helpers(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    helpers = [
        node for node in ast.walk(function)
        if node is not function
        and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _recursive_call_nodes(node)
    ]
    return helpers


def _has_unbounded_cache(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in function.decorator_list:
        name = (
            decorator.id if isinstance(decorator, ast.Name)
            else decorator.func.id if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name)
            else decorator.attr if isinstance(decorator, ast.Attribute)
            else None
        )
        if name == "cache":
            return True
        if name == "lru_cache" and isinstance(decorator, ast.Call):
            if any(keyword.arg == "maxsize" and isinstance(keyword.value, ast.Constant)
                   and keyword.value.value is None for keyword in decorator.keywords):
                return True
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and decorator.args[0].value is None:
                return True
    return False


def _memoized_helper_dimensions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> tuple[int, int] | None:
    """Estimate bounded memoized index-state space for simple local recursive helpers."""
    for helper in helpers:
        parameters = [*helper.args.posonlyargs, *helper.args.args]
        if not _has_unbounded_cache(helper) or not 1 <= len(parameters) <= 3:
            continue
        if _dynamic_loop_nesting(helper) > 0:
            continue
        recursive_calls = _recursive_call_nodes(helper)
        if not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == helper.name
            for statement in function.body
            for node in ast.walk(statement)
            if not any(node is nested for nested in ast.walk(helper))
        ):
            continue
        referenced_names = {
            node.id for node in ast.walk(helper)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        if not all(parameter.arg in referenced_names for parameter in parameters):
            continue
        if not all(len(call.args) >= len(parameters) for call in recursive_calls):
            continue
        return len(parameters), min(call.lineno for call in recursive_calls)
    return None


def _progresses_recursive_state(
    helper: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call
) -> bool:
    parameter_names = {
        argument.arg for argument in [*helper.args.posonlyargs, *helper.args.args]
    }
    for argument in call.args:
        if (
            isinstance(argument, ast.BinOp)
            and isinstance(argument.left, ast.Name)
            and argument.left.id in parameter_names
            and isinstance(argument.op, (ast.Add, ast.Sub))
            and isinstance(argument.right, ast.Constant)
        ):
            return True
        if (
            isinstance(argument, ast.Subscript)
            and isinstance(argument.value, ast.Name)
            and argument.value.id in parameter_names
            and isinstance(argument.slice, ast.Slice)
        ):
            return True
    return False


def _backtracking_helper_line(
    helpers: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> int | None:
    """Recognize recursive state advancement performed inside a candidate loop."""
    for helper in helpers:
        if _has_unbounded_cache(helper):
            continue
        calls = _recursive_call_nodes(helper)
        for loop in (
            node for node in ast.walk(helper) if isinstance(node, (ast.For, ast.While))
        ):
            if any(
                any(node is call for node in ast.walk(loop))
                and _progresses_recursive_state(helper, call)
                for call in calls
            ):
                return min(call.lineno for call in calls)
    return None


def _permutation_backtracking_line(
    helpers: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> int | None:
    """Recognize choose/recurse/unchoose generation using a shared path collection."""
    for helper in helpers:
        if _has_unbounded_cache(helper):
            continue
        calls = _recursive_call_nodes(helper)
        if not calls:
            continue
        for loop in (node for node in ast.walk(helper) if isinstance(node, ast.For)):
            calls_inside_loop = [
                call for call in calls if any(node is call for node in ast.walk(loop))
            ]
            if not calls_inside_loop:
                continue
            collections_with_append = {
                node.func.value.id
                for node in ast.walk(loop)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.attr == "append"
            }
            collections_with_pop = {
                node.func.value.id
                for node in ast.walk(loop)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.attr == "pop"
            }
            if collections_with_append & collections_with_pop:
                return calls_inside_loop[0].lineno
    return None


def _binary_recursive_branch_line(
    helpers: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> int | None:
    """Recognize an uncached helper that makes two progressing recursive branches."""
    for helper in helpers:
        if _has_unbounded_cache(helper):
            continue
        calls = _recursive_call_nodes(helper)
        progressing_calls = [
            call for call in calls if _progresses_recursive_state(helper, call)
        ]
        if len(progressing_calls) >= 2:
            return min(call.lineno for call in progressing_calls)
    return None


def _is_sieve_of_eratosthenes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize the standard prime-marking loop whose stride is the current prime."""
    for outer in (node for node in ast.walk(function) if isinstance(node, ast.While)):
        if not any(
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Mult)
            and isinstance(node.left, ast.Name)
            and isinstance(node.right, ast.Name)
            and node.left.id == node.right.id
            for node in ast.walk(outer.test)
        ):
            continue
        for inner in (node for node in ast.walk(outer) if isinstance(node, ast.For)):
            if not (
                isinstance(inner.iter, ast.Call)
                and isinstance(inner.iter.func, ast.Name)
                and inner.iter.func.id == "range"
                and len(inner.iter.args) == 3
                and isinstance(inner.iter.args[2], ast.Name)
            ):
                continue
            stride = inner.iter.args[2].id
            starts_at_square = isinstance(inner.iter.args[0], ast.BinOp) and isinstance(
                inner.iter.args[0].op, ast.Mult
            ) and all(
                isinstance(part, ast.Name) and part.id == stride
                for part in (inner.iter.args[0].left, inner.iter.args[0].right)
            )
            advances_stride = any(
                isinstance(node, ast.AugAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == stride
                and isinstance(node.op, ast.Add)
                and isinstance(node.value, ast.Constant)
                and node.value.value == 1
                for node in ast.walk(outer)
            )
            if starts_at_square and advances_stride:
                return outer.lineno
    return None


def _is_tree_recursive_walk(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize direct recursion over one or both child links of a tree node."""
    if any(
        isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
                           ast.DictComp, ast.GeneratorExp))
        for node in ast.walk(function)
    ):
        return None
    calls = _recursive_call_nodes(function)
    child_links = [
        call.args[0]
        for call in calls
        if call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].attr in {"left", "right"}
    ]
    if len(calls) not in {1, 2} or len(child_links) != len(calls):
        return None
    if len(child_links) == 2 and (
        child_links[0].value.id != child_links[1].value.id
        or child_links[0].attr == child_links[1].attr
    ):
        return None
    return min(call.lineno for call in calls)


def _is_adjacency_list_dfs(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize recursive DFS guarded by a visited set over adjacency lists."""
    calls = _recursive_call_nodes(function)
    if len(calls) != 1:
        return None
    for loop in (node for node in ast.walk(function) if isinstance(node, ast.For)):
        if not (
            isinstance(loop.target, ast.Name)
            and isinstance(loop.iter, ast.Subscript)
            and isinstance(loop.iter.value, ast.Name)
            and isinstance(loop.iter.slice, ast.Name)
        ):
            continue
        neighbor_name = loop.target.id
        if not any(
            isinstance(argument, ast.Name) and argument.id == neighbor_name
            for argument in calls[0].args
        ):
            continue
        for guard in (node for node in ast.walk(loop) if isinstance(node, ast.If)):
            test = guard.test
            if not (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == neighbor_name
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.NotIn)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Name)
            ):
                continue
            visited_name = test.comparators[0].id
            statements = guard.body
            add_index = next(
                (
                    index for index, statement in enumerate(statements)
                    if isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and isinstance(statement.value.func.value, ast.Name)
                    and statement.value.func.value.id == visited_name
                    and statement.value.func.attr == "add"
                    and statement.value.args
                    and isinstance(statement.value.args[0], ast.Name)
                    and statement.value.args[0].id == neighbor_name
                ),
                None,
            )
            call_index = next(
                (
                    index for index, statement in enumerate(statements)
                    if any(node is calls[0] for node in ast.walk(statement))
                ),
                None,
            )
            if add_index is not None and call_index is not None and add_index < call_index:
                return calls[0].lineno
    return None


def _is_local_adjacency_list_dfs(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """Recognize the same guarded DFS pattern when it is a local helper."""
    for helper in _local_recursive_helpers(function):
        line = _is_adjacency_list_dfs(helper)
        if line is not None:
            return line
        calls = _recursive_call_nodes(helper)
        parameters = [*helper.args.posonlyargs, *helper.args.args]
        if len(parameters) != 1 or len(calls) != 1:
            continue
        node_name = parameters[0].arg
        guard_names = {
            comparator.id
            for node in ast.walk(helper)
            if isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == node_name
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
            for comparator in node.comparators
        }
        marks_visited = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in guard_names
            and node.func.attr == "add"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == node_name
            for node in ast.walk(helper)
        )
        recursive_neighbor_loop = any(
            isinstance(loop.target, ast.Name)
            and isinstance(loop.iter, ast.Subscript)
            and isinstance(loop.iter.value, ast.Name)
            and isinstance(loop.iter.slice, ast.Name)
            and any(
                isinstance(argument, ast.Name) and argument.id == loop.target.id
                for argument in calls[0].args
            )
            for loop in ast.walk(helper)
            if isinstance(loop, ast.For)
        )
        if marks_visited and recursive_neighbor_loop:
            return calls[0].lineno
    return None


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
    signals: list[dict] = []
    loop_count = 0
    recursive_lines: list[int] = []
    membership_lines: list[int] = []
    collection_lines: list[int] = []
    sort_calls: list[tuple[str, int]] = []
    iterable_consumers: list[tuple[str, int]] = []
    stack: list[tuple[ast.AST, int]] = [(node, 0) for node in function.body]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            depth += 1
            loop_count += 1
            maximum_depth = max(maximum_depth, depth)
            has_while = has_while or isinstance(node, ast.While)
            loop_kind = "while" if isinstance(node, ast.While) else "for"
            signals.append({
                "kind": "loop",
                "label": f"{loop_kind} loop",
                "line": getattr(node, "lineno", None),
            })
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            depth += len(node.generators)
            loop_count += len(node.generators)
            maximum_depth = max(maximum_depth, depth)
            signals.append({
                "kind": "comprehension",
                "label": f"{len(node.generators)}-level comprehension",
                "line": getattr(node, "lineno", None),
            })
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == function.name:
                recursive = True
                recursive_lines.append(getattr(node, "lineno", 0))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == function.name:
                recursive = True
                recursive_lines.append(getattr(node, "lineno", 0))
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in {"sum", "min", "max", "any", "all"}
                and len(node.args) == 1
                and not _fixed_iterable(node.args[0])
            ):
                iterable_consumers.append((node.func.id, getattr(node, "lineno", 0)))
                # These built-ins consume their iterable, even when the submission
                # contains no explicit loop of its own.
                maximum_depth = max(maximum_depth, depth + 1)
            if (isinstance(node.func, ast.Name) and node.func.id == "sorted") or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "sort"
            ):
                has_sort = True
                name = node.func.id if isinstance(node.func, ast.Name) else ".sort()"
                sort_calls.append((name, getattr(node, "lineno", 0)))
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "get", "setdefault", "add", "discard", "contains", "append", "extend",
                "pop", "remove",
            }:
                collection_lines.append(getattr(node, "lineno", 0))
        if isinstance(node, ast.Compare) and any(
            isinstance(operator, (ast.In, ast.NotIn)) for operator in node.ops
        ):
            membership_lines.append(getattr(node, "lineno", 0))
        stack.extend((child, depth) for child in ast.iter_child_nodes(node))

    for name, line in iterable_consumers:
        signals.append({
            "kind": "iterable_consumer",
            "label": f"{name}() consumes an iterable",
            "line": line,
        })
    for name, line in sort_calls:
        signals.append({"kind": "sorting", "label": f"{name} sorting call", "line": line})
    for line in recursive_lines:
        signals.append({
            "kind": "recursion",
            "label": "Direct self-call; recurrence is not solved",
            "line": line,
        })
    for line in membership_lines:
        signals.append({
            "kind": "membership",
            "label": "Membership check; cost depends on the container",
            "line": line,
        })
    for line in collection_lines:
        signals.append({
            "kind": "collection_operation",
            "label": "Collection method call; concrete type and cost are not inferred",
            "line": line,
        })
    signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))

    amortized_forward_scan = _amortized_forward_scan(function)
    amortized_stack_line = _amortized_stack_scan(function)
    binary_search_line = _is_binary_search_loop(function)
    bisect_line = _has_bisect_call(function)
    kahn_line = _is_kahn_topological_sort(function)
    graph_bfs_line = _is_adjacency_list_bfs(function)
    graph_dfs_line = _is_adjacency_list_dfs(function)
    local_graph_dfs_line = _is_local_adjacency_list_dfs(function)
    tree_recursion_line = _is_tree_recursive_walk(function)
    sort_two_pointer_line = _is_sort_then_two_pointer_scan(function)
    floyd_line = _is_floyd_cycle_detection(function)
    matrix_staircase_line = _is_matrix_staircase_search(function)
    heap_pop_line = _is_heap_pop_scan(function)
    trie_build_line = _is_character_trie_build(function)
    ternary_search_line = _is_ternary_search_loop(function)
    dijkstra_line = _is_dijkstra_heap_traversal(function)
    fenwick_line = _is_fenwick_prefix_loop(function)
    z_algorithm_line = _is_z_algorithm(function)
    local_recursive_helpers = _local_recursive_helpers(function)
    memoized_state = _memoized_helper_dimensions(function, local_recursive_helpers)
    backtracking_line = _backtracking_helper_line(local_recursive_helpers)
    permutation_line = _permutation_backtracking_line(local_recursive_helpers)
    binary_branch_line = _binary_recursive_branch_line(local_recursive_helpers)
    sieve_line = _is_sieve_of_eratosthenes(function)
    data_dependent_loop_nesting = max(
        _dynamic_loop_nesting(function), 1 if iterable_consumers else 0
    )
    if graph_bfs_line is not None:
        method = "static_ast_graph_bfs"
        signals.append({
            "kind": "graph_bfs",
            "label": "Queue traversal over adjacency lists with a visited guard",
            "line": graph_bfs_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if graph_dfs_line is not None:
        method = "static_ast_graph_dfs"
        signals.append({
            "kind": "graph_dfs",
            "label": "Recursive adjacency-list traversal with a visited guard",
            "line": graph_dfs_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if local_graph_dfs_line is not None:
        method = "static_ast_graph_dfs"
        signals.append({
            "kind": "graph_dfs",
            "label": "Local recursive helper traverses adjacency lists with a visited guard",
            "line": local_graph_dfs_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if tree_recursion_line is not None:
        method = "static_ast_tree_recursion"
        signals.append({
            "kind": "tree_recursion",
            "label": "Recursion follows the left and/or right child link",
            "line": tree_recursion_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if binary_search_line is not None:
        signals.append({
            "kind": "binary_search",
            "label": "Interval-halving loop updates both search bounds from the midpoint",
            "line": binary_search_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if memoized_state is not None:
        signals.append({
            "kind": "memoized_recursion",
            "label": f"Memoized recursive helper with {memoized_state[0]} state indices",
            "line": memoized_state[1],
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if backtracking_line is not None:
        signals.append({
            "kind": "recursive_backtracking",
            "label": "Recursive state advancement inside a candidate loop",
            "line": backtracking_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if permutation_line is not None:
        signals.append({
            "kind": "permutation_backtracking",
            "label": "Choose, recurse, and unchoose path construction",
            "line": permutation_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if binary_branch_line is not None:
        signals.append({
            "kind": "binary_recursive_branching",
            "label": "Two progressing recursive branches without memoization",
            "line": binary_branch_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if sieve_line is not None:
        signals.append({
            "kind": "sieve", "label": "Prime-marking loop starts at each square", "line": sieve_line
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if bisect_line is not None:
        signals.append({
            "kind": "binary_search",
            "label": "Standard-library bisect call performs binary search",
            "line": bisect_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if amortized_stack_line is not None:
        signals.append({
            "kind": "amortized_stack_scan",
            "label": "Stack items are pushed in a scan and popped at most once",
            "line": amortized_stack_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if kahn_line is not None:
        signals.append({
            "kind": "topological_sort",
            "label": "Indegree queue scans each adjacency list",
            "line": kahn_line,
        })
        signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    for kind, label, line in (
        ("sort_two_pointer_scan", "Sort followed by two pointer motion", sort_two_pointer_line),
        ("floyd_cycle_detection", "Slow and fast linked-list pointers", floyd_line),
        ("matrix_staircase_search", "Matrix search moves one row or column per step", matrix_staircase_line),
        ("heap_pop_scan", "Heap construction followed by heap operations", heap_pop_line),
        ("trie_build", "Word and character loops build trie nodes", trie_build_line),
        ("ternary_search", "Three-way interval search", ternary_search_line),
        ("dijkstra", "Heap-based adjacency-list traversal", dijkstra_line),
        ("fenwick_prefix", "Fenwick index clears its lowest set bit", fenwick_line),
        ("z_algorithm", "Z-array scan advances a matching prefix boundary", z_algorithm_line),
    ):
        if line is not None:
            signals.append({"kind": kind, "label": label, "line": line})
    signals.sort(key=lambda signal: (signal.get("line") or 0, signal["kind"]))
    if graph_bfs_line is not None or graph_dfs_line is not None or local_graph_dfs_line is not None or kahn_line is not None:
        estimate = "O(V + E)"
        explanation = (
            "Recognized a graph traversal over adjacency lists with a visited guard. Assuming "
            "each vertex is processed once and each adjacency entry is scanned once, the work is "
            "O(V + E). This assumes constant-time visited-set operations; the syntax check is "
            "a heuristic."
        )
    elif tree_recursion_line is not None:
        estimate = "O(n)"
        explanation = (
            "Recognized direct recursion over left/right child links. Assuming the input is a "
            "tree with no cycles or shared subtrees, each node is processed once, for O(n) work. "
            "The syntax check cannot establish that input structure."
        )
    elif memoized_state is not None:
        dimensions, _ = memoized_state
        estimate = "O(n)" if dimensions == 1 else f"O(n^{dimensions})"
        method = "static_ast_memoized_recursion"
        explanation = (
            f"Recognized a cached recursive helper with {dimensions} state indices and no detected "
            f"input-sized loop inside the helper. Assuming each index ranges over at most n values, "
            f"the state space is {estimate}. This low-confidence pattern does not analyze helper "
            "calls, state bounds, or cache behavior beyond the decorator."
        )
    elif backtracking_line is not None:
        estimate = "O(2^n) (recursive search heuristic)"
        method = "static_ast_recursive_backtracking"
        explanation = (
            "Recognized recursive state advancement inside a candidate loop. Search paths may grow "
            "exponentially; this low-confidence pattern does not prove the branching factor or bound."
        )
    elif permutation_line is not None:
        estimate = "O(n * n!) (permutation search heuristic)"
        method = "static_ast_permutation_backtracking"
        explanation = (
            "Recognized path construction that chooses an option, recurses, then removes it. "
            "Generating all permutations creates n! outputs of length n, giving O(n * n!) work. "
            "This low-confidence pattern does not prove that every branch is reachable."
        )
    elif binary_branch_line is not None:
        estimate = "O(2^n) (recursive branching heuristic)"
        method = "static_ast_binary_recursive_branching"
        explanation = (
            "Recognized two progressing recursive branches without memoization. The number of "
            "paths can double at each input position, so this is conservatively reported as O(2^n)."
        )
    elif recursive or local_recursive_helpers:
        estimate = "unknown (recursion detected)"
        explanation += " Recursive helper behavior is not inferred by this analyzer."
    elif amortized_forward_scan:
        method = "static_ast_amortized_pointer_scan"
        estimate = "O(n)"
        explanation = (
            "Recognized a forward-only sliding-window scan: the outer loop advances through "
            "the input while an index initialized before it only moves forward. Each pointer "
            "advances at most n times, so their combined work is linear."
        )
    elif binary_search_line is not None or bisect_line is not None:
        method = "static_ast_binary_search"
        estimate = "O(log n)"
        explanation = (
            "Recognized an interval-halving search loop or standard-library bisect call. "
            "The search range shrinks by a constant factor per step, giving O(log n) work. "
            "This syntax-based recognition is a heuristic."
        )
    elif amortized_stack_line is not None:
        method = "static_ast_amortized_stack_scan"
        estimate = "O(n)"
        explanation = (
            "Recognized a monotonic-stack pattern: items are pushed during a scan and removed "
            "at most once. The total stack work is linear in the input length."
        )
    elif sort_two_pointer_line is not None:
        method = "static_ast_sort_two_pointer_scan"
        estimate = "O(n log n)"
        explanation = (
            "Recognized a sort followed by a two-ended scan. The scan is linear, and the sort "
            "dominates the total work at O(n log n)."
        )
    elif floyd_line is not None:
        method = "static_ast_floyd_cycle_detection"
        estimate = "O(n)"
        explanation = (
            "Recognized slow and fast pointers advancing through a linked-list next link. "
            "Both pointers take at most a linear number of steps before termination or meeting."
        )
    elif matrix_staircase_line is not None:
        method = "static_ast_matrix_staircase_search"
        estimate = "O(m + n)"
        explanation = (
            "Recognized a matrix staircase search: each step advances one row or one column. "
            "At most m + n positions are visited, assuming the matrix ordering required by this "
            "search is valid."
        )
    elif heap_pop_line is not None:
        method = "static_ast_heap_pop_scan"
        estimate = "O(n log n)"
        explanation = (
            "Recognized heap construction followed by an input-sized sequence of heap operations. "
            "Heapify is linear and each pop or push costs logarithmic time, so this is conservatively "
            "reported as O(n log n)."
        )
    elif trie_build_line is not None:
        method = "static_ast_trie_build"
        estimate = "O(n)"
        explanation = (
            "Recognized a trie build over words and their characters. Here n means the total number "
            "of input characters, and each character creates or follows one trie edge."
        )
    elif ternary_search_line is not None:
        method = "static_ast_ternary_search"
        estimate = "O(log n)"
        explanation = (
            "Recognized a three-way interval search. Each iteration keeps a constant fraction "
            "of the current range, so the number of score evaluations is logarithmic in the range."
        )
    elif dijkstra_line is not None:
        method = "static_ast_heap_graph_traversal"
        estimate = "O((V + E) log V)"
        explanation = (
            "Recognized a heap-based traversal over adjacency lists. With binary-heap push and pop "
            "operations, the conservative cost is O((V + E) log V). This assumes graph size bounds "
            "and heap operations follow the usual Dijkstra-style model."
        )
    elif fenwick_line is not None:
        method = "static_ast_fenwick_prefix"
        estimate = "O(log n)"
        explanation = (
            "Recognized a Fenwick prefix traversal that clears one set bit from the index each step. "
            "An index has at most logarithmically many set bits."
        )
    elif z_algorithm_line is not None:
        method = "static_ast_z_algorithm"
        estimate = "O(n)"
        explanation = (
            "Recognized a Z-array scan. Its right boundary only advances through the string, so the "
            "total matching work is linear."
        )
    elif sieve_line is not None:
        method = "static_ast_sieve_of_eratosthenes"
        estimate = "O(n log log n)"
        explanation = (
            "Recognized the Sieve of Eratosthenes: marking multiples begins at p² and advances by p. "
            "Under the usual prime-marking analysis, its time complexity is O(n log log n)."
        )
    elif has_while:
        estimate = "unknown (data-dependent loop bound)"
        explanation += (
            " A while-loop was detected, but its iteration count cannot be bounded by the "
            "current static rules. It may be linear, logarithmic, or depend on other input values."
        )
    elif data_dependent_loop_nesting >= 2:
        estimate = f"O(n^{data_dependent_loop_nesting})"
        explanation += (
            " Maximum data-dependent loop or comprehension nesting depth: "
            f"{data_dependent_loop_nesting}. Loops with source-level constant bounds are not "
            "counted as input growth."
        )
    elif data_dependent_loop_nesting == 1 and has_sort:
        estimate = "O(n log n)"
        explanation += (
            " One loop level and a built-in sort were detected; sort cost is treated as O(n log n)."
        )
    elif data_dependent_loop_nesting == 1:
        estimate = "O(n)"
        explanation += (
            " One loop/comprehension level or an iterable-consuming built-in was detected."
        )
    elif has_sort:
        estimate = "O(n log n)"
        explanation += " A built-in sort was detected."
    else:
        estimate = "O(1) (loop-free target)"
        explanation += " No loops or built-in sorting calls were detected in the target function."

    explanation += " Called helper functions are not included; this estimate is not a proof."
    confidence = "medium" if amortized_forward_scan or amortized_stack_line is not None else "low"
    return ComplexityEstimate(
        method,
        estimate,
        confidence,
        False,
        explanation,
        details={
            "code_analysis": {
                "language": "python",
                "scope": "selected entrypoint; called helpers are not expanded",
                "signals": signals,
                "loop_count": loop_count,
                "maximum_loop_nesting": maximum_depth,
                "maximum_data_dependent_loop_nesting": data_dependent_loop_nesting,
                "limitations": [
                    "A detected syntax pattern is evidence, not a full algorithmic proof.",
                    "Collection operation costs depend on the concrete type and implementation.",
                    "Recurrence relations and called helper functions are not analyzed.",
                ],
            }
        },
    )
