# External multi-family complexity review — pilot v1

**Status:** Proposed; pending project-owner review. Axioma has not been run on these cases. Do not treat these as human-approved labels or a frozen holdout.

This packet is sourced from exact upstream files at pinned commits in TheAlgorithms/Python and TheAlgorithms/Java. The complete source snapshots and MIT license notices are included. The proposed labels were assigned by source inspection and require owner verification before any analyzer run.

This five-case pilot covers search, sorting, tree traversal, dynamic programming, and graph traversal. It is a first external-source review batch only; the evaluation plan calls for a later 30–50-case broader evaluation.

## Review conventions

- Score worst-case time, except where a different case-specific assumption is stated.
- Treat labels as mathematical proposals; verify the exact implementation and assumptions below.
- `unknown` from Axioma is an abstention, not a correct complexity estimate. Do not change labels after seeing predictions without recording adjudication.
- Review source provenance and source SHA-256 values before approving. The manifest keeps owner confirmation and freeze status false.

## axioma-20261030-v3-01 — Binary search lower bound

- **Language / family:** python / search
- **Entry point:** `bisect_left`
- **Source:** `searches/binary_search.py` at `6e03a48579ca212a08b36be00378f887dc41a003` ([pinned file](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/searches/binary_search.py))
- **Source SHA-256:** `bf2d0a3cfb68b0518857385cfb41fccebd21c4884b1bd00f44360027b584b88e`
- **Input size:** n = len(sorted_collection)
- **Proposed expected time:** **O(log n)**
- **Assumptions:** sorted_collection is sorted ascending; item comparisons and indexed access are O(1); worst-case number of loop iterations is measured.
- **Rationale:** Each loop iteration halves the active interval [lo, hi), and the function returns once the interval is empty. Initialization and final return are O(1).
- **Owner decision:** pending — approve, revise (provide corrected label/rationale), or exclude.

## axioma-20261030-v3-02 — Insertion sort

- **Language / family:** python / sorting
- **Entry point:** `insertion_sort`
- **Source:** `sorts/insertion_sort.py` at `6e03a48579ca212a08b36be00378f887dc41a003` ([pinned file](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/sorts/insertion_sort.py))
- **Source SHA-256:** `2b244e03a5831e74fc615090828949d6155b56eb1e898e34e021c73ac0723b75`
- **Input size:** n = len(collection)
- **Proposed expected time:** **O(n^2)**
- **Assumptions:** Worst-case time; comparisons and indexed reads/writes are O(1); collection supports mutable indexed access.
- **Rationale:** In reverse order, the inner while loop shifts each new item across all prior items; total shifts sum to 1 + 2 + ... + (n-1) = Theta(n^2).
- **Owner decision:** pending — approve, revise (provide corrected label/rationale), or exclude.

## axioma-20261030-v3-03 — Recursive binary-tree preorder traversal

- **Language / family:** python / tree_traversal
- **Entry point:** `preorder`
- **Source:** `data_structures/binary_tree/binary_tree_traversals.py` at `6e03a48579ca212a08b36be00378f887dc41a003` ([pinned file](https://github.com/TheAlgorithms/Python/blob/6e03a48579ca212a08b36be00378f887dc41a003/data_structures/binary_tree/binary_tree_traversals.py))
- **Source SHA-256:** `828ca8cdba0a2f30dbace78ca4017eb83beea7266928d41de89b24cc6db434d2`
- **Input size:** n = number of nodes in the input tree
- **Proposed expected time:** **O(n)**
- **Assumptions:** Input is a finite binary tree; each node has at most two child references; count traversal time, not the time a caller may spend consuming yielded values beyond one O(1) yield per node.
- **Rationale:** The function yields once per node and recursively visits each existing left and right child exactly once; all per-node work is O(1).
- **Owner decision:** pending — approve, revise (provide corrected label/rationale), or exclude.

## axioma-20261030-v3-04 — Longest common subsequence

- **Language / family:** java / dynamic_programming
- **Entry point:** `LongestCommonSubsequence.getLCS`
- **Source:** `src/main/java/com/thealgorithms/dynamicprogramming/LongestCommonSubsequence.java` at `410f08753505a0af9e46423396e8768bc97cbc1c` ([pinned file](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/dynamicprogramming/LongestCommonSubsequence.java))
- **Source SHA-256:** `ed98d5f455bd5e792a734d763bae810767a679333f3f160f353b2769ded84b5b`
- **Input size:** n = |str1| + |str2|
- **Proposed expected time:** **O(n^2)**
- **Assumptions:** Worst-case over pairs of strings with total length n; character/string operations are treated as O(1) under the standard word/cell model; null and empty inputs return in O(1) or linear setup.
- **Rationale:** The DP table loops over every pair of positions, costing Theta(m*n). With m+n=n, this is O(n^2) and is Theta(n^2) for similarly sized strings. Converting strings and reconstructing the result add O(n), which is dominated.
- **Owner decision:** pending — approve, revise (provide corrected label/rationale), or exclude.

## axioma-20261030-v3-05 — Breadth-first search over child adjacency lists

- **Language / family:** java / graph_traversal
- **Entry point:** `BreadthFirstSearch.search`
- **Source:** `src/main/java/com/thealgorithms/searches/BreadthFirstSearch.java` at `410f08753505a0af9e46423396e8768bc97cbc1c` ([pinned file](https://github.com/TheAlgorithms/Java/blob/410f08753505a0af9e46423396e8768bc97cbc1c/src/main/java/com/thealgorithms/searches/BreadthFirstSearch.java))
- **Source SHA-256:** `830a110a2827d491a5ce9efc4dd49110171950b587ddc2e379c89016c80690e0`
- **Input size:** n = V + E, where E counts child references enumerated by getChildren()
- **Proposed expected time:** **O(n)**
- **Assumptions:** One call on a fresh BreadthFirstSearch instance; graph nodes are reachable through child lists; getChildren iteration/addAll takes O(degree); HashSet operations are expected O(1); equality/hashCode are O(1) expected.
- **Rationale:** The visited set causes each reachable node to be expanded at most once; each child reference is enqueued at most once per edge, and queue/list/hash-set work totals O(V+E)=O(n). Early success only reduces work; the worst case exhausts the reachable graph.
- **Owner decision:** pending — approve, revise (provide corrected label/rationale), or exclude.
