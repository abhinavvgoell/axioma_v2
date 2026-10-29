from axioma_api.problem_constraints import (
    constraints_match_samples,
    parse_problem_constraints,
)


def test_parses_named_argument_ranges_and_powers_of_ten() -> None:
    constraints = parse_problem_constraints(
        "Problem text\nConstraints:\n"
        "- 2 <= nums.length <= 10^4\n"
        "- -10^9 <= target <= 10^9\n"
        "- -10^9 <= nums[i] <= 10^9\n",
        ["nums", "target"],
    )

    assert [item.model_dump() for item in constraints] == [
        {
            "path": "args[0].length",
            "minimum": 2,
            "maximum": 10_000,
            "description": "2 <= nums.length <= 10^4",
        },
        {
            "path": "args[1]",
            "minimum": -1_000_000_000,
            "maximum": 1_000_000_000,
            "description": "-10^9 <= target <= 10^9",
        },
    ]


def test_only_parses_ranges_after_constraints_heading_and_known_arguments() -> None:
    constraints = parse_problem_constraints(
        "1 <= count <= 10\nConstraints:\n"
        "1 <= text.length <= 500\n"
        "1 <= missing.length <= 100\n",
        ["text"],
    )

    assert len(constraints) == 1
    assert constraints[0].path == "args[0].length"
    assert constraints[0].maximum == 500


def test_skips_ambiguous_or_unsupported_constraint_ranges() -> None:
    statement = (
        "Constraints:\n"
        "- 0 <= nums[i] <= 10^5\n"
        "- -2^31 <= value <= 2^31 - 1\n"
        "- 1 <= nums.length <= 99999999999999999999\n"
    )

    assert parse_problem_constraints(statement, ["nums", "nums"]) == []
    assert parse_problem_constraints(statement, ["nums", "value"]) == []


def test_drops_extracted_ranges_that_conflict_with_imported_examples() -> None:
    constraints = parse_problem_constraints(
        "Constraints:\n- 1 <= text.length <= 10^4\n- 1 <= target <= 100\n",
        ["text", "target"],
    )

    kept = constraints_match_samples(
        constraints,
        [
            {"args": ["hello", 5]},
            {"args": ["a", 101]},
        ],
    )

    assert [item.path for item in kept] == ["args[0].length"]
