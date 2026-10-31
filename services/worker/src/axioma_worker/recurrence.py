from __future__ import annotations


RULE_VERSION = "bounded_recurrence_v1"


def solve_bounded_recurrence(
    recursive_calls: int,
    size_reduction: str,
    nonrecursive_work: str,
) -> tuple[str, str, str] | None:
    """Solve a deliberately small set of recurrences used by static recognizers."""
    if size_reduction == "constant_decrement" and recursive_calls == 1:
        if nonrecursive_work == "constant":
            return "T(n) = T(n - c) + O(1)", "O(n)", "decrement_recurrence_constant_work"
        if nonrecursive_work == "linear":
            return "T(n) = T(n - c) + O(n)", "O(n^2)", "decrement_recurrence_linear_work"

    if size_reduction != "factor_two":
        return None
    if recursive_calls == 1 and nonrecursive_work == "constant":
        return "T(n) = T(n / 2) + O(1)", "O(log n)", "master_theorem_case_2a"
    if recursive_calls == 1 and nonrecursive_work == "linear":
        return "T(n) = T(n / 2) + O(n)", "O(n)", "master_theorem_case_2b"
    if recursive_calls == 2 and nonrecursive_work == "constant":
        return "T(n) = 2T(n / 2) + O(1)", "O(n)", "master_theorem_case_1"
    if recursive_calls == 2 and nonrecursive_work == "linear":
        return "T(n) = 2T(n / 2) + O(n)", "O(n log n)", "master_theorem_case_2"
    return None


def recurrence_evidence(
    *,
    function: str,
    recursive_calls: int,
    size_reduction: str,
    nonrecursive_work: str,
    recurrence: str,
    solving_rule: str,
    complexity: str,
    assumptions: list[str],
    location: dict[str, int | str | None] | None = None,
) -> dict:
    work_label = {"constant": "O(1)", "linear": "O(n)"}.get(
        nonrecursive_work, nonrecursive_work
    )
    return {
        "rule_version": RULE_VERSION,
        "source_location": location or {"function": function, "line": None},
        "recursive_call_pattern": f"{recursive_calls} recursive call(s) per recurrence level",
        "recursive_calls_per_level": recursive_calls,
        "input_size_reduction": size_reduction,
        "nonrecursive_work": work_label,
        "base_case": "recognized terminating base case required by the language-specific matcher",
        "recurrence": recurrence,
        "solving_rule": solving_rule,
        "complexity": complexity,
        "assumptions": assumptions,
        "inference_kind": "heuristic_pattern_match",
    }
