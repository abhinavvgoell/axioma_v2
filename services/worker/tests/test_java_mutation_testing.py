from axioma_worker.java_mutation_testing import generate_java_mutants


def test_generates_single_operator_mutants_in_the_selected_reference_method() -> None:
    source = '''class Reference {
    public int solve(int value) {
        // This plus is a comment and should not be mutated: +
        String marker = "+";
        return value + 1;
    }
    public int helper(int value) { return value * 3; }
}
'''

    mutants = generate_java_mutants(source, "solve", limit=3)

    assert len(mutants) == 1
    mutant = mutants[0]
    assert mutant.id == "mutant_1"
    assert mutant.class_name == "AxiomaMutant1"
    assert "class AxiomaMutant1" in mutant.code
    assert "return value - 1;" in mutant.code
    assert 'String marker = "+";' in mutant.code
    assert "This plus is a comment and should not be mutated: +" in mutant.code
    assert "helper(int value) { return value * 3; }" in mutant.code


def test_does_not_mutate_operator_tokens_outside_the_target_method() -> None:
    source = '''class Reference {
    public int solve(int value) {
        return value + 1;
    }
    public int helper(int value) {
        return value * 3;
    }
}
'''

    mutants = generate_java_mutants(source, "solve")

    assert len(mutants) == 1
    assert "return value - 1;" in mutants[0].code
    assert "return value * 3;" in mutants[0].code


def test_returns_no_mutants_for_missing_or_ambiguous_reference_methods() -> None:
    source = "class Reference { int solve(int value) { return value + 1; } }"
    overloaded = "class Reference { int solve(int a) { return a + 1; } int solve(long a) { return (int)a + 2; } }"

    assert generate_java_mutants(source, "missing") == []
    assert generate_java_mutants(overloaded, "solve") == []
    assert generate_java_mutants(source.replace("Reference", "Other"), "solve") == []
