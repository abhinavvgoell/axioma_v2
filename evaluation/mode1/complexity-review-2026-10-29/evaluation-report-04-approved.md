# Fresh complexity evaluation — packet 04

- **Run date:** 2026-10-29
- **Dataset:** `axioma-20261029-review-packet-04`
- **Partition:** Calibration / diagnostic; not a final holdout
- **Cases:** 5 (Java 3, Python 2)
- **Human labels:** Approved by the project owner before analysis. Frozen labels: [`gold-reviewed-04.jsonl`](gold-reviewed-04.jsonl), SHA-256 `6b81097959a0c48f430fc6215883a4f843a0b96386463e85c1ad2580e3922f45`.

## Objective and methodology

Measure the current Java/Python static complexity routines on five owner-reviewed source fixtures. The evaluation called the same functions used by the existing calibration replay: `analyze_java_complexity(source, entrypoint)` and `analyze_python_complexity(source, entrypoint)`. It did not change either analyzer. Each case was labeled for worst-case time and auxiliary space before the run. The approved space convention excludes input and returned-output storage, includes auxiliary structures and recursion, and uses the usual scalar word/cell model.

The analyzer does not emit auxiliary-space classes. For space scoring, every eligible case is retained and the prediction is `unknown` (abstention); no benchmark memory measurement is substituted. Unknown estimates count as uncovered and incorrect for conservative accuracy. Exact accuracy among answered is undefined when no case was answered. No cases were ambiguous or excluded.

The packet has no valid benchmark inputs or benchmark configuration. No benchmarks were run, and no asymptotic claim was inferred from runtime measurements. Static estimates and benchmark evidence are separate in the machine-readable output.

## Dataset provenance and case inventory

The five fixtures are from the prepared packet; it lists no external problem IDs. The approved labels and source hashes are in the frozen JSONL. Each source hash matched both the case record and prepared packet manifest before execution. The five families are recursive search, dynamic programming, monotonic stack, grid BFS, and quicksort. The prepared packet is explicitly marked calibration. It must not be described as an untouched final holdout; related algorithm families also appear in earlier development/calibration data.

The complete code snapshots, approved expected labels, source hashes, exact analyzer output, rationale, and static signals are preserved in [`analysis-output-04-approved.json`](analysis-output-04-approved.json). Per-dimension predictions and evidence are in [`predictions-04-approved.jsonl`](predictions-04-approved.jsonl).

## Analyzer version and reproducibility

- Branch: `main`
- Git commit: `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`
- Java static method: `static_java_token_loop_depth`
- Python static method: `static_ast_loop_depth`
- Java analyzer source SHA-256: `247e1e0506acebd384e7f56f6131ef49d61950c91b7802ff5ca47e2118859d1d`
- Python analyzer source SHA-256: `ceacb44a10704a4b02cdee70bc56979f611d628bf13a60615e7c911faecda171`
- Evaluation runner SHA-256: `1f771b5a8d4f2d4c7dc460c7db58a23f1b22645c69cf5d8347a24ae466fcf22f`
- Runtime used for this direct static call: Python 3.14.3 on Windows 11 / AMD64; reported CPU count 16. Host details do not affect the static estimates.
- Overall checkout was dirty with existing user changes; the analyzer source files matched the recorded checkout. No analyzer code was modified.

The run used the clean-checkout Python 3.14.3 interpreter with this PowerShell command (the temporary interpreter path may no longer exist):

```powershell
$py='<temporary-checkout>\services\api\.venv\Scripts\python.exe'; & $py evaluation/mode1/run_reviewed_packet_04.py
```

From a fresh configured checkout, the equivalent command is `services/api/.venv/Scripts/python evaluation/mode1/run_reviewed_packet_04.py`.

The runner verifies the approved label/case hashes, Git commit, and analyzer file hashes before it calls the analyzer. It refuses to overwrite any output. It produced [`analysis-output-04-approved.json`](analysis-output-04-approved.json), [`predictions-04-approved.jsonl`](predictions-04-approved.jsonl), [`evaluation-report-04-approved.json`](evaluation-report-04-approved.json), and [`results-manifest-04-approved.json`](results-manifest-04-approved.json). Their file hashes are recorded in the results manifest.

## Results

### Time complexity

| Measure | Result |
|---|---:|
| Eligible cases | 5 |
| Answered | 0/5 |
| Abstentions | 5/5 |
| Coverage | 0% |
| Exact accuracy among answered | Undefined (no answered cases) |
| Conservative exact accuracy across eligible cases | 0/5 (0%) |

Every family had 0/1 coverage. Java had 0/3 coverage; Python had 0/2. With one case per family and only two languages, those slices are descriptive only.

### Auxiliary-space complexity

| Measure | Result |
|---|---:|
| Eligible cases | 5 |
| Answered | 0/5 |
| Abstentions | 5/5 |
| Coverage | 0% |
| Exact accuracy among answered | Undefined (no answered cases) |
| Conservative exact accuracy across eligible cases | 0/5 (0%) |

This is a dimension-wide unsupported state: the current static analyzer emits no auxiliary-space estimate. Java had 0/3 and Python 0/2 coverage. These figures are not evidence that an emitted space estimate was wrong; none was emitted.

## Error analysis

| Case | Expected time | Prediction | Evidence / likely cause | Follow-up investigation |
|---|---|---|---|---|
| 16 — Recursive binary search (Java) | O(log n) | unknown | The analyzer detects direct recursion, but states that it does not solve recurrences. It does not recognize that each recursive call halves the interval. | Investigate a guarded interval-halving recurrence rule, with near-miss recursion tests. |
| 17 — Memoized Fibonacci (Python) | O(n) | unknown | The analyzer detects self-calls but does not account for `lru_cache` or solve the recurrence/state count. | Investigate memoized recursion and cache-state counting; preserve the approved unit-cost integer assumption. |
| 18 — Next greater element (Java) | O(n) | unknown | The analyzer detects a `while` loop but cannot bound its iteration count. It does not infer that each index is pushed once and popped at most once across the whole run. | Investigate an amortized stack push/pop recognizer and counterexamples where an element can be reprocessed. |
| 19 — Count islands (Python) | O(n²) | unknown | The analyzer detects nested/data-dependent loops but does not connect BFS queue processing, the visited set, and the bounded four-neighbor work per cell. | Investigate grid/graph BFS bounds from visited-state and fixed-degree neighbor traversal. |
| 20 — Last-pivot quicksort (Java) | O(n²) | unknown | Direct recursion is detected but its recurrence is not solved. The method name `sort` also appears as a sorting-call signal, even though those calls are self-recursion. | Investigate worst-case quicksort recurrence and distinguish self-calls from library sort calls. |

All five cases abstained, so there are no wrong emitted time classes to compare. The cases reveal missing coverage for recursion and amortized traversal, not confident incorrect estimates. Space has no prediction method at all in this implementation.

## Limits and interpretation

- This five-case calibration batch measures these exact snippets only; it does not establish general accuracy.
- Selective accuracy is undefined because the analyzer answered none. Reporting “0% accuracy among answered” would be mathematically misleading; 0% above is the separate conservative all-eligible score.
- No benchmark was run. Timings, memory measurements, and operation counts are absent and did not contribute to these scores.
- Case 17's approved label uses the usual DSA scalar-cost model. Python arbitrary-precision bit costs are documented in the label assumptions but are outside this scoring convention.
- Case 17's approved rationale refers to the first/cold call. `lru_cache` is attached at module scope and retains values across later calls; this evaluation labels one cold invocation, not repeated warm-cache calls.
- Previous evaluation outputs remain separate and unchanged. In particular, earlier calibration results are not pooled with this packet or represented as final holdout results.

## Broader evaluation proposal

Use **30 independently reviewed solutions** as the next broad corpus: 20 diagnostic/calibration cases and 10 reserved evaluation cases. The 20 diagnostic cases can comprise the existing 15 reviewed cases plus this five-case packet; the 10 evaluation cases must be newly selected, reviewed, frozen, and left unseen until the analyzer candidate is fixed. Balance Java/Python and cover linear/nested loops, binary search, sorting, hashing, sliding window/two pointers, recursion, tree/graph traversal, and dynamic programming. Split by problem/source and implementation pattern to prevent near-duplicate leakage. Keep the partitions grouped across language variants of the same solution. Ten holdout cases would still be an exploratory sample, not strong evidence for broad accuracy; this 30-case proposal is also below the existing evaluator's 50-distinct-solution readiness marker.

## Recommended next technical milestone

Build a development-only regression set and investigate recurrence handling first: three of five time cases abstained because recursive recurrences are not analyzed. Then investigate amortized stack and BFS bounds. Preserve this packet as calibration data; once used to guide changes, it must not be presented as untouched holdout. A separate auxiliary-space estimator requires its own explicit analysis design and evaluation—benchmark memory observations alone are not a substitute.
