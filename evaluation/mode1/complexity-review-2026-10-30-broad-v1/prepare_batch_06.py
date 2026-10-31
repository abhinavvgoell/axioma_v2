from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = json.loads((ROOT / "manifest-v2.json").read_text(encoding="utf-8"))
REPOS = BASE["upstream_repositories"]
CASES = [
    {
        "id": "axioma-20261030-broad-026", "title": "Linear two-pointer palindrome check", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "strings/palindrome.py", "local_path": "batch-06/sources/python/strings/palindrome.py", "entrypoint": "is_palindrome", "family": "string_processing",
        "input_size": "n = len(s).", "expected_time": "O(n)", "expected_time_exact": "O(n)", "expected_auxiliary_space": "O(1)", "expected_auxiliary_space_exact": "O(1)",
        "time_rationale": "The two indices move inward, comparing at most floor(n/2) character pairs. In the worst case all pairs are examined, so time is O(n).",
        "space_rationale": "Only two integer indices are stored; no substring or reversed copy is created.",
        "assumptions": "Analyze is_palindrome only, not the other functions or module-level benchmark. String indexing and character equality are O(1); input is excluded.",
    },
    {
        "id": "axioma-20261030-broad-027", "title": "Randomized quick sort with list partitions", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "sorts/quick_sort.py", "local_path": "batch-06/sources/python/sorts/quick_sort.py", "entrypoint": "quick_sort", "family": "sorting",
        "input_size": "n = len(collection).", "expected_time": "O(n^2)", "expected_time_exact": "O(n^2) worst case; expected O(n log n) with uniformly random pivot ranks and distinct values",
        "expected_auxiliary_space": "O(n^2)", "expected_auxiliary_space_exact": "O(n^2) worst case; expected O(n) for uniformly random pivot ranks",
        "time_rationale": "Every call builds lesser/equal/greater lists in O(k) for its subproblem size k. Repeated maximally unbalanced pivots yield n+(n-1)+...=O(n²) work; random pivots give expected O(n log n) comparisons for distinct values.",
        "space_rationale": "The recursive frames retain partition lists. With maximally unbalanced partitions, live lists across the call chain sum to n+(n-1)+...=O(n²); balanced random partitions use expected O(n) peak list storage.",
        "assumptions": "Use worst-case labels for scoring. Each pivot selection and comparison is O(1); the random pivot can repeatedly produce a one-sided partition. The expected-case note assumes uniformly random pivot ranks and distinct values. Count partition lists and returned lists as auxiliary storage; exclude the original input.",
    },
    {
        "id": "axioma-20261030-broad-028", "title": "Lazy-priority-queue Dijkstra on an adjacency matrix", "language": "java", "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/datastructures/graphs/DijkstraAlgorithm.java", "local_path": "batch-06/sources/java/datastructures/graphs/DijkstraAlgorithm.java", "entrypoint": "DijkstraAlgorithm.run", "family": "graph_traversal",
        "input_size": "V = vertexCount; E = nonzero matrix entries; n = V + E.", "expected_time": "O(n log n)", "expected_time_exact": "O(V^2 + E log(E + 1))",
        "expected_auxiliary_space": "O(n)", "expected_auxiliary_space_exact": "O(V + E)",
        "time_rationale": "Each processed vertex scans an entire matrix row, for O(V²) scans. Every successful relaxation may enqueue another Node, so up to O(E) heap entries can be inserted and removed at O(log(E+1)) each. Printing distances adds O(V).",
        "space_rationale": "Distances and processed flags use O(V); lazy duplicate queue entries can occupy O(E). The input adjacency matrix is excluded.",
        "assumptions": "Analyze a valid V×V adjacency matrix with nonnegative edge weights, 0 meaning no edge, valid source, and primitive comparisons/heap node comparisons O(1). Score with n=V+E; exact time is O(V²+E log(E+1)). Include the method's O(V) output printing in time.",
    },
    {
        "id": "axioma-20261030-broad-029", "title": "Minimum coin count by bottom-up dynamic programming", "language": "java", "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/dynamicprogramming/CoinChange.java", "local_path": "batch-06/sources/java/dynamicprogramming/CoinChange.java", "entrypoint": "CoinChange.minimumCoins", "family": "dynamic_programming",
        "input_size": "A = amount; C = number of coin denominations; n = max(A,C).", "expected_time": "O(n^2)", "expected_time_exact": "O(A * C)",
        "expected_auxiliary_space": "O(n)", "expected_auxiliary_space_exact": "O(A)",
        "time_rationale": "The method initializes A+1 entries, then for each of A positive amounts scans all C coin denominations. Time is O(A*C + A); for A,C≤n this is O(n²).",
        "space_rationale": "The single minimumCoins array has A+1 integer entries, so auxiliary space is O(A), bounded by O(n).",
        "assumptions": "Analyze minimumCoins, not change. Amount A≥1 and denominations are positive; C≥1. Use n=max(A,C) for coarse scoring and treat fixed-width integer operations as O(1). Exclude input and scalar output.",
    },
    {
        "id": "axioma-20261030-broad-030", "title": "Linear search", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "searches/linear_search.py", "local_path": "batch-06/sources/python/searches/linear_search.py", "entrypoint": "linear_search", "family": "searching",
        "input_size": "n = len(sequence).", "expected_time": "O(n)", "expected_time_exact": "O(n) worst case",
        "expected_auxiliary_space": "O(1)", "expected_auxiliary_space_exact": "O(1)",
        "time_rationale": "The loop compares items in order and may inspect every element when the target is absent or last. Each iteration does constant work.",
        "space_rationale": "The loop stores only the current index and item reference.",
        "assumptions": "Analyze the iterative linear_search entrypoint only, not the recursive helper or command-line code. Element equality is O(1); input sequence is excluded.",
    },
]


def main() -> None:
    used: set[str] = set()
    for name in (
        "candidate-cases-batch-01-v2.jsonl", "candidate-cases-batch-02-v1.jsonl", "candidate-cases-batch-03-v1.jsonl",
        "candidate-cases-batch-04-v1.jsonl", "candidate-cases-batch-05-v1.jsonl",
    ):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                used.add(json.loads(line)["source_sha256"])
    for case in CASES:
        repo = REPOS[case["repo"]]
        case["commit"] = repo["commit"]
        case["source_url"] = f"https://github.com/{case['repo']}/blob/{repo['commit']}/{case['repo_path']}"
        case["source_provenance"] = "Exact source file from pinned upstream repository commit."
        case["partition"] = "calibration"
        case["decision_status"] = case["label_status"] = "proposed_pending_owner_confirmation"
        case["owner_decision"] = case["reviewer"] = case["review_date"] = None
        path = (ROOT / case["local_path"]).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError(f"missing snapshot for {case['id']}")
        case["source"] = path.read_bytes().decode("utf-8")
        case["source_sha256"] = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if case["source_sha256"] in used:
            raise ValueError(f"duplicate source hash for {case['id']}")
        used.add(case["source_sha256"])

    packet_path = ROOT / "candidate-cases-batch-06-v1.jsonl"
    packet_path.write_text("".join(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for case in CASES), encoding="utf-8", newline="")
    packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    ids = [case["id"] for case in CASES]
    manifest = {
        "dataset_id": "axioma-20261030-external-broad-calibration-v2", "status": "candidate_review_in_progress", "target_case_count": 30,
        "target_range": [30, 50], "current_batch": "06", "batch_size": 5, "case_count_current_batch": 5, "case_ids": ids,
        "languages": {"python": 3, "java": 2}, "families": ["string_processing", "sorting", "graph_traversal", "dynamic_programming", "searching"],
        "candidate_file": packet_path.name, "candidate_file_sha256": packet_hash, "source_sha256": {case["id"]: case["source_sha256"] for case in CASES},
        "upstream_repositories": REPOS, "previously_used_sets_excluded": BASE["previously_used_sets_excluded"], "reviewed_by": None, "review_date": None,
        "gold_labels_frozen": False, "analyzer_run": False, "independence_note": "Calibration only; pinned upstream sources; not a repository-held-out final evaluation.",
        "supersedes": None, "revision_note": "Five proposed cases with pinned source snapshots; labels pending owner review; Axioma not run.", "partition": "calibration",
    }
    (ROOT / "manifest-batch-06-v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = ["# Complexity calibration — batch 06 (proposed)", "", "**Status:** Five labels proposed and pending owner confirmation. Axioma has not been run. Complete pinned source code, assumptions, rationales, and hashes are included.", "", f"Packet SHA-256: `{packet_hash}`", ""]
    for case in CASES:
        lines.extend([f"## {case['id']} — {case['title']}", "", f"- **Source:** [{case['repo_path']}]({case['source_url']}) (commit `{case['commit']}`)", f"- **SHA-256:** `{case['source_sha256']}`", f"- **Proposed time:** `{case['expected_time_exact']}` (coarse `{case['expected_time']}`)", f"- **Proposed auxiliary space:** `{case['expected_auxiliary_space_exact']}` (coarse `{case['expected_auxiliary_space']}`)", f"- **Entrypoint:** `{case['entrypoint']}`", f"- **Input size:** {case['input_size']}", f"- **Assumptions:** {case['assumptions']}", f"- **Time rationale:** {case['time_rationale']}", f"- **Space rationale:** {case['space_rationale']}", "", f"```{'java' if case['language'] == 'java' else 'python'}", case["source"].rstrip("\r\n"), "```", ""])
    (ROOT / "review-batch-06-v1.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "summary-batch-06-v1.md").write_text("# Batch 06 review summary\n\n- Proposed cases: 5 (026–030); all owner decisions pending.\n- Batches 01–06 contain 30 candidates; only batch 01 has 5 owner-confirmed labels.\n- Full calibration labels frozen: no. Axioma run against these candidates: no.\n\nReview remains in packets of five, beginning with batch 02.\n", encoding="utf-8")
    print(json.dumps({"candidate_sha256": packet_hash, "source_sha256": manifest["source_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
