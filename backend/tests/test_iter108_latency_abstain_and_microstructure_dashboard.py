"""
Iter 108 — Latency Abstain gate + Microstructure Dashboard regression tests.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


# ===========================================================================
# A) Latency-Driven Abstain gate (TM bundle side)
# ===========================================================================
class TestIter108LatencyAbstainBundle:
    def test_gate_module_exists(self):
        p = Path("/app/tampermonkey-src/src/trading/latencyAbstainGate.js")
        assert p.exists(), "latencyAbstainGate.js missing"
        src = p.read_text()
        assert "class LatencyAbstainGate" in src
        for method in ("isPaused", "setThreshold", "register", "getState"):
            assert method in src, f"gate missing {method}()"

    def test_gate_wired_into_appsignalpoller(self):
        src = Path("/app/tampermonkey-src/src/trading/appSignalPoller.js").read_text()
        assert "latencyAbstainGate" in src
        assert "latencyAbstainGate.isPaused()" in src, (
            "appSignalPoller doesn't consult the gate before firing"
        )
        assert "latency_abstain" in src, (
            "aborted_reason=latency_abstain not surfaced in state.lastSignal"
        )

    def test_slider_in_config_tab(self):
        text = BUNDLE_PATH.read_text()
        assert "latency-abstain-slider" in text
        assert "latency-abstain-section" in text
        assert "latency-abstain-state" in text
        assert "onLatencyAbstainThresholdChange" in text

    def test_gate_state_chip_states(self):
        src = Path("/app/tampermonkey-src/src/ui/panel.js").read_text()
        # All three chip states must be defined
        for state in ("healthy", "paused", "off"):
            assert f"'{state}'" in src or f'"{state}"' in src, (
                f"chip state '{state}' not defined in panel.js"
            )

    def test_boot_restores_persisted_threshold(self):
        idx = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "_latencyAbstainThreshold" in idx
        assert "latencyAbstainGate.setThreshold(" in idx
        assert "latencyAbstainGate.register(setLatencyAbstainState)" in idx

    def test_bundle_version_at_least_136(self):
        v = Path("/app/tampermonkey-src/version.txt").read_text().strip()
        parts = [int(x) for x in v.split(".")]
        assert tuple(parts) >= (8, 136, 0), f"version regressed: {v}"


# ===========================================================================
# B) Microstructure Dashboard (React tab)
# ===========================================================================
class TestIter108MicrostructureDashboard:
    def test_component_exists(self):
        p = Path("/app/frontend/src/components/MicrostructureDashboard.jsx")
        assert p.exists()
        src = p.read_text()
        # Must fetch the Iter 105 endpoint
        assert "/api/microstructure/models" in src
        # Auto-refresh cadence must be reasonable
        m = re.search(r"setInterval\(load,\s*(\d+)\s*[),]", src)
        if m:
            assert int(m.group(1)) <= 15_000, f"refresh too slow: {m.group(1)}"

    def test_app_wires_route_and_nav(self):
        src = Path("/app/frontend/src/App.js").read_text()
        assert "MicrostructureDashboard" in src, (
            "App.js does not import MicrostructureDashboard"
        )
        assert 'case "microstructure":' in src, (
            "App.js has no case for 'microstructure'"
        )
        assert '"microstructure"' in src and 'Microstructure' in src

    def test_dashboard_has_all_testids(self):
        src = Path("/app/frontend/src/components/MicrostructureDashboard.jsx").read_text()
        for tid in (
            "microstructure-dashboard", "ms-controls", "ms-kyle-card",
            "ms-gm-card", "ms-comparison", "ms-comparison-table",
            "ms-lookback", "ms-refresh", "ms-custom-asset",
        ):
            assert f'data-testid="{tid}"' in src, f"missing data-testid={tid}"

    def test_dashboard_shows_both_kyle_and_gm_fields(self):
        src = Path("/app/frontend/src/components/MicrostructureDashboard.jsx").read_text()
        # Kyle fields
        for k in ("kyle.lambda", "kyle.beta", "kyle.sigma_v", "kyle.sigma_u",
                  "kyle.illiquidity_bps", "kyle.interpretation"):
            assert k in src, f"Kyle field '{k}' not rendered"
        # GM fields
        for k in ("gm.ask", "gm.bid", "gm.spread_bps", "gm.alpha_informed",
                  "gm.adverse_selection_pct", "gm.interpretation"):
            assert k in src, f"GM field '{k}' not rendered"


# ===========================================================================
# C) Endpoint sanity (must still return correct shape)
# ===========================================================================
class TestIter108MicrostructureEndpoint:
    def test_models_endpoint_returns_both_kyle_and_gm(self):
        try:
            r = requests.get(
                f"{BASE_URL}/api/microstructure/models",
                params={"asset": "EURUSD_OTC", "lookback": 40},
                timeout=20,
            )
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        payload: Dict[str, Any] = r.json()
        assert "kyle_result" in payload
        assert "gm_result" in payload


# ===========================================================================
# D) No regression from prior iters
# ===========================================================================
class TestIter108NoRegression:
    def test_prior_bundle_markers_preserved(self):
        text = BUNDLE_PATH.read_text()
        assert "cycleMode" not in text
        assert "clickAsset" in text
        assert "netlat" in text
        assert "tampermonkey/heartbeat" in text
        # Iter 107 AI tab
        assert "ai-confidence-card" in text
        assert "tab-ai" in text
