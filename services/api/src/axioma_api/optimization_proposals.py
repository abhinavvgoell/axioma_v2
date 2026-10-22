"""Narrow, deterministic optimization suggestions that never execute submitted code."""

from __future__ import annotations

import ast
import re

from axioma_api.contracts import (
    FunctionInterface,
    FunctionSample,
    OptimizationProposal,
    OptimizationProposalResponse,
    ProblemSpec,
)

_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"
_TITLE = "Replace an explicit integer-array accumulation loop with a reduction"
_SUMMARY = (
    "This exact accumulation pattern can be expressed with the language's built-in sum "
    "operation. The rewrite is a candidate to check; it is not assumed to be faster."
)
_LIMITATIONS = [
    "The rule recognizes one exact function pattern and integer-array examples only.",
    "A static match does not establish equivalent behavior for every valid input.",
    "Run sample and reference-guided differential checks before relying on the candidate.",
    "Benchmark the original and candidate on representative increasing input sizes; a lower source-level cost does not guarantee a speedup.",
]
_TWO_SUM_LIMITATIONS = [
    "This rule supports Python functions with the exact nested pair-search structure it recognizes.",
    "The hash-map lookup has expected O(n) time and uses O(n) auxiliary space; hash operations have worst-case caveats.",
    "The candidate scans from right to left so it preserves the first pair returned by the recognized nested-loop order.",
    "A static match is only a candidate. Run the supplied checks and increasing-size benchmarks before relying on it.",
]


def _has_integer_first_argument_samples(problem: ProblemSpec) -> bool:
    return bool(problem.samples) and all(
        isinstance(sample, FunctionSample)
        and bool(sample.args)
        and isinstance(sample.args[0], list)
        and all(type(value) is int for value in sample.args[0])
        for sample in problem.samples
    )


def _python_candidate(code: str, entrypoint: str) -> str | None:
    if "." in entrypoint:
        return None
    try:
        module = ast.parse(code)
    except SyntaxError:
        return None
    functions = [
        node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint
    ]
    if len(functions) != 1 or not isinstance(functions[0], ast.FunctionDef):
        return None
    function = functions[0]
    if len(function.body) != 3:
        return None
    initialize, loop, result = function.body
    if not isinstance(initialize, ast.Assign) or len(initialize.targets) != 1:
        return None
    if not isinstance(initialize.targets[0], ast.Name):
        return None
    accumulator = initialize.targets[0].id
    if not isinstance(initialize.value, ast.Constant) or type(initialize.value.value) is not int:
        return None
    if initialize.value.value != 0 or not isinstance(loop, ast.For) or loop.orelse:
        return None
    if not isinstance(loop.target, ast.Name) or not isinstance(loop.iter, ast.Name):
        return None
    item_name = loop.target.id
    sequence_name = loop.iter.id
    parameters = [*function.args.posonlyargs, *function.args.args]
    if not parameters or parameters[0].arg != sequence_name or len(loop.body) != 1:
        return None
    addition = loop.body[0]
    if (
        not isinstance(addition, ast.AugAssign)
        or not isinstance(addition.target, ast.Name)
        or addition.target.id != accumulator
        or not isinstance(addition.op, ast.Add)
        or not isinstance(addition.value, ast.Name)
        or addition.value.id != item_name
    ):
        return None
    if (
        not isinstance(result, ast.Return)
        or not isinstance(result.value, ast.Name)
        or result.value.id != accumulator
        or result.end_lineno is None
    ):
        return None

    lines = code.splitlines(keepends=True)
    start = initialize.lineno - 1
    end = result.end_lineno
    original_line = lines[start]
    indentation = original_line[: len(original_line) - len(original_line.lstrip(" \t"))]
    newline = "\r\n" if original_line.endswith("\r\n") else "\n"
    replacement = f"{indentation}return sum({sequence_name}){newline}"
    return "".join([*lines[:start], replacement, *lines[end:]])


def _is_two_sum_problem(problem: ProblemSpec) -> bool:
    statement = re.sub(r"\s+", " ", problem.statement).casefold()
    return bool(
        re.search(r"\btwo[ -]*sum\b", statement)
        or re.search(
            r"\breturn indices of the two numbers\b.{0,180}\badd up to (?:the )?target\b",
            statement,
        )
    )


def _python_two_sum_candidate(code: str, entrypoint: str) -> str | None:
    try:
        module = ast.parse(code)
    except SyntaxError:
        return None
    parts = entrypoint.split(".")
    if len(parts) == 1:
        functions = [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == parts[0]
        ]
    else:
        classes = [
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == parts[0]
        ]
        if len(classes) != 1:
            return None
        functions = [
            node for node in classes[0].body
            if isinstance(node, ast.FunctionDef) and node.name == parts[1]
        ]
    if len(functions) != 1:
        return None
    function = functions[0]
    parameters = [*function.args.posonlyargs, *function.args.args]
    if len(parts) > 1:
        parameters = [parameter for parameter in parameters if parameter.arg != "self"]
    if len(parameters) != 2 or len(function.body) != 2:
        return None
    nums_name, target_name = (parameter.arg for parameter in parameters)
    outer, fallback = function.body
    if not isinstance(outer, ast.For) or outer.orelse or not isinstance(outer.target, ast.Name):
        return None
    i_name = outer.target.id
    if not (
        isinstance(outer.iter, ast.Call)
        and isinstance(outer.iter.func, ast.Name)
        and outer.iter.func.id == "range"
        and len(outer.iter.args) == 1
        and isinstance(outer.iter.args[0], ast.Call)
        and isinstance(outer.iter.args[0].func, ast.Name)
        and outer.iter.args[0].func.id == "len"
        and len(outer.iter.args[0].args) == 1
        and isinstance(outer.iter.args[0].args[0], ast.Name)
        and outer.iter.args[0].args[0].id == nums_name
        and len(outer.body) == 1
    ):
        return None
    inner = outer.body[0]
    if not isinstance(inner, ast.For) or inner.orelse or not isinstance(inner.target, ast.Name):
        return None
    j_name = inner.target.id
    inner_range = inner.iter
    if not (
        isinstance(inner_range, ast.Call)
        and isinstance(inner_range.func, ast.Name)
        and inner_range.func.id == "range"
        and len(inner_range.args) == 2
        and isinstance(inner_range.args[0], ast.BinOp)
        and isinstance(inner_range.args[0].left, ast.Name)
        and inner_range.args[0].left.id == i_name
        and isinstance(inner_range.args[0].op, ast.Add)
        and isinstance(inner_range.args[0].right, ast.Constant)
        and inner_range.args[0].right.value == 1
        and isinstance(inner_range.args[1], ast.Call)
        and isinstance(inner_range.args[1].func, ast.Name)
        and inner_range.args[1].func.id == "len"
        and len(inner_range.args[1].args) == 1
        and isinstance(inner_range.args[1].args[0], ast.Name)
        and inner_range.args[1].args[0].id == nums_name
        and len(inner.body) == 1
    ):
        return None
    condition = inner.body[0]
    if not (
        isinstance(condition, ast.If)
        and not condition.orelse
        and len(condition.body) == 1
        and isinstance(condition.test, ast.Compare)
        and len(condition.test.ops) == 1
        and isinstance(condition.test.ops[0], ast.Eq)
        and len(condition.test.comparators) == 1
    ):
        return None
    comparison = condition.test
    addition = comparison.left
    def is_indexed_name(node: ast.AST, index_name: str) -> bool:
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == nums_name
            and isinstance(node.slice, ast.Name)
            and node.slice.id == index_name
        )

    if not (
        isinstance(addition, ast.BinOp)
        and isinstance(addition.op, ast.Add)
        and is_indexed_name(addition.left, i_name)
        and is_indexed_name(addition.right, j_name)
    ):
        return None
    if not isinstance(comparison.comparators[0], ast.Name) or comparison.comparators[0].id != target_name:
        return None
    answer = condition.body[0]
    if not (
        isinstance(answer, ast.Return)
        and isinstance(answer.value, ast.List)
        and len(answer.value.elts) == 2
        and all(isinstance(value, ast.Name) for value in answer.value.elts)
        and [value.id for value in answer.value.elts] == [i_name, j_name]
    ):
        return None
    if not (
        isinstance(fallback, ast.Return)
        and isinstance(fallback.value, ast.List)
        and not fallback.value.elts
        and outer.end_lineno is not None
        and fallback.end_lineno is not None
    ):
        return None

    lines = code.splitlines(keepends=True)
    start = outer.lineno - 1
    end = fallback.end_lineno
    outer_line = lines[start]
    outer_indent = outer_line[: len(outer_line) - len(outer_line.lstrip(" \t"))]
    inner_line = lines[inner.lineno - 1]
    inner_indent = inner_line[: len(inner_line) - len(inner_line.lstrip(" \t"))]
    step = inner_indent[len(outer_indent) :]
    if not step:
        return None
    newline = "\r\n" if outer_line.endswith("\r\n") else "\n"
    deeper_indent = inner_indent + step
    replacement_lines = [
        f"{outer_indent}seen = {{}}{newline}",
        f"{outer_indent}answer = None{newline}",
        f"{outer_indent}for {i_name} in range(len({nums_name}) - 1, -1, -1):{newline}",
        f"{inner_indent}complement = {target_name} - {nums_name}[{i_name}]{newline}",
        f"{inner_indent}if complement in seen:{newline}",
        f"{deeper_indent}answer = [{i_name}, seen[complement]]{newline}",
        f"{inner_indent}seen[{nums_name}[{i_name}]] = {i_name}{newline}",
        f"{outer_indent}return answer if answer is not None else []{newline}",
    ]
    return "".join([*lines[:start], *replacement_lines, *lines[end:]])


def _java_candidate(code: str, entrypoint: str) -> str | None:
    method_name = entrypoint.rsplit(".", maxsplit=1)[-1]
    declaration = re.search(
        rf"\bint\s+{re.escape(method_name)}\s*\(\s*int\s*\[\s*\]\s*(?P<sequence>{_IDENTIFIER})\s*\)",
        code,
    )
    if declaration is None:
        return None
    sequence = declaration.group("sequence")
    loop = re.compile(
        rf"^(?P<indent>[ \t]*)int\s+(?P<total>{_IDENTIFIER})\s*=\s*0;\r?\n"
        rf"(?P=indent)for\s*\(\s*int\s+(?P<item>{_IDENTIFIER})\s*:\s*{re.escape(sequence)}\s*\)\s*\{{\r?\n"
        rf"(?P<body_indent>[ \t]+)(?P=total)\s*\+=\s*(?P=item)\s*;\r?\n"
        rf"(?P=indent)\}}\r?\n"
        rf"(?P=indent)return\s+(?P=total)\s*;(?=\r?$)",
        re.MULTILINE,
    )
    matches = list(loop.finditer(code))
    if len(matches) != 1:
        return None
    match = matches[0]
    replacement = f"{match.group('indent')}return java.util.Arrays.stream({sequence}).sum();"
    return code[: match.start()] + replacement + code[match.end() :]


def propose_optimizations(
    language: str,
    code: str,
    problem: ProblemSpec,
) -> OptimizationProposalResponse:
    if not isinstance(problem.interface, FunctionInterface):
        return OptimizationProposalResponse(
            proposals=[], message="Rule-based proposals currently require a function interface."
        )
    if _is_two_sum_problem(problem):
        if language != "python":
            return OptimizationProposalResponse(
                proposals=[],
                message="The Two Sum improvement rule currently supports Python only.",
            )
        if not _has_integer_first_argument_samples(problem) or not all(
            isinstance(sample, FunctionSample)
            and len(sample.args) >= 2
            and type(sample.args[1]) is int
            for sample in problem.samples
        ):
            return OptimizationProposalResponse(
                proposals=[],
                message="No Two Sum proposal was made: examples must include an integer array and integer target.",
            )
        candidate = _python_two_sum_candidate(code, problem.interface.entrypoint)
        if candidate is None:
            return OptimizationProposalResponse(
                proposals=[],
                message="No supported nested pair-search pattern matched; the original source was left unchanged.",
            )
        proposal = OptimizationProposal(
            rule_id="two_sum_pairwise_to_hash_map_v1",
            title="Replace pairwise search with a hash map",
            summary=(
                "The nested loop checks pairs in O(n²) time. This candidate scans backward and "
                "uses a hash map for expected O(n) time, preserving the first pair returned by "
                "the recognized loop order at the cost of O(n) extra space."
            ),
            candidate_code=candidate,
            limitations=list(_TWO_SUM_LIMITATIONS),
        )
        return OptimizationProposalResponse(
            proposals=[proposal],
            message="A static candidate matched. Run it against the supplied checks and benchmarks before relying on it.",
        )
    if not _has_integer_first_argument_samples(problem):
        return OptimizationProposalResponse(
            proposals=[],
            message="No proposal was made: this rule requires integer-array examples in the first argument.",
        )

    candidate = (
        _python_candidate(code, problem.interface.entrypoint)
        if language == "python"
        else _java_candidate(code, problem.interface.entrypoint)
        if language == "java"
        else None
    )
    if candidate is None:
        return OptimizationProposalResponse(
            proposals=[],
            message="No supported pattern matched. The original source was left unchanged.",
        )

    proposal = OptimizationProposal(
        rule_id="integer_array_accumulation_to_sum_v1",
        title=_TITLE,
        summary=_SUMMARY,
        candidate_code=candidate,
        limitations=list(_LIMITATIONS),
    )
    return OptimizationProposalResponse(
        proposals=[proposal],
        message="A static candidate matched. It remains unverified until you run Mode 1 checks.",
    )
