from axioma_api.problem_catalog import match_problem_statement
from axioma_api.catalog_selection import select_catalog_packs


def test_catalog_selection_covers_topics_and_difficulty_before_extra_examples() -> None:
    packs = [
        {"slug": "array-1", "question_id": 1, "difficulty": "Medium", "topics": ["Array"]},
        {"slug": "array-2", "question_id": 2, "difficulty": "Medium", "topics": ["Array"]},
        {"slug": "graph-hard", "question_id": 3, "difficulty": "Hard", "topics": ["Graph"]},
        {
            "slug": "dynamic-easy",
            "question_id": 4,
            "difficulty": "Easy",
            "topics": ["Dynamic Programming"],
        },
    ]

    selected = select_catalog_packs(packs, 3)

    assert {pack["slug"] for pack in selected} == {"array-1", "graph-hard", "dynamic-easy"}


def test_catalog_recognizes_standard_two_sum_statement_without_title() -> None:
    match = match_problem_statement(
        "Given an array of integers nums and an integer target, return indices of the two "
        "numbers such that they add up to target."
    )

    assert match.recognized is True
    assert match.slug == "two-sum"
    assert match.problem is not None
    assert match.test_count >= 3


def test_catalog_recognizes_standard_permutation_statement_without_title() -> None:
    match = match_problem_statement(
        "Given two strings s1 and s2, return true if s2 contains a permutation of s1, "
        "or false otherwise."
    )

    assert match.recognized is True
    assert match.slug == "permutation-in-string"
    assert match.problem is not None
    assert match.test_count >= 3


def test_catalog_does_not_match_a_shorter_title_inside_a_longer_title(monkeypatch) -> None:
    from axioma_api import problem_catalog

    monkeypatch.setattr(
        problem_catalog,
        "_imported_packs",
        lambda: (
            {
                "slug": "longest-valid-parentheses",
                "title": "Longest Valid Parentheses",
                "topics": ["string", "dynamic programming"],
                "entrypoint": "Solution.longestValidParentheses",
                "constraints": [],
                "samples": [
                    {"name": "example", "args": [")()())"], "kwargs": {}, "expected": 4}
                ],
            },
        ),
    )

    match = match_problem_statement("32. Longest Valid Parentheses")

    assert match.recognized is True
    assert match.slug == "longest-valid-parentheses"


def test_catalog_matches_a_titleless_description_from_imported_packs(monkeypatch) -> None:
    from axioma_api import problem_catalog

    monkeypatch.setattr(
        problem_catalog,
        "_imported_packs",
        lambda: (
            {
                "slug": "minimum-size-subarray-sum",
                "title": "Minimum Size Subarray Sum",
                "description": (
                    "Given an array of positive integers nums and a positive integer target, "
                    "return the minimal length of a subarray whose sum is greater than or "
                    "equal to target. If there is no such subarray, return 0 instead."
                ),
                "topics": ["array", "binary search", "sliding window"],
                "entrypoint": "Solution.minSubArrayLen",
                "constraints": [],
                "samples": [
                    {"name": "example", "args": [7, [2, 3, 1, 2, 4, 3]], "kwargs": {}, "expected": 2}
                ],
            },
            {
                "slug": "valid-parentheses",
                "title": "Valid Parentheses",
                "description": (
                    "Given a string s containing just the characters parentheses and brackets, "
                    "determine if the input string is valid. Open brackets must be closed by "
                    "the same type of brackets and in the correct order."
                ),
                "topics": ["string", "stack"],
                "entrypoint": "Solution.isValid",
                "constraints": [],
                "samples": [],
            },
        ),
    )

    match = match_problem_statement(
        "Given an array of positive integers nums and a positive integer target, return the "
        "minimal length of a subarray whose sum is greater than or equal to target. If there "
        "is no such subarray, return 0 instead."
    )

    assert match.recognized is True
    assert match.slug == "minimum-size-subarray-sum"
    assert match.test_count == 1


def test_catalog_does_not_guess_for_vague_statement(monkeypatch) -> None:
    from axioma_api import problem_catalog

    monkeypatch.setattr(
        problem_catalog,
        "_imported_packs",
        lambda: (
            {
                "slug": "maximum-result",
                "title": "Maximum Result",
                "description": "Given an array of integers, return the maximum result.",
                "topics": [],
                "entrypoint": "Solution.solve",
                "constraints": [],
                "samples": [],
            },
        ),
    )

    match = match_problem_statement("Given an array of integers, return the maximum result.")

    assert match.recognized is False
