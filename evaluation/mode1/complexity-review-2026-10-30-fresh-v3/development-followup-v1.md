# Development follow-up after the external multifamily pilot

This note records a development change informed by the five-case calibration pilot. It does not alter or replace `analysis-output-v1.json`, `predictions-v1.jsonl`, `evaluation-report-v1.json`, or `run-manifest-v1.json`.

## Observed issue

The frozen pilot's `axioma-20261030-v3-03` case is a recursive tree generator using `yield from`. The original saved prediction was `O(n)` while the owner-reviewed worst-case label was `O(n^2)`. The run report remains the authoritative record of that pre-change result.

## Development change

The Python static analyzer now has a bounded rule for a directly recursive tree walk that delegates recursively with `yield from`. It reports worst-case `O(n^2)` and explains the more precise `O(n*h)` sum-of-depths cost (`O(n log n)` for balanced trees), under the no-cycle/no-shared-subtree assumption. It does not apply to arbitrary recursive generators; those continue through the existing recurrence or unknown paths. The result remains a low-confidence heuristic, not a proof.

## Verification and boundaries

- `services/api/.venv/Scripts/python.exe -m pytest services/worker/tests/test_python_complexity.py -o addopts='' -q` — **57 passed**.
- `services/api/.venv/Scripts/python.exe -m ruff check services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_python_complexity.py` — **passed**.
- `git diff --check -- docs/api-contract.md services/worker/src/axioma_worker/python_complexity.py services/worker/tests/test_python_complexity.py` — **passed** (Git printed only line-ending conversion warnings for this Windows working tree).
- The frozen pilot was not rerun; no frozen prediction, report, or manifest was overwritten.

The broad calibration review packet remains separate and pending owner confirmation. No claim about improved evaluation accuracy is made until a new, properly frozen calibration run and a separate untouched evaluation are completed.
