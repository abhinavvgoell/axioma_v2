# Bounded BFS traversal analysis — 2026-10-29

## Scope and diagnostic case

This milestone extends the existing Java token analyzer and Python AST analyzer with bounded BFS evidence. The unresolved frozen case `axioma-20261029-19` is Python **grid** BFS, not ordinary graph BFS. Its outer loops inspect an `n × n` grid. A shared visited set bounds component traversal across those loops; each land cell is enqueued at most once and each dequeued cell checks four neighbors. Its approved time label remains `O(n²)`.

The packet is calibration/development data and is not an untouched holdout. The gold labels and source were not changed. No benchmark or space-complexity result was produced.

## Supported patterns and evidence

- **Graph adjacency-list BFS:** existing Java and Python recognizers continue to support queue traversal with visited-state checks. Evidence distinguishes `V` vertices and `E` adjacency entries and derives `O(V + E)` from processing each vertex once and scanning each adjacency entry once. An enclosing input-sized loop prevents the single-traversal rule from matching.
- **Java adjacency-matrix BFS:** remains distinct and reports `O(V²)` when each processed vertex scans a full matrix row and marks vertices before enqueue.
- **Python grid component BFS:** recognizes two dimension-bounded outer loops, a shared visited set, tuple-coordinate queue, explicit four-neighbor enumeration, and visited-before-enqueue marking. Square symbolic dimensions report `O(n²)`; separate dimensions report `O(R * C)`. Extra input-sized scans within a dequeue and missing visited updates are not accepted.
- **Java single-source grid BFS:** recognizes a queue, a two-dimensional visited array marked before enqueue, and a fixed-bound 4- or 8-direction loop, yielding `O(R * C)`. It rejects an enclosing repeated traversal.

Accepted BFS evidence lives in `details.code_analysis.bfs` and records language, rule version, pattern, input-size symbols, queue, visited-state behavior, neighbor representation/bound, amortized/bounded work argument, result, assumptions, limitations, and `heuristic_static_bounded_argument`. It is a heuristic static estimate, not a proof. Auxiliary space is not estimated.

## Case 19 replay

Run:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/replay_grid_bfs_diagnostic.py
```

The runner verifies frozen source hashes, calls the normal Python analyzer, and writes a new result without overwriting earlier artifacts. Result: see `grid-bfs-diagnostic-results-2026-10-29.json`. This one calibration case is a diagnostic, not independent accuracy evidence.

## Verification

Complexity tests cover Java/Python adjacency-list BFS, matrix BFS, Python square and rectangular grid BFS, Java four/eight-direction BFS, missing visited guards, unrelated queue use, nested independent grid scans, and outer-loop traversal multipliers. Existing recurrence and monotonic-stack regressions remain in the same suites.

No API, database, dependency, migration, or execution-sandbox changes were made.
