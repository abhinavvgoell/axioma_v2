import ast

from axioma_worker.mutation_testing import generate_mutants


def test_generates_deterministic_operator_mutants_with_valid_python() -> None:
    source = "def solve(value):\n    return value + 1\n"

    first = generate_mutants(source, limit=4)
    second = generate_mutants(source, limit=4)

    assert first == second
    assert first
    assert all(mutant.id.startswith("mutant_") for mutant in first)
    assert all("value - 1" in mutant.code for mutant in first[:1])
    for mutant in first:
        ast.parse(mutant.code)


def test_caps_mutant_count_and_returns_none_for_unparseable_source() -> None:
    assert len(generate_mutants("def solve(x): return (x + 1) * 2", limit=2)) == 2
    assert generate_mutants("def solve(:", limit=5) == []
