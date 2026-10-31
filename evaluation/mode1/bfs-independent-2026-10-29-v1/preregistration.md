# Independent BFS evaluation — preregistration

**Dataset:** `axioma-independent-bfs-2026-10-29-v1`  
**Partition:** new source fixtures; provisional labels  
**Frozen before analyzer execution:** see `manifest-pre-run.json` for case, label, and analyzer source hashes.

## Label status and provenance

The 22 snippets were newly authored for this evaluation and are not copies of case 19 or the earlier BFS unit fixtures. Labels and rationales were written from the source algorithms before running Axioma. No second human reviewer was available, so every label is explicitly provisional and unreviewed. This evaluation must not be described as a human-reviewed or publication-grade independent holdout. The analyzer will run only after this freeze; the case and label files will not be changed after predictions are produced.

No submitted code is compiled or executed. The static Java/Python complexity functions are called directly.

## Case inventory

| ID | Language | Pattern | Expected time | Expected analyzer response |
|---|---|---|---|---|
| bfs-ind-001 | Java | adjacency-list, set guard | O(V + E) | estimate |
| bfs-ind-002 | Java | adjacency-list, boolean visited array | O(V + E) | estimate |
| bfs-ind-003 | Java | adjacency-list, multi-source | O(V + E) | estimate |
| bfs-ind-004 | Java | adjacency matrix | O(V²) | estimate |
| bfs-ind-005 | Java | repeated BFS inside a vertex loop | O(V(V + E)) | unknown |
| bfs-ind-006 | Java | no visited bound; may not terminate | unbounded | unknown; excluded from complexity metrics |
| bfs-ind-007 | Java | hidden neighbor helper representation | O(V + E) | unknown |
| bfs-ind-008 | Java | grid, four directions | O(R * C) | estimate |
| bfs-ind-009 | Java | grid, eight directions | O(R * C) | estimate |
| bfs-ind-010 | Java | full-grid scan inside each neighbor step | O((R * C)²) | unknown |
| bfs-ind-011 | Java | queue drains a list; not BFS | O(N) | unknown |
| bfs-ind-012 | Python | adjacency-list, set guard | O(V + E) | estimate |
| bfs-ind-013 | Python | adjacency-list, multi-source | O(V + E) | estimate |
| bfs-ind-014 | Python | mark on dequeue, expand once | O(V + E) | estimate |
| bfs-ind-015 | Python | adjacency matrix | O(V²) | unknown |
| bfs-ind-016 | Python | repeated BFS inside a vertex loop | O(V(V + E)) | unknown |
| bfs-ind-017 | Python | no visited bound; may not terminate | unbounded | unknown; excluded from complexity metrics |
| bfs-ind-018 | Python | queue drains a task list; not BFS | O(N) | unknown |
| bfs-ind-019 | Python | rectangular grid, four directions | O(R * C) | estimate |
| bfs-ind-020 | Python | grid, eight directions | O(R * C) | unknown |
| bfs-ind-021 | Python | grid neighbors hidden behind helper | O(R * C) | unknown |
| bfs-ind-022 | Python | full-grid scan inside each neighbor step | O((R * C)²) | unknown |

`expected_analyzer_response` is the preregistered decision target. A mathematically known complexity on an unsupported representation can correctly expect `unknown`. `supported_pattern_candidate` identifies cases where the bounded BFS contract should support a concrete estimate; this includes the Python dequeue-time visited variant as an equivalent bounded visitation strategy.

## Preregistered scoring

- Normalize whitespace in complexity expressions only; do not equate different growth classes.
- A case is scorable for complexity accuracy/coverage when `complexity_scorable=true` and a finite `time_complexity` label exists. The two potentially nonterminating cases remain in response-agreement and false-positive analysis but are excluded from complexity accuracy and coverage.
- **Exact accuracy among answered / selective accuracy:** exact truth-label matches divided by concrete predictions on scorable cases. Always report with coverage.
- **Coverage:** concrete predictions divided by all scorable cases.
- **All-case exact rate:** exact concrete predictions divided by all scorable cases; shown as a conservative companion metric.
- **Supported-pattern coverage:** concrete predictions divided by cases with `supported_pattern_candidate=true`.
- **Expected abstention agreement:** `unknown` predictions divided by cases whose expected analyzer response is `unknown`.
- **Negative-case false positives:** concrete estimates on cases expecting `unknown`. Report separately whether an estimate happens to match the provisional mathematical truth; a truth match does not make evidence from an unsupported rule justified.
- Report all metrics by language and pattern/category. Execution failures are counted separately and are not converted into abstentions.
- No cases will be excluded after prediction inspection. There are no ambiguous labels in the provisional set; unreviewed status is disclosed for every case.

## Frozen files

- Cases: `cases.jsonl`
- Provisional gold labels: `gold-provisional.jsonl`
- Hashes, source hashes, analyzer source hashes, and rules: `manifest-pre-run.json`

The analyzer run must refuse to proceed if any frozen case, label, or analyzer source hash differs from the preregistered manifest.
