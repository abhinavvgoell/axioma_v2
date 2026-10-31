from __future__ import annotations

import re

from evaluate_complexity import CLASSES, UNKNOWN


_CLASS_BY_COMPACT = {re.sub(r"\s+", "", label): label for label in CLASSES}


def normalize_complexity_estimate(estimate: str) -> tuple[str, str | None]:
    """Map an analyzer estimate to a canonical evaluator label without losing spacing."""
    label = estimate.split(" (", maxsplit=1)[0].replace("²", "^2").strip()
    compact = re.sub(r"\s+", "", label)
    if compact.startswith(UNKNOWN):
        return UNKNOWN, None
    canonical = _CLASS_BY_COMPACT.get(compact)
    if canonical is not None:
        return canonical, None
    if compact == "O(V+E)":
        return "O(n)", "Normalized O(V + E) to O(n) using reviewed n = V + E convention."
    return UNKNOWN, f"Estimate {label!r} is outside the predeclared scoring vocabulary."
