# Broad complexity calibration review — batch 01, revised proposal v2

**Status: proposed; pending owner confirmation.** Axioma has not been run on these cases. This revision preserves the original v1 packet and source files. It corrects the edit-distance exact bounds to include the boundary row and column, including when either string is empty. The exact code for every case remains in review-batch-01.md; the source snapshots and SHA-256 values are unchanged.

If confirmed, this batch belongs to the evaluator's supported calibration partition.

For each case, confirm or revise the time and auxiliary-space labels. Reply by case ID, for example: axioma-20261030-broad-001 approve.

| Case ID | Implementation | Proposed time | Proposed auxiliary space | Decision |
|---|---|---|---|---|
| axioma-20261030-broad-001 | Python adjacency-list BFS | O(V + E); coarse score O(n), n = V + E | O(V); coarse score O(n) | Pending |
| axioma-20261030-broad-002 | Python bottom-up edit distance | O((m + 1)(k + 1)); worst case O(N²), N = max(m,k) | O((m + 1)(k + 1)); worst case O(N²) | Pending |
| axioma-20261030-broad-003 | Java KMP string matcher | O(m + k) | O(k) excluding returned occurrences | Pending |
| axioma-20261030-broad-004 | Java Kadane maximum-subarray check | O(n) | O(1) | Pending |
| axioma-20261030-broad-005 | Python longest substring without repeats | O(n) expected | O(U), where U is distinct characters and U ≤ n | Pending |

## Case rationales and assumptions

### axioma-20261030-broad-001

The BFS marks each vertex visited before enqueueing it. Each reachable vertex is therefore enqueued and expanded once, and each reachable adjacency entry is scanned once: O(V + E). The visited set and queue use O(V) space.

Assumptions: the graph is represented by adjacency lists; every reachable vertex has a dictionary entry; the start vertex is valid; E counts adjacency entries scanned; set operations are expected O(1) and queue operations are amortized O(1).

Source SHA-256: 621e11bd4a320c7437bba42e29715608b05e84a5939562715cde8e32a576a529

### axioma-20261030-broad-002

The bottom-up implementation fills every cell in an (m+1) by (k+1) table. The complete time and auxiliary-space bounds are O((m+1)(k+1)), equivalently O(mk + m + k + 1). This includes boundary work when either input is empty. With N = max(m,k), the worst-case class is O(N²).

Assumptions: analyze only min_dist_bottom_up; character comparisons and table access are O(1); m and k may independently be zero or positive. The table is auxiliary storage; the function returns a scalar.

Source SHA-256: e844589a5505736ab8a8ee6aee2494f124a7c56c28d92ab860fb817993f0e433

### axioma-20261030-broad-003

KMP builds a prefix-function table in O(k) and scans the haystack in amortized O(m); total time is O(m+k). The prefix table uses O(k) auxiliary space. The returned occurrence list is output storage and may contain O(m) matches; it is excluded from the auxiliary-space label.

Assumptions: character access is O(1); ArrayList.add is amortized O(1); k > 0 for the non-early-return path; include the prefix-function helper in the analysis.

Source SHA-256: 2b7b74597b3246e29ff751dfae3399b833fe7ae6b3367a1fd959e9c7c18a2816

### axioma-20261030-broad-004

Kadane's scan performs constant work for each array element, so time is O(n) and auxiliary space is O(1).

Assumptions: a is non-empty because the method reads a[0]; integer arithmetic is treated as O(1); n = a.length.

Source SHA-256: 2d23e1c8f889ef2784b78faab71959a7e374281c39e7cd36658848ffba85567c

### axioma-20261030-broad-005

The right pointer scans the string once. The left pointer only moves forward, so total pointer movement and expected dictionary work are O(n). The dictionary retains at most one entry per distinct character: O(U) auxiliary space.

Assumptions: input is a Python string; dictionary operations are expected O(1); n is string length and U is its number of distinct characters.

Source SHA-256: 6d2f69289af704e62a323b78a104b538297cce92fe19478c1d4db273b6cccea2

## Review integrity

- Candidate packet: candidate-cases-batch-01-v2.jsonl
- Manifest: manifest-v2.json
- All five decisions remain proposed and pending owner confirmation.
- Gold labels are not frozen.
- No Axioma predictions or analyzer evidence are included.
- The original v1 packet, manifest, review sheet, and source snapshots remain preserved.
