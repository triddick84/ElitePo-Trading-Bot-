"""
Network Latency Probe Service — Iter 103 (Feb 2026)

Continuously measures TCP-connect round-trip latency to Pocket Option's
public host from the backend container. Exposes rolling p50 / p95 / p99 /
p99.9 statistics so the trader can see if their network edge is degrading.

Design notes
------------
* Uses `socket.create_connection` with a short timeout — no third-party deps.
* Runs in a background asyncio task; probes every `interval_s` (default 3s).
* Keeps a rolling deque of the last `window` samples (default 300 → ~15 min
  at 3s cadence).
* Non-blocking — probe runs in a thread via `asyncio.to_thread` so the FastAPI
  event loop is never stalled.
* Idempotent start(): safe to call multiple times.

Why the backend? Browser userscripts (GM_xmlhttpRequest) can't do raw TCP,
so we measure server-side and the TM panel polls the result via the
existing REST channel.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import statistics
import time
from collections import deque
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class NetworkLatencyProbe:
    """Background TCP-connect latency probe with rolling window stats."""

    DEFAULT_TARGETS = [
        # (label, host, port). Kept short so probes finish fast.
        ("pocketoption", "pocketoption.com", 443),
        ("po.market",    "po.market",       443),
    ]

    def __init__(self, window: int = 300, interval_s: float = 3.0,
                 timeout_ms: int = 250) -> None:
        self.window = window
        self.interval_s = float(interval_s)
        self.timeout = timeout_ms / 1000.0
        # {label: deque[float ms]}
        self.samples: Dict[str, deque] = {}
        self.last_samples: Dict[str, Optional[float]] = {}
        self.failure_count: Dict[str, int] = {}
        self.probe_count: Dict[str, int] = {}
        self.last_error: Dict[str, str] = {}
        self._task: Optional[asyncio.Task] = None
        self._started_at: Optional[float] = None
        # Targets are mutable so tests / admins can override
        self.targets = list(self.DEFAULT_TARGETS)
        for label, _h, _p in self.targets:
            self.samples[label] = deque(maxlen=self.window)
            self.last_samples[label] = None
            self.failure_count[label] = 0
            self.probe_count[label] = 0
            self.last_error[label] = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Idempotently start the background probe loop."""
        if self._task and not self._task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("[latency_probe] no running loop — start() called too early")
            return
        self._started_at = time.time()
        self._task = loop.create_task(self._run_loop(), name="network-latency-probe")
        logger.info(
            "[latency_probe] started — targets=%s interval=%.1fs window=%d",
            [t[0] for t in self.targets], self.interval_s, self.window,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        logger.info("[latency_probe] stopped")

    async def measure_once(self, label: Optional[str] = None) -> Dict[str, Any]:
        """One-shot measurement of every configured target (or one specific
        target when `label` is supplied). Returns the fresh samples.
        """
        results = {}
        for tlabel, host, port in self.targets:
            if label and tlabel != label:
                continue
            latency_ms = await asyncio.to_thread(self._tcp_connect_ms, host, port)
            self.probe_count[tlabel] = self.probe_count.get(tlabel, 0) + 1
            if latency_ms is None:
                self.failure_count[tlabel] = self.failure_count.get(tlabel, 0) + 1
                results[tlabel] = {"success": False, "error": self.last_error.get(tlabel, "unknown")}
            else:
                self.samples[tlabel].append(latency_ms)
                self.last_samples[tlabel] = latency_ms
                results[tlabel] = {"success": True, "latency_ms": latency_ms}
        return results

    def get_stats(self, label: Optional[str] = None) -> Dict[str, Any]:
        """Return rolling stats. When `label` is None, returns all targets."""
        if label is not None:
            return self._stats_for(label)
        return {tlabel: self._stats_for(tlabel) for tlabel, _h, _p in self.targets}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _tcp_connect_ms(self, host: str, port: int) -> Optional[float]:
        """Blocking TCP-connect probe. Runs off-thread via asyncio.to_thread."""
        start = time.perf_counter_ns()
        try:
            with socket.create_connection((host, port), timeout=self.timeout):
                pass
            return (time.perf_counter_ns() - start) / 1_000_000.0
        except socket.timeout:
            self.last_error[self._label_of(host, port)] = "timeout"
            return None
        except OSError as e:
            self.last_error[self._label_of(host, port)] = f"os_error:{e.errno or 'unknown'}"
            return None
        except Exception as e:
            self.last_error[self._label_of(host, port)] = f"exc:{type(e).__name__}"
            return None

    def _label_of(self, host: str, port: int) -> str:
        for lbl, h, p in self.targets:
            if h == host and p == port:
                return lbl
        return f"{host}:{port}"

    async def _run_loop(self) -> None:
        # First probe immediately; then on the fixed cadence.
        while True:
            try:
                await self.measure_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("[latency_probe] tick error: %s", e)
            try:
                await asyncio.sleep(self.interval_s)
            except asyncio.CancelledError:
                raise

    def _stats_for(self, label: str) -> Dict[str, Any]:
        arr = list(self.samples.get(label, []))
        base = {
            "label": label,
            "sample_count": len(arr),
            "probe_count": int(self.probe_count.get(label, 0)),
            "failure_count": int(self.failure_count.get(label, 0)),
            "last_ms": self.last_samples.get(label),
            "last_error": self.last_error.get(label) or None,
            "window": self.window,
            "interval_s": self.interval_s,
        }
        if not arr:
            base.update({"p50_ms": None, "p95_ms": None, "p99_ms": None, "p999_ms": None,
                         "min_ms": None, "max_ms": None, "mean_ms": None})
            return base
        srt = sorted(arr)
        n = len(srt)

        def pct(p: float) -> float:
            # Nearest-rank percentile — deterministic and matches the classic
            # sorted-index approach shown in the user's Python snippets.
            idx = min(n - 1, max(0, int(round(p * (n - 1)))))
            return srt[idx]

        base.update({
            "min_ms": srt[0],
            "max_ms": srt[-1],
            "mean_ms": statistics.fmean(arr),
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "p999_ms": pct(0.999),
        })
        return base


# Global singleton — imported by routes/latency.py and lifecycle wiring in server.py
network_latency_probe = NetworkLatencyProbe()
