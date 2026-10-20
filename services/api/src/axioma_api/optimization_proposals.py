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
