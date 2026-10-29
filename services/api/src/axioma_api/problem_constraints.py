from __future__ import annotations

import re

from axioma_api.contracts import ConstraintRange


_BOUND = r"-?\d+(?:\^\d+)?"
_RANGE = re.compile(
    rf"^\s*(?:[-*•]\s*)?(?P<minimum>{_BOUND})\s*<=\s*"
    rf"(?P<name>[A-Za-z_]\w*(?:\.length)?)\s*<=\s*(?P<maximum>{_BOUND})\s*$",
    re.MULTILINE,
)
_CONSTRAINTS_SECTION = re.compile(
    r"(?:^|\n)\s*Constraints\s*:\s*(?P<body>.*)", re.IGNORECASE | re.DOTALL
)


def _number(source: str) -> int | None:
    sign = -1 if source.startswith("-") else 1
    unsigned = source[1:] if sign < 0 else source
    if "^" in unsigned:
        base_text, exponent_text = unsigned.split("^", maxsplit=1)
        if len(base_text) > 9 or len(exponent_text) > 2:
            return None
        base, exponent = int(base_text), int(exponent_text)
        if exponent > 64:
            return None
        result = base**exponent
    elif re.fullmatch(r"10[3-9]", unsigned):
        # The pinned plain-text dataset drops the superscript marker in values
        # such as 10^4, leaving 104. Treat only this common LeetCode form as a
        # power; other ambiguous numeric forms remain literal or unsupported.
        result = 10 ** int(unsigned[-1])
    else:
        if len(unsigned) > 19:
            return None
        result = int(unsigned)
    if result.bit_length() > 63:
        return None
    return sign * result


def parse_problem_constraints(
    statement: str, argument_order: list[str]
) -> list[ConstraintRange]:
    """Extract only simple LeetCode numeric ranges with a known argument mapping."""
    section = _CONSTRAINTS_SECTION.search(statement)
    if section is None:
        return []

    indexes: dict[str, int] = {}
    for index, name in enumerate(argument_order):
        if name in indexes:
            return []
        indexes[name] = index

    constraints: list[ConstraintRange] = []
    seen_paths: set[str] = set()
    for match in _RANGE.finditer(section.group("body")):
        variable = match.group("name")
        is_length = variable.endswith(".length")
        name = variable.removesuffix(".length") if is_length else variable
        if name not in indexes:
            continue
        minimum = _number(match.group("minimum"))
        maximum = _number(match.group("maximum"))
        if minimum is None or maximum is None or minimum > maximum:
            continue
        path = f"args[{indexes[name]}]" + (".length" if is_length else "")
        if path in seen_paths:
            continue
        seen_paths.add(path)
        constraints.append(
            ConstraintRange(
                path=path,
                minimum=minimum,
                maximum=maximum,
                description=re.sub(r"^[-*•]\s*", "", match.group(0).strip()),
            )
        )
    return constraints


def constraints_match_samples(
    constraints: list[ConstraintRange], samples: list[dict]
) -> list[ConstraintRange]:
    """Keep extracted ranges only when every imported example satisfies them."""
    compatible: list[ConstraintRange] = []
    for constraint in constraints:
        match = re.fullmatch(r"args\[(\d+)\](\.length)?", constraint.path)
        if match is None:
            continue
        index = int(match.group(1))
        is_length = match.group(2) is not None
        values = []
        for sample in samples:
            args = sample.get("args", [])
            if index >= len(args):
                break
            value = args[index]
            if is_length:
                if not isinstance(value, (str, list, dict)):
                    break
                value = len(value)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                break
            values.append(value)
        if len(values) != len(samples):
            continue
        if all(
            (constraint.minimum is None or value >= constraint.minimum)
            and (constraint.maximum is None or value <= constraint.maximum)
            for value in values
        ):
            compatible.append(constraint)
    return compatible
