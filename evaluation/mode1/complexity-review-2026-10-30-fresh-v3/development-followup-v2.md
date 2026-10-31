# Development follow-up: Python insertion-sort recognition

This note records a bounded analyzer change prompted by the reviewed v3 calibration case `axioma-20261030-v3-02`. The frozen pilot artifacts and its original prediction remain unchanged.

## Change

The Python static analyzer now recognizes a narrow insertion-sort shape: a forward `range(1, len(sequence))` loop saves the current item, shifts preceding items while the saved item is smaller, decrements the insertion index, and restores the saved item. It reports worst-case `O(n^2)` and documents best-case `O(n)` when the input is already sorted. The estimate assumes constant-time comparisons and indexed access. Other unrecognized data-dependent `while` loops continue to return unknown.

## Verification

- The exact pinned source for `axioma-20261030-v3-02` returns `O(n^2)` with method `static_ast_insertion_sort`; its source SHA-256 is recorded in `development-insertion-sort-diagnostic-v1.json`.
- A near-miss that omits the shifting assignment returns `unknown (data-dependent loop bound)`.
- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_python_complexity.py -o addopts='' -q` — **58 passed**.
- `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_python_complexity.py` — **passed**.
- `git diff --check -- docs/api-contract.md services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_python_complexity.py` — **passed**; Git reported expected LF-to-CRLF conversion warnings for the Windows working tree.

The five-case frozen pilot was not rerun. This single-case calibration diagnostic is not independent evaluation evidence and does not establish general insertion-sort recognition accuracy.
