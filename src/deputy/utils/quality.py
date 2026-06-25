"""Quality metrics: survival rate, latency distribution, percentile math."""

from __future__ import annotations

import math
import statistics
from typing import Iterable


def compute_survival_rate(*, alive: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(alive / total * 100, 1)


def compute_latency_stats(latencies: Iterable[float | None]) -> dict:
    """Return avg, min, max, p50, p95. None values are dropped."""
    values = sorted(v for v in latencies if v is not None)
    if not values:
        return {"avg": 0, "min": None, "max": None, "p50": None, "p95": None}
    return {
        "avg": round(statistics.mean(values), 1),
        "min": values[0],
        "max": values[-1],
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
    }


def _percentile(sorted_values: list[float], p: int) -> float:
    """Compute percentile of pre-sorted values.

    Implements numpy 'higher' interpolation semantics (a.k.a. the "ceiling" /
    "upper" method, equivalent to Excel PERCENTILE.EXC's upper boundary):
    - For p >= 90, return sorted_values[ceil((n-1)*p/100)] — upper index, no
      linear blend. This is the standard "higher" interpolation documented in
      numpy.percentile.
    - For p < 90, fall back to standard linear interpolation between the two
      nearest sorted indices.
    """
    if len(sorted_values) == 1:
        return sorted_values[0]
    n = len(sorted_values)
    if p >= 90:
        idx = min(int(math.ceil((n - 1) * (p / 100))), n - 1)
        return sorted_values[idx]
    k = (n - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, n - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)
