# Java adjacency-list BFS recognition — 2026-10-29

## Root cause

The old Java graph-BFS matcher required a braced `if` body and only checked tokens inside brace spans. The reviewed snippets use the valid single-statement form `if (visited.add(neighbor)) queue.offer(neighbor);`, so the matcher fell back to the generic loop-depth estimate. The multi-source case also needs its `starts` loop represented as `O(S)`; simplifying it to `O(V + E)` without an `S <= V` assumption would be unsound.

## Change

The Java analyzer now has a bounded adjacency-list BFS rule (`bounded_bfs_traversal_v2`). It requires typed adjacency-list and queue declarations, a queue drain loop, a typed set or boolean-array visitation pattern, an initial seed marked before enqueue, and a neighbor enqueue protected by the same visited condition. It accounts for one input-sized multi-source seed loop as `O(S)`, retains `O(S + V + E)`, and records the conditional simplification only when `S <= V`. A narrowly shaped disconnected-components traversal is supported when one global visited set gates each component seed. Extra nested graph scans, repeated traversals, unsupported graph containers, mismatched queue values, and missing initial visited state abstain.

Evidence includes representation/type, queue setup and dequeue, visited/enqueue relationship, source lines, per-vertex and adjacency-entry bounds, seed cost, assumptions, limitations, final expression, and low-confidence heuristic classification. This is static evidence, not a formal proof for arbitrary Java.

## Diagnostic replay

`java-adjacency-bfs-diagnostic-2026-10-29.json` is a new diagnostic-only record. The old output for both reviewed cases was `unknown` from `static_java_token_loop_depth`. The new outputs are:

- `bfs-ind-001`: `O(V + E)` — exact match to the human-reviewed label.
- `bfs-ind-003`: `O(S + V + E)` — exact match; the evidence confirms duplicate starts are deduplicated. It states that `O(V + E)` applies only if `S <= V`.

The reviewed label artifact remains unchanged (SHA-256 `a6a8aaad56b0dc09141ec8e7ecb2db73d39870ed92628ac94743691493cb6eff`), as do `gold-provisional.jsonl`, `predictions.jsonl`, and the original independent packet. Since these examples informed the implementation, they are regression diagnostics, not an untouched evaluation.

Replay with:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/replay_java_adjacency_bfs_reviewed.py
```

The runner refuses to overwrite an existing diagnostic and verifies case source hashes and reviewed-label artifact hash.

## Verification

- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py -o addopts= -q` — 49 passed.
- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_python_complexity.py -o addopts= -q` — 52 passed.
- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests -o addopts= -q` — 153 passed.
- `services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1 -o addopts= -q` — 34 passed.
- `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/java_complexity.py services/worker/tests/test_java_complexity.py evaluation/mode1/replay_java_adjacency_bfs_reviewed.py` — passed.
- `git diff --check` — passed; Git printed existing LF-to-CRLF working-copy warnings.
- Reviewed label SHA-256 remained `a6a8aaad56b0dc09141ec8e7ecb2db73d39870ed92628ac94743691493cb6eff`; provisional label SHA-256 remained `9bda67401a794613b4ac01fd351af8f4e0e3904f0c9464d4254efef930d95298`.

PostgreSQL was not part of this analyzer-only change, and no database verification is claimed. No API, database, Python analyzer, grid rule, recurrence rule, or stack rule changes were made as part of this milestone. No commit or push was made.
