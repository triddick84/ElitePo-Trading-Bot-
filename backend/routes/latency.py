"""
Latency REST endpoints — Iter 86 + Iter 103.

Iter 86 endpoints (existing):
  - GET /latency/stats     — rolling p50/p95/p99/p99.9 per API route
  - GET /latency/route     — one route's stats
  - GET /latency/healthy   — health decision used by /signals/latest

Iter 103 endpoints (network probe):
  - GET  /latency/network             — rolling TCP-RTT to PO hosts
  - POST /latency/network/measure     — one-shot probe (returns fresh sample)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from request_latency_histogram import (
    get_all_stats, get_route_stats, is_healthy,
)
from latency_probe_service import network_latency_probe

router = APIRouter()


@router.get("/latency/stats")
async def stats() -> Dict[str, Any]:
    rows = get_all_stats()
    return {"success": True, "count": len(rows), "routes": rows}


@router.get("/latency/route")
async def one_route(route: str) -> Dict[str, Any]:
    return {"success": True, "stat": get_route_stats(route)}


@router.get("/latency/healthy")
async def healthy(
    p99_threshold_ms: float = Query(250.0, ge=25.0, le=10000.0)
) -> Dict[str, Any]:
    return {"success": True, **is_healthy(p99_threshold_ms=p99_threshold_ms)}


# ---------------------------------------------------------------------------
# Iter 103 — Network-latency probe
# ---------------------------------------------------------------------------
@router.get("/latency/network")
async def network_latency(
    label: Optional[str] = Query(None, description="Target label (e.g., 'pocketoption')"),
) -> Dict[str, Any]:
    """Rolling TCP round-trip latency to Pocket Option hosts.

    Returns per-target stats:
      { sample_count, last_ms, min_ms, max_ms, mean_ms,
        p50_ms, p95_ms, p99_ms, p999_ms, probe_count, failure_count }

    When `label` is provided, returns just that target's stats.
    """
    if label:
        return {"success": True, "stats": network_latency_probe.get_stats(label)}
    return {"success": True, "stats": network_latency_probe.get_stats()}


@router.post("/latency/network/measure")
async def network_latency_measure(
    label: Optional[str] = Query(None, description="Target label to probe (default: all)"),
) -> Dict[str, Any]:
    """Fire an immediate probe and return the raw sample. Useful for a
    "ping now" button in the TM panel that doesn't wait for the next
    scheduled tick."""
    result = await network_latency_probe.measure_once(label)
    return {"success": True, "samples": result,
            "stats": network_latency_probe.get_stats(label)}
