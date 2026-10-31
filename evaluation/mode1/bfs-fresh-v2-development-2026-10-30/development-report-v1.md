# BFS v2 post-change development replay

**Status:** Development diagnostic only; not an untouched holdout.

The current Java and Python analyzers were run once against the existing 28-case BFS v2 source packet after the follow-up recognizer changes. The frozen source packet and owner-reviewed gold labels were read as inputs; the runner passed source code and entrypoints to the analyzer, not the labels. Original baseline files were not overwritten.

## Results

| Metric | Original baseline | Development replay |
|---|---:|---:|
| Response agreement | 23/28 (82.1%) | 25/28 (89.3%) |
| Estimates emitted | 3/28 (10.7%) | 5/28 (17.9%) |
| Exact among emitted estimates | 3/3 (100%) | 5/5 (100%) |
| Unexpected abstentions on estimate cases | 5 | 3 |
| Unexpected estimates on expected-unknown cases | 0 | 0 |
| Execution errors | 0 | 0 |

The replay newly estimated **J05** as `O(V^2)` and **J11** as `O(R * C)`, both matching their reviewed labels. J12, J13, and P11 remain expected-estimate cases where the analyzer abstained. The 100% exact rate is conditional on only five emitted estimates.

These cases have already informed analyzer development, so this replay is a development result and cannot be presented as independent post-change performance. It covers BFS patterns only and says nothing about other algorithm families. No runtime complexity proof or benchmark claim is made.

## Reproduction

Tests run before the replay:

```powershell
services/api/.venv/Scripts/python.exe -m pytest -o addopts='' services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py -q
```

Result: **111 passed**.

Analyzer replay:

```powershell
services/api/.venv/Scripts/python.exe evaluation/mode1/run_bfs_v2_predictions.py evaluation/mode1/bfs-fresh-v2-review-2026-10-30/review-packet.jsonl --packet-sha256 d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1 --output evaluation/mode1/bfs-fresh-v2-development-2026-10-30/predictions-dev-v1.jsonl
services/api/.venv/Scripts/python.exe evaluation/mode1/evaluate_bfs_v2.py evaluation/mode1/bfs-fresh-v2-review-2026-10-30/gold-labels-v2.json evaluation/mode1/bfs-fresh-v2-development-2026-10-30/predictions-dev-v1.jsonl --output evaluation/mode1/bfs-fresh-v2-development-2026-10-30/score-dev-v1.json --csv evaluation/mode1/bfs-fresh-v2-development-2026-10-30/case-results-dev-v1.csv
```

See `development-manifest-v1.json` for current analyzer, packet, labels, runner, scorer, and output SHA-256 values, plus the baseline comparison. Git HEAD was `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`; the worktree was dirty during evaluation.
