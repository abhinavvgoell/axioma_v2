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


def two_sum_problem(entrypoint: str = "Solution.twoSum") -> ProblemSpec:
    return ProblemSpec.model_validate(
        {
            "statement": (
                "You are given an array of integers nums and an integer target, "
                "return indices of the two numbers such that they add up to target."
            ),
            "interface": {"kind": "function", "entrypoint": entrypoint},
            "constraints": [{"path": "args[0].length", "minimum": 2, "maximum": 10000}],
            "samples": [
                {
                    "kind": "function",
                    "name": "example",
                    "args": [[2, 7, 11, 15], 9],
                    "kwargs": {},
                    "expected": [0, 1],
                },
                {
                    "kind": "function",
                    "name": "duplicate_values",
                    "args": [[3, 3], 6],
                    "kwargs": {},
                    "expected": [0, 1],
                },
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


def test_python_two_sum_pairwise_search_proposes_order_preserving_hash_map() -> None:
    source = """class Solution:
    def twoSum(self, nums, target):
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                if nums[i] + nums[j] == target:
                    return [i, j]
        return []
"""

    result = propose_optimizations("python", source, two_sum_problem())

    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.rule_id == "two_sum_pairwise_to_hash_map_v1"
    assert proposal.evidence_type == "static"
    assert "expected O(n)" in proposal.summary
    assert "seen = {}" in proposal.candidate_code
    assert "for i in range(len(nums) - 1, -1, -1):" in proposal.candidate_code

    namespace: dict[str, object] = {}
    exec(proposal.candidate_code, namespace)
    candidate = namespace["Solution"]().twoSum
    assert candidate([2, 7, 11, 15], 9) == [0, 1]
    assert candidate([3, 3], 6) == [0, 1]
    assert candidate([1, 5, 4, 4], 9) == [1, 2]
    assert candidate([1, 2, 3], 7) == []


def test_java_two_sum_pairwise_search_proposes_order_preserving_hash_map() -> None:
    source = """class Solution {
    public int[] twoSum(int[] nums, int target) {
        for (int i = 0; i < nums.length; i++) {
            for (int j = i + 1; j < nums.length; j++) {
                if (nums[i] + nums[j] == target) {
                    return new int[]{i, j};
                }
            }
        }
        return new int[0];
    }
}
"""

    result = propose_optimizations("java", source, two_sum_problem())

    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.rule_id == "two_sum_pairwise_to_hash_map_v1"
    assert proposal.evidence_type == "static"
    assert "expected O(n)" in proposal.summary
    assert "class AxiomaOptimized" in proposal.candidate_code
    assert "for (int i = nums.length - 1; i >= 0; i--)" in proposal.candidate_code
    assert "answer = new int[]{i, seen.get(complement)};" in proposal.candidate_code
    assert "return answer;" in proposal.candidate_code


def test_two_sum_rule_requires_problem_match_and_exact_nested_pattern() -> None:
    source = """def solve(nums, target):
    seen = {}
    for i, value in enumerate(nums):
        if target - value in seen:
            return [seen[target - value], i]
        seen[value] = i
    return []
"""

    assert not propose_optimizations("python", source, integer_array_problem()).proposals
    unsupported = propose_optimizations("python", source, two_sum_problem("solve"))
    assert unsupported.proposals == []
    assert "No supported nested pair-search pattern" in unsupported.message


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
