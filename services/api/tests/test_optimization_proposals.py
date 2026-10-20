from axioma_api.contracts import FunctionSample, ProblemSpec
from axioma_api.optimization_proposals import propose_optimizations


def integer_array_problem(entrypoint: str = "solve") -> ProblemSpec:
    return ProblemSpec.model_validate(
        {
            "statement": "Given an integer array, return its sum.",
            "interface": {"kind": "function", "entrypoint": entrypoint},
            "constraints": [{"path": "args[0].length", "minimum": 1, "maximum": 100}],
            "samples": [
                {
                    "kind": "function",
                    "name": "example",
                    "args": [[1, 2, 3]],
                    "kwargs": {},
                    "expected": 6,
                }
            ],
        }
    )


def test_python_accumulation_loop_returns_a_static_candidate() -> None:
    source = "def solve(values):\n    total = 0\n    for value in values:\n        total += value\n    return total\n"

    result = propose_optimizations("python", source, integer_array_problem())

    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.evidence_type == "static"
    assert proposal.confidence == "low"
    assert "return sum(values)" in proposal.candidate_code
    assert proposal.candidate_code != source
    assert any("does not establish equivalent behavior" in item for item in proposal.limitations)


def test_java_accumulation_loop_returns_a_static_candidate() -> None:
    source = """class Solution {
    public int solve(int[] values) {
        int total = 0;
        for (int value : values) {
            total += value;
        }
        return total;
    }
}
"""

    result = propose_optimizations("java", source, integer_array_problem("Solution.solve"))

    assert len(result.proposals) == 1
    assert "java.util.Arrays.stream(values).sum()" in result.proposals[0].candidate_code
    assert result.proposals[0].evidence_type == "static"


def test_unrecognized_or_non_integer_patterns_do_not_get_a_candidate() -> None:
    problem = integer_array_problem()
    source = "def solve(values):\n    return sum(values)\n"

    assert not propose_optimizations("python", source, problem).proposals

    problem.samples[0] = FunctionSample(
        name="string-data", args=[["a", "b"]], kwargs={}, expected="ab"
    )
    result = propose_optimizations("python", source, problem)
    assert result.proposals == []
    assert "integer-array" in result.message
