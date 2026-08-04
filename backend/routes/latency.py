"""
Latency REST endpoints — Iter 86.

Exposes rolling p50/p95/p99/p99.9 request latency per route, plus a health
decision used by `/signals/latest` to abstain on time-sensitive signals when
the pipe is degraded.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from request_latency_histogram import (
    get_all_stats, get_route_stats, is_healthy,
)

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
