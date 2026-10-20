# Mode 1 complexity evaluation

This folder contains a small, dependency-free evaluator for a human-reviewed complexity gold set. No benchmark examples or labels are bundled: the project owner must select and label solutions before reporting accuracy.

It also contains a detection evaluator for known-correct controls and intentionally mutated solutions. It consumes Axioma's stored test counts after the evaluator owner joins each report with an independently assigned `correct` or `mutant` label.

## Record format

Create a UTF-8 JSON Lines file, one record per expected/predicted comparison:

```json
{"id":"python-merge-01","method":"static_ast_loop_depth","expected":"O(n log n)","predicted":"O(n log n)","confidence":"low","partition":"calibration"}
{"id":"java-search-01","method":"static_java_token_loop_depth","expected":"O(log n)","predicted":"O(n)","confidence":"low","partition":"evaluation"}
```

`id` identifies the gold-set solution. `method` identifies the Axioma signal being evaluated; use one record for each signal when a report contains both static and measured fits. `expected` is the class assigned by human review, and `predicted` is the class emitted by that signal. The supported ordered classes are `O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, and `O(2^n)`. An estimate outside these classes must be reviewed and mapped under a documented rule before scoring; the script intentionally does not guess.

`confidence` is optional and accepts `high`, `medium`, or `low`. `partition` is optional and accepts `calibration` or `evaluation`; it defaults to `evaluation` for older files. Keep every record for one solution ID in the same partition, even when that ID has rows for multiple methods. The evaluator rejects cross-partition IDs.

Without both partitions, confidence is descriptive only and no calibration metric is reported. With both, the evaluator learns each method's confidence-category accuracy on calibration IDs, then reports Brier score, log loss, and expected calibration error on held-out evaluation IDs. It also reports learned category rates and Wilson intervals. These empirical probabilities are specific to the calibration set; do not describe them as universal confidence values.

The evaluator reports exact accuracy, within-one-class accuracy, per-method and per-partition breakdowns, a confusion matrix, and 95% Wilson intervals. Within-one-class means adjacent entries in the ordered class list above. Intervals are record-level and assume independent observations; when multiple methods are recorded for the same solution, combined intervals are descriptive and method-specific intervals are more informative. Small sets produce wide intervals. The project target remains at least 50 distinct human-reviewed solutions; that count alone does not guarantee useful calibration precision.

## Run

From the repository root:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_complexity.py path/to/gold.jsonl --output evaluation/mode1/report.json
```

The JSON output includes record count, input SHA-256, evaluator version, point estimates, and uncertainty intervals. Preserve the gold JSONL, review notes, partition assignment, and report together for reproducibility. Do not present results from a small or selectively labeled set as general performance.

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

## Labeling and evaluation limits

- Curate at least 50 distinct solutions before using this as the project evaluation; do not create labels by copying Axioma's prediction.
- Have a reviewer inspect the algorithm and its intended input-size variable. For ambiguous algorithms, record the decision and assumptions alongside the dataset.
- Preselect the solutions and labeling rules before running Axioma, then preserve the data file hash and report.
- These are class accuracy metrics only. They do not evaluate bug detection, runtime, memory, or whether the tested implementation represents a broader population. Held-out confidence calibration is available only when separate calibration and evaluation solution IDs are provided; a confidence label without that split is not a calibrated probability.
- A methods-disagree result needs separate rows for the static and measured signals. Do not collapse the two into a favorable single label.
