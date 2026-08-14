"""
Iter 106 — Connection Dashboard + Heartbeat Reporter regression tests.

Covers:
  A) Enriched /api/tampermonkey/status payload has all new fields
  B) Heartbeat endpoint accepts and persists new fields (script_version,
     ssid_bridge_active, current_timeframe, chart_type)
  C) State-bucket logic: fresh / stale / lost / never_seen behaves correctly
  D) TM bundle wires heartbeatReporter and posts to /tampermonkey/heartbeat
  E) React dashboard component present + wired into MobileAutoTraderPage
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


class TestIter106StatusEndpointShape:
    def _get(self) -> Dict[str, Any]:
        r = requests.get(f"{BASE_URL}/api/tampermonkey/status", timeout=15)
        assert r.status_code == 200
        return r.json()

    def test_status_returns_enriched_fields(self):
        try:
            payload = self._get()
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        # Every new field the dashboard needs
        for k in (
            "connection_state", "seconds_since_heartbeat",
            "installed_version", "latest_version", "is_stale",
            "ssid_bridge_active", "active_target", "network_latency",
        ):
            assert k in payload, f"status endpoint missing '{k}'"

    def test_active_target_shape(self):
        try:
            payload = self._get()
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        at = payload["active_target"]
        assert isinstance(at, dict)
        for k in ("asset", "timeframe", "chart_type"):
            assert k in at

    def test_latest_version_is_set(self):
        try:
            payload = self._get()
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        v = payload.get("latest_version") or ""
        assert re.match(r"^\d+\.\d+\.\d+$", v), (
            f"latest_version should be x.y.z; got {v!r}"
        )


class TestIter106HeartbeatIngest:
    def test_heartbeat_persists_new_fields(self):
        try:
            hb = requests.post(
                f"{BASE_URL}/api/tampermonkey/heartbeat",
                json={
                    "script_version": "8.134.0",
                    "ssid_bridge_active": True,
                    "current_asset": "EURUSD_OTC",
                    "current_timeframe": "1m",
                    "chart_type": "candles",
                    "user_agent": "pytest-agent",
                    "page_url": "pocketoption.com",
                },
                timeout=15,
            )
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert hb.status_code == 200, hb.status_code
        assert hb.json().get("success") is True

        # Verify /status now reflects the payload
        status = requests.get(f"{BASE_URL}/api/tampermonkey/status", timeout=15).json()
        assert status["installed_version"] == "8.134.0"
        assert status["ssid_bridge_active"] is True
        at = status["active_target"]
        assert at["asset"] == "EURUSD_OTC"
        assert at["timeframe"] == "1m"
        assert at["chart_type"] == "candles"

    def test_fresh_state_after_recent_heartbeat(self):
        try:
            requests.post(
                f"{BASE_URL}/api/tampermonkey/heartbeat",
                json={"script_version": "8.134.0"}, timeout=15,
            )
            status = requests.get(f"{BASE_URL}/api/tampermonkey/status", timeout=15).json()
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert status["connection_state"] == "fresh", (
            f"expected 'fresh' immediately after heartbeat, got {status['connection_state']}"
        )
        assert status["connection_active"] is True
        assert status["seconds_since_heartbeat"] is not None
        assert status["seconds_since_heartbeat"] < 30

    def test_stale_detection_on_version_downgrade(self):
        """If TM reports an older version than what version.txt says, is_stale=True."""
        try:
            # 8.100 is guaranteed lower than the current bundle
            requests.post(
                f"{BASE_URL}/api/tampermonkey/heartbeat",
                json={"script_version": "8.100.0"}, timeout=15,
            )
            status = requests.get(f"{BASE_URL}/api/tampermonkey/status", timeout=15).json()
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert status["is_stale"] is True
        assert status["installed_version"] == "8.100.0"


class TestIter106BundleWiring:
    def test_bundle_posts_to_heartbeat_endpoint(self):
        text = BUNDLE_PATH.read_text()
        assert "tampermonkey/heartbeat" in text, (
            "compiled bundle doesn't reference /tampermonkey/heartbeat"
        )
        # Payload keys the reporter sends
        for key in ("script_version", "ssid_bridge_active",
                    "current_asset", "current_timeframe"):
            assert key in text, f"heartbeat payload missing '{key}' in bundle"

    def test_reporter_source_module_present(self):
        p = Path("/app/tampermonkey-src/src/trading/heartbeatReporter.js")
        assert p.exists(), "heartbeatReporter.js was not created"
        src = p.read_text()
        assert "class HeartbeatReporter" in src
        assert "backing off" in src.lower() or "BACKOFF" in src.upper()

    def test_index_starts_and_stops_reporter(self):
        idx = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "heartbeatReporter.start()" in idx
        assert "heartbeatReporter.stop()" in idx

    def test_version_bumped(self):
        v = Path("/app/tampermonkey-src/version.txt").read_text().strip()
        parts = [int(x) for x in v.split(".")]
        assert tuple(parts) >= (8, 134, 0), f"version regressed: {v}"


class TestIter106ReactWiring:
    def test_connection_dashboard_component_exists(self):
        p = Path("/app/frontend/src/components/TampermonkeyConnectionDashboard.jsx")
        assert p.exists()
        src = p.read_text()
        # Component must fetch /tampermonkey/status
        assert "/api/tampermonkey/status" in src
        # Auto-refresh cadence
        assert "setInterval" in src
        # Poll cadence should be tight enough for realtime UX (<=5s)
        m = re.search(r"setInterval\([^,]+,\s*(\d+)\s*\)", src)
        assert m, "no setInterval interval found"
        # First interval in the file is the 4s status poll; must be ≤ 5000ms
        assert int(m.group(1)) <= 5000

    def test_mobile_page_uses_dashboard(self):
        src = Path("/app/frontend/src/components/MobileAutoTraderPage.jsx").read_text()
        assert "TampermonkeyConnectionDashboard" in src, (
            "MobileAutoTraderPage does not import the new dashboard"
        )
        assert "<TampermonkeyConnectionDashboard" in src, (
            "MobileAutoTraderPage does not render the new dashboard"
        )

    def test_dashboard_has_key_testids(self):
        src = Path("/app/frontend/src/components/TampermonkeyConnectionDashboard.jsx").read_text()
        for tid in ("tm-connection-dashboard", "tm-conn-hero",
                    "tm-metric-version", "tm-metric-target",
                    "tm-metric-ssid", "tm-metric-latency-p50",
                    "tm-metric-latency-p99", "tm-conn-refresh"):
            assert f'data-testid="{tid}"' in src, f"missing data-testid={tid}"
