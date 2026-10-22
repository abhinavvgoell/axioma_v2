from __future__ import annotations

from collections import defaultdict
from typing import Any


_TOPIC_ORDER = (
    "Array",
    "String",
    "Hash Table",
    "Two Pointers",
    "Sliding Window",
    "Stack",
    "Queue",
    "Binary Search",
    "Tree",
    "Depth-First Search",
    "Breadth-First Search",
    "Graph",
    "Dynamic Programming",
    "Backtracking",
    "Heap (Priority Queue)",
    "Trie",
    "Union Find",
    "Greedy",
    "Prefix Sum",
)
_DIFFICULTY_ORDER = ("Easy", "Medium", "Hard")


def _pack_order(pack: dict[str, Any]) -> tuple[int, str]:
    question_id = pack.get("question_id")
    return (
        question_id if isinstance(question_id, int) else 10**9,
        str(pack.get("slug", "")),
    )


def select_catalog_packs(packs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Select a reproducible topic/difficulty mix, then fill remaining slots by ID."""
    ordered = sorted(packs, key=_pack_order)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for pack in ordered:
        difficulty = pack.get("difficulty")
        if difficulty not in _DIFFICULTY_ORDER:
            continue
        topics = {str(topic).casefold() for topic in pack.get("topics", [])}
        for topic in _TOPIC_ORDER:
            if topic.casefold() in topics:
                buckets[(topic, difficulty)].append(pack)

    cursors: dict[tuple[str, str], int] = defaultdict(int)
    selected: dict[str, dict[str, Any]] = {}
    while len(selected) < limit:
        added = False
        for topic in _TOPIC_ORDER:
            for difficulty in _DIFFICULTY_ORDER:
                key = (topic, difficulty)
                bucket = buckets[key]
                while cursors[key] < len(bucket):
                    pack = bucket[cursors[key]]
                    cursors[key] += 1
                    slug = str(pack["slug"])
                    if slug in selected:
                        continue
                    selected[slug] = pack
                    added = True
                    break
                if len(selected) == limit:
                    break
            if len(selected) == limit:
                break
        if not added:
            break

    if len(selected) < limit:
        for pack in ordered:
            selected.setdefault(str(pack["slug"]), pack)
            if len(selected) == limit:
                break
    return sorted(selected.values(), key=_pack_order)
