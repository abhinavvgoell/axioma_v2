from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class JavaMutationSource:
    id: str
    label: str
    class_name: str
    code: str


_REPLACEMENTS: dict[str, tuple[str, ...]] = {
    "+": ("-",),
    "-": ("+",),
    "*": ("/",),
    "/": ("*", "%"),
    "%": ("/",),
    "==": ("!=",),
    "!=": ("==",),
    "<": ("<=", ">"),
    "<=": ("<",),
    ">": (">=", "<"),
    ">=": (">",),
    "&&": ("||",),
    "||": ("&&",),
}
_OPERATORS = tuple(sorted({*_REPLACEMENTS, "+=", "-=", "*=", "/=", "%=", "++", "--", "->", "::"}, key=len, reverse=True))
_NON_RETURN_TYPES = {"return", "throw", "new", "this", "super", "if", "for", "while", "switch", "catch"}


@dataclass(frozen=True)
class _Token:
    value: str
    start: int
    end: int
    kind: str


def _tokens(source: str) -> list[_Token]:
    result: list[_Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline < 0 else newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
            continue
        if source.startswith('"""', index):
            end = source.find('"""', index + 3)
            index = len(source) if end < 0 else end + 3
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            continue
        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < len(source) and (source[index].isalnum() or source[index] in "_$"):
                index += 1
            result.append(_Token(source[start:index], start, index, "identifier"))
            continue
        operator = next((value for value in _OPERATORS if source.startswith(value, index)), None)
        if operator is not None:
            result.append(_Token(operator, index, index + len(operator), "operator"))
            index += len(operator)
            continue
        result.append(_Token(char, index, index + 1, "punctuation"))
        index += 1
    return result


def _replace(source: str, edits: list[tuple[int, int, str]]) -> str:
    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _target_method_body(tokens: list[_Token], method_name: str) -> tuple[int, int] | None:
    method_ranges: list[tuple[int, int]] = []
    for index, token in enumerate(tokens[:-1]):
        if token.value != method_name or tokens[index + 1].value != "(":
            continue
        previous = tokens[index - 1].value if index else ""
        if previous in _NON_RETURN_TYPES or previous == ".":
            continue
        depth = 0
        closing = None
        for cursor in range(index + 1, len(tokens)):
            if tokens[cursor].value == "(":
                depth += 1
            elif tokens[cursor].value == ")":
                depth -= 1
                if depth == 0:
                    closing = cursor
                    break
        if closing is None:
            continue
        cursor = closing + 1
        while cursor < len(tokens) and tokens[cursor].value not in {"{", ";"}:
            cursor += 1
        if cursor >= len(tokens) or tokens[cursor].value != "{":
            continue
        body_depth = 1
        end = cursor + 1
        while end < len(tokens) and body_depth:
            if tokens[end].value == "{":
                body_depth += 1
            elif tokens[end].value == "}":
                body_depth -= 1
            end += 1
        if body_depth == 0:
            method_ranges.append((cursor + 1, end - 1))
    return method_ranges[0] if len(method_ranges) == 1 else None


def generate_java_mutants(
    source: str,
    method_name: str,
    limit: int = 20,
) -> list[JavaMutationSource]:
    """Create deterministic single-operator mutants inside the selected Reference method."""
    if limit <= 0:
        return []
    tokens = _tokens(source)
    class_declarations = [
        index
        for index in range(len(tokens) - 1)
        if tokens[index].value == "class" and tokens[index + 1].value == "Reference"
    ]
    if len(class_declarations) != 1:
        return []
    body = _target_method_body(tokens, method_name)
    if body is None:
        return []
    reference_tokens = [
        token for token in tokens if token.kind == "identifier" and token.value == "Reference"
    ]
    if not reference_tokens:
        return []

    mutants: list[JavaMutationSource] = []
    for token_index, token in enumerate(tokens):
        if not body[0] <= token_index < body[1]:
            continue
        for replacement in _REPLACEMENTS.get(token.value, ()):
            if token.kind != "operator":
                continue
            mutant_id = f"mutant_{len(mutants) + 1}"
            class_name = f"AxiomaMutant{len(mutants) + 1}"
            edits = [(item.start, item.end, class_name) for item in reference_tokens]
            edits.append((token.start, token.end, replacement))
            mutants.append(
                JavaMutationSource(
                    id=mutant_id,
                    label=f"operator_{token.value}_to_{replacement}_offset_{token.start}",
                    class_name=class_name,
                    code=_replace(source, edits),
                )
            )
            if len(mutants) >= limit:
                return mutants
    return mutants
