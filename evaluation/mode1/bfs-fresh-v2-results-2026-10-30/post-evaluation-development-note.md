# Post-evaluation development note

The v2 report and scorer outputs are the baseline from before this follow-up. The frozen packet was not rerun after the analyzer edits below, so its reported metrics remain the original baseline and must not be presented as performance of the updated analyzer.

- Java analyzer SHA-256 at evaluation time: `d21679b5dc79f657db1ad8e58252580ff0db0a4de7169dc16debcb7c135b4228`.
- Python analyzer SHA-256 at evaluation time: `378ab6344620d1606f5a93ebbec96cba8bf9c259804ded3a6057aa87bf3774ea`.
- Java analyzer SHA-256 after grid-alias and queue-method support: `6bce6a69308beb5673b9b22f72692f112db91012cea85655e0d0b87622ae2fd8`.
- Java analyzer SHA-256 after unbraced matrix-loop support: `59db17c21e9fe183ab3ce633e70c81b4543078c1e6961c3939b1c16304144cb2`.
- Java analyzer SHA-256 after separate-bounds-guard scan support: `486b2492626cabbffe31c9e19106a716a0e3038e363775e608c93f1c9fe49b57`.
- Python analyzer SHA-256 after development changes: `ec79121599eb2220db9b730c2a8b62fb09284b3425cb709437622d4b0db1550a`.
- The frozen label SHA-256 (`60af3adc6ecdb39cf0590eead0694e8d1d3b0bdf8ed8b48d7f06638def8dea9d`) and source-packet SHA-256 (`d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1`) remain unchanged.

## Failure analysis

- **Java grid BFS (J11/J12/J13):** the recognizer accepted the literal names `rows` and `cols` for visited-array dimensions and full-grid loop bounds. Common local aliases such as `height = grid.length` and `width = grid[0].length` were outside that rule shape. J12 also uses `ArrayDeque.addLast`, while the grid rule only matched `add` for initial and neighbor enqueue operations.
- **Java adjacency-matrix BFS (J05):** at baseline, the matrix matcher depended on loop spans; the span parser ended an unbraced `for` at the following `if`, before the guarded neighbor body. The matcher now uses a bounded statement-end check for this case.
- **Python component-sweep grid BFS (P11):** the AST recognizer expects each neighbor tuple to contain a direct coordinate expression. P11 iterates over four delta pairs and computes candidate coordinates in a separate assignment, so the current rule does not recognize it.
- **Java repeated grid scan (J13):** in addition to dimension aliases, the full scan is inside the bounds guard but before a separate visited-cell guard. The current grid matcher expects the visited and grid-cell checks in one guard. This shape still needs separate development coverage.

## Development change made

The Java grid rule now accepts two-dimensional visited arrays whose dimensions are local aliases derived from the grid, uses those aliases to validate row/column loop bounds, and recognizes `add`, `offer`, and `addLast` queue enqueue calls. New development fixtures cover local dimension aliases with an `addLast` queue, a repeated full-grid scan using those aliases, and rejection of a column dimension incorrectly derived from the row count.

The Java adjacency-matrix rule now derives the bounded end of an `if` statement used as an unbraced `for` body, so it can inspect the guarded visited mark and enqueue without widening generic loop-span behavior. A paired near-miss verifies that enqueue-before-marking still abstains. This remains a unit-fixture result; J05 itself was not rerun.

The Java grid matcher now has a separate path for a full-grid scan inside a complete neighbor-bounds guard and before a distinct visited guard. It requires a rectangular-grid dimension match, current-coordinate-plus-direction-array candidate expressions, literal orthogonal (4-way) or surrounding (8-way) offsets, and mark-before-enqueue. Development near-misses with a missing bound or non-neighbor offsets remain inconclusive. This remains a unit-fixture result; J13 itself was not rerun.

The Python component-grid rule now recognizes four fixed delta pairs when the candidate coordinate is assigned as current coordinate plus its corresponding delta. It also follows tuple-unpacked row/column dimensions when each expression is derived from the grid. A development near-miss with an incomplete three-direction set remains inconclusive.

These are heuristic extensions. J13's guard-order shape has development-fixture coverage, but no result for the frozen J13 case is claimed. No frozen case source or label was changed, and the analyzer was not run against the frozen packet again.

## Validation

- `services/api/.venv/Scripts/python.exe -m pytest -o addopts='' services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py -q` — 111 passed.
- `services/api/.venv/Scripts/ruff.exe check services/worker/src/axioma_worker/java_complexity.py services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py` — passed.
- `git diff --check -- services/worker/src/axioma_worker/java_complexity.py services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py` — passed; Git printed only line-ending normalization warnings for existing files.

## Evaluation status and next step

The 28-case v2 results are now a preserved pre-change diagnostic baseline. Continue development using separate synthetic fixtures; do not rescore this packet as an untouched holdout. After systematic improvements are complete, prepare and freeze a new independently reviewed evaluation set across multiple algorithm families before making broader coverage claims.

### Follow-up development replay — 2026-10-30

After the Java and Python grid-recognizer follow-ups, the same BFS packet was run as explicitly labeled development data. The replay recognized the previously abstaining J12, J13, and P11 cases; together with the earlier J05 and J11 changes, all eight expected-estimate cases were estimated exactly, while all 20 expected-unknown cases remained unknown. Response agreement was 28/28. This is not an independent holdout result. The focused changes, 113 passing complexity tests, Ruff result, predictions, score, case table, and current source/input hashes are preserved in `evaluation/mode1/bfs-fresh-v2-development-2026-10-30-run-02/`.

The next evaluation claim requires a newly selected, independently reviewed multi-family set that has not informed recognizer changes. The repository instruction file currently contains an older note that five fresh cases were awaiting analysis; the later BFS v2 packet and its development replays supersede that historical status for BFS, but do not provide a broad untouched holdout.
