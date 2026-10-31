# Mode 1 complexity evaluation

This folder contains a small, dependency-free evaluator for a human-reviewed complexity gold set. No benchmark examples or labels are bundled: the project owner must select and label solutions before reporting accuracy.

It also contains a detection evaluator for known-correct controls and intentionally mutated solutions. It consumes Axioma's stored test counts after the evaluator owner joins each report with an independently assigned `correct` or `mutant` label.

The optimization evaluator scores output-preservation separately from paired performance measurements. It reports Java wall-time speedup only when the candidate passes every requested equivalence check, has at least four paired increasing input sizes, and its median wall time is lower at every size. Python source-line and opcode reductions are reported as work-count changes, never as wall-clock speedup.

The latency evaluator summarizes completed-job timing from the API database's persisted `jobs` and `job_events` timestamps. It reports queue-to-first-start, latest worker lifecycle, and end-to-end distributions by language. It does not select source code or report payloads, run a load test, or claim an SLO. Failed jobs are included in status counts but excluded from success-latency distributions.

## Record format

Create a UTF-8 JSON Lines file, one record per expected/predicted comparison. Use a separate record for each evaluated dimension:

```json
{"id":"python-merge-01","method":"static_ast_loop_depth","expected":"O(n log n)","predicted":"O(n log n)","confidence":"low","partition":"calibration"}
{"id":"java-search-01","method":"static_java_token_loop_depth","expected":"O(log n)","predicted":"O(n)","confidence":"low","partition":"evaluation"}
{"id":"python-scan-01","method":"static_ast_loop_depth","expected":"O(n)","predicted":"unknown","partition":"evaluation"}
{"id":"python-scan-01","method":"static_ast_loop_depth","dimension":"auxiliary_space","expected":"O(1)","predicted":"O(1)","partition":"evaluation"}
```

`id` identifies the gold-set solution. `method` identifies the Axioma signal being evaluated; use one record for each signal when a report contains both static and measured fits. `expected` is the class assigned by human review, and `predicted` is the class emitted by that signal. The supported ordered classes are `O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, and `O(2^n)`. `predicted` may instead be the literal `unknown` when Axioma abstains; `expected` must be one of the supported classes. An expected or predicted estimate outside the supported classes must be mapped under a documented rule before scoring; the script intentionally does not guess.

`confidence` is optional and accepts `high`, `medium`, or `low`. `partition` is optional and accepts `calibration` or `evaluation`; it defaults to `evaluation` for older files. Keep every record for one solution ID in the same partition, even when that ID has rows for multiple methods. The evaluator rejects cross-partition IDs.

`dimension` is optional and accepts `time` or `auxiliary_space`; it defaults to `time` for existing records. An ID/method pair may appear once in each dimension. When both dimensions are present, metrics are reported independently under `dimensions.time` and `dimensions.auxiliary_space`; no combined accuracy score is produced across unlike dimensions. Each dimension retains its own family, language, method, confidence, and partition breakdowns.

Optional `family` and `language` strings can be included on human-reviewed gold records. The preparation script carries them into joined records, and the evaluator reports `by_family` and `by_language` slices for records that provide those fields. All method rows for one solution ID must agree on its family and language. Older records without either field remain valid; absent metadata is omitted from that slice rather than inferred.

Overall accuracy counts an abstention as not correct. Reports also show coverage and selective accuracy among non-unknown predictions; read those together so abstaining on difficult examples cannot make accuracy look better by itself. The confusion matrix includes an `unknown` prediction column. Confidence calibration excludes abstentions.

Without both partitions, confidence is descriptive only and no calibration metric is reported. With both, the evaluator learns each method's confidence-category accuracy on calibration IDs, then reports Brier score, log loss, and expected calibration error on held-out evaluation IDs. It also reports learned category rates and Wilson intervals. These empirical probabilities are specific to the calibration set; do not describe them as universal confidence values.

The evaluator reports exact accuracy, within-one-class accuracy, per-method and per-partition breakdowns, a confusion matrix, and 95% Wilson intervals. The JSON reports the number of distinct solution IDs separately from prediction rows and marks whether the 50-distinct-solution minimum is met. Within-one-class means adjacent entries in the ordered class list above. Intervals are record-level and assume independent observations; when multiple methods are recorded for the same solution, combined intervals are descriptive and method-specific intervals are more informative. Small sets produce wide intervals. The 50-solution threshold alone does not guarantee useful calibration precision.

## Run

From the repository root:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/prepare_complexity_evaluation.py path/to/reviewed-gold.jsonl path/to/predictions.jsonl --output path/to/joined-evaluation.jsonl
services/api/.venv/Scripts/python evaluation/mode1/evaluate_complexity.py path/to/joined-evaluation.jsonl --output path/to/report.json
```

Keep reviewed labels and Axioma predictions in separate files until review is complete. The gold file has one record per unique solution. Existing time-only labels use `expected`; labels for both dimensions can use `expected_time` and `expected_auxiliary_space`:

```json
{"id":"python-merge-01","expected":"O(n log n)","partition":"calibration","reviewer":"reviewer-1","rationale":"Merge sort divides and merges each level.","source_sha256":"<64 lowercase hex characters>"}
{"id":"java-merge-01","expected_time":"O(n log n)","expected_auxiliary_space":"O(n)","partition":"evaluation","reviewer":"reviewer-1","rationale":"Merge work is n log n and the temporary buffer is linear.","source_sha256":"<64 lowercase hex characters>"}
```

The predictions file has one record per solution, method, and dimension, using values from saved Axioma reports. Omit `dimension` for legacy time records. Normalize any Axioma estimate beginning with `unknown` to the literal `unknown`; retain its full reason in the original report:

```json
{"id":"python-merge-01","method":"static_ast_loop_depth","predicted":"O(n log n)","confidence":"medium","report_sha256":"<64 lowercase hex characters>"}
{"id":"java-merge-01","method":"static_java_token_loop_depth","dimension":"auxiliary_space","predicted":"O(n)","confidence":"low","report_sha256":"<64 lowercase hex characters>"}
```

Compute `source_sha256` from the exact source file reviewed, and `report_sha256` from the saved report file. The preparation script rejects duplicate gold IDs, duplicate solution/method rows, unknown IDs, missing predictions, unsupported classes, invalid hashes, and incomplete coverage. It sorts the joined JSONL deterministically and includes hashes of both input files on every joined row. Then the evaluator's JSON report includes the joined file SHA-256 and evaluator version. These hashes make the artifacts traceable; they do not establish that a reviewer was independent or that a label is correct.

The JSON output includes record count, input SHA-256, evaluator version, point estimates, and uncertainty intervals. Preserve the original gold and prediction files, review notes, partition assignment, joined file, and report together for reproducibility. Do not present results from a small or selectively labeled set as general performance.

## Test-detection evaluation

Create a second JSON Lines file with one record per evaluated solution or mutant:

```json
{"id":"control-001","label":"correct","passed":15,"failed":0,"skipped":0}
{"id":"mutant-001","label":"mutant","passed":14,"failed":1,"skipped":0}
```

The counts should come from the individual stored test records in Axioma's report. A failure means a mutant was detected; any failure on a known-correct control counts as a false positive. A no-failure run with skipped cases is incomplete and excluded from the recall and false-positive denominators. The output includes mutant detection recall, correct-control false-positive rate, precision, confusion counts, exclusions, Wilson intervals, and the input SHA-256. These intervals do not account for dependencies between related mutants from one source solution.

Run it with:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_detection.py path/to/detection.jsonl --output evaluation/mode1/detection-report.json
```

Do not label a solution as correct merely because its configured tests passed. The labels must come from the curated evaluation set, and the results apply only to that set.

## Observed job latency

Run from the repository root after installing the API dependencies and generating local job history:

```powershell
$env:DATABASE_URL = "sqlite:///services/api/axioma.db"
services/api/.venv/Scripts/python evaluation/mode1/evaluate_latency.py --output evaluation/mode1/latency-report.json
```

The report hashes its canonical input records and includes sample counts, nearest-rank p50/p95, minimum and maximum, plus limitations. Queue time ends at the first `running` event. The worker lifecycle starts at the latest `running` event before the current terminal state, which may include recovery time after a retry; it is not CPU time. End-to-end uses job creation through the current terminal event. Only completed jobs with all valid timestamps enter the distributions. Do not interpret a small local sample as a service guarantee. The command reports no measured latency unless the database contains jobs.

## Optimization evaluation

Create a JSON Lines file with one record per proposed optimization candidate. Join the independent candidate identity, equivalence-check counts, and paired measurements from the saved optimization evidence claims:

```json
{"id":"candidate-001","checks":{"requested":8,"checked":8,"passed":8,"failed":0,"skipped":0},"measurements":{"jvm_reflective_wall_time":[{"size":10,"before":10000,"after":9000},{"size":20,"before":20000,"after":18000},{"size":40,"before":40000,"after":36000},{"size":80,"before":80000,"after":72000}]}}
```

`checks` must reconcile (`passed + failed + skipped = checked`). A candidate is preserved only when all requested checks were checked and passed, with no failures or skips. A failure is a counterexample; incomplete records without a failure are excluded from the preservation denominator. Measurements use `{size, before, after}` values from the same report and must have positive finite values and increasing unique sizes. Candidate reports need at least four sizes to contribute to a paired-measurement rate.

Supported measurement keys are `jvm_reflective_wall_time`, `executed_source_line_events`, and `executed_cpython_opcode_events`. For Java, map `elapsed_ns` to `before` and `optimized_elapsed_ns` to `after`. For Python, map `line_events`/`optimized_line_events` or `opcode_events`/`optimized_opcode_events`. Preserve the original report and record its hash alongside the evaluation artifact; the evaluator hashes the joined JSONL input.

Run it from the repository root:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_optimization.py path/to/optimization.jsonl --output evaluation/mode1/optimization-report.json
```

The evaluator does not create labels, declare a candidate useful, or prove general speedup. Its all-sizes rule is deliberately conservative. Python operation-count reductions are not wall-time evidence, and Java wall-time results remain host- and harness-dependent. No performance claim is available until real candidate runs are independently selected and evaluated.

### Preserved local smoke evaluations

- `optimization-preselection-2026-10-22.json` and `optimization-preselection-twosum-2026-10-22.json` record two candidates selected before their measurements. Their raw harness reports, input records, hashes, and combined result are saved as `optimization-source-report-*.json`, `optimization-evaluation-controlled-2026-10-22.jsonl`, and `optimization-report-controlled-2026-10-22.json`. Both candidates passed all configured visible checks and reduced Python line/opcode counts at each of four sizes. This is a two-candidate local smoke sample and does not establish runtime speedup.
- `detection-preselection-2026-10-22.json`, `detection-source-report-2026-10-22.json`, `detection-evaluation-2026-10-22.jsonl`, and `detection-report-2026-10-22.json` preserve one correct control and three intentionally faulty sum implementations. All three mutants failed at least one configured case; the control passed all five. The sample is too small and narrow to generalize.
- `latency-report-controlled-20261022.json` preserves 20 sequential local Python jobs. It is host-specific and is not a service-level objective.

## Labeling and evaluation limits

- Curate at least 50 distinct solutions before using this as the project evaluation; do not create labels by copying Axioma's prediction.
- Have a reviewer inspect the algorithm and its intended input-size variable. For ambiguous algorithms, record the decision and assumptions alongside the dataset.
- Preselect the solutions and labeling rules before running Axioma, then preserve the data file hash and report.
- These are class accuracy and coverage metrics only. They do not evaluate bug detection, runtime, memory, or whether the tested implementation represents a broader population. Held-out confidence calibration is available only when separate calibration and evaluation solution IDs are provided; a confidence label without that split is not a calibrated probability.
- A methods-disagree result needs separate rows for the static and measured signals. Do not collapse the two into a favorable single label.
