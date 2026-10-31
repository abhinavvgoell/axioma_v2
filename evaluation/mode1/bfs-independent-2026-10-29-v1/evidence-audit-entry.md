# Evidence audit entry — independent BFS evaluation (2026-10-29)

This dated entry supplements the existing mode 1 evidence audit; it does not replace or edit earlier audit conclusions.

## Scope and provenance

- Dataset: `axioma-independent-bfs-2026-10-29-v1`, 22 newly authored snippets (11 Java, 11 Python), across graph adjacency lists, adjacency matrices, grids, visitation variants, repeated traversals, and negative/near-miss queue patterns.
- Labels: `gold-provisional.jsonl`, SHA-256 `9bda67401a794613b4ac01fd351af8f4e0e3904f0c9464d4254efef930d95298`. All 22 labels were authored before analyzer execution but did not receive independent human review; all are provisional.
- Cases: `cases.jsonl`, SHA-256 `ba79da949e040b42ff24426559b41cf88fa1417fcce99c597b136c058037af40`.
- Preregistration: `preregistration.md`, SHA-256 `415aeb1718ca5c000faf27eebb700bc24c4b4be98a7011dcb471f66cfa18a457`.
- Analyzer: Git HEAD `55ba24c3edac23a83ebbf610be63ee3e3b30e15f`; working-tree hashes are in `manifest-pre-run.json` and `run-manifest.json`. Both language analyzers were unchanged during this evaluation.
- Rule version: `bounded_bfs_traversal_v1`.
- Raw predictions and structured evidence: `predictions.jsonl`; aggregate metrics: `results.json`; narrative report: `evaluation-report.md`.
- Historical approved packet 04 labels retained their prior SHA-256: `6b81097959a0c48f430fc6215883a4f843a0b96386463e85c1ad2580e3922f45`.

## Results and caveat

Of 20 scorable cases, Axioma returned 6 concrete estimates: 5 matched the provisional mathematical labels (83.3% selective accuracy at 30.0% coverage). All-case exact rate was 25.0%. Among 10 supported-pattern candidates, it answered 5 (50.0% coverage). It abstained on 11 of 12 cases preregistered to expect `unknown` (91.7% agreement) and produced one unsupported-pattern estimate; that Java grid estimate was false against the provisional `O((R*C)^2)` label. There were no analyzer execution failures. Two potentially nonterminating examples (one per language) were excluded from complexity accuracy/coverage.

These are exploratory metrics on provisional labels, not human-approved accuracy. The one false positive and the abstentions are reviewed and ranked in `evaluation-report.md`. No analyzer rules were tuned from this packet; after inspection, it must now be treated as development/evaluation data and not as a future untouched holdout.

## Verification performed

- `services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1/bfs-independent-2026-10-29-v1/test_independent_bfs_eval.py -q` — 3 passed.
- `services/api/.venv/Scripts/python.exe -m pytest evaluation/mode1 -q` — 34 passed.
- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_java_complexity.py services/worker/tests/test_python_complexity.py -q` — exit code 0; 89 tests passed (pytest was configured without a summary line for this invocation).
- `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/java_complexity.py services/worker/src/axioma_worker/python_complexity.py evaluation/mode1/bfs-independent-2026-10-29-v1/run_independent_bfs_eval.py evaluation/mode1/bfs-independent-2026-10-29-v1/test_independent_bfs_eval.py` — passed.
- `git diff --check` — exit code 0. Git emitted only existing LF-to-CRLF working-copy warnings.
- PostgreSQL integration tests were not run; this evaluation does not change database behavior, and no database availability is claimed.

No submitted programs were compiled or executed. No commits or pushes were made.
