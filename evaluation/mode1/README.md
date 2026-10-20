# Mode 1 complexity evaluation

This folder contains a small, dependency-free evaluator for a human-reviewed complexity gold set. No benchmark examples or labels are bundled: the project owner must select and label solutions before reporting accuracy.

It also contains a detection evaluator for known-correct controls and intentionally mutated solutions. It consumes Axioma's stored test counts after the evaluator owner joins each report with an independently assigned `correct` or `mutant` label.

## Record format

Create a UTF-8 JSON Lines file, one record per expected/predicted comparison:

```json
{"id":"python-merge-01","method":"static_ast_loop_depth","expected":"O(n log n)","predicted":"O(n log n)","confidence":"low"}
{"id":"java-search-01","method":"static_java_token_loop_depth","expected":"O(log n)","predicted":"O(n)","confidence":"low"}
```

`id` identifies the gold-set solution. `method` identifies the Axioma signal being evaluated; use one record for each signal when a report contains both static and measured fits. `expected` is the class assigned by human review, and `predicted` is the class emitted by that signal. The supported ordered classes are `O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, and `O(2^n)`. An estimate outside these classes must be reviewed and mapped under a documented rule before scoring; the script intentionally does not guess.

`confidence` is optional and accepts `high`, `medium`, or `low`. The output groups accuracy by these labels for inspection, but does not treat them as probabilities or calculate calibration error. The evaluator reports exact accuracy, within-one-class accuracy, method breakdowns, and a confusion matrix. Within-one-class means adjacent entries in the ordered class list above.

## Run

From the repository root:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_complexity.py path/to/gold.jsonl --output evaluation/mode1/report.json
```

The JSON output includes the number of scored records. Preserve the gold JSONL, its review notes, and the output report together for reproducibility. Do not present results from a small or selectively labeled set as general performance.

## Test-detection evaluation

Create a second JSON Lines file with one record per evaluated solution or mutant:

```json
{"id":"control-001","label":"correct","passed":15,"failed":0,"skipped":0}
{"id":"mutant-001","label":"mutant","passed":14,"failed":1,"skipped":0}
```

The counts should come from the individual stored test records in Axioma's report. A failure means a mutant was detected; any failure on a known-correct control counts as a false positive. A no-failure run with skipped cases is incomplete and excluded from the recall and false-positive denominators. The output includes mutant detection recall, correct-control false-positive rate, precision, confusion counts, exclusions, and the input SHA-256.

Run it with:

```powershell
services/api/.venv/Scripts/python evaluation/mode1/evaluate_detection.py path/to/detection.jsonl --output evaluation/mode1/detection-report.json
```

Do not label a solution as correct merely because its configured tests passed. The labels must come from the curated evaluation set, and the results apply only to that set.

## Labeling and evaluation limits

- Curate at least 50 distinct solutions before using this as the project evaluation; do not create labels by copying Axioma's prediction.
- Have a reviewer inspect the algorithm and its intended input-size variable. For ambiguous algorithms, record the decision and assumptions alongside the dataset.
- Preselect the solutions and labeling rules before running Axioma, then preserve the data file hash and report.
- These are class accuracy metrics only. They do not evaluate bug detection, runtime, memory, calibration, or whether the tested implementation represents a broader population.
- A methods-disagree result needs separate rows for the static and measured signals. Do not collapse the two into a favorable single label.
