from __future__ import annotations

import re

from axioma_worker.python_complexity import ComplexityEstimate
from axioma_worker.python_complexity import add_line_event_fit, fit_growth_model

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
            return tokens[body_open + 1 : body_close]
    return None


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


def _is_adjacency_list_bfs(tokens: list[str], spans: list[tuple[int, int]]) -> bool:
    """Recognize queue-based BFS over adjacency lists with a visited-set guard."""
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
            for_header = tokens[inner_open + 1 : inner_close]
            if ":" not in for_header:
                continue
            colon = for_header.index(":")
            if colon < 1:
                continue
            neighbor = for_header[colon - 1]
            adjacency = for_header[colon + 1 :]
            if not any(
                adjacency[index : index + 4] == [".", "get", "(", current_node]
                for index in range(len(adjacency) - 3)
            ):
                continue

            for guard_start in range(inner_start + 1, inner_end):
                if tokens[guard_start] != "if":
                    continue
                guard_header = _loop_header(tokens, guard_start)
                if guard_header is None:
                    continue
                guard_open, guard_close = guard_header
                guard_body = guard_close + 1
                if guard_body >= inner_end or tokens[guard_body] != "{":
                    continue
                guard_end = _matching(tokens, guard_body, "{", "}")
                if guard_end is None or guard_end > inner_end:
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
                visited_array_name = next(
                    (
                        guard[index - 2]
                        for index in range(3, len(guard) - 1)
                        if guard[index - 3] == "!"
                        and guard[index - 1] == "["
                        and guard[index] == neighbor
                        and guard[index + 1] == "]"
                    ),
                    None,
                )
                array_guard_marks_visited = (
                    visited_array_name is not None
                    and any(
                        body[index : index + 6]
                        == [visited_array_name, "[", neighbor, "]", "=", "true"]
                        for index in range(len(body) - 5)
                    )
                )
                if (
                    (visited_name is not None or array_guard_marks_visited)
                    and _has_method_call(body, queue_name, {"add", "offer", "addLast"}, neighbor)
                ):
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
    class_range = _class_body(tokens, parts[0])
    if class_range is None:
        return ComplexityEstimate(
            method,
            "unknown (class not found)",
            "low",
            False,
            f"Could not locate class {parts[0]} in the source.",
        )
    body = _method_body(tokens, class_range, parts[1])
    if body is None:
        return ComplexityEstimate(
            method,
            "unknown (method not found)",
            "low",
            False,
            f"Could not locate method {parts[1]} in class {parts[0]}.",
        )

    spans, incomplete_loop = _loop_spans(body)
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
        token in {"sort", "parallelSort"} and index + 1 < len(body) and body[index + 1] == "("
        for index, token in enumerate(body)
    )
    has_while = any(token == "while" for token in body)
    binary_search = _is_binary_search_loop(body, spans)
    insertion_sort_shift = _is_insertion_sort_shift(body, spans)
    tree_recursion = not spans and recursive and _is_tree_recursive_walk(body, parts[1])
    graph_bfs = not recursive and _is_adjacency_list_bfs(body, spans)
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
        if token in {"sort", "parallelSort"} and body[index + 1] == "(":
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
    if insertion_sort_shift:
        signals.append({
            "kind": "insertion_sort_shift",
            "label": "Nested shifting loop moves an indexed element left one position at a time",
            "line": None,
        })

    amortized_forward_scan = _amortized_forward_scan(body, spans)
    if graph_bfs or graph_dfs:
        estimate = "O(V + E)"
        method = "static_java_graph_dfs" if graph_dfs else "static_java_graph_bfs"
        traversal = "recursive traversal" if graph_dfs else "queue-based traversal"
        work_unit = "visited once" if graph_dfs else "enqueued once"
        explanation = (
            f"Recognized {traversal} over adjacency lists with a visited-state guard. Assuming "
            f"each vertex is {work_unit} and each adjacency entry is scanned once, the work is "
            "O(V + E). Visited checks must be constant-time; the syntax match is a heuristic."
        )
    elif tree_recursion:
        method = "static_java_tree_recursion"
        estimate = "O(n)"
        explanation = (
            "Recognized direct recursion over a tree node's left/right child link. Assuming the "
            "input is a tree with no cycles or shared subtrees, each visited node is processed "
            "once, for O(n) work. The syntax check cannot establish that input structure."
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
                "scope": "selected method; called helpers are not expanded",
                "signals": signals,
                "loop_count": len(spans),
                "maximum_loop_nesting": maximum_depth,
                "limitations": [
                    "Tokenizer-based signals are approximate and do not retain source line numbers.",
                    "Collection operation costs depend on the concrete type and implementation.",
                    "Recurrence relations and called helper functions are not analyzed.",
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
