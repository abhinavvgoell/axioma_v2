from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = json.loads((ROOT / "manifest-v2.json").read_text(encoding="utf-8"))
REPOS = BASE["upstream_repositories"]

CASES = [
    {
        "id": "axioma-20261030-broad-016",
        "title": "Merge overlapping intervals",
        "language": "python",
        "repo": "TheAlgorithms/Python",
        "repo_path": "data_structures/arrays/merge_intervals.py",
        "local_path": "batch-04/sources/python/data_structures/arrays/merge_intervals.py",
        "entrypoint": "merge_intervals",
        "family": "sorting",
        "input_size": "n = number of intervals.",
        "expected_time": "O(n log n)",
        "expected_time_exact": "O(n log n)",
        "expected_auxiliary_space": "O(n)",
        "expected_auxiliary_space_exact": "O(n)",
        "time_rationale": "Sorting the copied interval list by start takes O(n log n). Validation and the one-pass merge each take O(n), so sorting dominates.",
        "space_rationale": "The sorted copy, merged output, and interval copies each require O(n) storage.",
        "assumptions": "Intervals are two-element lists of integers. Sorting uses O(n log n) comparisons, each O(1). Count returned intervals and temporary copies in space; exclude the input.",
    },
    {
        "id": "axioma-20261030-broad-017",
        "title": "Fractional knapsack by value-to-weight ratio",
        "language": "python",
        "repo": "TheAlgorithms/Python",
        "repo_path": "greedy_methods/fractional_knapsack.py",
        "local_path": "batch-04/sources/python/greedy_methods/fractional_knapsack.py",
        "entrypoint": "frac_knapsack",
        "family": "greedy",
        "input_size": "n = number of items; vl and wt have length n.",
        "expected_time": "O(n log n)",
        "expected_time_exact": "O(n log n)",
        "expected_auxiliary_space": "O(n)",
        "expected_auxiliary_space_exact": "O(n)",
        "time_rationale": "Sorting n value/weight pairs takes O(n log n). Building lists and prefix sums is O(n), bisect is O(log n), and the final slice sum is O(n); sorting dominates.",
        "space_rationale": "The sorted tuple list, copied value and weight lists, and accumulated weights each use O(n) storage.",
        "assumptions": "Analyze valid input with vl and wt equal in length n, n matching that length, positive weights, and O(1) arithmetic/comparisons. Exclude input and scalar output.",
    },
    {
        "id": "axioma-20261030-broad-018",
        "title": "DFS topological ordering",
        "language": "python",
        "repo": "TheAlgorithms/Python",
        "repo_path": "graphs/g_topological_sort.py",
        "local_path": "batch-04/sources/python/graphs/g_topological_sort.py",
        "entrypoint": "topological_sort",
        "family": "graph_traversal",
        "input_size": "V = len(graph); E = total adjacency entries; n = V + E.",
        "expected_time": "O(n)",
        "expected_time_exact": "O(V + E)",
        "expected_auxiliary_space": "O(n)",
        "expected_auxiliary_space_exact": "O(V)",
        "time_rationale": "With a zeroed visited list, the driver starts DFS once per unvisited vertex. Each vertex is marked before descent and each adjacency entry is checked once, so work is O(V+E).",
        "space_rationale": "Recursion depth is at most V and each vertex is appended once to the output stack, giving O(V) space.",
        "assumptions": "Analyze one call on a DAG with dense vertex IDs 0..V-1, valid adjacency endpoints, a zero-initialized visited list of length V, and an empty global stack. The recursive implementation may hit Python recursion limits on deep graphs. Scoring class uses n=V+E.",
    },
    {
        "id": "axioma-20261030-broad-019",
        "title": "Sentinel linear search",
        "language": "java",
        "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/searches/SentinelLinearSearch.java",
        "local_path": "batch-04/sources/java/searches/SentinelLinearSearch.java",
        "entrypoint": "SentinelLinearSearch.find",
        "family": "searching",
        "input_size": "n = array.length.",
        "expected_time": "O(n)",
        "expected_time_exact": "O(n) worst case",
        "expected_auxiliary_space": "O(1)",
        "expected_auxiliary_space_exact": "O(1)",
        "time_rationale": "The sentinel loop can inspect n entries when the key is absent; the null-key helper also scans n entries. Setup and restoration are constant-time.",
        "space_rationale": "The methods store only the prior last value and a loop index.",
        "assumptions": "Analyze one find call with O(1) comparisons. The method temporarily replaces the last array element and restores it. The imported SearchAlgorithm type only declares the method contract.",
    },
    {
        "id": "axioma-20261030-broad-020",
        "title": "Counting sort with value-range histogram",
        "language": "java",
        "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/sorts/CountingSort.java",
        "local_path": "batch-04/sources/java/sorts/CountingSort.java",
        "entrypoint": "CountingSort.sort",
        "family": "sorting",
        "input_size": "n = array length; k = max(array)-min(array)+1.",
        "expected_time": "O(n)",
        "expected_time_exact": "O(n + k)",
        "expected_auxiliary_space": "O(n)",
        "expected_auxiliary_space_exact": "O(n + k)",
        "time_rationale": "The method scans n values for min/max, builds a k-cell histogram, accumulates k counts, and reconstructs n outputs: O(n+k). The coarse O(n) score requires k=O(n).",
        "space_rationale": "The count array has k entries and the result has n entries, so space is O(n+k); coarse O(n) requires k=O(n).",
        "assumptions": "Input is an int array; k is positive and fits array-size limits. For coarse scoring assume value spread k=O(n); exact time and auxiliary space are O(n+k). Treat fixed-width integer operations and array access as O(1).",
    },
]


def main() -> None:
    seen_hashes: set[str] = set()
    for name in (
        "candidate-cases-batch-01-v2.jsonl",
        "candidate-cases-batch-02-v1.jsonl",
        "candidate-cases-batch-03-v1.jsonl",
    ):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen_hashes.add(json.loads(line)["source_sha256"])

    for case in CASES:
        upstream = REPOS[case["repo"]]
        case["commit"] = upstream["commit"]
        case["source_url"] = (
            f"https://github.com/{case['repo']}/blob/{case['commit']}/{case['repo_path']}"
        )
        case["source_provenance"] = "Exact source file from pinned upstream repository commit."
        case["partition"] = "calibration"
        case["decision_status"] = "proposed_pending_owner_confirmation"
        case["label_status"] = case["decision_status"]
        case["owner_decision"] = case["reviewer"] = case["review_date"] = None
        source_path = (ROOT / case["local_path"]).resolve()
        if ROOT not in source_path.parents or not source_path.is_file():
            raise ValueError(f"missing source snapshot: {case['id']}")
        case["source"] = source_path.read_bytes().decode("utf-8")
        case["source_sha256"] = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if case["source_sha256"] in seen_hashes:
            raise ValueError(f"duplicate source hash: {case['id']}")
        seen_hashes.add(case["source_sha256"])

    packet_path = ROOT / "candidate-cases-batch-04-v1.jsonl"
    packet_path.write_text(
        "".join(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for case in CASES),
        encoding="utf-8",
        newline="",
    )
    packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    ids = [case["id"] for case in CASES]
    manifest = {
        "dataset_id": "axioma-20261030-external-broad-calibration-v2",
        "status": "candidate_review_in_progress",
        "target_case_count": 30,
        "target_range": [30, 50],
        "current_batch": "04",
        "batch_size": 5,
        "case_count_current_batch": len(CASES),
        "case_ids": ids,
        "languages": {"python": 3, "java": 2},
        "families": ["sorting", "greedy", "graph_traversal", "searching"],
        "candidate_file": packet_path.name,
        "candidate_file_sha256": packet_hash,
        "source_sha256": {case["id"]: case["source_sha256"] for case in CASES},
        "upstream_repositories": REPOS,
        "previously_used_sets_excluded": BASE["previously_used_sets_excluded"],
        "reviewed_by": None,
        "review_date": None,
        "gold_labels_frozen": False,
        "analyzer_run": False,
        "independence_note": "Calibration batch from pinned upstream repositories; not a repository-held-out final evaluation.",
        "supersedes": None,
        "revision_note": "Five proposed cases with pinned source snapshots and explicit assumptions for multi-parameter coarse labels. Owner review pending; Axioma not run.",
        "partition": "calibration",
    }
    (ROOT / "manifest-batch-04-v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Complexity calibration — batch 04 (proposed)",
        "",
        "**Status:** Five labels are proposed and pending owner confirmation. Axioma has not been run. Full source code is included; review cases 016–020 after the preceding batches.",
        "",
        f"Packet SHA-256: `{packet_hash}`",
        "",
    ]
    for case in CASES:
        lines.extend(
            [
                f"## {case['id']} — {case['title']}",
                "",
                f"- **Source:** [{case['repo_path']}]({case['source_url']}) (commit `{case['commit']}`)",
                f"- **SHA-256:** `{case['source_sha256']}`",
                f"- **Proposed time:** `{case['expected_time_exact']}` (coarse `{case['expected_time']}`)",
                f"- **Proposed auxiliary space:** `{case['expected_auxiliary_space_exact']}` (coarse `{case['expected_auxiliary_space']}`)",
                f"- **Entrypoint:** `{case['entrypoint']}`",
                f"- **Input size:** {case['input_size']}",
                f"- **Assumptions:** {case['assumptions']}",
                f"- **Time rationale:** {case['time_rationale']}",
                f"- **Space rationale:** {case['space_rationale']}",
                "",
                f"```{'java' if case['language'] == 'java' else 'python'}",
                case["source"].rstrip("\r\n"),
                "```",
                "",
            ]
        )
    (ROOT / "review-batch-04-v1.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "summary-batch-04-v1.md").write_text(
        "# Batch 04 review summary\n\n"
        "- Proposed cases: 5 (016–020); all owner decisions pending.\n"
        "- Batch 01: 5 owner-confirmed, partial freeze only. Batches 02–04: 15 proposals pending.\n"
        "- Prepared candidates: 20/30; owner-confirmed labels: 5/30.\n"
        "- Full calibration labels frozen: no. Axioma run against these candidates: no.\n\n"
        "Review remains in packets of five, beginning with batch 02.\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate_sha256": packet_hash, "source_sha256": manifest["source_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
