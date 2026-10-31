# Java grid BFS cost-accounting fix — 2026-10-29

## Root cause and outcome

The Java grid recognizer previously returned `O(R*C)` after matching a queue loop, a fixed 4/8-direction loop, and mark-before-enqueue. It did not account for other loops inside the queue traversal. Frozen development case `bfs-ind-010` has a nested `rows × cols` scan inside neighbor processing, so the scan runs for each dequeued cell and each fixed direction. Since each cell is enqueued at most once, the repeated full-grid work is `O((R*C)^2)`.

The original prediction was `O(R * C)` from `static_java_grid_bfs_v1`. The updated prediction is `O((R * C)^2)` from `static_java_grid_bfs_v2`, rule `bounded_bfs_traversal_v2`. It exactly matches the **unchanged provisional** label. This is a development diagnostic, not evidence of generalization or improved independent accuracy.

The frozen Java source remains in `bfs-independent-2026-10-29-v1/cases.jsonl` with SHA-256 `9d75899b2760a19d3aa3d6ac3287e3f3a784e04d7c9c898093c7314753a67551`. The label file and original independent evaluation report were not modified. The label is still marked `provisional_not_human_reviewed`.

## Narrow rule behavior

The recognizer now accounts for loops nested in a recognized grid traversal. It recognizes explicit `for (row=0; row<rows; row++)` / `for (col=0; col<cols; col++)` scans that read a cell from the same grid argument. A scan inside queue processing contributes `O(R*C)` per dequeued cell and yields `O((R*C)^2)`. A recognized scan before or after the traversal contributes a separate `O(R*C)` phase, so the aggregate remains `O(R*C)`. Other unaccounted loop structures cause the grid recognizer to abstain and leave the existing conservative fallback in place.

Structured evidence records queue, dequeue, neighbor-loop, guard and additional-scan token indexes and source lines, loop costs, aggregate work, assumptions, limitations, confidence, method and rule version. The estimate remains a low-confidence static heuristic, not a formal proof.

## Diagnostic record

Machine-readable before/after evidence is in `java-grid-bfs-fix-diagnostic-2026-10-29.json`. Reproduce it with:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/replay_java_grid_bfs_fix.py
```

The script refuses to overwrite its output and verifies the original case source hash and expected label before analyzing it.

## Verification

- Regression-first check against old behavior: `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py -k 'frozen_java_grid_full_scan_case or full_scan_once_before or full_scan_per_dequeued or ambiguous_nested_loop or java_grid_bfs' -q` — initially failed on the old `O(R*C)` result; after the fix, 7 passed.
- Java complexity tests: `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py -o addopts= -q` — 41 passed.
- Python complexity tests: `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_python_complexity.py -o addopts= -q` — 52 passed.
- Complete worker suite: `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests -o addopts= -q` — 145 passed, including sandbox tests; no retry was needed.
- Mode 1 evaluation tests: `services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1 -o addopts= -q` — 34 passed.
- Ruff: `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/java_complexity.py services/worker/tests/test_java_complexity.py evaluation/mode1/replay_java_grid_bfs_fix.py` — passed.
- `git diff --check` — passed. Git printed existing LF-to-CRLF working-copy warnings.

No API, database, dependency, or Python analyzer changes were made. PostgreSQL tests were not run, and no PostgreSQL verification is claimed.

## Limitations and next task

Only explicit two-dimensional loops with the `rows` and `cols` bounds and a direct indexed read from the recognized grid are costed. Other nested costs, helper calls, aliasing, nonstandard dimension names, or complex control flow remain outside this heuristic and should abstain. The evidence is source-shape based and low confidence.

Next single technical task: after a human reviews the still-provisional BFS labels, address the Java adjacency-list BFS abstentions from cases `bfs-ind-001` and `bfs-ind-003` with positive and near-miss regression tests. Do not use the already inspected packet as a fresh holdout.
