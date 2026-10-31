# BFS v2 development replay 02

**Status:** Development diagnostic only; not an untouched holdout.

The updated Java and Python analyzers were run once on the existing 28-case BFS v2 packet (14 Java, 14 Python). The source packet and frozen reviewed labels were not modified. The runner received only source code and entrypoints; it did not receive the labels.

## Results

| Metric | Original baseline | Development run 01 | Development run 02 |
|---|---:|---:|---:|
| Response agreement | 23/28 (82.1%) | 25/28 (89.3%) | 28/28 (100%) |
| Estimates emitted | 3/28 (10.7%) | 5/28 (17.9%) | 8/28 (28.6%) |
| Exact among emitted estimates | 3/3 | 5/5 | 8/8 |
| Unexpected estimate-case abstentions | 5 | 3 | 0 |
| Unexpected estimates on expected-unknown cases | 0 | 0 | 0 |
| Execution errors | 0 | 0 | 0 |

The three additional recognized cases in this run are Java eight-neighbor grid BFS (`J12`, `O(R * C)`), Java BFS with a full-grid scan during neighbor processing (`J13`, `O((R * C)^2)`), and Python four-neighbor component-sweep BFS (`P11`, `O(R * C)`).

Compared with the original baseline:

- `axioma-bfs-v2-j05`: unknown (unknown (data-dependent or incomplete loop)) → estimate (O(V^2)), expected O(V^2).
- `axioma-bfs-v2-j11`: unknown (unknown (data-dependent or incomplete loop)) → estimate (O(R * C)), expected O(R * C).
- `axioma-bfs-v2-j12`: unknown (unknown (data-dependent or incomplete loop)) → estimate (O(R * C)), expected O(R * C).
- `axioma-bfs-v2-j13`: unknown (unknown (data-dependent or incomplete loop)) → estimate (O((R * C)^2)), expected O((R * C)^2).
- `axioma-bfs-v2-p11`: unknown (unknown (data-dependent loop bound)) → estimate (O(R * C)), expected O(R * C).

The score is conditional on this small BFS-only development set. All eight estimates match their reviewed labels here, while twenty expected-unknown cases remain abstentions. This does not show how the analyzer performs on unseen code or other algorithm families.

## Verification

- Complexity regression tests: **113 passed**.
- Ruff on the two analyzer modules and their tests: **passed**.
- Prediction and scoring records: **28 unique cases, 28 executions completed, 0 errors**.
- Source packet and gold-label SHA-256 values are in `development-manifest-v2.json`; the original baseline prediction and score hashes are also recorded there for integrity comparison.

Commands and SHA-256 values for all relevant inputs and outputs are recorded in the manifest. The code worktree was dirty at Git HEAD `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`.
