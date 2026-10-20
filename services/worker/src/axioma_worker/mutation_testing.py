from __future__ import annotations

import ast
import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class MutationSource:
    id: str
    label: str
    code: str


_BINARY_REPLACEMENTS: dict[type[ast.operator], tuple[type[ast.operator], ...]] = {
    ast.Add: (ast.Sub,),
    ast.Sub: (ast.Add,),
    ast.Mult: (ast.Add, ast.FloorDiv),
    ast.FloorDiv: (ast.Mult, ast.Mod),
    ast.Mod: (ast.FloorDiv,),
}
_COMPARISON_REPLACEMENTS: dict[type[ast.cmpop], tuple[type[ast.cmpop], ...]] = {
    ast.Eq: (ast.NotEq,),
    ast.NotEq: (ast.Eq,),
    ast.Lt: (ast.LtE, ast.Gt),
    ast.LtE: (ast.Lt,),
    ast.Gt: (ast.GtE, ast.Lt),
    ast.GtE: (ast.Gt,),
}


def generate_mutants(source: str, limit: int = 20) -> list[MutationSource]:
    """Create deterministic, single-operator Python mutants from simple AST rewrites."""
    if limit <= 0:
        return []
    try:
        original = ast.parse(source)
    except SyntaxError:
        return []

    mutants: list[MutationSource] = []
    nodes = list(ast.walk(original))
    for node_index, node in enumerate(nodes):
        replacements: list[tuple[str, ast.AST]] = []
        if isinstance(node, ast.BinOp):
            for replacement in _BINARY_REPLACEMENTS.get(type(node.op), ()):
                replacements.append((type(replacement).__name__, replacement()))
        elif isinstance(node, ast.Compare):
            for operator_index, operator in enumerate(node.ops):
                for replacement in _COMPARISON_REPLACEMENTS.get(type(operator), ()):
                    replacements.append(
                        (
                            type(replacement).__name__,
                            (operator_index, replacement()),
                        )
                    )
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            replacements.append(("UAdd", ast.UAdd()))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            replacements.append(("USub", ast.USub()))

        for replacement_name, replacement in replacements:
            mutant_tree = copy.deepcopy(original)
            target = list(ast.walk(mutant_tree))[node_index]
            if isinstance(target, ast.BinOp):
                target.op = replacement
            elif isinstance(target, ast.Compare):
                operator_index, operator = replacement
                target.ops[operator_index] = operator
            elif isinstance(target, ast.UnaryOp):
                target.op = replacement
            ast.fix_missing_locations(mutant_tree)
            line = getattr(node, "lineno", 0)
            label = f"{type(node).__name__}_{replacement_name}_line_{line}"
            mutant_id = f"mutant_{len(mutants) + 1}"
            mutants.append(MutationSource(id=mutant_id, label=label, code=ast.unparse(mutant_tree)))
            if len(mutants) >= limit:
                return mutants
    return mutants
