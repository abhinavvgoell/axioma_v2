from __future__ import annotations

import re
import json
import os
import html
import math
from functools import lru_cache
from pathlib import Path

from axioma_api.contracts import (
    ProblemCatalogMatchResponse,
    ProblemSpec,
)


# Small, locally maintained packs make the expected results inspectable and do
# not depend on scraping a third-party judge or calling an AI service.
_PACKS: list[dict] = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "topics": ["array", "hash table"],
        "entrypoint": "Solution.twoSum",
        "constraints": [
            {"path": "args[0].length", "minimum": 2, "maximum": 10000},
            {"path": "args[1]", "minimum": -1000000000, "maximum": 1000000000},
        ],
        "samples": [
            {"name": "example_pair", "args": [[2, 7, 11, 15], 9], "kwargs": {}, "expected": [0, 1]},
            {"name": "middle_pair", "args": [[3, 2, 4], 6], "kwargs": {}, "expected": [1, 2]},
            {"name": "duplicate_values", "args": [[3, 3], 6], "kwargs": {}, "expected": [0, 1]},
            {"name": "negative_values", "args": [[-3, 4, 3, 90], 0], "kwargs": {}, "expected": [0, 2]},
            {"name": "zero_pair", "args": [[0, 4, 3, 0], 0], "kwargs": {}, "expected": [0, 3]},
            {"name": "answer_at_end", "args": [[1, 5, 9, -2], 14], "kwargs": {}, "expected": [1, 2]},
        ],
        "matches": (
            r"\btwo\s*sum\b",
            r"\b1\s*[.]\s*two\s+sum\b",
            r"\breturn indices of the two numbers\b.{0,180}\badd up to (?:the )?target\b",
        ),
    },
    {
        "slug": "best-time-to-buy-and-sell-stock",
        "title": "Best Time to Buy and Sell Stock",
        "topics": ["array", "dynamic programming"],
        "entrypoint": "Solution.maxProfit",
        "constraints": [
            {"path": "args[0].length", "minimum": 1, "maximum": 100000},
            {"path": "args[0][0]", "minimum": 0, "maximum": 10000},
        ],
        "samples": [
            {"name": "example_profit", "args": [[7, 1, 5, 3, 6, 4]], "kwargs": {}, "expected": 5},
            {"name": "falling_prices", "args": [[7, 6, 4, 3, 1]], "kwargs": {}, "expected": 0},
            {"name": "buy_before_rise", "args": [[2, 4, 1]], "kwargs": {}, "expected": 2},
            {"name": "single_day", "args": [[5]], "kwargs": {}, "expected": 0},
            {"name": "small_gain", "args": [[2, 1, 2, 0, 1]], "kwargs": {}, "expected": 1},
        ],
        "matches": (r"\bbest\s+time\s+to\s+buy\s+and\s+sell\s+stock\b",),
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "topics": ["string", "stack"],
        "entrypoint": "Solution.isValid",
        "constraints": [{"path": "args[0].length", "minimum": 0, "maximum": 10000}],
        "samples": [
            {"name": "one_pair", "args": ["()"], "kwargs": {}, "expected": True},
            {"name": "mixed_pairs", "args": ["()[]{}"], "kwargs": {}, "expected": True},
            {"name": "wrong_pair", "args": ["(]"], "kwargs": {}, "expected": False},
            {"name": "nested_pairs", "args": ["([])"], "kwargs": {}, "expected": True},
            {"name": "unclosed_openers", "args": ["((("], "kwargs": {}, "expected": False},
            {"name": "empty_input", "args": [""], "kwargs": {}, "expected": True},
        ],
        "matches": (),
    },
    {
        "slug": "permutation-in-string",
        "title": "Permutation in String",
        "topics": ["string", "sliding window", "frequency counting"],
        "entrypoint": "Solution.checkInclusion",
        "constraints": [
            {"path": "args[0].length", "minimum": 1, "maximum": 10000},
            {"path": "args[1].length", "minimum": 1, "maximum": 10000},
        ],
        "samples": [
            {"name": "permutation_in_middle", "args": ["ab", "eidbaooo"], "kwargs": {}, "expected": True},
            {"name": "no_permutation", "args": ["ab", "eidboaoo"], "kwargs": {}, "expected": False},
            {"name": "single_matching_character", "args": ["a", "a"], "kwargs": {}, "expected": True},
            {"name": "permutation_at_end", "args": ["abc", "bbbca"], "kwargs": {}, "expected": True},
            {"name": "repeated_characters", "args": ["aabc", "xacaabb"], "kwargs": {}, "expected": True},
            {"name": "longer_pattern", "args": ["hello", "ooolleoooleh"], "kwargs": {}, "expected": False},
        ],
        "matches": (
            r"\bpermutation\s+in\s+string\b",
            r"\bs2 contains a permutation of s1\b",
        ),
    },
]


def _catalog_path() -> Path:
    configured = os.environ.get("AXIOMA_PROBLEM_CATALOG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "problem_catalog.json"


@lru_cache(maxsize=4)
def _read_imported_packs(path: str, modified_ns: int) -> tuple[dict, ...]:
    del modified_ns  # The timestamp is part of the cache key so imports reload after replacement.
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    packs = document.get("problems", []) if isinstance(document, dict) else []
    return tuple(pack for pack in packs if isinstance(pack, dict))


def _imported_packs() -> tuple[dict, ...]:
    path = _catalog_path()
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return ()
    return _read_imported_packs(str(path), modified_ns)


@lru_cache(maxsize=4096)
def _title_heading_pattern(title: str) -> re.Pattern[str] | None:
    words = re.findall(r"[a-z0-9]+", title.strip().casefold())
    if not words:
        return None
    title_pattern = r"[\s-]+".join(map(re.escape, words))
    return re.compile(
        r"(?im)^\s*(?:(?:leetcode|problem)\s+)?(?:\d+\s*[.)]?\s*)?"
        + title_pattern
        + r"(?=\s|$|[.:—-])"
    )


@lru_cache(maxsize=4096)
def _title_first_word(title: str) -> str:
    match = re.search(r"[a-z0-9]+", title.casefold())
    return match.group(0) if match else ""


def _matches_pack(normalized: str, first_word: str, statement: str, pack: dict) -> bool:
    patterns = pack.get("matches", [])
    if any(re.search(pattern, normalized) for pattern in patterns if isinstance(pattern, str)):
        return True
    title = str(pack.get("title", ""))
    if not first_word or _title_first_word(title) != first_word:
        return False
    # Match an exact title heading, optionally preceded by its LeetCode number.
    # Requiring the heading start avoids matching "Valid Parentheses" inside
    # the distinct title "Longest Valid Parentheses".
    heading_pattern = _title_heading_pattern(title)
    return heading_pattern is not None and heading_pattern.search(statement.strip()) is not None


_DESCRIPTION_STOP_WORDS = frozenset(
    "a an and are as at be been being by can could do does each for from had has have "
    "he her here hers him his how i if in into is it its may might more most must no not "
    "of on or our she should so some such than that the their them then there these they "
    "this those to too under up us was we were what when where which while who will with "
    "would you your return given input output example constraints follows solution write "
    "function class method integer array string true false".split()
)


def _description_tokens(value: str) -> set[str]:
    text = html.unescape(value)
    text = re.sub(r"<[^>]*>", " ", text)
    tokens = re.findall(r"[a-z][a-z0-9]+", text.casefold())
    return {token for token in tokens if token not in _DESCRIPTION_STOP_WORDS and len(token) > 1}


@lru_cache(maxsize=4)
def _description_index(
    descriptions: tuple[str, ...],
) -> tuple[dict[str, tuple[int, ...]], int]:
    tokens = tuple(frozenset(_description_tokens(description)) for description in descriptions)
    postings: dict[str, list[int]] = {}
    for index, document in enumerate(tokens):
        for token in document:
            postings.setdefault(token, []).append(index)
    return {token: tuple(indices) for token, indices in postings.items()}, sum(bool(doc) for doc in tokens)


def _match_by_description(
    statement: str, packs: tuple[dict, ...]
) -> tuple[dict | None, list[dict]]:
    query_tokens = _description_tokens(statement)
    if len(query_tokens) < 5:
        return None, []

    postings, document_count = _description_index(
        tuple(str(pack.get("description", "")) for pack in packs)
    )
    if not document_count:
        return None, []

    query_weights = {
        token: math.log((document_count + 1) / (len(postings.get(token, ())) + 1)) + 1
        for token in query_tokens
    }
    query_weight = sum(query_weights.values())
    if not query_weight:
        return None, []
    matched_weights: dict[int, float] = {}
    for token, token_weight in query_weights.items():
        for index in postings.get(token, ()):
            matched_weights[index] = matched_weights.get(index, 0.0) + token_weight
    candidates = [
        (matched_weight / query_weight, packs[index])
        for index, matched_weight in matched_weights.items()
    ]
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    if not candidates or candidates[0][0] < 0.58:
        return None, []
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.08:
        return None, [pack for _, pack in candidates[:3]]
    return candidates[0][1], []


def _problem_from_pack(statement: str, pack: dict) -> ProblemSpec:
    samples = pack.get("samples", [])
    return ProblemSpec.model_validate(
        {
            "statement": statement,
            "interface": {"kind": "function", "entrypoint": pack["entrypoint"]},
            "constraints": pack.get("constraints", []),
            "samples": [{"kind": "function", **sample} for sample in samples],
        }
    )


def match_problem_statement(statement: str) -> ProblemCatalogMatchResponse:
    normalized = re.sub(r"\s+", " ", statement).strip().casefold()
    first_line = statement.strip().splitlines()[0] if statement.strip() else ""
    heading_text = re.sub(
        r"^\s*(?:(?:leetcode|problem)\s+)?(?:\d+\s*[.)]?\s*)?",
        "",
        first_line,
        count=1,
        flags=re.IGNORECASE,
    )
    first_word_match = re.match(r"[a-z0-9]+", heading_text.strip(), flags=re.IGNORECASE)
    first_word = first_word_match.group(0).casefold() if first_word_match else ""
    imported_packs = _imported_packs()
    packs = (*_PACKS, *imported_packs)
    title_matches: dict[str, dict] = {}
    for pack in packs:
        if _matches_pack(normalized, first_word, statement, pack):
            title_matches.setdefault(str(pack.get("slug", pack.get("title", ""))), pack)
    if len(title_matches) > 1:
        return ProblemCatalogMatchResponse(
            recognized=False,
            match_state="ambiguous",
            candidate_titles=[str(pack.get("title", "Unknown problem")) for pack in title_matches.values()][:3],
        )

    pack = next(iter(title_matches.values()), None)
    ambiguous_candidates: list[dict] = []
    if pack is None:
        pack, ambiguous_candidates = _match_by_description(statement, imported_packs)
    if ambiguous_candidates:
        return ProblemCatalogMatchResponse(
            recognized=False,
            match_state="ambiguous",
            candidate_titles=[str(candidate.get("title", "Unknown problem")) for candidate in ambiguous_candidates],
        )
    if pack is None:
        return ProblemCatalogMatchResponse(recognized=False, match_state="not_found")
    problem = _problem_from_pack(statement, pack)
    return ProblemCatalogMatchResponse(
        recognized=True,
        match_state="matched",
        slug=pack["slug"],
        title=pack["title"],
        topics=pack["topics"],
        test_count=len(pack["samples"]),
        test_source=pack.get(
            "test_source",
            "Axioma curated pack; these are not LeetCode hidden judge tests.",
        ),
        problem=problem,
    )
