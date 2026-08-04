"""
API request-latency histogram — p50/p95/p99/p99.9 per route.

Iter 86 (Jul 2026, P1 · d).

Distinct from `latency_monitor.py` (which tracks per-phase pipeline timings).
This module is a FastAPI **middleware** that records every request's total
handling time and exposes rolling percentiles per route via
`/api/latency/stats`.

Why
---
Per the domain research the user provided, HFT firms optimise for p99 (not
mean). We can't race on µs, but if OUR pipe degrades to 250 ms p99 on
`/signals/latest`, a 5-second binary option is already stale by the time it
lands. The TM script gets a `latency_ok=false` flag and abstains for the
next few cycles.

Everything runs in-process with bounded memory (`deque(maxlen=1000)` per
normalized route). No external metrics stack required.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_MAX_SAMPLES_PER_ROUTE = 1000
_route_latencies: Dict[str, Deque[float]] = defaultdict(
    lambda: deque(maxlen=_MAX_SAMPLES_PER_ROUTE)
)


def _percentile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[idx]


def get_route_stats(route: str) -> Dict[str, Any]:
    samples = list(_route_latencies.get(route, ()))
    if not samples:
        return {"route": route, "count": 0}
    sorted_ms = sorted(samples)
    return {
        "route": route,
        "count": len(samples),
        "min":   round(sorted_ms[0], 2),
        "p50":   round(_percentile(sorted_ms, 0.50), 2),
        "p95":   round(_percentile(sorted_ms, 0.95), 2),
        "p99":   round(_percentile(sorted_ms, 0.99), 2),
        "p999":  round(_percentile(sorted_ms, 0.999), 2),
        "max":   round(sorted_ms[-1], 2),
        "mean":  round(sum(samples) / len(samples), 2),
    }


def get_all_stats() -> List[Dict[str, Any]]:
    out = [get_route_stats(r) for r in _route_latencies.keys()]
    return sorted(out, key=lambda r: -r.get("p99", 0.0))


def is_healthy(p99_threshold_ms: float = 250.0) -> Dict[str, Any]:
    """
    Return `{ok, worst_route, worst_p99}`. If any route's p99 > threshold,
    the pipe is considered degraded and time-sensitive signals should abstain.
    """
    worst_route = None
    worst_p99 = 0.0
    for route, samples in _route_latencies.items():
        if len(samples) < 10:
            continue
        p99 = _percentile(sorted(samples), 0.99)
        if p99 > worst_p99:
            worst_p99 = p99
            worst_route = route
    return {
        "ok": worst_p99 <= p99_threshold_ms,
        "worst_route": worst_route,
        "worst_p99_ms": round(worst_p99, 2),
        "threshold_ms": p99_threshold_ms,
    }


def _normalize_path(path: str) -> str:
    """Strip query, bucket high-cardinality path params like UUIDs / MongoIDs."""
    if "?" in path:
        path = path.split("?", 1)[0]
    parts = path.split("/")
    cleaned = []
    for p in parts:
        if (len(p) >= 20 and any(c.isdigit() for c in p) and "-" in p) \
                or (p.isdigit() and len(p) >= 6):
            cleaned.append("{id}")
        else:
            cleaned.append(p)
    return "/".join(cleaned)


class RequestLatencyMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware — records handling time per route."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            route = f"{request.method} {_normalize_path(request.url.path)}"
            _route_latencies[route].append(elapsed_ms)
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        route = f"{request.method} {_normalize_path(request.url.path)}"
        _route_latencies[route].append(elapsed_ms)
        try:
            response.headers["x-server-time-ms"] = f"{elapsed_ms:.1f}"
        except Exception:
            pass
        return response
