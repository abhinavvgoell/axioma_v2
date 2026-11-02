from __future__ import annotations

from bisect import bisect_right
import re

from axioma_worker.python_complexity import ComplexityEstimate
from axioma_worker.python_complexity import add_line_event_fit, fit_growth_model
from axioma_worker.recurrence import recurrence_evidence, solve_bounded_recurrence

_TOKEN = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"[A-Za-z_$][\w$]*|\d+|\+\+|--|\+=|-=|==|!=|<=|>=|&&|\|\||[^\s]"
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


def _token_line_numbers(source: str) -> list[int]:
    """Return source lines parallel to _tokens, excluding comments and string literals."""
    line_starts = [0] + [index + 1 for index, char in enumerate(source) if char == "\n"]
    return [
        bisect_right(line_starts, match.start())
        for match in _TOKEN.finditer(source)
        if not match.group().startswith(("//", "/*", '"', "'"))
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
    bounds = _method_body_bounds(tokens, class_range, method_name)
    return tokens[bounds[0] : bounds[1]] if bounds is not None else None


def _method_body_bounds(
    tokens: list[str], class_range: tuple[int, int], method_name: str
) -> tuple[int, int] | None:
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
            return body_open + 1, body_close
    return None


def _call_arguments(tokens: list[str], name: str) -> list[tuple[int, list[list[str]]]]:
    calls: list[tuple[int, list[list[str]]]] = []
    for index in range(len(tokens) - 1):
        if tokens[index] != name or tokens[index + 1] != "(":
            continue
        close = _matching(tokens, index + 1, "(", ")")
        if close is None:
            continue
        arguments: list[list[str]] = []
        start = index + 2
        depth = 0
        for cursor in range(start, close):
            if tokens[cursor] in {"(", "[", "{"}:
                depth += 1
            elif tokens[cursor] in {")", "]", "}"}:
                depth -= 1
            elif tokens[cursor] == "," and depth == 0:
                arguments.append(tokens[start:cursor])
                start = cursor + 1
        if start < close:
            arguments.append(tokens[start:close])
        calls.append((index, arguments))
    return calls


def _method_parameter_names(
    tokens: list[str], class_range: tuple[int, int], method_name: str
) -> list[str] | None:
    class_start, class_end = class_range
    for index in range(class_start + 1, class_end - 1):
        if tokens[index] != method_name or tokens[index + 1] != "(":
            continue
        close = _matching(tokens, index + 1, "(", ")")
        if close is None:
            continue
        names: list[str] = []
        start = index + 2
        depth = 0
        for cursor in range(start, close + 1):
            if cursor < close and tokens[cursor] in {"<", "[", "("}:
                depth += 1
            elif cursor < close and tokens[cursor] in {">", "]", ")"}:
                depth -= 1
            if cursor == close or (tokens[cursor] == "," and depth == 0):
                group = tokens[start:cursor]
                identifiers = [token for token in group if re.fullmatch(r"[A-Za-z_$][\w$]*", token)]
                if identifiers:
                    names.append(identifiers[-1])
                start = cursor + 1
        return names
    return None


def _strip_parentheses(expression: list[str]) -> list[str]:
    while (
        len(expression) >= 2
        and expression[0] == "("
        and _matching(expression, 0, "(", ")") == len(expression) - 1
    ):
        expression = expression[1:-1]
    return expression


def _java_scalar_reduction(expression: list[str], parameter: str) -> str | None:
    expression = _strip_parentheses(expression)
    if len(expression) == 3 and expression[0] == parameter and expression[2].isdigit():
        amount = int(expression[2])
        if amount > 0 and expression[1] == "-":
            return "constant_decrement"
        if amount == 2 and expression[1] == "/":
            return "factor_two"
    return None


def _has_java_scalar_base_case(tokens: list[str], parameter: str) -> bool:
    for index, token in enumerate(tokens):
        if token != "if":
            continue
        header = _loop_header(tokens, index)
        if header is None:
            continue
        opening, closing = header
        condition = tokens[opening + 1 : closing]
        if not (
            len(condition) == 3
            and condition[0] == parameter
            and condition[1] in {"<", ">", "<=", ">="}
            and condition[2].isdigit()
        ):
            continue
        branch = tokens[closing + 1 :]
        if branch and branch[0] == "{":
            end = _matching(branch, 0, "{", "}")
            branch = branch[1:end] if end is not None else []
        else:
            semicolon = next(
                (index for index, item in enumerate(branch) if item == ";"), -1
            )
            branch = branch[: semicolon + 1] if semicolon >= 0 else []
        if branch and branch[0] == "return":
            return True
    return False


def _java_linear_loop(tokens: list[str], parameter: str, recursive_positions: list[int]) -> bool:
    spans, incomplete = _loop_spans(tokens)
    if incomplete or len(spans) != 1:
        return False
    start, end = spans[0]
    if tokens[start] != "for" or any(start <= position <= end for position in recursive_positions):
        return False
    header = _loop_header(tokens, start)
    if header is None:
        return False
    opening, closing = header
    parts = tokens[opening + 1 : closing]
    separators = [index for index, token in enumerate(parts) if token == ";"]
    if len(separators) != 2:
        return False
    initialization = parts[: separators[0]]
    condition = parts[separators[0] + 1 : separators[1]]
    update = parts[separators[1] + 1 :]
    for variable in initialization:
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", variable):
            continue
        grows_to_parameter = any(
            condition[index : index + 3] in (
                [variable, "<", parameter],
                [variable, "<=", parameter],
                [parameter, ">", variable],
                [parameter, ">=", variable],
            )
            for index in range(len(condition) - 2)
        )
        increments_variable = any(
            update[index : index + 2] in ([variable, "++"], ["++", variable])
            or update[index : index + 3] == [variable, "+=", "1"]
            for index in range(len(update))
        )
        if grows_to_parameter and increments_variable:
            return True
    return False


def _recursive_scalar_recurrence(
    tokens: list[str], method_name: str, class_range: tuple[int, int], body: list[str]
) -> tuple[str, dict] | None:
    parameters = _method_parameter_names(tokens, class_range, method_name)
    if parameters is None or len(parameters) != 1:
        return None
    parameter = parameters[0]
    calls = _call_arguments(body, method_name)
    if not calls or not _has_java_scalar_base_case(body, parameter):
        return None
    reductions = {
        _java_scalar_reduction(arguments[0], parameter)
        for _, arguments in calls if len(arguments) == 1
    }
    if len(reductions) != 1 or None in reductions or any(len(arguments) != 1 for _, arguments in calls):
        return None
    reduction = next(iter(reductions))
    if len(calls) == 2:
        first, second = calls[0][0], calls[1][0]
        return_start = max(
            (index for index, token in enumerate(body[:first]) if token == "return"),
            default=-1,
        )
        semicolon = next(
            (index for index in range(second, len(body)) if body[index] == ";"), -1
        )
        if return_start < 0 or semicolon < 0 or any(
            token in {"if", "else", "?", ":"} for token in body[return_start:semicolon]
        ):
            return None
    elif len(calls) != 1:
        return None
    positions = [position for position, _ in calls]
    spans, incomplete = _loop_spans(body)
    if incomplete or any(token in {"while", "do"} for token in body):
        return None
    if spans:
        if not _java_linear_loop(body, parameter, positions):
            return None
        work = "linear"
    else:
        work = "constant"
    solved = solve_bounded_recurrence(len(calls), reduction, work)
    if solved is None:
        return None
    recurrence, estimate, rule = solved
    evidence = recurrence_evidence(
        function=method_name,
        recursive_calls=len(calls),
        size_reduction=reduction,
        nonrecursive_work=work,
        recurrence=recurrence,
        solving_rule=rule,
        complexity=estimate,
        assumptions=[
            "The single scalar parameter is a non-negative integer input size.",
            "A parameter-guarded terminating base case is present.",
            "All recursive calls use the same recognized size reduction.",
            "Any detected loop is a single for-loop bounded by the scalar parameter and is outside recursive calls.",
            "Arithmetic and constant-time operations use the usual unit-cost model.",
        ],
        location={"function": method_name, "line": None},
    )
    return estimate, evidence


def _recursive_binary_search_recurrence(
    tokens: list[str], method_name: str, body: list[str]
) -> tuple[str, dict] | None:
    calls = _call_arguments(body, method_name)
    if len(calls) != 2:
        return None
    low_high = None
    for index in range(len(body) - 5):
        if body[index] == "if":
            header = _loop_header(body, index)
            if header is None:
                continue
            opening, closing = header
            condition = body[opening + 1 : closing]
            if len(condition) == 3 and condition[1] in {">", "<"}:
                low_high = (
                    (condition[0], condition[2])
                    if condition[1] == ">"
                    else (condition[2], condition[0])
                )
                break
    if low_high is None:
        return None
    low, high = low_high
    accepted_midpoints = (
        [low, "+", "(", high, "-", low, ")", "/", "2"],
        ["(", low, "+", high, ")", "/", "2"],
    )
    mid = next(
        (
            body[index - 1]
            for index in range(1, len(body) - 5)
            if body[index] == "="
            and any(body[index + 1 : index + 1 + len(expression)] == expression
                    for expression in accepted_midpoints)
        ),
        None,
    )
    if mid is None:
        return None
    argument_lists = [arguments for _, arguments in calls]
    if any(len(arguments) != 4 for arguments in argument_lists):
        return None
    bound_indexes = [
        index
        for index in range(4)
        if argument_lists[0][index] != argument_lists[1][index]
    ]
    if len(bound_indexes) != 2:
        return None
    bound_shapes = {
        tuple(tuple(_strip_parentheses(arguments[index])) for index in bound_indexes)
        for arguments in argument_lists
    }
    expected_shapes = {
        ((low,), (mid, "-", "1")),
        ((mid, "+", "1"), (high,)),
    }
    reverse_parameter_order = {
        ((mid, "-", "1"), (low,)),
        ((high,), (mid, "+", "1")),
    }
    if bound_shapes not in {frozenset(expected_shapes), frozenset(reverse_parameter_order)}:
        return None
    call_positions = [position for position, _ in calls]
    first_return = max(
        (index for index, token in enumerate(body[:call_positions[0]]) if token == "return"),
        default=-1,
    )
    second_return = max(
        (index for index, token in enumerate(body[:call_positions[1]]) if token == "return"),
        default=-1,
    )
    array_name = argument_lists[0][0][0] if len(argument_lists[0][0]) == 1 else None
    if (
        first_return < 0
        or second_return <= first_return
        or array_name is None
        or [array_name, "[", mid, "]"] not in [body[i : i + 4] for i in range(len(body) - 3)]
        or mid not in body
    ):
        return None
    mutually_exclusive_branch = False
    for branch_if, token in enumerate(body[: call_positions[0]]):
        if token != "if":
            continue
        branch_header = _loop_header(body, branch_if)
        if branch_header is None:
            continue
        branch_close = _matching(body, branch_header[1] + 1, "{", "}")
        if (
            branch_close is not None
            and branch_header[1] < call_positions[0] < branch_close
            and call_positions[1] > branch_close
        ):
            mutually_exclusive_branch = True
            break
    if not mutually_exclusive_branch:
        return None
    recurrence, estimate, rule = solve_bounded_recurrence(1, "factor_two", "constant") or ("", "", "")
    evidence = recurrence_evidence(
        function=method_name,
        recursive_calls=1,
        size_reduction="factor_two",
        nonrecursive_work="constant",
        recurrence=recurrence,
        solving_rule=rule,
        complexity=estimate,
        assumptions=[
            "The selected method has one mutually exclusive recursive branch per call.",
            "The midpoint divides the inclusive [low, high] interval into halves.",
            "The bounds are valid array indices and array access is O(1).",
            "The base case returns when the lower bound exceeds the upper bound.",
        ],
        location={"function": method_name, "line": None},
    )
    return estimate, evidence


def _returned_helper_name(body: list[str], method_name: str) -> str | None:
    """Return the callee for a method whose entire body is `return helper(...);`."""
    if len(body) < 5 or body[0] != "return" or body[2] != "(":
        return None
    helper_name = body[1]
    if helper_name == method_name or not re.fullmatch(r"[A-Za-z_$][\w$]*", helper_name):
        return None
    close = _matching(body, 2, "(", ")")
    if close is None or body[close + 1 :] != [";"]:
        return None
    return helper_name


def _is_last_pivot_quicksort(
    all_tokens: list[str], class_range: tuple[int, int], body: list[str], method_name: str
) -> bool:
    calls = _call_arguments(body, method_name)
    if len(calls) != 2:
        return False
    partition_name = next(
        (
            body[index + 1]
            for index in range(len(body) - 3)
            if body[index] == "="
            and re.fullmatch(r"[A-Za-z_$][\w$]*", body[index + 1])
            and body[index + 2] == "("
        ),
        None,
    )
    if partition_name is None or not any(
        body[index : index + 5] == [partition_name, "(", "values", ",", "low"]
        for index in range(len(body) - 4)
    ):
        return False
    arguments = [args for _, args in calls]
    if any(len(args) != 3 for args in arguments):
        return False
    if not (
        arguments[0][0] == arguments[1][0]
        and arguments[0][1] == ["low"]
        and arguments[1][1] == ["pivot", "+", "1"]
        and arguments[0][2] == ["pivot", "-", "1"]
        and arguments[1][2] == ["high"]
    ):
        return False
    partition = _method_body(all_tokens, class_range, partition_name)
    if partition is None:
        return False
    has_last_pivot = any(
        partition[index : index + 5] == ["=", "values", "[", "high", "]"]
        for index in range(len(partition) - 4)
    )
    has_range_loop = any(
        partition[index] == "for"
        and (header := _loop_header(partition, index)) is not None
        and "low" in partition[header[0] + 1 : header[1]]
        and "high" in partition[header[0] + 1 : header[1]]
        for index in range(len(partition))
    )
    has_terminal_pivot_return = any(
        partition[index : index + 4] == ["return", "boundary", "+", "1"]
        for index in range(len(partition) - 3)
    )
    has_partition_comparison = any(
        partition[index : index + 5] == ["values", "[", "current", "]", "<="]
        and index + 6 < len(partition)
        and partition[index + 5] == "pivot"
        for index in range(len(partition) - 5)
    )
    base_guard = any(
        body[index : index + 6] == ["if", "(", "low", ">=", "high", ")"]
        and "return" in body[index + 6 : index + 10]
        for index in range(len(body) - 5)
    )
    return (
        has_last_pivot
        and has_range_loop
        and has_terminal_pivot_return
        and has_partition_comparison
        and base_guard
    )


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


def _loop_header(tokens: list[str], start: int) -> tuple[int, int] | None:
    opening = next(
        (i for i in range(start + 1, len(tokens)) if tokens[i] in {"(", "{", ";"}),
        None,
    )
    if opening is None or tokens[opening] != "(":
        return None
    closing = _matching(tokens, opening, "(", ")")
    return (opening, closing) if closing is not None else None


def _is_positive_step(tokens: list[str], variable: str) -> bool:
    for index, token in enumerate(tokens):
        if token == variable:
            if index + 1 < len(tokens) and tokens[index + 1] == "++":
                return True
            if index + 2 < len(tokens) and tokens[index + 1 : index + 3] == ["+=", "1"]:
                return True
            if (
                index + 4 < len(tokens)
                and tokens[index + 1 : index + 4] == ["=", variable, "+"]
                and tokens[index + 4] == "1"
            ):
                return True
        if token == "++" and index + 1 < len(tokens) and tokens[index + 1] == variable:
            return True
    return False


def _has_reset(tokens: list[str], variable: str) -> bool:
    for index, token in enumerate(tokens[:-1]):
        if token != variable or tokens[index + 1] != "=":
            continue
        if index > 0 and tokens[index - 1] in {"=", "!", "<", ">"}:
            continue
        if index + 3 < len(tokens) and tokens[index + 2] == variable and tokens[index + 3] == "+":
            continue
        return True
    return False


def _amortized_forward_scan(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize a bounded for-loop with an outer-initialized, forward-only array pointer.

    The pattern covers common sliding-window/two-pointer code. It deliberately rejects
    conditional updates, pointer resets, nested work in the while body, and non-array scans.
    """
    for outer_start, outer_end in spans:
        if tokens[outer_start] != "for":
            continue
        header = _loop_header(tokens, outer_start)
        if header is None:
            continue
        opening, closing = header
        for_header = tokens[opening + 1 : closing]
        if ";" not in for_header or not any(step in for_header for step in ("++", "+=")):
            continue
        nested_while = [
            (start, end)
            for start, end in spans
            if outer_start < start < outer_end and end <= outer_end and tokens[start] == "while"
        ]
        if len(nested_while) != 1:
            continue
        while_start, while_end = nested_while[0]
        while_header = _loop_header(tokens, while_start)
        if while_header is None:
            continue
        _, while_condition_end = while_header
        body_start = while_condition_end + 1
        if body_start >= len(tokens) or tokens[body_start] != "{":
            continue
        while_body = tokens[body_start + 1 : while_end]
        if any(token in {"for", "while", "do", "if", "switch", "?", "continue", "return"} for token in while_body):
            continue
        for variable in dict.fromkeys(
            token for token in while_body if re.fullmatch(r"[A-Za-z_$][\w$]*", token)
        ):
            if not _is_positive_step(while_body, variable):
                continue
            # Require a local initialization before the outer loop, such as `int left = 0`.
            initialized = any(
                index + 2 < outer_start
                and tokens[index] == variable
                and tokens[index + 1] == "="
                and re.fullmatch(r"\d+", tokens[index + 2])
                and index > 0
                and re.fullmatch(r"[A-Za-z_$][\w$]*", tokens[index - 1])
                for index in range(1, outer_start)
            )
            if not initialized:
                continue
            if _has_reset(tokens[outer_start + 1 : outer_end], variable):
                continue
            if not any(
                while_body[index] == "["
                and index + 2 < len(while_body)
                and while_body[index + 1] == variable
                and while_body[index + 2] == "]"
                for index in range(len(while_body))
            ):
                continue
            return True
    return False


def _is_binary_search_loop(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize a common closed-interval search whose midpoint updates both bounds."""
    for start, end in spans:
        if tokens[start] != "while":
            continue
        header = _loop_header(tokens, start)
        if header is None:
            continue
        opening, closing = header
        condition = tokens[opening + 1 : closing]
        compared = next(
            (
                (condition[index], condition[index + 2])
                for index in range(len(condition) - 2)
                if re.fullmatch(r"[A-Za-z_$][\w$]*", condition[index])
                and condition[index + 1] in {"<", "<=", ">", ">="}
                and re.fullmatch(r"[A-Za-z_$][\w$]*", condition[index + 2])
            ),
            None,
        )
        if compared is None:
            continue
        first, second = compared
        if condition[condition.index(first) + 1] in {">", ">="}:
            low, high = second, first
        else:
            low, high = first, second

        body_open = closing + 1
        if body_open >= end or tokens[body_open] != "{":
            continue
        loop_body = tokens[body_open + 1 : end]
        midpoint_names: set[str] = set()
        for index in range(len(loop_body) - 1):
            if loop_body[index + 1] != "=" or index == 0:
                continue
            name = loop_body[index]
            if not re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                continue
            statement_end = next(
                (pos for pos in range(index + 2, len(loop_body)) if loop_body[pos] == ";"),
                None,
            )
            if statement_end is None:
                continue
            rhs = loop_body[index + 2 : statement_end]
            has_both_bounds = low in rhs and high in rhs
            halves_interval = any(
                rhs[pos : pos + 2] == ["/", "2"]
                or rhs[pos : pos + 2] == [">>", "1"]
                for pos in range(len(rhs) - 1)
            )
            if has_both_bounds and halves_interval:
                midpoint_names.add(name)
        if not midpoint_names:
            continue

        updates_low = any(
            loop_body[pos] == low
            and pos + 4 < len(loop_body)
            and loop_body[pos + 1] == "="
            and loop_body[pos + 2] in midpoint_names
            and loop_body[pos + 3 : pos + 5] == ["+", "1"]
            for pos in range(len(loop_body))
        )
        updates_high = any(
            loop_body[pos] == high
            and pos + 4 < len(loop_body)
            and loop_body[pos + 1] == "="
            and loop_body[pos + 2] in midpoint_names
            and loop_body[pos + 3 : pos + 5] == ["-", "1"]
            for pos in range(len(loop_body))
        )
        if updates_low and updates_high:
            return True
    return False


def _unit_step_count(tokens: list[str], variable: str, direction: str) -> int:
    operator = "+" if direction == "positive" else "-"
    prefix = "++" if direction == "positive" else "--"
    return sum(
        token == variable and index + 1 < len(tokens) and tokens[index + 1] == prefix
        or token == prefix and index + 1 < len(tokens) and tokens[index + 1] == variable
        or token == variable
        and index + 2 < len(tokens)
        and tokens[index + 1 : index + 3] == [operator + "=", "1"]
        or token == variable
        and index + 4 < len(tokens)
        and tokens[index + 1 : index + 4] == ["=", variable, operator]
        and tokens[index + 4] == "1"
        for index, token in enumerate(tokens)
    )


def _is_inward_two_pointer_scan(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize a single linear scan over a sequence using opposing cursors."""
    if len(spans) != 1 or tokens[spans[0][0]] != "while":
        return False
    start, end = spans[0]
    header = _loop_header(tokens, start)
    if header is None:
        return False
    opening, closing = header
    condition = tokens[opening + 1 : closing]
    comparison = next(
        (
            (condition[index], condition[index + 1], condition[index + 2])
            for index in range(len(condition) - 2)
            if condition[index + 1] in {"<", "<=", ">", ">="}
            and all(re.fullmatch(r"[A-Za-z_$][\w$]*", condition[pos]) for pos in (index, index + 2))
        ),
        None,
    )
    if comparison is None:
        return False
    first, operator, second = comparison
    low, high = (first, second) if operator in {"<", "<="} else (second, first)
    body_open = closing + 1
    if body_open >= end or tokens[body_open] != "{":
        return False
    body = tokens[body_open + 1 : end]
    if any(token in {"for", "while", "do", "continue", "switch", "?"} for token in body):
        return False

    def prior_value(variable: str) -> list[str]:
        assignments = [
            index for index in range(start - 1)
            if tokens[index] == variable and tokens[index + 1] == "="
        ]
        if not assignments:
            return []
        value_start = assignments[-1] + 2
        value_end = next(
            (index for index in range(value_start, start) if tokens[index] == ";"), start
        )
        return tokens[value_start:value_end]

    low_start = prior_value(low) == ["0"]
    high_value = prior_value(high)
    high_bound = any(
        high_value[index - 1 : index + 1] == [".", "length"]
        for index in range(1, len(high_value))
    ) and (high_value[-1:] in ([")"], ["length"]) or high_value[-2:] == ["-", "1"])
    if not low_start or not high_bound:
        return False
    if _unit_step_count(body, low, "positive") != 1 or _unit_step_count(body, high, "negative") != 1:
        return False
    if _unit_step_count(body, low, "negative") or _unit_step_count(body, high, "positive"):
        return False
    if _has_reset(body, low) or _has_reset(body, high):
        return False
    for index, token in enumerate(body):
        if token == "if":
            guard = _loop_header(body, index)
            if guard is None or body[guard[1] + 1 : guard[1] + 2] != ["return"]:
                return False
    return True


def _receiver_call_sites(
    tokens: list[str], receiver: str, method: str
) -> list[tuple[int, list[list[str]], int]]:
    calls: list[tuple[int, list[list[str]], int]] = []
    for index in range(len(tokens) - 3):
        if tokens[index : index + 4] != [receiver, ".", method, "("]:
            continue
        close = _matching(tokens, index + 3, "(", ")")
        if close is None:
            continue
        arguments: list[list[str]] = []
        start = index + 4
        depth = 0
        for cursor in range(start, close):
            if tokens[cursor] in {"(", "[", "{"}:
                depth += 1
            elif tokens[cursor] in {")", "]", "}"}:
                depth -= 1
            elif tokens[cursor] == "," and depth == 0:
                arguments.append(tokens[start:cursor])
                start = cursor + 1
        if start < close:
            arguments.append(tokens[start:close])
        calls.append((index, arguments, close))
    return calls


def _amortized_monotonic_stack_scan(
    tokens: list[str], spans: list[tuple[int, int]], incomplete_loop: bool
) -> dict | None:
    """Recognize one ArrayDeque index push per array step and monotonic pops."""
    loops = [(start, end, tokens[start]) for start, end in spans]
    outer_loops = [(start, end) for start, end, kind in loops if kind == "for"]
    while_loops = [(start, end) for start, end, kind in loops if kind == "while"]
    if len(outer_loops) != 1 or len(while_loops) not in {1, 2}:
        return None

    outer_start, outer_end = outer_loops[0]
    outer_header = _loop_header(tokens, outer_start)
    if outer_header is None:
        return None
    outer_open, outer_close = outer_header
    if outer_close + 1 >= len(tokens) or tokens[outer_close + 1] != "{":
        return None
    if _matching(tokens, outer_close + 1, "{", "}") != outer_end:
        return None
    header = tokens[outer_open + 1 : outer_close]
    semicolons = [index for index, token in enumerate(header) if token == ";"]
    if len(semicolons) != 2:
        return None
    initializer = header[: semicolons[0]]
    condition = header[semicolons[0] + 1 : semicolons[1]]
    update = header[semicolons[1] + 1 :]
    index_name = next(
        (
            initializer[position - 1]
            for position, token in enumerate(initializer)
            if token == "=" and position >= 1 and initializer[position + 1 : position + 2] == ["0"]
        ),
        None,
    )
    if index_name is None or not re.fullmatch(r"[A-Za-z_$][\w$]*", index_name):
        return None
    array_name = (
        condition[2]
        if len(condition) == 5
        and condition[:2] == [index_name, "<"]
        and condition[3:] == [".", "length"]
        else None
    )
    if array_name is None or not re.fullmatch(r"[A-Za-z_$][\w$]*", array_name):
        return None
    if update not in ([index_name, "++"], ["++", index_name], [index_name, "+=", "1"]):
        return None

    deque_constructors = [
        index for index in range(len(tokens) - 1)
        if tokens[index : index + 2] == ["new", "ArrayDeque"]
    ]
    if len(deque_constructors) != 1:
        return None
    constructor = deque_constructors[0]
    if constructor < 2 or tokens[constructor - 1] != "=":
        return None
    receiver = tokens[constructor - 2]
    if not re.fullmatch(r"[A-Za-z_$][\w$]*", receiver):
        return None

    nested_pops = [
        (start, end)
        for start, end in while_loops
        if outer_start < start < end <= outer_end
    ]
    if len(nested_pops) != 1:
        return None
    pop_start, pop_end = nested_pops[0]
    main_header = _loop_header(tokens, pop_start)
    if main_header is None:
        return None
    main_open, main_close = main_header
    main_condition = tokens[main_open + 1 : main_close]
    if main_condition[:7] != ["!", receiver, ".", "isEmpty", "(", ")", "&&"]:
        return None
    value_compare = [
        array_name, "[", receiver, ".", "peek", "(", ")", "]",
    ]
    comparison_start = next(
        (
            position for position in range(len(main_condition) - len(value_compare))
            if main_condition[position : position + len(value_compare)] == value_compare
        ),
        None,
    )
    if comparison_start is None:
        return None
    after_top = comparison_start + len(value_compare)
    if after_top >= len(main_condition) or main_condition[after_top] not in {"<", "<=", ">", ">="}:
        return None
    if main_condition[after_top + 1 :] != [array_name, "[", index_name, "]"]:
        return None
    main_body_open = main_close + 1
    if main_body_open >= pop_end or tokens[main_body_open] != "{":
        return None
    if _matching(tokens, main_body_open, "{", "}") != pop_end:
        return None
    main_body = tokens[main_body_open + 1 : pop_end]
    if any(token in {"for", "while", "do", "if", "switch", "?", "continue", "return"} for token in main_body):
        return None

    push_calls = _receiver_call_sites(tokens, receiver, "push")
    if len(push_calls) != 1:
        return None
    push_position, push_arguments, push_close = push_calls[0]
    if push_arguments != [[index_name]] or not pop_end < push_position < outer_end:
        return None
    if tokens[push_close + 1 : push_close + 2] != [";"]:
        return None
    if any(token in {"if", "switch", "?", "continue", "return"} for token in tokens[outer_start + 1 : outer_end]):
        return None

    pop_calls = _receiver_call_sites(tokens, receiver, "pop")
    main_pop_calls = [call for call in pop_calls if main_body_open < call[0] < pop_end]
    if len(main_pop_calls) != 1 or main_pop_calls[0][1]:
        return None
    pop_locations = [main_pop_calls[0][0]]
    drain_location = None
    remaining_whiles = [loop for loop in while_loops if loop != (pop_start, pop_end)]
    if incomplete_loop and not remaining_whiles:
        return None
    if remaining_whiles:
        if len(remaining_whiles) != 1:
            return None
        drain_start, drain_end = remaining_whiles[0]
        if drain_start <= outer_end:
            return None
        drain_header = _loop_header(tokens, drain_start)
        if drain_header is None:
            return None
        drain_open, drain_close = drain_header
        if tokens[drain_open + 1 : drain_close] != [
            "!", receiver, ".", "isEmpty", "(", ")"
        ]:
            return None
        statement_start = drain_close + 1
        if tokens[statement_start : statement_start + 1] == ["{"]:
            statement_end = _matching(tokens, statement_start, "{", "}")
            drain_body = tokens[statement_start + 1 : statement_end] if statement_end is not None else []
        else:
            semicolon = next(
                (position for position in range(statement_start, len(tokens)) if tokens[position] == ";"),
                None,
            )
            statement_end = semicolon
            drain_body = tokens[statement_start:semicolon] if semicolon is not None else []
        drain_pops = [
            call for call in pop_calls
            if statement_start < call[0] < (statement_end if statement_end is not None else statement_start)
        ]
        if len(drain_pops) != 1 or drain_pops[0][1]:
            return None
        if drain_body.count("while") or any(token in {"for", "if", "switch", "?", "continue", "return"} for token in drain_body):
            return None
        drain_location = drain_pops[0][0]
        pop_locations.append(drain_location)
    elif len(pop_calls) != 1:
        return None
    if len(pop_calls) != len(pop_locations):
        return None

    peek_calls = _receiver_call_sites(tokens, receiver, "peek")
    empty_calls = _receiver_call_sites(tokens, receiver, "isEmpty")
    if not peek_calls or len(empty_calls) < len(while_loops):
        return None
    allowed_call_ranges = [(outer_start, outer_end)]
    allowed_call_ranges.extend(remaining_whiles)
    if any(
        not any(start < call[0] < end for start, end in allowed_call_ranges)
        for call in peek_calls + empty_calls
    ):
        return None
    other_calls = []
    control_words = {"for", "while", "if", "switch", "catch", "synchronized"}
    allowed_calls = {"ArrayDeque", "push", "pop", "peek", "isEmpty"}
    for position in range(len(tokens) - 1):
        if (
            re.fullmatch(r"[A-Za-z_$][\w$]*", tokens[position])
            and tokens[position + 1] == "("
            and tokens[position] not in control_words | allowed_calls
        ):
            other_calls.append(tokens[position])
    if other_calls:
        return None
    receiver_call_count = sum(
        1 for position, token in enumerate(tokens)
        if token == receiver and position + 1 < len(tokens) and tokens[position + 1] == "."
    )
    receiver_reference_count = tokens.count(receiver)
    if (
        receiver_call_count != len(push_calls) + len(pop_calls) + len(peek_calls) + len(empty_calls)
        or receiver_reference_count != receiver_call_count + 1
    ):
        return None

    loop_locations = {
        "outer_for_token_index": outer_start,
        "monotonic_while_token_index": pop_start,
    }
    if remaining_whiles:
        loop_locations["final_drain_while_token_index"] = remaining_whiles[0][0]
    return {
        "language": "java",
        "rule_version": "java_monotonic_stack_amortized_v1",
        "pattern_id": "java_arraydeque_single_push_monotonic_pop",
        "source_locations": {
            **loop_locations,
            "push_token_index": push_position,
            "pop_token_indices": pop_locations,
            "peek_token_index": peek_calls[0][0],
        },
        "bounded_push_evidence": {
            "container": "ArrayDeque",
            "outer_loop_bound": f"{index_name} from 0 to {array_name}.length - 1",
            "push_sites": 1,
            "push_argument": index_name,
            "push_once_per_iteration": True,
        },
        "bounded_removal_evidence": {
            "pop_sites": len(pop_locations),
            "monotonic_condition": (
                f"{array_name}[{receiver}.peek()] {main_condition[after_top]} "
                f"{array_name}[{index_name}]"
            ),
            "popped_entries_reinserted": False,
            "optional_final_drain": drain_location is not None,
        },
        "amortized_argument": (
            "The outer loop pushes each array index once. Each pop removes the current top "
            "permanently, so each index can be popped at most once by the monotonic loop or "
            "the final drain. Total pushes and pops are O(n)."
        ),
        "complexity": "O(n)",
        "assumptions": [
            "The loop traverses the array once from index 0 to values.length - 1.",
            "ArrayDeque push, peek, pop, and isEmpty are O(1).",
            "Only the recognized push site mutates the stack by adding entries.",
            "Only the recognized pop sites remove entries; popped indices are not reinserted.",
            "No hidden helper work or aliases mutate the stack.",
            "This is a heuristic static match, not a formal proof for arbitrary Java code.",
        ],
        "limitations": [
            "Locations are token offsets because this tokenizer does not retain source line numbers.",
            "Only ArrayDeque with direct push, peek, pop, and isEmpty calls is recognized.",
            "Aliases, helper calls, additional stack mutations, and other control flow are not analyzed.",
        ],
        "inference_kind": "heuristic_static_amortized_argument",
    }


def _is_insertion_sort_shift(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize a nested insertion-sort shift loop with a decreasing array index."""
    for outer_start, outer_end in spans:
        if tokens[outer_start] != "for":
            continue
        outer_header = _loop_header(tokens, outer_start)
        if outer_header is None:
            continue
        header_open, header_close = outer_header
        header = tokens[header_open + 1 : header_close]
        semicolons = [i for i, token in enumerate(header) if token == ";"]
        if len(semicolons) != 2:
            continue
        initializer = header[: semicolons[0]]
        condition = header[semicolons[0] + 1 : semicolons[1]]
        update = header[semicolons[1] + 1 :]
        assignment = next(
            (index for index, token in enumerate(initializer) if token == "="), None
        )
        if assignment is None or assignment < 1 or assignment + 1 >= len(initializer):
            continue
        outer_index = initializer[assignment - 1]
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", outer_index):
            continue
        if not any(
            condition[index : index + 2] == [outer_index, "<"]
            and "length" in condition[index + 2 :]
            for index in range(len(condition) - 1)
        ):
            continue
        if not (outer_index in update and ("++" in update or "+=" in update)):
            continue

        for inner_start, inner_end in spans:
            if not (
                outer_start < inner_start < inner_end <= outer_end
                and tokens[inner_start] == "while"
            ):
                continue
            inner_header = _loop_header(tokens, inner_start)
            if inner_header is None:
                continue
            condition_open, condition_close = inner_header
            inner_condition = tokens[condition_open + 1 : condition_close]
            inner_index = next(
                (
                    inner_condition[index]
                    for index in range(len(inner_condition) - 2)
                    if inner_condition[index + 1 : index + 3] == [">=", "0"]
                    or inner_condition[index + 1 : index + 3] == [">", "-1"]
                ),
                None,
            )
            if inner_index is None:
                continue

            # The inner pointer must be initialized from the outer index just before
            # the while-loop, as in `j = i - 1`.
            before_while = tokens[outer_start + 1 : inner_start]
            pointer_initialized = any(
                before_while[index : index + 5]
                == [inner_index, "=", outer_index, "-", "1"]
                for index in range(len(before_while) - 4)
            )
            if not pointer_initialized:
                continue

            body_open = condition_close + 1
            if body_open >= inner_end or tokens[body_open] != "{":
                continue
            body = tokens[body_open + 1 : inner_end]
            shift_assignment = any(
                len(body[index : index + 12]) == 12
                and body[index + 1] == "["
                and body[index + 2] == inner_index
                and body[index + 3 : index + 6] == ["+", "1", "]"]
                and body[index + 6] == "="
                and body[index + 7] == body[index]
                and body[index + 8 : index + 11] == ["[", inner_index, "]"]
                for index in range(len(body))
            )
            pointer_decrements = any(
                body[index : index + 2] in ([inner_index, "--"], ["--", inner_index])
                or body[index : index + 3] == [inner_index, "-=", "1"]
                for index in range(len(body))
            )
            if shift_assignment and pointer_decrements:
                return True
    return False


def _is_tree_recursive_walk(tokens: list[str], method_name: str) -> bool:
    """Recognize direct recursion over one or both child links of a tree node."""
    recursive_children: list[tuple[str, str]] = []
    for index in range(len(tokens) - 1):
        if tokens[index] != method_name or tokens[index + 1] != "(":
            continue
        closing = _matching(tokens, index + 1, "(", ")")
        if closing is None or index + 2 >= closing:
            return False
        argument = tokens[index + 2 : closing]
        if (
            len(argument) != 3
            or not re.fullmatch(r"[A-Za-z_$][\w$]*", argument[0])
            or argument[1] != "."
            or argument[2] not in {"left", "right"}
        ):
            return False
        recursive_children.append((argument[0], argument[2]))

    if len(recursive_children) not in {1, 2}:
        return False
    if len(recursive_children) == 2:
        return (
            recursive_children[0][0] == recursive_children[1][0]
            and recursive_children[0][1] != recursive_children[1][1]
        )
    return True


def _has_method_call(tokens: list[str], receiver: str, methods: set[str], argument: str) -> bool:
    return any(
        tokens[index] == receiver
        and tokens[index + 1] == "."
        and tokens[index + 2] in methods
        and tokens[index + 3 : index + 5] == ["(", argument]
        for index in range(len(tokens) - 4)
    )


def _java_statement_end(tokens: list[str], start: int, limit: int) -> int | None:
    depth = 0
    for index in range(start, limit):
        if tokens[index] in {"(", "[", "{"}:
            depth += 1
        elif tokens[index] in {")", "]", "}"}:
            depth -= 1
        elif tokens[index] == ";" and depth == 0:
            return index
    return None


def _java_control_statement_end(tokens: list[str], start: int, limit: int) -> int | None:
    """Bound one block, if statement, or simple statement inside a control body."""
    if start >= limit:
        return None
    if tokens[start] == "{":
        end = _matching(tokens, start, "{", "}")
        return end if end is not None and end < limit else None
    if tokens[start] == "if":
        header = _loop_header(tokens, start)
        if header is None:
            return None
        then_end = _java_control_statement_end(tokens, header[1] + 1, limit)
        if then_end is None:
            return None
        else_start = then_end + 1
        if else_start < limit and tokens[else_start] == "else":
            return _java_control_statement_end(tokens, else_start + 1, limit)
        return then_end
    return _java_statement_end(tokens, start, limit)


def _is_adjacency_list_bfs(
    tokens: list[str], spans: list[tuple[int, int]], lines: list[int],
    declaration_tokens: list[str],
) -> dict | None:
    """Recognize a narrowly bounded Java adjacency-list BFS with enqueue deduplication."""
    def typed_declaration(name: str, type_shapes: tuple[tuple[str, ...], ...]) -> bool:
        declared = declaration_tokens + tokens
        for index, token in enumerate(declared):
            if token != name:
                continue
            for shape in type_shapes:
                if declared[index - len(shape) : index] == list(shape):
                    return True
        return False

    def body_bounds(start: int, limit: int) -> tuple[int, int] | None:
        header = _loop_header(tokens, start) if tokens[start] in {"for", "while", "if"} else None
        if header is None:
            return None
        body_start = header[1] + 1
        if body_start >= limit:
            return None
        if tokens[body_start] == "{":
            end = _matching(tokens, body_start, "{", "}")
            return (body_start + 1, end) if end is not None and end < limit else None
        end = _java_statement_end(tokens, body_start, limit)
        return (body_start, end + 1) if end is not None else None

    def guarded_enqueue(start: int, limit: int, neighbor: str, queue: str) -> tuple[str, int] | None:
        bounds = body_bounds(start, limit)
        header = _loop_header(tokens, start)
        if bounds is None or header is None:
            return None
        guard = tokens[header[0] + 1 : header[1]]
        set_name = next((guard[i - 1] for i in range(1, len(guard) - 2)
                         if guard[i : i + 2] == [".", "add"]
                         and guard[i + 2 : i + 5] == ["(", neighbor, ")"]), None)
        inner = tokens[bounds[0] : bounds[1]]
        if (set_name is not None and len(inner) >= 5 and inner[0] == queue and inner[1] == "."
                and inner[2] in {"add", "offer", "addLast"}
                and inner[3:6] == ["(", neighbor, ")"]):
            return set_name, bounds[0]
        array_name = next((guard[i - 2] for i in range(3, len(guard) - 1)
                           if guard[i - 3] == "!" and guard[i - 1] == "["
                           and guard[i] == neighbor and guard[i + 1] == "]"), None)
        mark = [array_name, "[", neighbor, "]", "=", "true"]
        mark_index = next((i for i in range(len(inner) - len(mark) + 1)
                           if inner[i:i + len(mark)] == mark), None) if array_name else None
        enqueue_index = next((i for i in range(len(inner) - 4)
                              if inner[i:i + 4] == [queue, ".", "add", "("]
                              and inner[i + 4:i + 6] == [neighbor, ")"]), None)
        if (array_name and mark_index is not None and enqueue_index is not None
                and mark_index < enqueue_index):
            return array_name, bounds[0]
        return None

    for outer_start, outer_end in spans:
        if tokens[outer_start] != "while":
            continue
        enclosing_loops = [(start, end) for start, end in spans
                           if start < outer_start and end >= outer_end]
        component_loop = (enclosing_loops[0][0] if len(enclosing_loops) == 1
                         and tokens[enclosing_loops[0][0]] == "for" else None)
        if enclosing_loops and component_loop is None:
            continue
        header = _loop_header(tokens, outer_start)
        if header is None:
            continue
        opening, closing = header
        condition = tokens[opening + 1 : closing]
        queue_name = next(
            (
                condition[index - 1]
                for index in range(1, len(condition) - 1)
                if condition[index : index + 2] == [".", "isEmpty"]
                and "!" in condition[:index]
            ),
            None,
        )
        if queue_name is None or not typed_declaration(
            queue_name, (("Queue", "<", "Integer", ">"), ("Deque", "<", "Integer", ">"),
                         ("ArrayDeque", "<", "Integer", ">"))
        ):
            continue
        current_node = next(
            (
                tokens[index - 2]
                for index in range(outer_start + 3, outer_end - 3)
                if tokens[index] == queue_name
                and tokens[index + 1 : index + 4]
                in ([".", "poll", "("], [".", "remove", "("], [".", "pollFirst", "("], [".", "removeFirst", "("])
                and tokens[index - 1] == "="
            ),
            None,
        )
        if current_node is None:
            continue

        for inner_start, inner_end in spans:
            if not (
                outer_start < inner_start < inner_end <= outer_end
                and tokens[inner_start] == "for"
            ):
                continue
            inner_header = _loop_header(tokens, inner_start)
            if inner_header is None:
                continue
            inner_open, inner_close = inner_header
            for_header = tokens[inner_open + 1 : inner_close]
            if ":" not in for_header:
                continue
            colon = for_header.index(":")
            if colon < 1:
                continue
            neighbor = for_header[colon - 1]
            adjacency = for_header[colon + 1 :]
            adjacency_name = next(
                (adjacency[i - 1] for i in range(1, len(adjacency) - 3)
                 if adjacency[i : i + 3] == [".", "get", "("]
                 and i + 4 < len(adjacency) and adjacency[i + 4] == ")"),
                None,
            )
            if adjacency_name is None or not any(
                adjacency[index : index + 4] == [".", "get", "(", current_node]
                for index in range(len(adjacency) - 3)
            ):
                continue
            if not typed_declaration(adjacency_name, (
                ("List", "<", "List", "<", "Integer", ">", ">"),
                ("Map", "<", "Integer", ",", "List", "<", "Integer", ">", ">"),
                ("HashMap", "<", "Integer", ",", "List", "<", "Integer", ">", ">"),
            )):
                continue
            neighbor_bounds = body_bounds(inner_start, outer_end)
            if neighbor_bounds is None:
                continue
            neighbor_body_start, neighbor_body_end = neighbor_bounds
            guard_start = neighbor_body_start
            if guard_start >= neighbor_body_end or tokens[guard_start] != "if":
                continue
            guarded = guarded_enqueue(guard_start, neighbor_body_end, neighbor, queue_name)
            if guarded is None:
                continue
            visited_name, enqueue_index = guarded
            guard_header = _loop_header(tokens, guard_start)
            guard_body_start = guard_header[1] + 1 if guard_header else guard_start
            guard_body_kind = "braced" if tokens[guard_body_start] == "{" else "single_statement"
            set_visited = typed_declaration(visited_name, (("Set", "<", "Integer", ">"),
                                                           ("HashSet", "<", "Integer", ">")))
            boolean_visited = any(tokens[i:i + 3] == ["boolean", "[", "]"]
                                  and tokens[i + 3:i + 4] == [visited_name]
                                  for i in range(len(tokens) - 3))
            if not set_visited and not boolean_visited:
                continue
            # Reject any additional input-sized loop beyond the queue, neighbor scan,
            # and optional multi-source seed loop.
            extra_loops = [start for start, _ in spans
                           if start not in {outer_start, inner_start, component_loop}]
            seed_loop = next((start for start in extra_loops if tokens[start] == "for"
                              and start < outer_start), None)
            if any(start != seed_loop for start in extra_loops):
                continue
            starts_count = None
            seed_line = None
            deduplicated = False
            if component_loop is not None:
                component_header = _loop_header(tokens, component_loop)
                if component_header is None:
                    continue
                component_condition = tokens[component_header[0] + 1:component_header[1]]
                if not any(component_condition[i:i + 3] == [adjacency_name, ".", "size"]
                           for i in range(len(component_condition) - 2)):
                    continue
                root_name = next((component_condition[i - 1] for i in range(1, len(component_condition))
                                  if component_condition[i] == "="), None)
                root_guard = next((i for i in range(component_header[1] + 1, outer_start)
                                   if tokens[i] == "if"), None)
                if root_name is None or root_guard is None:
                    continue
                root_guard_header = _loop_header(tokens, root_guard)
                component_end = next(end for start, end in spans if start == component_loop)
                root_bounds = body_bounds(root_guard, component_end)
                if root_guard_header is None or root_bounds is None:
                    continue
                root_condition = tokens[root_guard_header[0] + 1:root_guard_header[1]]
                if not any(root_condition[i:i + 5] == [visited_name, ".", "add", "(", root_name]
                           for i in range(len(root_condition) - 4)):
                    continue
                root_body = tokens[root_bounds[0]:root_bounds[1]]
                if not any(root_body[i:i + 5] == [queue_name, ".", "add", "(", root_name]
                           for i in range(len(root_body) - 4)):
                    continue
                if not any(i < component_loop and tokens[i:i + 4] ==
                           ["Set", "<", "Integer", ">"]
                           for i in range(len(tokens) - 3)):
                    continue
                component_traversal = True
            else:
                component_traversal = False
            if seed_loop is not None:
                seed_header = _loop_header(tokens, seed_loop)
                if seed_header is None:
                    continue
                seed_parts = tokens[seed_header[0] + 1 : seed_header[1]]
                if ":" not in seed_parts:
                    continue
                colon = seed_parts.index(":")
                seed_name = seed_parts[colon - 1]
                seed_input = seed_parts[colon + 1]
                seed_bounds = body_bounds(seed_loop, outer_start)
                if seed_bounds is None:
                    continue
                seed_if = seed_bounds[0]
                if seed_if >= seed_bounds[1] or tokens[seed_if] != "if":
                    continue
                seed_enqueue = guarded_enqueue(seed_if, seed_bounds[1], seed_name, queue_name)
                if (seed_enqueue is None or seed_enqueue[0] != visited_name
                        or not re.fullmatch(r"[A-Za-z_$][\w$]*", seed_input)):
                    continue
                starts_count, seed_line, deduplicated = seed_input, lines[seed_loop], True
                complexity = "O(S + V + E)"
            else:
                if component_loop is None:
                    prefix = tokens[:outer_start]
                    initial_nodes = []
                    for index in range(len(prefix) - 5):
                        is_set_mark = prefix[index:index + 4] == [visited_name, ".", "add", "("]
                        if is_set_mark and prefix[index + 5] == ")":
                            initial_nodes.append(prefix[index + 4])
                        is_array_mark = (prefix[index:index + 2] == [visited_name, "["]
                                         and prefix[index + 3:index + 6] == ["]", "=", "true"])
                        if is_array_mark:
                            initial_nodes.append(prefix[index + 2])
                    if not any(
                        node in initial_nodes
                        and any(prefix[i:i + 4] == [queue_name, ".", method, "("]
                                and prefix[i + 4:i + 6] == [node, ")"]
                                for i in range(len(prefix) - 5)
                                for method in {"add", "offer", "addLast"})
                        for node in initial_nodes
                    ):
                        continue
                complexity = "O(V + E)"
            return {
                "language": "java", "rule_version": "bounded_bfs_traversal_v2",
                "pattern_id": "java_adjacency_list_bfs_visited_guard",
                "input_size": {"vertices": "V", "adjacency_entries": "E",
                               "edge_count_measure": "total directed adjacency entries; an undirected list commonly stores each edge twice",
                               **({"start_entries": "S"} if starts_count else {})},
                "queue": {"driver": "while queue is not empty", "name": queue_name,
                          "initialized_before_traversal": True,
                          "dequeue_token_index": next((i for i in range(len(tokens)-2)
                              if tokens[i] == queue_name and tokens[i+1] == "."
                              and tokens[i+2] in {"poll", "remove", "pollFirst", "removeFirst"}), None),
                          "initial_enqueue_token_index": next((i for i in range(outer_start)
                              if tokens[i] == queue_name and tokens[i+1:i+3] in
                              ([".", "add"], [".", "offer"], [".", "addLast"])), None)},
                "visited_state": {"name": visited_name, "guard_body": guard_body_kind,
                                  "bound": "each vertex enqueued at most once",
                                  "guard_kind": "set_add_true_condition" if set_visited else "boolean_array_mark_before_enqueue",
                                  "mark_before_enqueue": True,
                                  "one_enqueue_per_vertex": True},
                "enqueues": {"guarded_enqueue_count": 1,
                             "same_neighbor_guarded_and_enqueued": True},
                "neighbor_enumeration": {"representation": "adjacency_list",
                                          "bound": "each adjacency entry is scanned once"},
                "adjacency_list_evidence": {
                    "parameter": adjacency_name,
                    "parameter_type": next(("".join(shape).replace("><", ">,<")
                        for shape in (("List", "<", "List", "<", "Integer", ">", ">"),
                                      ("Map", "<", "Integer", ",", "List", "<", "Integer", ">", ">"),
                                      ("HashMap", "<", "Integer", ",", "List", "<", "Integer", ">", ">"))
                        if typed_declaration(adjacency_name, (shape,))), "typed adjacency-list parameter"),
                },
                "seed_initialization": {"input_entries": "S" if starts_count else 1,
                                        "bound": "O(S)" if starts_count else "O(1)",
                                        "duplicates_deduplicated": deduplicated,
                                        "duplicate_starts_deduplicated": deduplicated,
                                        "simplification": {"result": "O(V + E)",
                                            "only_if": "S <= V"} if starts_count else None},
                **({"component_traversal": {"global_visited_state": True,
                                              "each_component_seeded_once": True}}
                   if component_traversal else {}),
                "source_locations": {"neighbor_loop_token_index": inner_start,
                                     "neighbor_loop_line": lines[inner_start],
                                     "visited_guard_token_index": guard_start,
                                     "visited_guard_line": lines[guard_start],
                                     "neighbor_enqueue_token_index": enqueue_index,
                                     "neighbor_enqueue_line": lines[enqueue_index],
                                     "seed_loop_line": seed_line,
                                     "queue_loop_line": lines[outer_start]},
                "bounded_work_argument": ("Seed processing is O(S); each vertex is enqueued and "
                    "processed at most once for O(V), and each adjacency entry is scanned once for O(E)."
                    if starts_count else "Each vertex is enqueued and processed at most once, contributing O(V); "
                    "scanning all adjacency entries contributes O(E)."),
                "complexity": complexity,
                "assumptions": ["The graph parameter is a typed adjacency-list collection.",
                    "Set membership/insertion and queue operations are expected O(1).",
                    "No input-sized loop repeats the traversal or adds nested work."],
                "limitations": ["Tokenizer pattern matching is heuristic and does not resolve aliases or helpers."],
                "inference_kind": "heuristic_static_bounded_argument",
            }
    return None


def _is_node_children_bfs(
    tokens: list[str], body: list[str], spans: list[tuple[int, int]],
    signature_tokens: list[str],
) -> dict | None:
    """Recognize a bounded object-graph BFS that deduplicates when dequeuing."""
    if len(spans) != 1 or body[spans[0][0]] != "while":
        return None

    root_type = next((
        (signature_tokens[index + 2], signature_tokens[index + 4])
        for index in range(len(signature_tokens) - 4)
        if signature_tokens[index : index + 2] == ["Node", "<"]
        and signature_tokens[index + 3] == ">"
        and re.fullmatch(r"[A-Za-z_$][\w$]*", signature_tokens[index + 4])
    ), None)
    if root_type is None:
        return None
    type_name, root = root_type

    queue_declaration = next((
        (index + 7, body[index + 7])
        for index in range(len(body) - 7)
        if body[index : index + 7] == ["Queue", "<", "Node", "<", type_name, ">", ">"]
        and re.fullmatch(r"[A-Za-z_$][\w$]*", body[index + 7])
    ), None)
    if queue_declaration is None:
        return None
    queue = queue_declaration[1]

    contains_call = next((
        (body[index], body[index + 4])
        for index in range(len(body) - 5)
        if body[index + 1 : index + 4] == [".", "contains", "("]
        and body[index + 5] == ")"
        and re.fullmatch(r"[A-Za-z_$][\w$]*", body[index + 4])
    ), None)
    if contains_call is None:
        return None
    visited_name, contained_value = contains_call
    if not any(
        tokens[index : index + 5] == [collection, "<", type_name, ">", visited_name]
        for collection in ("Set", "HashSet")
        for index in range(len(tokens) - 4)
    ):
        return None

    loop_start, loop_end = spans[0]
    header = _loop_header(body, loop_start)
    if header is None:
        return None
    opening, closing = header
    if body[opening + 1 : closing] != ["!", queue, ".", "isEmpty", "(", ")"]:
        return None

    before_loop = body[:loop_start]
    queue_init = [queue, "=", "new", "ArrayDeque", "<", ">", "(", root, ".",
                  "getChildren", "(", ")", ")"]
    if not any(before_loop[index : index + len(queue_init)] == queue_init
               for index in range(len(before_loop) - len(queue_init) + 1)):
        return None
    root_seed = [visited_name, ".", "add", "(", root, ".", "getValue", "(", ")", ")"]
    if not any(
        before_loop[index : index + len(root_seed)] == root_seed
        for index in range(len(before_loop) - len(root_seed) + 1)
    ):
        return None

    loop_body = body[closing + 1 : loop_end]
    dequeue = next((
        (loop_body[index - 2], index)
        for index in range(2, len(loop_body) - 5)
        if loop_body[index : index + 6] == [queue, ".", "poll", "(", ")", ";"]
    ), None)
    if dequeue is None:
        return None
    current, dequeue_index = dequeue
    current_value = next((
        loop_body[index]
        for index in range(len(loop_body) - 6)
        if loop_body[index + 1 : index + 7] == ["=", current, ".", "getValue", "(", ")"]
    ), None)
    if current_value is None or current_value != contained_value:
        return None

    guard = ["if", "(", visited_name, ".", "contains", "(", current_value, ")", ")", "{"]
    guard_start = next((
        index for index in range(len(loop_body) - len(guard))
        if loop_body[index : index + len(guard)] == guard
        and loop_body[index + len(guard) : index + len(guard) + 2] == ["continue", ";"]
    ), None)
    if guard_start is None or dequeue_index >= guard_start:
        return None
    mark = [visited_name, ".", "add", "(", current_value, ")"]
    mark_index = next((
        index for index in range(guard_start + len(guard) + 2, len(loop_body) - len(mark) + 1)
        if loop_body[index : index + len(mark)] == mark
    ), None)
    child_enqueue = [queue, ".", "addAll", "(", current, ".", "getChildren", "(", ")", ")"]
    enqueue_index = next((
        index for index in range(len(loop_body) - len(child_enqueue) + 1)
        if loop_body[index : index + len(child_enqueue)] == child_enqueue
    ), None)
    if mark_index is None or enqueue_index is None or mark_index >= enqueue_index:
        return None

    return {
        "language": "java",
        "rule_version": "bounded_object_bfs_v1",
        "pattern_id": "java_node_children_bfs_dequeue_deduplication",
        "complexity": "O(V + E)",
        "input_size": {
            "vertices": "V = distinct reachable values expanded",
            "adjacency_entries": "E = child references enumerated from expanded values",
        },
        "queue": {"driver": "while queue is not empty", "name": queue,
                  "initialization": "root.getChildren()"},
        "visited_state": {"name": visited_name, "deduplication": "on dequeue",
                          "each_value_expanded_at_most_once": True,
                          "one_enqueue_per_vertex": False},
        "neighbor_enumeration": {"representation": "Node child lists",
                                  "bound": "getChildren/addAll work is O(degree)"},
        "pending_queue_bound": "O(E); duplicate references may be queued before dequeue deduplication",
        "source_locations": {"queue_loop_token_index": loop_start,
                             "dequeue_token_index": closing + 1 + dequeue_index,
                             "visited_guard_token_index": closing + 1 + guard_start,
                             "child_enqueue_token_index": closing + 1 + enqueue_index},
        "bounded_work_argument": (
            "Each distinct value is expanded at most once, so child-list enumeration totals O(E). "
            "At most O(E) child references are queued and checked, while visited/list updates "
            "cost O(V), giving O(V + E)."
        ),
        "assumptions": [
            "The analyzed method runs on a fresh traversal instance.",
            "Each getChildren iteration and queue.addAll operation is O(degree).",
            "HashSet contains/add and value equality/hashCode are expected O(1).",
            "The graph has V reachable distinct values and E child references enumerated from expanded values.",
        ],
        "limitations": [
            "Dequeue-time deduplication can hold O(E) duplicate references in the queue.",
            "The tokenizer rule recognizes this specific Node<T>/Queue pattern only.",
        ],
        "inference_kind": "heuristic_static_bounded_argument",
    }


def _for_loop_bound(
    tokens: list[str], start: int, accepted_bounds: set[str] | None = None
) -> tuple[str, str] | None:
    """Read a deliberately narrow for (int x=0; x<bound; x++) loop shape."""
    header = _loop_header(tokens, start)
    if header is None:
        return None
    opening, closing = header
    parts = tokens[opening + 1 : closing]
    separators = [index for index, token in enumerate(parts) if token == ";"]
    if len(separators) != 2:
        return None
    initializer = parts[: separators[0]]
    condition = parts[separators[0] + 1 : separators[1]]
    update = parts[separators[1] + 1 :]
    variable = next((
        initializer[index - 1]
        for index, token in enumerate(initializer)
        if token == "=" and index >= 1 and initializer[index + 1 : index + 2] == ["0"]
        and re.fullmatch(r"[A-Za-z_$][\w$]*", initializer[index - 1])
    ), None)
    accepted_bounds = accepted_bounds or {"rows", "cols"}
    if (
        variable is None
        or len(condition) != 3
        or condition[0] != variable
        or condition[1] != "<"
        or condition[2] not in accepted_bounds
    ):
        return None
    if update not in ([variable, "++"], ["++", variable], [variable, "+=", "1"]):
        return None
    return variable, condition[2]


def _is_grid_cell_access(
    tokens: list[str], start: int, end: int, grid_name: str, row_name: str, col_name: str
) -> bool:
    access = [grid_name, "[", row_name, "]", "[", col_name, "]"]
    return any(tokens[index : index + len(access)] == access for index in range(start, end))


def _is_grid_bfs(
    tokens: list[str],
    spans: list[tuple[int, int]],
    line_numbers: list[int] | None = None,
) -> dict | None:
    """Recognize a single-source grid BFS with a fixed 4- or 8-direction loop."""
    line_numbers = line_numbers or [None] * len(tokens)
    for queue_start, queue_end in spans:
        if tokens[queue_start] != "while":
            continue
        if any(start < queue_start and end >= queue_end for start, end in spans):
            continue
        header = _loop_header(tokens, queue_start)
        if header is None:
            continue
        open_header, close_header = header
        condition = tokens[open_header + 1 : close_header]
        queue_name = next((
            condition[index - 1]
            for index in range(1, len(condition) - 1)
            if condition[index : index + 2] == [".", "isEmpty"] and "!" in condition[:index]
        ), None)
        if queue_name is None:
            continue
        dequeue_index = next((
            index
            for index in range(queue_start + 3, queue_end - 3)
            if tokens[index] == queue_name and tokens[index + 1 : index + 4]
            in ([".", "remove", "("], [".", "removeFirst", "("],
                [".", "poll", "("], [".", "pollFirst", "("])
            and tokens[index - 1] == "="
        ), None)
        if dequeue_index is None:
            continue
        for neighbor_start, neighbor_end in spans:
            if not (queue_start < neighbor_start < neighbor_end <= queue_end):
                continue
            if tokens[neighbor_start] != "for":
                continue
            neighbor_header = _loop_header(tokens, neighbor_start)
            if neighbor_header is None:
                continue
            neighbor_open, neighbor_close = neighbor_header
            parts = tokens[neighbor_open + 1 : neighbor_close]
            separators = [index for index, token in enumerate(parts) if token == ";"]
            if len(separators) != 2:
                continue
            initializer = parts[: separators[0]]
            loop_condition = parts[separators[0] + 1 : separators[1]]
            update = parts[separators[1] + 1 :]
            direction_count = next((
                int(loop_condition[index + 2])
                for index in range(len(loop_condition) - 2)
                if loop_condition[index + 1] == "<" and loop_condition[index + 2].isdigit()
            ), None)
            if direction_count not in {4, 8}:
                continue
            index_name = next((
                initializer[index - 1]
                for index, token in enumerate(initializer)
                if token == "=" and index >= 1 and initializer[index + 1 : index + 2] == ["0"]
            ), None)
            if index_name is None or update not in (
                [index_name, "++"], ["++", index_name], [index_name, "+=", "1"]
            ):
                continue
            neighbor_body_open = neighbor_close + 1
            if neighbor_body_open >= neighbor_end or tokens[neighbor_body_open] != "{":
                continue
            neighbor_body_end = _matching(tokens, neighbor_body_open, "{", "}")
            if neighbor_body_end is None or neighbor_body_end > neighbor_end:
                continue
            for guard_start in range(neighbor_body_open + 1, neighbor_body_end):
                if tokens[guard_start] != "if":
                    continue
                guard_header = _loop_header(tokens, guard_start)
                if guard_header is None:
                    continue
                guard_open, guard_close = guard_header
                guard = tokens[guard_open + 1 : guard_close]
                visited_condition = next((
                    guard[index : index + 8]
                    for index in range(len(guard) - 7)
                    if guard[index] == "!"
                    and guard[index + 2] == "["
                    and guard[index + 4 : index + 6] == ["]", "["]
                    and guard[index + 7] == "]"
                ), None)
                if visited_condition is None:
                    continue
                visited_name = visited_condition[1]
                row_index, col_index = visited_condition[3], visited_condition[6]
                visited_decl = next((
                    index for index in range(queue_start)
                    if tokens[index : index + 3] == ["new", "boolean", "["]
                    and index + 7 < queue_start
                    and index >= 2
                    and tokens[index - 1] == "="
                    and index >= 3
                    and tokens[index - 2] == visited_name
                    and re.fullmatch(r"[A-Za-z_$][\w$]*", tokens[index + 3])
                    and tokens[index + 4 : index + 6] == ["]", "["]
                    and re.fullmatch(r"[A-Za-z_$][\w$]*", tokens[index + 6])
                    and tokens[index + 7] == "]"
                ), None)
                if visited_decl is None:
                    continue
                row_dimension = tokens[visited_decl + 3]
                column_dimension = tokens[visited_decl + 6]
                queue_created = any(
                    tokens[index : index + 2] == ["new", "ArrayDeque"]
                    and index >= 2
                    and tokens[index - 2] == queue_name
                    and tokens[index - 1] == "="
                    for index in range(queue_start)
                )
                seed_enqueue = next((
                    index for index in range(queue_start - 4)
                    if tokens[index : index + 3]
                    in ([queue_name, ".", "add"], [queue_name, ".", "offer"],
                        [queue_name, ".", "addLast"])
                    and tokens[index + 3] == "("
                ), None)
                seed_mark = next((
                    index for index in range(queue_start - 8)
                    if tokens[index : index + 8] == [
                        visited_name, "[", tokens[index + 2], "]", "[", tokens[index + 5], "]", "="
                    ]
                    and tokens[index + 8 : index + 9] == ["true"]
                ), None)
                if (
                    not queue_created or seed_enqueue is None or seed_mark is None
                    or seed_mark >= seed_enqueue
                ):
                    continue
                def control_body_end(start: int, limit: int) -> int | None:
                    if start >= limit:
                        return None
                    if tokens[start] in {"for", "while"}:
                        control_header = _loop_header(tokens, start)
                        if control_header is None:
                            return None
                        return control_body_end(control_header[1] + 1, limit)
                    return _java_control_statement_end(tokens, start, limit)

                scan_loop_spans = []
                for start, _ in spans:
                    if tokens[start] != "for":
                        continue
                    control_header = _loop_header(tokens, start)
                    if control_header is None:
                        continue
                    body_end = control_body_end(control_header[1] + 1, queue_end)
                    if body_end is not None:
                        scan_loop_spans.append((start, body_end + 1))

                grid_name = next((
                    guard[index]
                    for index in range(len(guard) - 6)
                    if re.fullmatch(r"[A-Za-z_$][\w$]*", guard[index])
                    and guard[index + 1 : index + 3] == ["[", row_index]
                    and guard[index + 3 : index + 6] == ["]", "[", col_index]
                    and guard[index + 6] == "]"
                    and guard[index] != visited_name
                ), None)
                separate_bounds_guard = grid_name is None

                if grid_name is None:
                    for row_start, row_end in scan_loop_spans:
                        if not (
                            neighbor_body_open < row_start < row_end <= neighbor_body_end
                            and tokens[row_start] == "for"
                        ):
                            continue
                        row_bound = _for_loop_bound(tokens, row_start, {row_dimension})
                        if row_bound is None:
                            continue
                        for col_start, col_end in scan_loop_spans:
                            if not (row_start < col_start < col_end <= row_end):
                                continue
                            col_bound = _for_loop_bound(
                                tokens, col_start, {column_dimension}
                            )
                            if col_bound is None:
                                continue
                            grid_name = next((
                                tokens[index]
                                for index in range(col_start, col_end - 6)
                                if re.fullmatch(r"[A-Za-z_$][\w$]*", tokens[index])
                                and tokens[index] != visited_name
                                and tokens[index + 1 : index + 7] == [
                                    "[", row_bound[0], "]", "[", col_bound[0], "]"
                                ]
                            ), None)
                            if grid_name is not None:
                                break
                        if grid_name is not None:
                            break
                if grid_name is None:
                    continue

                def dimension_matches_grid(dimension: str, axis: str) -> bool:
                    if dimension == ("rows" if axis == "rows" else "cols"):
                        return True
                    if axis == "rows":
                        expected = [dimension, "=", grid_name, ".", "length"]
                    else:
                        expected = [
                            dimension, "=", grid_name, "[", "0", "]", ".", "length"
                        ]
                    return any(
                        tokens[index : index + len(expected)] == expected
                        for index in range(queue_start - len(expected) + 1)
                    )

                def literal_offset_array(array_name: str) -> list[int] | None:
                    for index in range(neighbor_start):
                        if not (
                            tokens[index] == array_name
                            and tokens[index + 1 : index + 3] == ["=", "{"]
                        ):
                            continue
                        end = _matching(tokens, index + 2, "{", "}")
                        if end is None:
                            return None
                        values: list[int] = []
                        item = tokens[index + 3 : end]
                        cursor = 0
                        while cursor < len(item):
                            sign = 1
                            if item[cursor] == "-":
                                sign = -1
                                cursor += 1
                            if cursor >= len(item) or not item[cursor].isdigit():
                                return None
                            values.append(sign * int(item[cursor]))
                            cursor += 1
                            if cursor < len(item):
                                if item[cursor] != ",":
                                    return None
                                cursor += 1
                        return values
                    return None

                def candidate_offset_array(
                    candidate: str, coordinate: str, before: int
                ) -> str | None:
                    current_coordinate = [
                        tokens[dequeue_index - 2], "[", coordinate, "]"
                    ]
                    for index in range(neighbor_close + 1, before - 1):
                        if tokens[index : index + 2] != [candidate, "="]:
                            continue
                        rhs_end = index + 2
                        bracket_depth = 0
                        while rhs_end < before:
                            token = tokens[rhs_end]
                            if token == "[":
                                bracket_depth += 1
                            elif token == "]":
                                bracket_depth -= 1
                            elif token in {",", ";"} and bracket_depth == 0:
                                break
                            rhs_end += 1
                        rhs = tokens[index + 2 : rhs_end]
                        if "+" not in rhs or not any(
                            rhs[position : position + len(current_coordinate)]
                            == current_coordinate
                            for position in range(len(rhs) - len(current_coordinate) + 1)
                        ):
                            continue
                        offset_name = next((
                            rhs[position]
                            for position in range(len(rhs) - 3)
                            if re.fullmatch(r"[A-Za-z_$][\w$]*", rhs[position])
                            and rhs[position + 1 : position + 4] == ["[", index_name, "]"]
                        ), None)
                        if offset_name is not None:
                            return offset_name
                    return None

                if separate_bounds_guard:
                    row_offsets = candidate_offset_array(row_index, "0", guard_start)
                    column_offsets = candidate_offset_array(col_index, "1", guard_start)
                    row_values = literal_offset_array(row_offsets) if row_offsets else None
                    column_values = literal_offset_array(column_offsets) if column_offsets else None
                    if (
                        row_values is None or column_values is None
                        or len(row_values) != direction_count
                        or len(column_values) != direction_count
                    ):
                        continue
                    direction_pairs = set(zip(row_values, column_values))
                    expected_directions = (
                        {(-1, 0), (1, 0), (0, -1), (0, 1)}
                        if direction_count == 4
                        else {
                            (row_step, col_step)
                            for row_step in (-1, 0, 1)
                            for col_step in (-1, 0, 1)
                            if (row_step, col_step) != (0, 0)
                        }
                    )
                    if direction_pairs != expected_directions:
                        continue

                if not (
                    dimension_matches_grid(row_dimension, "rows")
                    and dimension_matches_grid(column_dimension, "cols")
                ):
                    continue
                guard_body_open = guard_close + 1
                if guard_body_open >= neighbor_body_end or tokens[guard_body_open] != "{":
                    continue
                guard_body_end = _matching(tokens, guard_body_open, "{", "}")
                if guard_body_end is None:
                    continue
                body = tokens[guard_body_open + 1 : guard_body_end]
                mark = next((
                    index for index in range(len(body) - 8)
                    if body[index : index + 9] == [
                        visited_name, "[", row_index, "]", "[", col_index, "]", "=", "true"
                    ]
                ), None)
                if mark is None:
                    continue
                enqueue = next((
                    index for index in range(len(body) - 3)
                    if body[index : index + 3]
                    in ([queue_name, ".", "add"], [queue_name, ".", "offer"],
                        [queue_name, ".", "addLast"])
                    and index + 3 < len(body) and body[index + 3] == "("
                ), None)
                if enqueue is None or mark >= enqueue:
                    continue

                full_grid_scans = []
                recognized_scan_loop_starts: set[int] = set()
                for row_start, row_end in scan_loop_spans:
                    if tokens[row_start] != "for":
                        continue
                    row_bound = _for_loop_bound(tokens, row_start, {row_dimension})
                    if row_bound is None:
                        continue
                    for col_start, col_end in scan_loop_spans:
                        if not (
                            row_start < col_start < col_end <= row_end
                            or row_end == col_start
                        ):
                            continue
                        col_bound = _for_loop_bound(tokens, col_start, {column_dimension})
                        if col_bound is None:
                            continue
                        if not _is_grid_cell_access(
                            tokens, col_start, col_end, grid_name, row_bound[0], col_bound[0]
                        ):
                            continue
                        if queue_start < row_start and col_end <= queue_end:
                            placement = (
                                "inside_neighbor_processing"
                                if neighbor_start < row_start and col_end <= neighbor_end
                                else "inside_queue_processing"
                            )
                        elif col_end < queue_start or row_start > queue_end:
                            placement = "outside_traversal"
                        else:
                            continue
                        full_grid_scans.append({
                            "placement": placement,
                            "row_bound": row_dimension,
                            "column_bound": column_dimension,
                            "estimated_cost": "O(R*C)",
                            "source_locations": {
                                "row_loop_token_index": row_start,
                                "row_loop_line": line_numbers[row_start],
                                "column_loop_token_index": col_start,
                                "column_loop_line": line_numbers[col_start],
                            },
                        })
                        recognized_scan_loop_starts.update((row_start, col_start))

                if separate_bounds_guard:
                    if not full_grid_scans:
                        continue

                    def has_condition_sequence(
                        condition_tokens: list[str], pattern: tuple[str, ...]
                    ) -> bool:
                        return any(
                            condition_tokens[index : index + len(pattern)] == list(pattern)
                            for index in range(len(condition_tokens) - len(pattern) + 1)
                        )

                    scan_starts = [
                        scan["source_locations"]["row_loop_token_index"]
                        for scan in full_grid_scans
                    ]
                    scan_col_ends = [
                        next((
                            end for start, end in spans
                            if start == scan["source_locations"]["column_loop_token_index"]
                        ), -1)
                        for scan in full_grid_scans
                    ]
                    enclosing_bounds = False
                    for bounds_start in range(neighbor_body_open + 1, guard_start):
                        if tokens[bounds_start] != "if":
                            continue
                        bounds_header = _loop_header(tokens, bounds_start)
                        if bounds_header is None:
                            continue
                        bounds_condition = tokens[bounds_header[0] + 1 : bounds_header[1]]
                        bounds_body = bounds_header[1] + 1
                        if bounds_body >= neighbor_body_end or tokens[bounds_body] != "{":
                            continue
                        bounds_end = _matching(tokens, bounds_body, "{", "}")
                        if bounds_end is None or bounds_end > neighbor_body_end:
                            continue
                        covers_row = (
                            has_condition_sequence(bounds_condition, (row_index, ">=", "0"))
                            or has_condition_sequence(bounds_condition, ("0", "<=", row_index))
                        ) and (
                            has_condition_sequence(bounds_condition, (row_index, "<", row_dimension))
                            or has_condition_sequence(
                                bounds_condition, (row_dimension, ">", row_index)
                            )
                        )
                        covers_column = (
                            has_condition_sequence(bounds_condition, (col_index, ">=", "0"))
                            or has_condition_sequence(bounds_condition, ("0", "<=", col_index))
                        ) and (
                            has_condition_sequence(
                                bounds_condition, (col_index, "<", column_dimension)
                            )
                            or has_condition_sequence(
                                bounds_condition, (column_dimension, ">", col_index)
                            )
                        )
                        if (
                            covers_row and covers_column
                            and all(bounds_body < start for start in scan_starts)
                            and all(end < guard_start for end in scan_col_ends)
                            and all(end < bounds_end for end in scan_col_ends)
                            and bounds_start < guard_start < bounds_end
                        ):
                            enclosing_bounds = True
                            break
                    if not enclosing_bounds:
                        continue

                traversal_loop_starts = {
                    start for start, _ in spans
                    if queue_start < start < queue_end and start != neighbor_start
                }
                if not traversal_loop_starts <= recognized_scan_loop_starts:
                    continue
                outside_loop_starts = {
                    start for start, _ in spans
                    if not (queue_start <= start <= queue_end) and start != queue_start
                }
                if not outside_loop_starts <= recognized_scan_loop_starts:
                    continue

                repeated_grid_scan = any(
                    scan["placement"] != "outside_traversal" for scan in full_grid_scans
                )
                complexity = "O((R * C)^2)" if repeated_grid_scan else "O(R * C)"
                aggregate_work = (
                    "O(R*C) dequeued cells * O(R*C) full-grid work per cell = O((R*C)^2)"
                    if repeated_grid_scan
                    else "O(R*C) pre/post traversal scan + O(R*C) bounded BFS = O(R*C)"
                    if full_grid_scans
                    else "O(R*C) dequeued cells * O(1) bounded neighbor work = O(R*C)"
                )
                return {
                    "language": "java",
                    "rule_version": "bounded_bfs_traversal_v2",
                    "pattern_id": "java_grid_bfs_fixed_direction_loop",
                    "source_locations": {
                        "queue_loop_token_index": queue_start,
                        "queue_loop_line": line_numbers[queue_start],
                        "dequeue_call_token_index": dequeue_index,
                        "dequeue_call_line": line_numbers[dequeue_index],
                        "neighbor_loop_token_index": neighbor_start,
                        "neighbor_loop_line": line_numbers[neighbor_start],
                        "visited_guard_token_index": guard_start,
                        "visited_guard_line": line_numbers[guard_start],
                        "initial_visited_mark_token_index": seed_mark,
                        "initial_enqueue_token_index": seed_enqueue,
                        "neighbor_visited_mark_token_index": guard_body_open + 1 + mark,
                        "neighbor_enqueue_token_index": guard_body_open + 1 + enqueue,
                        "neighbor_enqueue_line": line_numbers[guard_body_open + 1 + enqueue],
                    },
                    "input_size": {"rows": "R", "columns": "C"},
                    "queue": {"driver": queue_name, "dequeue": "remove/poll", "token_index": queue_start},
                    "visited_state": {"container": "boolean[][]", "name": visited_name,
                                      "mark_before_enqueue": True, "one_enqueue_per_cell": True},
                    "neighbor_enumeration": {"fixed_neighbors_per_cell": direction_count,
                                             "loop_index": index_name, "loop_token_index": neighbor_start},
                    "additional_grid_scans": full_grid_scans,
                    "loop_costs": {
                        "queue_processing": "O(R*C), since each cell is enqueued and processed at most once",
                        "neighbor_enumeration": f"O(1) per dequeued cell ({direction_count} fixed directions)",
                        "additional_full_grid_scan": "O(R*C) per execution when present",
                    },
                    "aggregate_work": aggregate_work,
                    "bounded_work_argument": (
                        "Each cell is enqueued at most once. The analyzer checks every nested loop "
                        "in the traversal. Recognized full-grid loops cost O(R*C); a scan repeated "
                        "per dequeued cell raises total work to O((R*C)^2). One scan outside the "
                        "traversal adds O(R*C) to the bounded O(R*C) traversal."
                    ),
                    "complexity": complexity,
                    "assumptions": [
                        "The grid dimensions are R by C and the traversal is single-source.",
                        "The visited cell is marked before it is enqueued.",
                        "Queue operations and grid/visited accesses are O(1).",
                        f"The direction loop executes exactly {direction_count} times per cell.",
                        "Recognized additional scans iterate rows and columns and read a grid cell.",
                    ],
                    "limitations": [
                        "Only fixed-bound 4- or 8-direction loops are recognized.",
                        "Tokenizer offsets are used; this is a narrow static heuristic, not a proof.",
                        "Only explicit rows/columns full-grid scans are costed; other loop work inside or adjacent to the traversal causes the grid rule to abstain.",
                    ],
                    "inference_kind": "heuristic_static_bounded_argument",
                }
    return None


def _is_adjacency_matrix_bfs(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize BFS with visited-before-enqueue marking and a full matrix row scan."""
    if len(spans) != 2:
        return False
    for outer_start, outer_end in spans:
        if tokens[outer_start] != "while":
            continue
        header = _loop_header(tokens, outer_start)
        if header is None:
            continue
        opening, closing = header
        condition = tokens[opening + 1 : closing]
        queue_name = next(
            (
                condition[index - 1]
                for index in range(1, len(condition) - 1)
                if condition[index : index + 2] == [".", "isEmpty"]
                and "!" in condition[:index]
            ),
            None,
        )
        if queue_name is None:
            continue
        current_node = next(
            (
                tokens[index - 2]
                for index in range(outer_start + 3, outer_end - 3)
                if tokens[index] == queue_name
                and tokens[index + 1 : index + 4]
                in ([".", "poll", "("], [".", "remove", "("], [".", "pollFirst", "("], [".", "removeFirst", "("])
                and tokens[index - 1] == "="
            ),
            None,
        )
        if current_node is None:
            continue

        for inner_start, inner_end in spans:
            if not (
                outer_start < inner_start < inner_end <= outer_end
                and tokens[inner_start] == "for"
            ):
                continue
            inner_header = _loop_header(tokens, inner_start)
            if inner_header is None:
                continue
            inner_open, inner_close = inner_header
            inner_statement_end = _java_control_statement_end(
                tokens, inner_close + 1, outer_end
            )
            if inner_statement_end is None:
                continue
            loop_header = tokens[inner_open + 1 : inner_close]
            separators = [index for index, token in enumerate(loop_header) if token == ";"]
            if len(separators) != 2:
                continue
            initializer = loop_header[: separators[0]]
            loop_condition = loop_header[separators[0] + 1 : separators[1]]
            update = loop_header[separators[1] + 1 :]
            if len(initializer) < 3 or initializer[-2:] != ["=", "0"]:
                continue
            neighbor = initializer[-3]
            size = next(
                (
                    loop_condition[index + 2]
                    for index in range(len(loop_condition) - 2)
                    if loop_condition[index : index + 2] == [neighbor, "<"]
                ),
                None,
            )
            if size is None or not _is_positive_step(update, neighbor):
                continue

            for guard_start in range(inner_close + 1, inner_statement_end + 1):
                if tokens[guard_start] != "if":
                    continue
                guard_header = _loop_header(tokens, guard_start)
                if guard_header is None:
                    continue
                guard_open, guard_close = guard_header
                guard = tokens[guard_open + 1 : guard_close]
                matrix_name = next(
                    (
                        guard[index]
                        for index in range(len(guard) - 6)
                        if guard[index + 1 : index + 7]
                        == ["[", current_node, "]", "[", neighbor, "]"]
                    ),
                    None,
                )
                visited_name = next(
                    (
                        guard[index + 1]
                        for index in range(len(guard) - 4)
                        if guard[index] == "!"
                        and guard[index + 2 : index + 5] == ["[", neighbor, "]"]
                    ),
                    None,
                )
                if matrix_name is None or visited_name is None or "&&" not in guard:
                    continue
                size_init = [size, "=", matrix_name, ".", "length"]
                if not any(
                    tokens[index : index + len(size_init)] == size_init
                    for index in range(outer_start - len(size_init) + 1)
                ):
                    continue
                visited_init = [visited_name, "=", "new", "boolean", "[", size, "]"]
                if not any(
                    tokens[index : index + len(visited_init)] == visited_init
                    for index in range(outer_start - len(visited_init) + 1)
                ):
                    continue
                guard_body = guard_close + 1
                if guard_body > inner_statement_end or tokens[guard_body] != "{":
                    continue
                guard_end = _matching(tokens, guard_body, "{", "}")
                if guard_end is None or guard_end > inner_statement_end:
                    continue
                body = tokens[guard_body + 1 : guard_end]
                mark = next((index for index in range(len(body) - 5)
                             if body[index : index + 6] == [visited_name, "[", neighbor, "]", "=", "true"]), None)
                enqueue = next(
                    (
                        index
                        for index in range(len(body) - 4)
                        if body[index] == queue_name
                        and body[index + 1] == "."
                        and body[index + 2] in {"add", "offer", "addLast"}
                        and body[index + 3 : index + 5] == ["(", neighbor]
                    ),
                    None,
                )
                if mark is None or enqueue is None or mark >= enqueue:
                    continue
                before_queue = tokens[:outer_start]
                seed = next(
                    (
                        before_queue[index + 4]
                        for index in range(len(before_queue) - 5)
                        if before_queue[index : index + 4]
                        in ([queue_name, ".", "add", "("],
                            [queue_name, ".", "offer", "("],
                            [queue_name, ".", "addLast", "("])
                        and re.fullmatch(r"[A-Za-z_$][\w$]*", before_queue[index + 4])
                        and before_queue[index + 5] == ")"
                    ),
                    None,
                )
                if seed is None:
                    continue
                return True
    return False


def _is_adjacency_list_dfs(
    tokens: list[str], spans: list[tuple[int, int]], method_name: str
) -> bool:
    """Recognize recursive DFS over adjacency lists with a visited-set guard."""
    recursive_calls = [
        index
        for index in range(len(tokens) - 1)
        if tokens[index] == method_name and tokens[index + 1] == "("
    ]
    if len(recursive_calls) != 1:
        return False

    for loop_start, loop_end in spans:
        if tokens[loop_start] != "for":
            continue
        header = _loop_header(tokens, loop_start)
        if header is None:
            continue
        opening, closing = header
        loop_header = tokens[opening + 1 : closing]
        if ":" not in loop_header:
            continue
        colon = loop_header.index(":")
        if colon < 1:
            continue
        neighbor = loop_header[colon - 1]
        adjacency = loop_header[colon + 1 :]
        if not any(
            adjacency[index : index + 3] == [".", "get", "("]
            for index in range(len(adjacency) - 2)
        ):
            continue

        for guard_start in range(loop_start + 1, loop_end):
            if tokens[guard_start] != "if":
                continue
            guard_header = _loop_header(tokens, guard_start)
            if guard_header is None:
                continue
            guard_open, guard_close = guard_header
            guard_body = guard_close + 1
            if guard_body >= loop_end or tokens[guard_body] != "{":
                continue
            guard_end = _matching(tokens, guard_body, "{", "}")
            if guard_end is None or guard_end > loop_end:
                continue
            guard = tokens[guard_open + 1 : guard_close]
            body = tokens[guard_body + 1 : guard_end]
            visited_name = next(
                (
                    guard[index - 1]
                    for index in range(1, len(guard) - 3)
                    if guard[index : index + 3] == [".", "add", "("]
                    and guard[index + 3] == neighbor
                ),
                None,
            )
            call_index = recursive_calls[0] - (guard_body + 1)
            if (
                visited_name is not None
                and 0 <= call_index < len(body) - 2
                and body[call_index + 2] == neighbor
                and _has_method_call(guard, visited_name, {"add"}, neighbor)
            ):
                return True
    return False


def _estimate_java_auxiliary_space(
    tokens: list[str],
    class_range: tuple[int, int],
    method_name: str,
    body: list[str],
    spans: list[tuple[int, int]],
) -> dict[str, object]:
    unknown = {
        "state": "unknown",
        "estimate": None,
        "method": "static_java_container_growth",
        "confidence": "low",
        "convention": "Excludes input storage and returned output.",
        "reasoning": "No supported auxiliary-space pattern was established.",
    }
    parameters = _method_parameter_names(tokens, class_range, method_name) or []
    containers: set[str] = set()
    supported_types = {"HashMap", "HashSet", "ArrayList", "ArrayDeque", "LinkedList"}
    for index in range(len(body) - 3):
        if body[index] == "=" and body[index + 1] == "new":
            type_index = index + 2
            if body[type_index] in supported_types:
                name = body[index - 1] if index else ""
                if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                    containers.add(name)

    if parameters and containers and len(spans) == 1:
        start, end = spans[0]
        header_end = next((index for index in range(start, end + 1) if body[index] == "{"), -1)
        header = body[start : header_end if header_end >= 0 else end]
        iterates_input = any(name in header for name in parameters) and (
            ":" in header or "length" in header
        )
        if iterates_input:
            loop_body = body[start : end + 1]
            returned = {
                body[index + 1]
                for index, token in enumerate(body[:-1])
                if token == "return"
            }
            for name in containers - returned:
                if any(
                    index + 2 < len(loop_body)
                    and loop_body[index] == name
                    and loop_body[index + 1] == "."
                    and loop_body[index + 2] in {"put", "add", "offer", "push", "addLast"}
                    for index in range(len(loop_body))
                ):
                    return {
                        "state": "estimated",
                        "estimate": "O(n)",
                        "method": "static_java_container_growth",
                        "confidence": "low",
                        "convention": "Excludes input storage and returned output.",
                        "reasoning": "A local collection is populated during one scan over an input parameter; O(n) is a conservative upper bound.",
                        "limitations": [
                            "This bounded rule does not prove the collection reaches linear size; its true bound may be smaller.",
                            "Called helpers, arrays, recursive space, and nested loops are not analyzed.",
                            "Collection operation costs depend on the concrete type and implementation.",
                        ],
                    }
    control_calls = {"if", "for", "while", "switch", "catch", "synchronized"}
    unsupported_call = any(
        token == "(" and index > 0
        and re.fullmatch(r"[A-Za-z_$][\w$]*", body[index - 1])
        and body[index - 1] not in control_calls
        and not (
            index >= 3
            and body[index - 1] in {"abs", "max", "min"}
            and body[index - 2] == "."
            and body[index - 3] == "Math"
        )
        for index, token in enumerate(body)
    )
    allocation_prone_types = {
        "String", "StringBuilder", "StringBuffer", "Integer", "Long", "Double", "Float",
        "Boolean", "Character", "Byte", "Short", "BigInteger", "BigDecimal",
    }
    string_concatenation = "String" in tokens and any(token in {"+", "+="} for token in body)
    if (
        "new" not in body
        and not unsupported_call
        and not string_concatenation
        and not allocation_prone_types.intersection(body)
    ):
        return {
            "state": "estimated",
            "estimate": "O(1)",
            "method": "static_java_allocation_free_state",
            "confidence": "low",
            "convention": "Excludes input storage and returned output.",
            "reasoning": "The selected method uses scalar/local state and no recognized input-sized allocation or recursion.",
            "limitations": [
                "This rule cannot prove that called library operations have no hidden allocations.",
                "Object construction, non-Math calls, string concatenation, and recursive space are reported as unknown.",
            ],
        }
    return unknown


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
    token_lines = _token_line_numbers(code)
    class_range = _class_body(tokens, parts[0])
    if class_range is None:
        return ComplexityEstimate(
            method,
            "unknown (class not found)",
            "low",
            False,
            f"Could not locate class {parts[0]} in the source.",
        )
    body_range = _method_body_bounds(tokens, class_range, parts[1])
    if body_range is None:
        return ComplexityEstimate(
            method,
            "unknown (method not found)",
            "low",
            False,
            f"Could not locate method {parts[1]} in class {parts[0]}.",
        )
    body = tokens[body_range[0] : body_range[1]]
    body_lines = token_lines[body_range[0] : body_range[1]]

    spans, incomplete_loop = _loop_spans(body)
    auxiliary_space = _estimate_java_auxiliary_space(
        tokens, class_range, parts[1], body, spans
    )
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
        token in {"sort", "parallelSort"}
        and token != parts[1]
        and index + 1 < len(body)
        and body[index + 1] == "("
        for index, token in enumerate(body)
    )
    has_while = any(token == "while" for token in body)
    binary_search = _is_binary_search_loop(body, spans)
    insertion_sort_shift = _is_insertion_sort_shift(body, spans)
    tree_recursion = not spans and recursive and _is_tree_recursive_walk(body, parts[1])
    method_open = body_range[0] - 1
    signature_tokens: list[str] = []
    if method_open >= 0:
        target_close = method_open - 1
        for candidate in range(max(0, target_close - 100), target_close):
            if tokens[candidate] == "(" and _matching(tokens, candidate, "(", ")") == target_close:
                signature_tokens = tokens[candidate + 1 : target_close]
                break
    graph_bfs_details = None
    if not recursive:
        graph_bfs_details = _is_adjacency_list_bfs(body, spans, body_lines, signature_tokens)
        if graph_bfs_details is None:
            graph_bfs_details = _is_node_children_bfs(
                tokens, body, spans, signature_tokens
            )
    graph_bfs = graph_bfs_details is not None
    matrix_bfs = not recursive and _is_adjacency_matrix_bfs(body, spans)
    grid_bfs = _is_grid_bfs(body, spans, body_lines) if not recursive else None
    graph_dfs = recursive and _is_adjacency_list_dfs(body, spans, parts[1])
    signals: list[dict] = []
    for start, _ in spans:
        signals.append({"kind": "loop", "label": f"{body[start]} loop", "line": None})
    if recursive:
        signals.append({
            "kind": "recursion",
            "label": (
                "Direct self-call; guarded graph traversal recognized"
                if graph_dfs
                else "Direct self-call; tree-child traversal recognized"
                if tree_recursion
                else "Direct self-call; recurrence is not solved"
            ),
            "line": None,
        })
    for index, token in enumerate(body[:-1]):
        if token in {"sort", "parallelSort"} and token != parts[1] and body[index + 1] == "(":
            signals.append({"kind": "sorting", "label": f"{token}() call", "line": None})
        if token in {"get", "put", "contains", "add", "remove"} and body[index + 1] == "(":
            signals.append({
                "kind": "collection_operation",
                "label": f".{token}() call; concrete type and cost are not inferred",
                "line": None,
            })
    if "[" in body:
        signals.append({
            "kind": "indexing",
            "label": "Array or indexed access; concrete access cost is not inferred",
            "line": None,
        })
    if binary_search:
        signals.append({
            "kind": "binary_search",
            "label": "Interval-halving loop updates both search bounds from the midpoint",
            "line": None,
        })
    if tree_recursion:
        signals.append({
            "kind": "tree_recursion",
            "label": "Recursion follows a left or right tree-child link",
            "line": None,
        })
    if graph_dfs:
        signals.append({
            "kind": "graph_dfs",
            "label": "Recursive adjacency-list traversal with a visited-set guard",
            "line": None,
        })
    if graph_bfs:
        signals.append({
            "kind": "graph_bfs",
            "label": "Queue traversal over adjacency lists with a visited guard",
            "line": None,
        })
    if matrix_bfs:
        signals.append({
            "kind": "graph_matrix_bfs",
            "label": "Queue traversal scans a full adjacency-matrix row per visited vertex",
            "line": None,
        })
    if grid_bfs is not None:
        signals.append({
            "kind": "grid_bfs",
            "label": "Queue traversal with a fixed-size grid neighborhood and visited-before-enqueue",
            "line": None,
        })
    if insertion_sort_shift:
        signals.append({
            "kind": "insertion_sort_shift",
            "label": "Nested shifting loop moves an indexed element left one position at a time",
            "line": None,
        })
    inward_two_pointer_scan = _is_inward_two_pointer_scan(body, spans)
    if inward_two_pointer_scan:
        signals.append({
            "kind": "inward_two_pointer_scan",
            "label": "Two sequence bounds move inward by one step per loop iteration",
            "line": None,
        })
    monotonic_stack = _amortized_monotonic_stack_scan(body, spans, incomplete_loop)
    if monotonic_stack is not None:
        signals.append({
            "kind": "amortized_monotonic_stack",
            "label": "One ArrayDeque push per array index with monotonic pops",
            "line": None,
        })

    binary_recurrence = _recursive_binary_search_recurrence(tokens, parts[1], body)
    delegated_binary_search = False
    helper_name = _returned_helper_name(body, parts[1])
    if binary_recurrence is None and helper_name is not None:
        helper_range = _method_body_bounds(tokens, class_range, helper_name)
        if helper_range is not None:
            helper_body = tokens[helper_range[0] : helper_range[1]]
            binary_recurrence = _recursive_binary_search_recurrence(
                tokens, helper_name, helper_body
            )
            delegated_binary_search = binary_recurrence is not None
            if delegated_binary_search and binary_recurrence is not None:
                binary_recurrence[1]["assumptions"].append(
                    "The selected entrypoint only returns this helper call, so wrapper overhead is O(1)."
                )
    quicksort_recurrence = _is_last_pivot_quicksort(tokens, class_range, body, parts[1])
    scalar_recurrence = (
        _recursive_scalar_recurrence(tokens, parts[1], class_range, body)
        if binary_recurrence is None and not quicksort_recurrence
        else None
    )
    recurrence_details = None
    if binary_recurrence is not None:
        recurrence_estimate, recurrence_details = binary_recurrence
    elif quicksort_recurrence:
        recurrence_estimate = "O(n^2)"
        recurrence_details = recurrence_evidence(
            function=parts[1],
            recursive_calls=1,
            size_reduction="constant_decrement in the worst case",
            nonrecursive_work="linear",
            recurrence="T(n) = T(n - 1) + O(n)",
            solving_rule="worst_case_decrement_recurrence_linear_work",
            complexity=recurrence_estimate,
            assumptions=[
                "The recursive method partitions around the last array element.",
                "Some sorted or all-equal inputs can place the pivot at an endpoint.",
                "Partition scans the current range once and performs O(n) work.",
                "Worst-case time is requested; the smaller recursive subproblem may be empty.",
                "The second recursive call on an empty subproblem has constant work.",
            ],
            location={"function": parts[1], "line": None},
        )
    elif scalar_recurrence is not None:
        recurrence_estimate, recurrence_details = scalar_recurrence
    if recurrence_details is not None:
        for signal in signals:
            if signal["kind"] == "recursion":
                signal["label"] = "Direct self-call; bounded recurrence recognized"
        if delegated_binary_search and helper_name is not None:
            signals.append({
                "kind": "delegated_binary_search",
                "label": f"Entrypoint directly returns recursive binary-search helper {helper_name}()",
                "line": None,
            })
        signals.append({
            "kind": "recurrence",
            "label": "Recursive call pattern matched by bounded recurrence rules",
            "line": recurrence_details["source_location"]["line"],
        })

    amortized_forward_scan = _amortized_forward_scan(body, spans)
    bfs_details = None
    if grid_bfs is not None:
        bfs_details = grid_bfs
        estimate = grid_bfs["complexity"]
        method = "static_java_grid_bfs_v2"
        explanation = grid_bfs["bounded_work_argument"] + (
            " This bounded tokenizer match is a heuristic static estimate, not a proof for "
            "arbitrary Java code."
        )
    elif graph_bfs or graph_dfs:
        estimate = graph_bfs_details["complexity"] if graph_bfs_details else "O(V + E)"
        method = "static_java_graph_dfs" if graph_dfs else "static_java_graph_bfs_v2"
        traversal = "recursive traversal" if graph_dfs else "queue-based traversal"
        work_unit = "visited once" if graph_dfs else "enqueued once"
        explanation = (
            f"Recognized {traversal} over adjacency lists with a visited-state guard. Assuming "
            f"each vertex is {work_unit} and each adjacency entry is scanned once, the work is "
            "O(V + E). Visited checks must be constant-time; the syntax match is a heuristic."
        )
        if graph_bfs:
            bfs_details = graph_bfs_details
            if graph_bfs_details["input_size"].get("start_entries"):
                explanation = (
                    "The multi-source initialization processes S start entries, costing O(S). "
                    "Visited-state guards enqueue each vertex at most once (O(V)), and the "
                    "traversal examines each adjacency entry at most once (O(E)), for "
                    "O(S + V + E). This simplifies to O(V + E) only if S <= V. The result is "
                    "a low-confidence heuristic static estimate, not a proof for arbitrary Java."
                )
            else:
                explanation = graph_bfs_details["bounded_work_argument"] + (
                    " This low-confidence tokenizer match is a heuristic static estimate, not "
                    "a proof for arbitrary Java."
                )
    elif matrix_bfs:
        method = "static_java_matrix_bfs"
        estimate = "O(V^2)"
        explanation = (
            "Recognized queue-based BFS over a square adjacency matrix. The visited array is "
            "marked before each neighbor is enqueued, so each vertex enters the queue at most "
            "once; processing each vertex scans V matrix entries. Assuming O(1) matrix, visited "
            "array, and queue operations, the total work is O(V^2). This tokenizer-based match "
            "is a heuristic."
        )
        bfs_details = {
            "language": "java",
            "rule_version": "bounded_bfs_traversal_v1",
            "pattern_id": "java_adjacency_matrix_bfs",
            "input_size": {"vertices": "V", "matrix_cells": "V * V"},
            "queue": {"driver": "while queue is not empty", "traversal_token_index": next(
                (index for index, token in enumerate(body) if token == "while"), None
            )},
            "source_locations": {
                "loop_token_indices": [start for start, _ in spans],
                "queue_operation_token_indices": [
                    index for index in range(len(body) - 3)
                    if body[index] in {"poll", "remove", "add", "offer"}
                    and index >= 2 and body[index - 1] == "." and body[index + 1] == "("
                ],
            },
            "visited_state": {"bound": "each vertex is enqueued at most once",
                              "mark_before_enqueue": True},
            "neighbor_enumeration": {"representation": "adjacency_matrix",
                                     "bound": "each processed vertex scans V columns"},
            "bounded_work_argument": (
                "At most V vertices are processed, and each scans a full V-entry matrix row, "
                "so the traversal takes O(V^2)."
            ),
            "complexity": "O(V^2)",
            "assumptions": ["The matrix is square and matrix access is O(1).",
                            "Each vertex is marked before enqueue."],
            "limitations": ["This is a token-based heuristic and does not expand aliases or helpers."],
            "inference_kind": "heuristic_static_bounded_argument",
        }
    elif tree_recursion:
        method = "static_java_tree_recursion"
        estimate = "O(n)"
        explanation = (
            "Recognized direct recursion over a tree node's left/right child link. Assuming the "
            "input is a tree with no cycles or shared subtrees, each visited node is processed "
            "once, for O(n) work. The syntax check cannot establish that input structure."
        )
    elif monotonic_stack is not None:
        method = "static_java_amortized_monotonic_stack_v1"
        estimate = "O(n)"
        explanation = (
            "Recognized one ArrayDeque push for each array index and a value-ordered pop loop. "
            "Each index is pushed once and, after it is popped, is not reinserted; the optional "
            "final drain also removes each remaining index once. Total stack operations are "
            "therefore O(n) amortized. This bounded tokenizer pattern is a heuristic, not a proof."
        )
    elif recurrence_details is not None:
        estimate = recurrence_estimate
        method = (
            "static_java_worst_case_quicksort_recurrence"
            if quicksort_recurrence
            else "static_java_delegated_binary_search_recurrence"
            if delegated_binary_search
            else "static_java_recurrence_v1"
        )
        explanation = (
            f"Recognized {recurrence_details['recurrence']} and applied "
            f"{recurrence_details['solving_rule']}, yielding {estimate}. "
            "This is a heuristic syntax match under the listed recurrence assumptions."
        )
    elif recursive:
        estimate = "unknown (recursion detected)"
        explanation += " Recurrence behavior is not inferred by this analyzer."
    elif amortized_forward_scan:
        method = "static_java_amortized_pointer_scan"
        estimate = "O(n)"
        explanation = (
            "Recognized a forward-only sliding-window scan: the outer index advances once, "
            "and the inner pointer starts before the outer loop and only moves forward. "
            "Each pointer advances at most n times, so their combined work is linear."
        )
    elif binary_search:
        estimate = "O(log n)"
        explanation = (
            "Recognized a closed-interval search pattern: the midpoint is computed from both "
            "bounds and each bound is updated to midpoint ± 1. The remaining interval shrinks "
            "by a constant factor per iteration. This tokenizer-based recognition is a heuristic."
        )
    elif inward_two_pointer_scan:
        method = "static_java_inward_two_pointer_scan"
        estimate = "O(n)"
        explanation = (
            "Recognized a single while-loop over a sequence-sized interval initialized from "
            "zero to its end, with the lower cursor incremented and upper cursor decremented "
            "once per continuing iteration. The interval shrinks by at least one each time, "
            "so the loop runs O(n) iterations, with constant work per iteration under the "
            "usual constant-time indexing assumption. This tokenizer-based pattern match is "
            "a heuristic."
        )
    elif insertion_sort_shift:
        method = "static_java_insertion_sort_shift"
        estimate = "O(n^2)"
        explanation = (
            "Recognized an outer pass over the array and an inner backward shift that can move "
            "each element across the preceding prefix. In the worst case the shifts sum to "
            "1 + 2 + ... + (n - 1), giving O(n^2). This structural pattern match is a heuristic."
        )
    elif has_while or incomplete_loop:
        estimate = "unknown (data-dependent or incomplete loop)"
        explanation += (
            " A while-loop or an unbraced loop was detected, but its iteration count cannot "
            "be bounded by the current static rules."
        )
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

    if recurrence_details is not None:
        explanation += " Other helper calls, library costs, and complex control flow are not analyzed; this is not a proof."
    else:
        explanation += " Called helpers, library costs, and complex control flow are not analyzed; this is not a proof."
    confidence = "medium" if amortized_forward_scan else "low"
    return ComplexityEstimate(
        method,
        estimate,
        confidence,
        False,
        explanation,
        details={
            "code_analysis": {
                "language": "java",
                "scope": (
                    "selected entrypoint and one directly returned binary-search helper"
                    if delegated_binary_search
                    else "selected method; called helpers are not expanded"
                ),
                "auxiliary_space": auxiliary_space,
                "signals": signals,
                **({"bfs": bfs_details} if bfs_details is not None else {}),
                **({"monotonic_stack": monotonic_stack} if monotonic_stack is not None else {}),
                **({"recurrence": recurrence_details} if recurrence_details is not None else {}),
                "loop_count": len(spans),
                "maximum_loop_nesting": maximum_depth,
                "limitations": [
                    "Generic tokenizer loop/collection signals do not retain source line numbers; recognized BFS evidence includes line numbers and token indexes.",
                    "Collection operation costs depend on the concrete type and implementation.",
                    "Only the documented bounded recurrence patterns are analyzed; helper calls are otherwise not expanded.",
                ],
            }
        },
    )


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
    details["code_analysis"] = static.details.get("code_analysis")
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


def estimate_java_heap_pool_peak_growth(
    measurements: list[dict[str, int]],
    value_key: str = "heap_pool_peak_increase_bytes",
) -> dict:
    """Fit a low-confidence growth class to JVM heap-pool peak-increase observations."""
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
        "method": "java_heap_pool_peak_increase_fit",
        "confidence": "low",
        "points": measurements,
        "measurement": "median sum of per-heap-pool peak usage increases in bytes",
        "limitations": (
            "Not process RSS; excludes off-heap/native memory; includes JVM and reflection overhead; "
            "pool migration can overcount; small allocations may read as zero at pool reporting granularity; "
            "submitted code can allocate concurrently; sizes are user-declared."
        ),
    }
    if len(points) < 4:
        return {**result, "state": "not_estimated", "reason": "At least four valid sizes are required."}
    if not any(point[value_key] > 0 for point in points):
        return {
            **result,
            "state": "not_estimated",
            "reason": "No positive heap-pool peak increase was observable at the measured sizes.",
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
