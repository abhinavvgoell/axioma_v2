from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = json.loads((ROOT / "manifest-v2.json").read_text(encoding="utf-8"))
UPSTREAM = BASE["upstream_repositories"]
CASES = [
    {
        "id": "axioma-20261030-broad-021", "title": "Lazy-heap Dijkstra shortest path", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "graphs/dijkstra.py", "local_path": "batch-05/sources/python/graphs/dijkstra.py", "entrypoint": "dijkstra", "family": "graph_traversal",
        "input_size": "V = vertices, E = adjacency entries; n = V + E.", "expected_time": "O(n log n)", "expected_time_exact": "O(V + E log(E + 1))",
        "expected_auxiliary_space": "O(n)", "expected_auxiliary_space_exact": "O(V + E)",
        "time_rationale": "Each settled vertex scans its adjacency list once. Every successful relaxation pushes one heap entry, so there are O(E) pushes and pops, each O(log(E+1)); initialization and graph scans add O(V+E). The implementation may stop earlier when it reaches the destination.",
        "space_rationale": "The cost map and visited set use O(V); stale duplicate heap entries can make the heap O(E). Exclude the input graph.",
        "assumptions": "Analyze the reachable graph with nonnegative edge weights, valid adjacency keys and endpoints, and expected O(1) hash operations. Node labels must be hashable and mutually orderable when equal-cost heap tuples are compared. Treat arithmetic as O(1).",
    },
    {
        "id": "axioma-20261030-broad-022", "title": "Iterative ternary search with fixed-size linear tail", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "searches/ternary_search.py", "local_path": "batch-05/sources/python/searches/ternary_search.py", "entrypoint": "ite_ternary_search", "family": "searching",
        "input_size": "n = len(array); precision is the module constant 10.", "expected_time": "O(log n)", "expected_time_exact": "O(log_3 n + precision) = O(log n)",
        "expected_auxiliary_space": "O(1)", "expected_auxiliary_space_exact": "O(1)",
        "time_rationale": "Each loop iteration reduces the active interval to at most about two thirds. Once its size is below the fixed precision threshold, linear search examines at most a constant number of entries.",
        "space_rationale": "The selected iterative entrypoint uses a fixed number of indices and scalar values; its tail search is also iterative.",
        "assumptions": "Analyze ite_ternary_search only, on an array sorted in ascending order, with module precision fixed independently of n and O(1) comparisons/indexing. The file also contains a separate recursive implementation, which is not the selected entrypoint.",
    },
    {
        "id": "axioma-20261030-broad-023", "title": "Longest common substring dynamic programming", "language": "python", "repo": "TheAlgorithms/Python",
        "repo_path": "dynamic_programming/longest_common_substring.py", "local_path": "batch-05/sources/python/dynamic_programming/longest_common_substring.py", "entrypoint": "longest_common_substring", "family": "dynamic_programming",
        "input_size": "m = len(text1), k = len(text2), n = max(m,k).", "expected_time": "O(n^2)", "expected_time_exact": "O(m * k)",
        "expected_auxiliary_space": "O(n^2)", "expected_auxiliary_space_exact": "O(m * k)",
        "time_rationale": "For nonempty strings the nested loops fill all m×k interior cells. The final substring slice is O(min(m,k)), dominated by O(mk). The coarse n² class assumes m and k are of comparable order, with n=max(m,k).",
        "space_rationale": "The DP table has (m+1)(k+1) cells. The returned substring uses at most O(min(m,k)) additional space, dominated by the table for nonempty strings.",
        "assumptions": "Inputs are nonempty strings for the coarse n² class; the exact two-parameter bound is O(mk), and an empty input returns in O(1). Character comparison and indexing are O(1). For coarse scoring assume m and k have comparable order.",
    },
    {
        "id": "axioma-20261030-broad-024", "title": "0/1 knapsack bottom-up tabulation", "language": "java", "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/dynamicprogramming/KnapsackZeroOneTabulation.java", "local_path": "batch-05/sources/java/dynamicprogramming/KnapsackZeroOneTabulation.java", "entrypoint": "KnapsackZeroOneTabulation.compute", "family": "dynamic_programming",
        "input_size": "i = itemCount, W = capacity, n = max(i,W).", "expected_time": "O(n^2)", "expected_time_exact": "O(i * W)",
        "expected_auxiliary_space": "O(n^2)", "expected_auxiliary_space_exact": "O(i * W)",
        "time_rationale": "The method allocates and fills a (i+1)×(W+1) table; each cell does constant work. The exact bound is O(iW); the coarse n² class uses n=max(i,W).",
        "space_rationale": "The full two-dimensional int table contains (i+1)(W+1) cells, so space is O(iW), scored coarsely as O(n²) for n=max(i,W).",
        "assumptions": "Analyze valid arrays and itemCount i with i≥1 and capacity W≥1; use n=max(i,W) for coarse scoring. Treat primitive arithmetic and array access as O(1); exclude inputs and scalar return.",
    },
    {
        "id": "axioma-20261030-broad-025", "title": "DFS topological sort with adjacency lists", "language": "java", "repo": "TheAlgorithms/Java",
        "repo_path": "src/main/java/com/thealgorithms/sorts/TopologicalSort.java", "local_path": "batch-05/sources/java/sorts/TopologicalSort.java", "entrypoint": "TopologicalSort.sort", "family": "graph_traversal",
        "input_size": "V = vertices, E = adjacency entries; n = V + E.", "expected_time": "O(n)", "expected_time_exact": "O(V + E)",
        "expected_auxiliary_space": "O(n)", "expected_auxiliary_space_exact": "O(V)",
        "time_rationale": "DFS colors each vertex once and checks each adjacency entry once. Linked-list front insertion is O(1), giving O(V+E) time.",
        "space_rationale": "The recursion stack and returned linked list each use O(V). The existing graph input is excluded; output storage is included and remains O(V).",
        "assumptions": "Input is a DAG represented by the source's adjacency lists; all referenced vertices are present. Hash-map operations for string labels are expected O(1), label hashing/comparison is O(1), and adjacency iteration is linear in degree. Analyze sort, not graph construction. Scoring class uses n=V+E.",
    },
]


def main() -> None:
    hashes: set[str] = set()
    for name in ("candidate-cases-batch-01-v2.jsonl", "candidate-cases-batch-02-v1.jsonl", "candidate-cases-batch-03-v1.jsonl", "candidate-cases-batch-04-v1.jsonl"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                hashes.add(json.loads(line)["source_sha256"])
    for case in CASES:
        repo = UPSTREAM[case["repo"]]
        case["commit"] = repo["commit"]
        case["source_url"] = f"https://github.com/{case['repo']}/blob/{case['commit']}/{case['repo_path']}"
        case["source_provenance"] = "Exact source file from pinned upstream repository commit."
        case["partition"] = "calibration"
        case["decision_status"] = case["label_status"] = "proposed_pending_owner_confirmation"
        case["owner_decision"] = case["reviewer"] = case["review_date"] = None
        path = (ROOT / case["local_path"]).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError(f"missing snapshot for {case['id']}")
        case["source"] = path.read_bytes().decode("utf-8")
        case["source_sha256"] = hashlib.sha256(case["source"].encode("utf-8")).hexdigest()
        if case["source_sha256"] in hashes:
            raise ValueError(f"duplicate source hash for {case['id']}")
        hashes.add(case["source_sha256"])

    packet_path = ROOT / "candidate-cases-batch-05-v1.jsonl"
    packet_path.write_text("".join(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for case in CASES), encoding="utf-8", newline="")
    packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    ids = [case["id"] for case in CASES]
    manifest = {
        "dataset_id": "axioma-20261030-external-broad-calibration-v2", "status": "candidate_review_in_progress", "target_case_count": 30,
        "target_range": [30, 50], "current_batch": "05", "batch_size": 5, "case_count_current_batch": 5, "case_ids": ids,
        "languages": {"python": 3, "java": 2}, "families": ["graph_traversal", "searching", "dynamic_programming"],
        "candidate_file": packet_path.name, "candidate_file_sha256": packet_hash,
        "source_sha256": {case["id"]: case["source_sha256"] for case in CASES}, "upstream_repositories": UPSTREAM,
        "previously_used_sets_excluded": BASE["previously_used_sets_excluded"], "reviewed_by": None, "review_date": None, "gold_labels_frozen": False,
        "analyzer_run": False, "independence_note": "Calibration only; pinned upstream sources; not a repository-held-out final evaluation.",
        "supersedes": None, "revision_note": "Five proposed source-backed cases; labels pending owner review; Axioma not run.", "partition": "calibration",
    }
    (ROOT / "manifest-batch-05-v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = ["# Complexity calibration — batch 05 (proposed)", "", "**Status:** Five proposed labels, all pending owner confirmation. Axioma has not been run. Full pinned sources, rationales, assumptions, and hashes are included.", "", f"Packet SHA-256: `{packet_hash}`", ""]
    for case in CASES:
        lines.extend([f"## {case['id']} — {case['title']}", "", f"- **Source:** [{case['repo_path']}]({case['source_url']}) (commit `{case['commit']}`)", f"- **SHA-256:** `{case['source_sha256']}`", f"- **Proposed time:** `{case['expected_time_exact']}` (coarse `{case['expected_time']}`)", f"- **Proposed auxiliary space:** `{case['expected_auxiliary_space_exact']}` (coarse `{case['expected_auxiliary_space']}`)", f"- **Entrypoint:** `{case['entrypoint']}`", f"- **Input size:** {case['input_size']}", f"- **Assumptions:** {case['assumptions']}", f"- **Time rationale:** {case['time_rationale']}", f"- **Space rationale:** {case['space_rationale']}", "", f"```{'java' if case['language'] == 'java' else 'python'}", case["source"].rstrip("\r\n"), "```", ""])
    (ROOT / "review-batch-05-v1.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "summary-batch-05-v1.md").write_text("# Batch 05 review summary\n\n- Proposed cases: 5 (021–025); all pending owner review.\n- Batch 01: 5 approved/frozen partially; batches 02–05: 20 proposed labels pending.\n- Candidate coverage: 25/30 prepared; 5/30 owner-confirmed.\n- Full calibration set frozen: no. Axioma run against candidates: no.\n\nReview in five-case increments, beginning with batch 02.\n", encoding="utf-8")
    print(json.dumps({"candidate_sha256": packet_hash, "source_sha256": manifest["source_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
