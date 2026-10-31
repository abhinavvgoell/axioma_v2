"""Safe parser and conservative comparator for BFS v2 Big-O labels."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import json
import math
import re
from typing import TypeAlias

VARIABLES = frozenset({"V", "E", "R", "C", "Q", "N", "S"})
MAX_EXPRESSION_LENGTH = 512
MAX_TOKENS = 256
MAX_POWER = 8
MAX_TERMS = 512

Monomial: TypeAlias = tuple[tuple[str, int], ...]
Polynomial: TypeAlias = dict[Monomial, int]


class ComplexitySyntaxError(ValueError):
    """Raised for unsupported or malformed complexity notation."""


@dataclass(frozen=True)
class _Node:
    kind: str
    value: str | int | None = None
    children: tuple[_Node, ...] = ()


@dataclass(frozen=True)
class ParsedComplexity:
    original: str
    normalized: str
    canonical: tuple[tuple[Monomial, int], ...]
    _polynomial: Polynomial


_TOKEN_RE = re.compile(r"\*\*|[()+*^=]|[A-Za-z][A-Za-z0-9_]*|\d+")


def _lex(expression: str) -> list[str]:
    if not isinstance(expression, str) or not expression.strip():
        raise ComplexitySyntaxError("complexity expression must be a non-empty string")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ComplexitySyntaxError("complexity expression exceeds the length limit")
    text = expression.replace("²", "^2").replace("×", "*").replace("·", "*")
    tokens: list[str] = []
    offset = 0
    while offset < len(text):
        if text[offset].isspace():
            offset += 1
            continue
        match = _TOKEN_RE.match(text, offset)
        if match is None:
            raise ComplexitySyntaxError(f"unsupported character at position {offset}")
        tokens.append(match.group())
        offset = match.end()
    if len(tokens) > MAX_TOKENS:
        raise ComplexitySyntaxError("complexity expression exceeds the token limit")

    # Accept conventional implicit multiplication such as V(E + 1), 2V, and VE.
    expanded_variables: list[str] = []
    for token in tokens:
        if (
            token not in VARIABLES
            and len(token) > 1
            and all(char in VARIABLES for char in token)
        ):
            expanded_variables.extend(token)
        else:
            expanded_variables.append(token)
    expanded: list[str] = []
    for token in expanded_variables:
        if expanded:
            previous = expanded[-1]
            previous_ends_atom = (
                previous == ")" or previous.isdigit() or (previous in VARIABLES)
            )
            next_starts_atom = (
                token == "(" or token.isdigit() or token in VARIABLES or token == "log"
            )
            is_function_open = token == "(" and previous in {"log", "O"}
            adjacent_numbers = previous.isdigit() and token.isdigit()
            if (
                previous_ends_atom
                and next_starts_atom
                and not is_function_open
                and not adjacent_numbers
            ):
                expanded.append("*")
        expanded.append(token)
    return expanded


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.position = 0

    def _peek(self) -> str | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None:
            raise ComplexitySyntaxError("unexpected end of expression")
        if expected is not None and token != expected:
            raise ComplexitySyntaxError(f"expected {expected!r}, found {token!r}")
        self.position += 1
        return token

    def parse_big_o(self) -> _Node:
        if self._take() != "O":
            raise ComplexitySyntaxError("expression must use an outer O(...) wrapper")
        self._take("(")
        node = self._parse_sum()
        self._take(")")
        if self._peek() is not None:
            raise ComplexitySyntaxError(f"unexpected token {self._peek()!r}")
        return node

    def _parse_sum(self) -> _Node:
        nodes = [self._parse_product()]
        while self._peek() == "+":
            self._take("+")
            nodes.append(self._parse_product())
        return nodes[0] if len(nodes) == 1 else _Node("add", children=tuple(nodes))

    def _parse_product(self) -> _Node:
        nodes = [self._parse_power()]
        while self._peek() == "*":
            self._take("*")
            nodes.append(self._parse_power())
        return nodes[0] if len(nodes) == 1 else _Node("mul", children=tuple(nodes))

    def _parse_power(self) -> _Node:
        base = self._parse_atom()
        if self._peek() in {"^", "**"}:
            self.position += 1
            exponent_token = self._take()
            if not exponent_token.isdigit():
                raise ComplexitySyntaxError(
                    "power must be a non-negative integer literal"
                )
            exponent = int(exponent_token)
            if exponent > MAX_POWER:
                raise ComplexitySyntaxError(
                    f"power exceeds the supported limit {MAX_POWER}"
                )
            if self._peek() in {"^", "**"}:
                raise ComplexitySyntaxError("chained powers are unsupported")
            return _Node("pow", value=exponent, children=(base,))
        return base

    def _parse_atom(self) -> _Node:
        token = self._take()
        if token == "(":
            node = self._parse_sum()
            self._take(")")
            return node
        if token.isdigit():
            value = int(token)
            if value > 1000:
                raise ComplexitySyntaxError(
                    "integer constant exceeds the supported limit"
                )
            return _Node("number", value=value)
        if token == "log":
            if self._peek() == "(":
                self._take("(")
                argument = self._parse_sum()
                self._take(")")
            else:
                argument = self._parse_atom()
            return _Node("log", children=(argument,))
        if token in VARIABLES:
            return _Node("variable", value=token)
        raise ComplexitySyntaxError(f"unsupported variable or function {token!r}")


def _flatten(node: _Node, kind: str) -> list[_Node]:
    if node.kind != kind:
        return [node]
    result: list[_Node] = []
    for child in node.children:
        result.extend(_flatten(child, kind))
    return result


def _render(node: _Node, parent_precedence: int = 0) -> str:
    precedence = {"add": 1, "mul": 2, "pow": 3, "log": 4, "variable": 4, "number": 4}[
        node.kind
    ]
    if node.kind == "variable":
        rendered = str(node.value)
    elif node.kind == "number":
        rendered = str(node.value)
    elif node.kind == "log":
        rendered = f"log({_render(node.children[0])})"
    elif node.kind == "pow":
        base = node.children[0]
        base_text = _render(base)
        if base.kind in {"add", "mul"}:
            base_text = f"({base_text})"
        rendered = f"{base_text}^{node.value}"
    elif node.kind == "add":
        rendered = "+".join(
            _render(child, precedence) for child in _flatten(node, "add")
        )
    else:
        pieces = []
        for child in _flatten(node, "mul"):
            child_text = _render(child)
            if child.kind == "add":
                child_text = f"({child_text})"
            pieces.append(child_text)
        rendered = "*".join(pieces)
    if precedence < parent_precedence:
        return f"({rendered})"
    return rendered


def _clean(poly: Polynomial) -> Polynomial:
    cleaned = {
        monomial: coefficient for monomial, coefficient in poly.items() if coefficient
    }
    if len(cleaned) > MAX_TERMS:
        raise ComplexitySyntaxError("expanded expression exceeds the term limit")
    return cleaned


def _poly_add(left: Polynomial, right: Polynomial) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in right.items():
        result[monomial] = result.get(monomial, 0) + coefficient
    return _clean(result)


def _multiply_monomials(left: Monomial, right: Monomial) -> Monomial:
    powers: dict[str, int] = {}
    for atom, exponent in (*left, *right):
        powers[atom] = powers.get(atom, 0) + exponent
    return tuple(sorted(powers.items()))


def _poly_mul(left: Polynomial, right: Polynomial) -> Polynomial:
    if len(left) * len(right) > MAX_TERMS * MAX_TERMS:
        raise ComplexitySyntaxError("multiplication exceeds the expansion limit")
    result: Polynomial = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            monomial = _multiply_monomials(left_monomial, right_monomial)
            result[monomial] = (
                result.get(monomial, 0) + left_coefficient * right_coefficient
            )
    return _clean(result)


def _poly_power(poly: Polynomial, exponent: int) -> Polynomial:
    result: Polynomial = {(): 1}
    for _ in range(exponent):
        result = _poly_mul(result, poly)
    return result


def _canonical_poly(poly: Polynomial) -> tuple[tuple[Monomial, int], ...]:
    cleaned = _clean(poly)
    if not cleaned:
        return ()
    divisor = math.gcd(*cleaned.values())
    return tuple(
        sorted(
            (monomial, coefficient // divisor)
            for monomial, coefficient in cleaned.items()
        )
    )


def _poly(node: _Node) -> Polynomial:
    if node.kind == "number":
        return {(): int(node.value)}
    if node.kind == "variable":
        return {((f"var:{node.value}", 1),): 1}
    if node.kind == "add":
        result: Polynomial = {}
        for child in node.children:
            result = _poly_add(result, _poly(child))
        return result
    if node.kind == "mul":
        result = {(): 1}
        for child in node.children:
            result = _poly_mul(result, _poly(child))
        return result
    if node.kind == "pow":
        return _poly_power(_poly(node.children[0]), int(node.value))
    if node.kind == "log":
        argument = _canonical_poly(_poly(node.children[0]))
        atom_key = "log:" + json.dumps(argument, separators=(",", ":"))
        return {((atom_key, 1),): 1}
    raise ComplexitySyntaxError(f"unsupported expression node {node.kind!r}")


def parse_complexity(expression: str) -> ParsedComplexity:
    """Parse a bounded Big-O expression without evaluating input text."""
    tokens = _lex(expression)
    parts: list[list[str]] = [[]]
    depth = 0
    for token in tokens:
        if token == "=":
            if depth != 0 or not parts[-1]:
                raise ComplexitySyntaxError(
                    "equality must separate complete Big-O expressions"
                )
            parts.append([])
            continue
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                raise ComplexitySyntaxError("unmatched closing parenthesis")
        parts[-1].append(token)
    if depth != 0 or not parts[-1]:
        raise ComplexitySyntaxError("unmatched parenthesis or incomplete equality")
    nodes = [_Parser(part).parse_big_o() for part in parts]
    polynomials = [_poly(node) for node in nodes]
    signatures = [_canonical_poly(poly) for poly in polynomials]
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ComplexitySyntaxError(
            "Big-O equality chain contains non-equivalent expressions"
        )
    polynomial = polynomials[0]
    normalized = " = ".join(f"O({_render(node)})" for node in nodes)
    canonical = _canonical_poly(polynomial)
    return ParsedComplexity(
        original=expression,
        normalized=normalized,
        canonical=canonical,
        _polynomial=polynomial,
    )


def _ray_degree(
    poly: Polynomial, variables: tuple[str, ...], weights: tuple[int, ...]
) -> int:
    best = -1
    weight_map = dict(zip(variables, weights))
    for monomial, coefficient in poly.items():
        if coefficient <= 0:
            continue
        degree = 0
        for atom, exponent in monomial:
            if not atom.startswith("var:"):
                raise ComplexitySyntaxError(
                    "logarithmic comparison requires a supported identity"
                )
            degree += weight_map[atom[4:]] * exponent
        best = max(best, degree)
    return best


def _proves_mismatch(left: ParsedComplexity, right: ParsedComplexity) -> bool:
    atoms = {
        atom
        for parsed in (left, right)
        for monomial, _ in parsed.canonical
        for atom, _ in monomial
    }
    if any(not atom.startswith("var:") for atom in atoms):
        return False
    variables = tuple(sorted(atom[4:] for atom in atoms))
    if not variables:
        return False
    # A different degree along any positive independent-parameter ray proves
    # non-equivalence. Failure to find a witness is deliberately unscorable.
    for weights in product(range(4), repeat=len(variables)):
        if not any(weights):
            continue
        if _ray_degree(left._polynomial, variables, weights) != _ray_degree(
            right._polynomial, variables, weights
        ):
            return True
    return False


def compare_complexities(expected: str, actual: str) -> dict[str, str | None]:
    """Compare complexity notation conservatively; never maps parse errors to unknown."""
    try:
        expected_parsed = parse_complexity(expected)
    except ComplexitySyntaxError as exc:
        return {
            "status": "unscorable",
            "expected_original": expected,
            "actual_original": actual,
            "expected_normalized": None,
            "actual_normalized": None,
            "reason": f"Expected expression could not be parsed: {exc}",
        }
    try:
        actual_parsed = parse_complexity(actual)
    except ComplexitySyntaxError as exc:
        return {
            "status": "unscorable",
            "expected_original": expected,
            "actual_original": actual,
            "expected_normalized": expected_parsed.normalized,
            "actual_normalized": None,
            "reason": f"Actual expression could not be parsed: {exc}",
        }
    if expected_parsed.normalized == actual_parsed.normalized:
        status = "exact_match"
        reason = "Notation matches after formatting normalization."
    elif expected_parsed.canonical == actual_parsed.canonical:
        status = "mathematically_equivalent"
        reason = "Expanded symbolic forms are algebraically identical up to a positive constant factor."
    elif _proves_mismatch(expected_parsed, actual_parsed):
        status = "mismatch"
        reason = "A positive independent-parameter growth ray proves different asymptotic orders."
    else:
        status = "unscorable"
        reason = (
            "The bounded comparator cannot safely establish equivalence or a mismatch."
        )
    return {
        "status": status,
        "expected_original": expected,
        "actual_original": actual,
        "expected_normalized": expected_parsed.normalized,
        "actual_normalized": actual_parsed.normalized,
        "reason": reason,
    }
