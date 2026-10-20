from axioma_api.contracts import ConstraintRange
from axioma_worker.python_complexity import (
    add_opcode_count_fit,
    add_line_event_fit,
    analyze_python_complexity,
    estimate_constraint_scale,
    triangulate_python_complexity,
)


def test_complexity_estimator_uses_maximum_nested_loop_depth() -> None:
    estimate = analyze_python_complexity(
        "def solve(values):\n    for x in values:\n        for y in values:\n            print(x, y)\n",
        "solve",
    )

    assert estimate.estimate == "O(n^2)"
    assert estimate.confidence == "low"
    assert estimate.methods_disagree is False


def test_complexity_estimator_accounts_for_sort_and_recursion_limits() -> None:
    sorted_case = analyze_python_complexity(
        "def solve(values):\n    return sorted(values)\n", "solve"
    )
    recursive_case = analyze_python_complexity("def solve(n):\n    return solve(n - 1)\n", "solve")

    assert sorted_case.estimate == "O(n log n)"
    assert recursive_case.estimate == "unknown (recursion detected)"


def test_complexity_estimator_reports_unavailable_entrypoint() -> None:
    estimate = analyze_python_complexity("def other(): pass", "solve")

    assert estimate.estimate == "unknown (entrypoint not found)"


def test_line_event_fit_compares_coarse_growth_and_keeps_raw_points() -> None:
    static = analyze_python_complexity(
        "def solve(value):\n    for item in range(value):\n        pass\n", "solve"
    )
    measured = add_line_event_fit(
        static,
        [
            {"size": 10, "line_events": 30},
            {"size": 20, "line_events": 60},
            {"size": 40, "line_events": 120},
            {"size": 80, "line_events": 240},
        ],
    )

    assert measured.method == "static_ast_loop_depth+dynamic_line_event_fit"
    assert measured.methods_disagree is False
    assert measured.confidence == "low"
    assert measured.details["measurement_method"] == "executed_source_line_events"
    assert len(measured.details["points"]) == 4


def test_line_event_fit_flags_disagreement_with_static_estimate() -> None:
    static = analyze_python_complexity("def solve(value): return value + 1", "solve")
    measured = add_line_event_fit(
        static,
        [
            {"size": 10, "line_events": 10},
            {"size": 20, "line_events": 40},
            {"size": 40, "line_events": 160},
            {"size": 80, "line_events": 640},
        ],
    )

    assert measured.methods_disagree is True
    assert "static O(1)" in measured.estimate
    assert "measured line-event fit O(n^2)" in measured.estimate
    assert measured.details["goodness_of_fit_r2"] == 1.0


def test_opcode_fit_is_reported_separately_from_line_event_fit() -> None:
    static = analyze_python_complexity(
        "def solve(values):\n    for value in values:\n        pass\n", "solve"
    )
    points = [
        {"size": 10, "line_events": 10, "opcode_events": 100},
        {"size": 20, "line_events": 20, "opcode_events": 400},
        {"size": 40, "line_events": 40, "opcode_events": 1600},
        {"size": 80, "line_events": 80, "opcode_events": 6400},
    ]

    opcode_fit = add_opcode_count_fit(static, points)
    triangulated = triangulate_python_complexity(static, points)

    assert opcode_fit.method.endswith("+dynamic_opcode_count_fit")
    assert opcode_fit.details["measurement_method"] == "executed_python_opcode_count"
    assert opcode_fit.details["fit"] == "O(n^2)"
    assert triangulated.methods_disagree is True
    assert triangulated.details["signals"]["line_event_fit"]["estimate"] == "O(n)"
    assert triangulated.details["signals"]["opcode_count_fit"]["estimate"] == "O(n^2)"


def test_constraint_scale_estimate_uses_declared_collection_maximum() -> None:
    result = estimate_constraint_scale(
        [ConstraintRange(path="args[0].length", minimum=0, maximum=1000)], "O(n^2)"
    )

    assert result["state"] == "estimated"
    assert result["rough_growth_scale"] == "about 1000000 growth units"
    assert result["confidence"] == "low"


def test_constraint_scale_does_not_infer_size_from_scalar_ranges() -> None:
    result = estimate_constraint_scale(
        [ConstraintRange(path="args[0]", minimum=0, maximum=1000)], "O(n)"
    )

    assert result["state"] == "not_estimated"
