"""
Iter 107 — TM panel extension-style upgrade regression tests.

Covers:
  A. Auto-invert threshold: snappy default (1 loss), user-tunable via slider,
     and revert threshold is now symmetric with activate threshold.
  B. Manual Chart Type dropdown wired in the Config tab.
  C. New AI tab with all cards + poller wiring.
  D. Panel default width bump (300 → 440 px desktop, 220 → 300 mobile).
  E. `/api/trades/recent-outcomes` endpoint alive + correct shape.
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


class TestIter107AutoInvertSnappy:
    def test_default_threshold_is_one(self):
        src = Path("/app/tampermonkey-src/src/core/config.js").read_text()
        # Default INVERT_AFTER_CONSECUTIVE_LOSSES must be 1 (was 2)
        assert re.search(r"INVERT_AFTER_CONSECUTIVE_LOSSES:\s*1\b", src), (
            "Default should be 1 for snappy invert — did the default change back to 2?"
        )
        # New revert config key must exist and default to 1
        assert re.search(r"INVERT_REVERT_AFTER_LOSSES:\s*1\b", src), (
            "INVERT_REVERT_AFTER_LOSSES missing or not defaulted to 1"
        )

    def test_cooldown_reduced_for_snappier_reaction(self):
        src = Path("/app/tampermonkey-src/src/core/config.js").read_text()
        m = re.search(r"INVERT_COOLDOWN_MS:\s*(\d+)", src)
        assert m, "INVERT_COOLDOWN_MS not found"
        # Iter 107 dropped cooldown from 10000ms → 3000ms
        assert int(m.group(1)) <= 5000, f"cooldown too high: {m.group(1)}ms"

    def test_smart_invert_uses_dynamic_revert_threshold(self):
        src = Path("/app/tampermonkey-src/src/trading/smartInvert.js").read_text()
        assert "INVERT_REVERT_AFTER_LOSSES" in src, (
            "smartInvert.js still uses hardcoded 2-loss revert threshold"
        )
        # The old hardcoded 2-slice comment should be gone
        assert "twoLossesInverted" not in src, (
            "old twoLossesInverted variable should have been renamed"
        )

    def test_threshold_slider_present_in_bundle(self):
        text = BUNDLE_PATH.read_text()
        for marker in ("invert-threshold-slider", "autoinvert-threshold-section",
                       "onInvertThresholdChange"):
            assert marker in text, f"missing {marker} in bundle"


class TestIter107ChartTypeSelector:
    def test_manual_chart_type_dropdown_present(self):
        text = BUNDLE_PATH.read_text()
        assert "chart-type-manual-select" in text, (
            "manual chart-type <select> missing from bundle"
        )
        # Should contain all 5 chart-type options + auto
        for opt in ("heikin_ashi", "candles", "line", "bars", "area"):
            assert opt in text, f"missing chart-type option '{opt}' in bundle"

    def test_chart_type_manual_callback_wired(self):
        idx = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "onChartTypeManualChange" in idx, (
            "onChartTypeManualChange callback not wired"
        )
        # Selecting a manual type should call chartTypeSwitcher.ensure()
        assert "chartTypeSwitcher.ensure(value)" in idx, (
            "manual override doesn't call chartTypeSwitcher.ensure()"
        )


class TestIter107AITab:
    def test_ai_tab_button_present(self):
        text = BUNDLE_PATH.read_text()
        assert '"tab-ai"' in text or "'tab-ai'" in text or "tab-ai" in text, (
            "AI tab button missing from bundle"
        )

    def test_all_ai_cards_present(self):
        text = BUNDLE_PATH.read_text()
        for card in ("ai-confidence-card", "ai-votes-card",
                     "ai-indicators-card", "ai-microstructure-card",
                     "ai-trades-card"):
            assert card in text, f"AI tab missing card '{card}'"

    def test_ai_poller_wired(self):
        text = BUNDLE_PATH.read_text()
        # Distinctive log tag survives minification
        assert "[aiPoller]" in text or "aiPoller" in text, (
            "aiAnalysisPoller not in bundle"
        )
        # Poller must reference all 4 endpoints
        assert "/signals/preview" in text
        assert "/microstructure/models" in text
        assert "/trades/recent-outcomes" in text

    def test_ai_poller_stopped_on_cleanup(self):
        idx = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "aiAnalysisPoller.start" in idx
        assert "aiAnalysisPoller.stop()" in idx


class TestIter107PanelSize:
    def test_default_width_bumped_to_440_desktop(self):
        src = Path("/app/tampermonkey-src/src/ui/panel.js").read_text()
        # Look for the const W declaration
        m = re.search(r"const W = mobile \? (\d+) : (\d+);", src)
        assert m, "could not locate `const W = mobile ? ...` line"
        mobile_w, desktop_w = int(m.group(1)), int(m.group(2))
        assert desktop_w >= 440, f"desktop width too small: {desktop_w}"
        assert mobile_w >= 280, f"mobile width too small: {mobile_w}"

    def test_max_resize_width_at_least_720(self):
        src = Path("/app/tampermonkey-src/src/ui/panel.js").read_text()
        # The resize handler clamps `newW` between MIN and MAX
        m = re.search(r"Math\.max\((\d+),\s*Math\.min\((\d+),\s*startW", src)
        assert m, "resize width clamp not found"
        max_w = int(m.group(2))
        assert max_w >= 720, f"resize max width too small: {max_w}"


class TestIter107RecentOutcomesEndpoint:
    def test_endpoint_responds_with_correct_shape(self):
        try:
            r = requests.get(f"{BASE_URL}/api/trades/recent-outcomes?limit=3",
                             timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200, r.status_code
        payload: Dict[str, Any] = r.json()
        assert "success" in payload
        assert "outcomes" in payload
        assert isinstance(payload["outcomes"], list)

    def test_endpoint_respects_limit(self):
        try:
            r = requests.get(f"{BASE_URL}/api/trades/recent-outcomes?limit=2",
                             timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        outcomes = r.json().get("outcomes", [])
        assert len(outcomes) <= 2

    def test_endpoint_filters_by_asset(self):
        try:
            r = requests.get(
                f"{BASE_URL}/api/trades/recent-outcomes",
                params={"limit": 10, "asset": "EURUSD_OTC"},
                timeout=15,
            )
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        # Every returned row (if any) must match the filter
        for row in r.json().get("outcomes", []):
            assert row.get("asset", "").upper().startswith("EURUSD"), row


class TestIter107VersionBumped:
    def test_bundle_version_at_least_135(self):
        v = Path("/app/tampermonkey-src/version.txt").read_text().strip()
        parts = [int(x) for x in v.split(".")]
        assert tuple(parts) >= (8, 135, 0), f"version regressed: {v}"

    def test_no_regressions_from_iter_100_106(self):
        text = BUNDLE_PATH.read_text()
        # Iter 100 — cycleMode purged
        assert "cycleMode" not in text
        # Iter 101 — favorites clickAsset
        assert "clickAsset" in text
        # Iter 103 — network latency widget
        assert "netlat" in text
        # Iter 104 — SNS direction mode
        assert "sns-direction-mode" in text
        # Iter 106 — heartbeat reporter
        assert "tampermonkey/heartbeat" in text
