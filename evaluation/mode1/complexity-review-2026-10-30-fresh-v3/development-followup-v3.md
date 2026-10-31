# Development follow-up: Java object-child BFS

This note records a targeted change prompted by the owner-reviewed `axioma-20261030-v3-05` calibration case. The earlier pilot reports and predictions remain unchanged.

## Observed issue and change

The Java analyzer recognized integer-ID adjacency-list BFS only when a visited guard prevented duplicate enqueueing. The reviewed implementation traverses `Node<T>` child lists and performs duplicate detection when a node is dequeued. Duplicate references may therefore be pending in the queue at once. A separate bounded recognizer now reports O(V + E), accounting for up to O(E) queued child references and at most one expansion per distinct value. It assumes expected O(1) `HashSet` operations and O(degree) child-list iteration and `addAll`; the estimate has low confidence and does not cover arbitrary helper implementations.

## Verification

- The exact reviewed case source hash matches its review packet and its owner decision is approved; the current analyzer returns O(V + E) with method `static_java_graph_bfs_v2`. Evidence is recorded in `development-java-node-bfs-diagnostic-v1.json`.
- The positive Java pattern test verifies dequeue-time deduplication and the O(E) pending-queue caveat. A near-miss without the dequeue-and-skip guard remains unknown.
- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py -o addopts='' -q` — **59 passed**.
- `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/java_complexity.py services/worker/tests/test_java_complexity.py` — **passed**.
- `git diff --check` — **passed** (Git may print Windows line-ending conversion warnings).

This one-case calibration diagnostic is not independent evaluation evidence and does not establish general Java BFS recognition accuracy. The broad candidate batch remains pending owner label review and has not been analyzed.
