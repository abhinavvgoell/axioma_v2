# Axioma Independent BFS Evaluation v2 — Results

**Run date:** 2026-10-30  
**Status:** One analyzer pass completed and scored. This is a 28-case targeted development evaluation.  
**Analyzer revision:** `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`; worktree was dirty before evaluation.  
**Scope:** No analyzer, harness, frozen labels, or source packet changes were made for this run.

## Run integrity

- Frozen labels SHA-256: `60af3adc6ecdb39cf0590eead0694e8d1d3b0bdf8ed8b48d7f06638def8dea9d`
- Source packet SHA-256: `d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1`
- Source manifest SHA-256: `f2c4564f3015670ee0c245e40771ee50c94466b2a7d18a87515c5f2e2f52799d`
- 28 cases: 14 Java and 14 Python. Case source hashes match the frozen labels.
- `runner-output-raw-v2.jsonl` preserves the runner output. `predictions-v2.jsonl` adds gold response/complexity and an actual-estimate field after the run to match the scorer schema; the nested analyzer outputs are unchanged. Gold labels were not passed to the analyzer.
- All emitted estimates had low confidence. Java runtime was unavailable; the static analysis did not require it.

## Aggregate results

| Metric | Result |
|---|---:|
| Response agreement | 23/28 (82.1%) |
| Correct estimate responses | 3 |
| Correct unknown/abstentions | 20 |
| Unexpected estimates on expected unknown | 0 |
| Unexpected abstentions on expected estimate | 5 |
| Execution errors | 0 |
| Estimate coverage | 3/28 (10.7%) |
| Coverage on expected-estimate subset | 3/8 (37.5%) |
| Exact complexity among emitted estimates | 3/3 (100.0%) |

The 100% exact result is conditional on only three emitted estimates; it does not imply broad accuracy. The analyzer estimated 3/28 cases (10.7%) and abstained on five cases expected to produce an estimate. Response agreement includes correct abstentions and is not complexity accuracy. This small BFS set is not a final holdout or evidence for other algorithm families.

## Unexpected abstentions on estimate cases

- `axioma-bfs-v2-j05`: expected `O(V^2)` estimate; actual response was unknown (`unknown (data-dependent or incomplete loop)`).
- `axioma-bfs-v2-j11`: expected `O(R * C)` estimate; actual response was unknown (`unknown (data-dependent or incomplete loop)`).
- `axioma-bfs-v2-j12`: expected `O(R * C)` estimate; actual response was unknown (`unknown (data-dependent or incomplete loop)`).
- `axioma-bfs-v2-j13`: expected `O((R * C)^2)` estimate; actual response was unknown (`unknown (data-dependent or incomplete loop)`).
- `axioma-bfs-v2-p11`: expected `O(R * C)` estimate; actual response was unknown (`unknown (data-dependent loop bound)`).

No unexpected estimates occurred on expected-unknown cases; no emitted estimate mismatched its mathematical label; and no execution errors occurred. The observed coverage gaps include Java matrix/grid cases and Python grid component sweep. Treat these as findings from this run, not as a generalization claim.

## Case results

| Case | Language | Expected response / complexity | Actual response / estimate | Comparison | Source SHA-256 |
|---|---|---|---|---|---|
| axioma-bfs-v2-j01 | java | estimate / O(V + E) | estimate / O(V + E) | exact_match | 216b479db758ab27134b82bff666e1c339561ebcf0863cfcd2134650cd937d20 |
| axioma-bfs-v2-j02 | java | estimate / O(S + V + E) | estimate / O(S + V + E) | exact_match | 9ee0c0d70038b29a28d6c6fce9ebd254f18a458f19afb8b40fbefc8e7cb4eed0 |
| axioma-bfs-v2-j03 | java | unknown / O(V + E) | unknown / None | not_applicable_abstention | 889cfb9e0734a97401746f26d48d05f85ecfd1ef3227edf0a31554727bacd4e7 |
| axioma-bfs-v2-j04 | java | unknown / O(V + E) | unknown / None | not_applicable_abstention | 7c195b389540f3f961b48d4ecf50c47f3b9ae8c3e389128d6e98c80e50e51284 |
| axioma-bfs-v2-j05 | java | estimate / O(V^2) | unknown / None | not_applicable_abstention | ec39246eaac54a8b20fec8fc2cce1807463d9cae32a98d388c85666bfa0099ad |
| axioma-bfs-v2-j06 | java | unknown / O(Q * (V + E)) | unknown / None | not_applicable_abstention | 4302bc4f48e8b71ed01c427318cec010e3d8de6ab862d2e343392b265baa6530 |
| axioma-bfs-v2-j07 | java | unknown / O((V + E) log V) | unknown / None | not_applicable_abstention | 284c25fbed7bf46f410f5cf7eb3e6b4c0d54497b79cd584d2b47f7e5fb4357b2 |
| axioma-bfs-v2-j08 | java | unknown / O(V + VE) = O(V(E + 1)) | unknown / None | not_applicable_abstention | 17037d0e839be2b1367515e132e86fa5c5e1a2b3be25b7947e0784cf64a71e3b |
| axioma-bfs-v2-j09 | java | unknown / O(V^2 + E) | unknown / None | not_applicable_abstention | 9bd2de6bec1b1504f75e144d2a906fafb7330402f1286716dd1e9b9bb62c892f |
| axioma-bfs-v2-j10 | java | unknown / O(V + E) | unknown / None | not_applicable_abstention | d3fadf415fa966b80e61966fefe881f038645f5f2084d4d1fdfd3bf96be4ae4f |
| axioma-bfs-v2-j11 | java | estimate / O(R * C) | unknown / None | not_applicable_abstention | 78ef756e81c64358d429c5db96421405e4c5a41a3c15d3890525989aeaa07144 |
| axioma-bfs-v2-j12 | java | estimate / O(R * C) | unknown / None | not_applicable_abstention | c79577dd525413a66c82e66a0c9388a45ca75c095e2fba7c2e4590c8adcf3986 |
| axioma-bfs-v2-j13 | java | estimate / O((R * C)^2) | unknown / None | not_applicable_abstention | 9d4503a0737f7f0b01504c1d766098ea346b4f0cea97562a19ad91c5e77e5238 |
| axioma-bfs-v2-j14 | java | unknown / O(V + E) | unknown / None | not_applicable_abstention | 4846d8fe44b7a56566206c23d60f06c6ca6a25fbfbedf35f483b761280c8e39e |
| axioma-bfs-v2-p01 | python | estimate / O(V + E) | estimate / O(V + E) | exact_match | 26399d442c257b39f52c329965aa198a514f5471e6f50ae6cd59b49746caf5be |
| axioma-bfs-v2-p02 | python | unknown / O(S + V + E) | unknown / None | not_applicable_abstention | 6a5c56e6341311208e1e8b4b4a68e580b0f57219b49947a1e603ab5cbe8d5f45 |
| axioma-bfs-v2-p03 | python | unknown / O(V + E) | unknown / None | not_applicable_abstention | d1a395bb31a5fe587457e683ba234de3a52ba62edceb1bce8c20040475e497cb |
| axioma-bfs-v2-p04 | python | unknown / O(V + E) | unknown / None | not_applicable_abstention | 1fe2d68938c1c7a6a7dca5f0ce3e05b6684cd0fd2d0a6cf12af9124cf29349b8 |
| axioma-bfs-v2-p05 | python | unknown / O(V^2) | unknown / None | not_applicable_abstention | 476d8169b8ac6af72b6070c269b1b797138c3b31ba341534a1f8654f44c976e5 |
| axioma-bfs-v2-p06 | python | unknown / O(Q * (V + E)) | unknown / None | not_applicable_abstention | 9352fa157deb34247aceb3b63f29004c84cdd8aa430926d143d577f7592fc03b |
| axioma-bfs-v2-p07 | python | unknown / O(V + E) | unknown / None | not_applicable_abstention | 28e2b5a872bd71470481770cf9922d9d98ca4985c0726f4b97f0ac580360b52d |
| axioma-bfs-v2-p08 | python | unknown / O(V^2 + E) | unknown / None | not_applicable_abstention | 2b9b3f0617fd144adaabcd13987f293ea1e843da2e1d65bfdcd413396a02c145 |
| axioma-bfs-v2-p09 | python | unknown / O(V + E) | unknown / None | not_applicable_abstention | 24e7bbb638cdf652bcec9cbbe057852bc001e982f03956017590f92746226031 |
| axioma-bfs-v2-p10 | python | unknown / O(N) | unknown / None | not_applicable_abstention | 19e9a6edcbd0e069665f9c363bfb7f8e55004c2b0cfe5c842abe0126b8e0d1ec |
| axioma-bfs-v2-p11 | python | estimate / O(R * C) | unknown / None | not_applicable_abstention | de3b72257eaba0d35e91b18c0f16dc424b37dea631ef930cfe7c23819dd65edb |
| axioma-bfs-v2-p12 | python | unknown / O(R * C) | unknown / None | not_applicable_abstention | f32093739f1765879464563a9110d6eeab439458a992e24ec1736d7b5cf18ef9 |
| axioma-bfs-v2-p13 | python | unknown / O((R * C)^2) | unknown / None | not_applicable_abstention | 776aa08ef1fd2b09f066e98854f6626a2488d4312f6d1fddd4fc3df50356a63c |
| axioma-bfs-v2-p14 | python | unknown / O((V + E) * log(V + E)) | unknown / None | not_applicable_abstention | 7e2474a5b0f9bff24722c54759bd01089326b41d7a2c3bab919697f24fd7824b |

## Commands

Analyzer (executed once):

```powershell
services/api/.venv/Scripts/python evaluation/mode1/run_bfs_v2_predictions.py evaluation/mode1/bfs-fresh-v2-review-2026-10-30/review-packet.jsonl --packet-sha256 d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1 --output evaluation/mode1/bfs-fresh-v2-results-2026-10-30/predictions-v2.jsonl
```

Scorer:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_bfs_v2.py evaluation/mode1/bfs-fresh-v2-review-2026-10-30/gold-labels-v2.json evaluation/mode1/bfs-fresh-v2-results-2026-10-30/predictions-v2.jsonl --output evaluation/mode1/bfs-fresh-v2-results-2026-10-30/score-v2.json --csv evaluation/mode1/bfs-fresh-v2-results-2026-10-30/case-results-v2.csv
```

Harness/regression tests run before evaluation: `services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1/test_bfs_v2_harness.py evaluation/mode1/test_evaluate_complexity.py evaluation/mode1/test_run_reviewed_packet_04.py -q` — **43 passed**. PostgreSQL integration tests were not applicable to this static evaluation.
