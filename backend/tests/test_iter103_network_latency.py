"""
Iter 103 — Network Latency Probe backend + TM widget regression tests.

Covers:
  A. Probe service unit tests (rolling window, percentile math, stats shape)
  B. /api/latency/network endpoints (GET stats + POST one-shot)
  C. Bundle wiring — networkLatencyPoller + updateNetworkLatency present
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


# ---------------------------------------------------------------------------
# Helper: bring up a tiny TCP listener on a random port so the probe can
# succeed without depending on external connectivity.
# ---------------------------------------------------------------------------
class _LocalTCPListener:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self._th = threading.Thread(target=self._accept_loop, daemon=True)
        self._th.start()

    def _accept_loop(self) -> None:
        while not self._stop:
            try:
                self.sock.settimeout(0.2)
                conn, _ = self.sock.accept()
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break

    def close(self) -> None:
        self._stop = True
        try: self.sock.close()
        except Exception: pass


# ---------------------------------------------------------------------------
# A. Probe service unit tests
# ---------------------------------------------------------------------------
class TestNetworkLatencyProbeService:
    def test_measure_once_records_sample_for_reachable_host(self):
        from latency_probe_service import NetworkLatencyProbe
        listener = _LocalTCPListener()
        try:
            probe = NetworkLatencyProbe(window=50)
            probe.targets = [("local", "127.0.0.1", listener.port)]
            probe.samples = {"local": __import__("collections").deque(maxlen=50)}
            probe.last_samples = {"local": None}
            probe.failure_count = {"local": 0}
            probe.probe_count = {"local": 0}
            probe.last_error = {"local": ""}

            async def _run():
                await probe.measure_once("local")

            asyncio.run(_run())
            stats = probe.get_stats("local")
            assert stats["sample_count"] == 1
            assert stats["last_ms"] is not None and stats["last_ms"] >= 0
            assert stats["failure_count"] == 0
            assert stats["probe_count"] == 1
        finally:
            listener.close()

    def test_measure_once_records_failure_for_unreachable_host(self):
        from latency_probe_service import NetworkLatencyProbe
        probe = NetworkLatencyProbe(window=10, timeout_ms=80)
        # Reserved-for-doc IP that black-holes → guaranteed timeout
        probe.targets = [("unreach", "192.0.2.1", 65530)]
        probe.samples = {"unreach": __import__("collections").deque(maxlen=10)}
        probe.last_samples = {"unreach": None}
        probe.failure_count = {"unreach": 0}
        probe.probe_count = {"unreach": 0}
        probe.last_error = {"unreach": ""}

        async def _run():
            await probe.measure_once("unreach")
        asyncio.run(_run())
        stats = probe.get_stats("unreach")
        assert stats["sample_count"] == 0
        assert stats["failure_count"] == 1
        assert stats["last_error"] is not None

    def test_stats_percentiles_match_nearest_rank(self):
        from latency_probe_service import NetworkLatencyProbe
        probe = NetworkLatencyProbe(window=100)
        probe.targets = [("t", "127.0.0.1", 1)]
        probe.samples = {"t": __import__("collections").deque(maxlen=100)}
        probe.last_samples = {"t": None}
        probe.failure_count = {"t": 0}
        probe.probe_count = {"t": 0}
        probe.last_error = {"t": ""}
        for v in range(1, 101):  # 1..100 ms
            probe.samples["t"].append(float(v))
        stats = probe.get_stats("t")
        assert stats["min_ms"] == 1.0
        assert stats["max_ms"] == 100.0
        assert stats["p50_ms"] == 50.0 or stats["p50_ms"] == 51.0
        assert stats["p99_ms"] in (99.0, 100.0)
        assert stats["p999_ms"] == 100.0


# ---------------------------------------------------------------------------
# B. HTTP endpoint tests
# ---------------------------------------------------------------------------
class TestNetworkLatencyEndpoints:
    def _get(self, path: str) -> Dict[str, Any]:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, r.status_code
        return r.json()

    def test_network_stats_endpoint_shape(self):
        try:
            payload = self._get("/api/latency/network")
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert payload.get("success") is True
        stats = payload.get("stats")
        assert isinstance(stats, dict)
        # Should have at least one target row keyed by label
        assert any(isinstance(v, dict) and "sample_count" in v for v in stats.values())

    def test_network_stats_specific_label(self):
        try:
            payload = self._get("/api/latency/network?label=pocketoption")
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert payload["success"] is True
        row = payload["stats"]
        assert row["label"] == "pocketoption"
        for k in ("sample_count", "probe_count", "failure_count",
                  "p50_ms", "p95_ms", "p99_ms", "p999_ms"):
            assert k in row

    def test_measure_endpoint_returns_fresh_sample(self):
        try:
            r = requests.post(f"{BASE_URL}/api/latency/network/measure",
                              timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        payload = r.json()
        assert payload["success"] is True
        assert "samples" in payload
        # Each sample dict has success + (latency_ms or error)
        for _lbl, sample in payload["samples"].items():
            assert "success" in sample


# ---------------------------------------------------------------------------
# C. Bundle wiring
# ---------------------------------------------------------------------------
class TestTMBundleNetworkLatencyWidget:
    def test_bundle_version_bumped(self):
        text = BUNDLE_PATH.read_text()
        assert "@version      8.132" in text or "@version      8.133" in text

    def test_bundle_contains_network_latency_poller(self):
        text = BUNDLE_PATH.read_text()
        # Look for the poller's distinctive log tag
        assert "netlat" in text, (
            "compiled bundle missing networkLatencyPoller wiring — rebuild via "
            "cd /app/tampermonkey-src && yarn build:deploy"
        )
        assert "/latency/network" in text, "poller doesn't reference the endpoint path"

    def test_bundle_contains_update_network_latency(self):
        text = BUNDLE_PATH.read_text()
        # Marker strings from panel.js updateNetworkLatency + widget HTML
        assert "netlatp99" in text
        assert "network-latency-widget" in text

    def test_no_previous_iter_regressions(self):
        text = BUNDLE_PATH.read_text()
        assert "cycleMode" not in text, "cycleMode leaked back into bundle"
        assert "clickAsset" in text, "Iter 101 clickAsset missing from bundle"
        assert "favCycle" in text, "favoritesCycle missing from bundle"
