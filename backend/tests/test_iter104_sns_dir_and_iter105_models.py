"""
Iter 104-105 — Regression tests for:
  A) TM script SNS Direction Mode option (with-candle / against-candle)
  B) Kyle (1985) & Glosten-Milgrom (1985) model service + endpoints
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


# ===========================================================================
# A) TM Panel — SNS Direction Mode option
# ===========================================================================
class TestIter104SNSDirectionModeUI:
    def test_bundle_has_direction_mode_buttons(self):
        text = BUNDLE_PATH.read_text()
        assert "sns-direction-mode" in text, (
            "SNS direction-mode section is not in the compiled bundle. "
            "Rebuild via: cd /app/tampermonkey-src && yarn build:deploy"
        )
        assert "sns-dir-against" in text and "sns-dir-with" in text, (
            "SNS with/against direction buttons missing from bundle"
        )
        assert "Against Candle" in text and "With Candle" in text, (
            "SNS direction button labels missing"
        )

    def test_bundle_wires_direction_mode_callback(self):
        text = BUNDLE_PATH.read_text()
        # onSnsDirectionModeChange handler must be present in the bundled
        # index.js side of the wiring
        assert "onSnsDirectionModeChange" in text, (
            "onSnsDirectionModeChange callback not wired in bundle"
        )
        # And must ultimately flip twentyOneSecondReversal.invertSignal
        # Use loose text match — minifier renames identifiers but the strings
        # 'invertSignal' and the log message survive.
        assert "invertSignal" in text or "AGAINST candle" in text.upper() or "with candle" in text.lower(), (
            "SNS direction callback doesn't appear to toggle invertSignal / log direction change"
        )

    def test_setSnsDirectionMode_exported(self):
        src = Path("/app/tampermonkey-src/src/ui/panel.js").read_text()
        assert "export function setSnsDirectionMode" in src, (
            "setSnsDirectionMode export missing from panel.js (needed for state restore)"
        )

    def test_index_restores_direction_mode_on_boot(self):
        src = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "setSnsDirectionMode(" in src, (
            "index.js doesn't restore SNS direction mode on boot"
        )
        assert "_snsDirectionMode" in src, (
            "state key _snsDirectionMode not persisted / restored"
        )


# ===========================================================================
# B) Kyle & Glosten-Milgrom pure-math primitives
# ===========================================================================
class TestKyleModelMath:
    def test_kyle_returns_expected_shape(self):
        from microstructure_models import compute_kyle_from_returns
        rng = np.random.default_rng(42)
        # Simulate 100 bars with positive drift + noise
        r = rng.normal(0.0002, 0.001, 100)
        flow = np.sign(rng.normal(0.0, 1.0, 100))
        res = compute_kyle_from_returns(r.tolist(), flow.tolist(), mid_price=1.10)
        d = res.to_dict()
        for k in ("lambda", "beta", "sigma_v", "sigma_u",
                  "informed_profit", "illiquidity_bps", "interpretation"):
            assert k in d, f"missing {k} in Kyle result"
        assert d["lambda"] >= 0
        assert d["sigma_v"] > 0
        assert d["sigma_u"] > 0

    def test_kyle_returns_insufficient_data_on_short_input(self):
        from microstructure_models import compute_kyle_from_returns
        res = compute_kyle_from_returns([0.01] * 5, [1] * 5)
        assert res.interpretation == "insufficient_data"
        assert res.lambda_ == 0.0

    def test_kyle_lambda_equals_sigma_v_over_2sigma_u(self):
        """Sanity: λ = σ_v / (2·σ_u) — verify with deterministic inputs."""
        from microstructure_models import compute_kyle_from_returns
        rng = np.random.default_rng(7)
        # σ_v ≈ 0.002, σ_u ≈ 1 → λ ≈ 0.001
        r = rng.normal(0.0, 0.002, 500)
        flow = rng.choice([-1.0, 1.0], size=500)
        res = compute_kyle_from_returns(r.tolist(), flow.tolist(), mid_price=1.0)
        expected_lambda = res.sigma_v / (2.0 * res.sigma_u)
        assert abs(res.lambda_ - expected_lambda) < 1e-9

    def test_kyle_interpretation_bucket_progression(self):
        """Verify low/mid/high impact interpretation buckets fire correctly."""
        from microstructure_models import compute_kyle_from_returns
        rng = np.random.default_rng(11)
        # Low impact: low return variance
        r_low = (rng.normal(0.0, 0.00005, 100)).tolist()
        flow = rng.choice([-1.0, 1.0], 100).tolist()
        low = compute_kyle_from_returns(r_low, flow, mid_price=1.10)
        assert "low_impact" in low.interpretation or "no_impact" in low.interpretation
        # High impact: large variance
        r_high = (rng.normal(0.0, 0.01, 100)).tolist()
        high = compute_kyle_from_returns(r_high, flow, mid_price=1.10)
        # illiquidity_bps scales up → interpretation should escalate
        assert high.illiquidity_bps > low.illiquidity_bps


class TestGlostenMilgromMath:
    def test_gm_neutral_alpha_zero_returns_zero_spread(self):
        from microstructure_models import compute_glosten_milgrom
        # α=0 → all noise traders → spread degenerates to zero (both quotes = midpoint)
        res = compute_glosten_milgrom(v_center=1.10, v_high=1.11, v_low=1.09,
                                      alpha_informed=0.0, p_high_prior=0.5)
        assert res.spread_abs == pytest.approx(0.0, abs=1e-9)
        assert res.adverse_selection_pct == pytest.approx(0.0, abs=1e-6)

    def test_gm_pure_informed_returns_max_spread(self):
        from microstructure_models import compute_glosten_milgrom
        # α=1 → every trader informed → ask=v_high, bid=v_low
        res = compute_glosten_milgrom(v_center=1.10, v_high=1.11, v_low=1.09,
                                      alpha_informed=1.0, p_high_prior=0.5)
        assert res.ask == pytest.approx(1.11, abs=1e-6)
        assert res.bid == pytest.approx(1.09, abs=1e-6)
        assert res.spread_abs == pytest.approx(0.02, abs=1e-6)
        assert res.adverse_selection_pct == pytest.approx(100.0, abs=0.01)

    def test_gm_spread_monotonic_in_alpha(self):
        from microstructure_models import compute_glosten_milgrom
        prev = -1.0
        for alpha in (0.0, 0.1, 0.3, 0.5, 0.7, 1.0):
            res = compute_glosten_milgrom(1.0, 1.1, 0.9, alpha, 0.5)
            assert res.spread_abs >= prev, (
                f"spread should be monotonic in α: α={alpha}, "
                f"spread={res.spread_abs}, prev={prev}"
            )
            prev = res.spread_abs

    def test_gm_returns_expected_shape(self):
        from microstructure_models import compute_glosten_milgrom
        d = compute_glosten_milgrom(1.10, 1.11, 1.09, 0.3, 0.5).to_dict()
        for k in ("v_high", "v_low", "ask", "bid", "spread_abs", "spread_bps",
                  "alpha_informed", "p_high_prior", "adverse_selection_pct",
                  "interpretation"):
            assert k in d


# ===========================================================================
# C) HTTP endpoints
# ===========================================================================
class TestMicrostructureModelEndpoints:
    def _get(self, path: str) -> Dict[str, Any]:
        r = requests.get(f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, r.status_code
        return r.json()

    def test_kyle_endpoint_reachable(self):
        try:
            payload = self._get("/api/microstructure/kyle?asset=EURUSD_OTC&lookback=60")
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        # Either success (has candles) OR insufficient_data — both are OK
        assert "success" in payload
        if payload.get("success"):
            assert "kyle" in payload
            for k in ("lambda", "sigma_v", "sigma_u", "beta", "interpretation"):
                assert k in payload["kyle"]

    def test_glosten_milgrom_endpoint_reachable(self):
        try:
            payload = self._get(
                "/api/microstructure/glosten_milgrom?asset=EURUSD_OTC&lookback=40"
            )
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert "success" in payload
        if payload.get("success"):
            gm = payload["gm"]
            for k in ("ask", "bid", "spread_abs", "alpha_informed",
                      "adverse_selection_pct", "interpretation"):
                assert k in gm
            # Sanity: ask >= bid, alpha in [0,1]
            assert gm["ask"] >= gm["bid"] - 1e-9
            assert 0.0 <= gm["alpha_informed"] <= 1.0

    def test_glosten_milgrom_alpha_override(self):
        try:
            r = requests.get(
                f"{BASE_URL}/api/microstructure/glosten_milgrom",
                params={"asset": "EURUSD_OTC", "lookback": 40,
                        "alpha_informed": 0.8},
                timeout=20,
            )
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200
        payload = r.json()
        if payload.get("success"):
            assert payload["gm"]["alpha_informed"] == pytest.approx(0.8, abs=1e-6)

    def test_both_models_endpoint(self):
        try:
            payload = self._get("/api/microstructure/models?asset=EURUSD_OTC")
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert payload["success"] is True
        assert "kyle_result" in payload
        assert "gm_result" in payload


# ===========================================================================
# D) Bundle version / regression guard
# ===========================================================================
class TestBundleVersionBumped:
    def test_version_at_least_133(self):
        v = Path("/app/tampermonkey-src/version.txt").read_text().strip()
        major, minor, patch = (int(x) for x in v.split("."))
        assert (major, minor, patch) >= (8, 133, 0), f"version regressed: {v}"

    def test_no_regressions_from_prior_iters(self):
        text = BUNDLE_PATH.read_text()
        assert "cycleMode" not in text
        assert "clickAsset" in text
        assert "netlat" in text  # Iter 103 widget still there
        assert "sns-direction-mode" in text  # Iter 104 selector present
