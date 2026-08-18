"""
Iter 109 — Elite Screener + Elite Score Gate tests.

Covers:
  • Backend elite_screener_service composite math
  • REST endpoints /api/screener/{scan,score,universe}
  • React EliteScreener page wired into App.js
  • Tampermonkey bundle contains all Elite-gate markers + at v8.137.0+
"""

import os
import re
import sys
import pytest
import numpy as np
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
TM_SRC = BACKEND_DIR.parent / "tampermonkey-src" / "src"
TM_BUNDLE = FRONTEND_DIR / "public" / "pocket-option-auto-trader.user.js"


# ---------------------------------------------------------------------------
# Composite math tests
# ---------------------------------------------------------------------------
class TestEliteCompositeMath:
    def _synthetic_candles(self, direction="bullish", n=60):
        """Generate synthetic OHLC with a false-breakout + Fib retrace setup."""
        rng = np.random.default_rng(42)
        base = 1.10000
        candles = []
        for i in range(n):
            if direction == "bullish" and i == n - 5:
                # Wick down below prior swing low then close back up
                o = base + 0.0002
                c = base + 0.0004
                h = base + 0.0006
                l = base - 0.0015
            elif direction == "bearish" and i == n - 5:
                o = base + 0.0002
                c = base - 0.0004
                h = base + 0.0025
                l = base - 0.0006
            else:
                drift = 0.00002 * (rng.random() - 0.5)
                o = base + drift
                c = base + drift + 0.00005 * (rng.random() - 0.5)
                h = max(o, c) + 0.0001 * rng.random()
                l = min(o, c) - 0.0001 * rng.random()
                base = c
            candles.append({"open": o, "high": h, "low": l, "close": c,
                            "timestamp": i * 1000})
        return candles

    def test_compute_elite_score_basic_shape(self):
        from elite_screener_service import compute_elite_score
        candles = self._synthetic_candles("bullish")
        result = compute_elite_score(candles, asset="TEST_OTC", timeframe="1m")
        d = result.to_dict()
        assert d["asset"] == "TEST_OTC"
        assert d["timeframe"] == "1m"
        assert 0 <= d["elite_score"] <= 100
        assert d["direction"] in ("CALL", "PUT", "NEUTRAL")
        assert set(d["sub_scores"].keys()) == {"smt", "sweep", "atr_band",
                                               "ob_fvg", "micro"}
        for v in d["sub_scores"].values():
            assert 0 <= v <= 100

    def test_insufficient_data_returns_zero_score(self):
        from elite_screener_service import compute_elite_score
        result = compute_elite_score(candles=[], asset="X", timeframe="1m")
        d = result.to_dict()
        assert d["elite_score"] == 0.0
        assert d["direction"] == "NEUTRAL"
        assert d["reason"] == "insufficient_data"

    def test_weights_sum_to_one(self):
        from elite_screener_service import DEFAULT_WEIGHTS
        s = sum(DEFAULT_WEIGHTS.values())
        assert abs(s - 1.0) < 0.001

    def test_direction_weighted_vote(self):
        from elite_screener_service import _combine_direction
        # 3 CALL sub-scores at 80 each dominate one PUT at 30
        dirs = {"smt": "CALL", "sweep": "CALL", "atr_band": "CALL",
                "ob_fvg": "PUT", "micro": "NEUTRAL"}
        scores = {"smt": 80, "sweep": 80, "atr_band": 80,
                  "ob_fvg": 30, "micro": 50}
        assert _combine_direction(dirs, scores) == "CALL"

    def test_neutral_direction_when_balanced(self):
        from elite_screener_service import _combine_direction
        dirs = {"smt": "CALL", "sweep": "PUT",
                "atr_band": "NEUTRAL", "ob_fvg": "NEUTRAL", "micro": "NEUTRAL"}
        scores = {"smt": 60, "sweep": 60,
                  "atr_band": 0, "ob_fvg": 0, "micro": 0}
        assert _combine_direction(dirs, scores) == "NEUTRAL"

    def test_microstructure_score_healthy(self):
        from elite_screener_service import score_microstructure
        kyle = {"success": True, "kyle": {"illiquidity_bps": 10.0}}
        gm = {"success": True, "gm": {"adverse_selection_pct": 15.0}}
        score, direction, _ = score_microstructure(kyle, gm)
        assert score >= 90.0
        assert direction == "NEUTRAL"

    def test_microstructure_score_toxic(self):
        from elite_screener_service import score_microstructure
        kyle = {"success": True, "kyle": {"illiquidity_bps": 200.0}}
        gm = {"success": True, "gm": {"adverse_selection_pct": 85.0}}
        score, _, _ = score_microstructure(kyle, gm)
        assert score < 30.0


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------
class TestScreenerEndpoints:
    @pytest.mark.asyncio
    async def test_scan_endpoint_shape(self):
        from routes.screener import screener_scan
        r = await screener_scan(assets="EURUSD_OTC,GBPUSD_OTC",
                                timeframe="1m", lookback=60, min_score=0.0)
        assert r["success"] is True
        assert "count" in r
        assert isinstance(r["results"], list)
        # Each row has full shape even when candles are missing
        for row in r["results"]:
            assert "asset" in row
            assert "elite_score" in row
            assert "direction" in row
            assert row["direction"] in ("CALL", "PUT", "NEUTRAL")
            assert "sub_scores" in row

    @pytest.mark.asyncio
    async def test_scan_default_universe(self):
        from routes.screener import screener_scan, DEFAULT_UNIVERSE
        r = await screener_scan(assets=None, timeframe="1m",
                                lookback=60, min_score=0.0)
        # Response should have exactly the default universe count when no
        # candles are cached (all returned as insufficient_data rows)
        assert r["count"] == len(DEFAULT_UNIVERSE)

    @pytest.mark.asyncio
    async def test_score_single_asset(self):
        from routes.screener import screener_score_one
        r = await screener_score_one(asset="EURUSD_OTC", timeframe="1m",
                                     lookback=60)
        assert r["success"] is True
        assert "result" in r
        assert r["result"]["asset"] == "EURUSD_OTC"

    @pytest.mark.asyncio
    async def test_universe_endpoint(self):
        from routes.screener import screener_universe
        r = await screener_universe()
        assert r["success"] is True
        assert len(r["universe"]) >= 10
        assert "EURUSD_OTC" in r["universe"]


# ---------------------------------------------------------------------------
# React wiring
# ---------------------------------------------------------------------------
class TestReactScreenerWiring:
    def test_component_file_exists(self):
        p = FRONTEND_DIR / "src" / "components" / "EliteScreener.jsx"
        assert p.exists(), "EliteScreener.jsx missing"
        body = p.read_text()
        # Key data-testids
        for tid in ("elite-screener-page", "refresh-btn", "assets-input",
                    "timeframe-select", "min-score-slider", "autorefresh-toggle",
                    "results-table"):
            assert f'data-testid="{tid}"' in body, f"{tid} missing"

    def test_app_wires_screener_route(self):
        p = FRONTEND_DIR / "src" / "App.js"
        body = p.read_text()
        assert 'import EliteScreener from "./components/EliteScreener"' in body
        assert '"elite-screener"' in body
        assert '<EliteScreener />' in body
        assert 'Elite Screener' in body


# ---------------------------------------------------------------------------
# Tampermonkey bundle wiring
# ---------------------------------------------------------------------------
class TestTampermonkeyEliteGate:
    def _bundle(self):
        assert TM_BUNDLE.exists(), "TM bundle not built"
        return TM_BUNDLE.read_text()

    def test_gate_module_source_exists(self):
        p = TM_SRC / "trading" / "eliteScoreGate.js"
        assert p.exists(), "eliteScoreGate.js source missing"
        body = p.read_text()
        assert "setThreshold" in body
        assert "setEnforceDirection" in body
        assert "check(" in body
        assert "/screener/score" in body

    def test_gate_wired_into_appsignalpoller_source(self):
        p = TM_SRC / "trading" / "appSignalPoller.js"
        body = p.read_text()
        assert "eliteScoreGate" in body
        assert "elite_gate" in body

    def test_bundle_contains_elite_gate_markers(self):
        b = self._bundle()
        # UI markers
        assert "Elite Score Gate" in b
        assert "elite-gate-section" in b
        assert "elite-gate-slider" in b
        assert "elite-gate-enforce-direction" in b
        assert "elite-gate-state" in b
        # Endpoint reference
        assert "screener/score" in b
        # State-key
        assert "_eliteGate" in b

    def test_bundle_version_at_least_137(self):
        b = self._bundle()
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", b)
        assert m, "no @version header"
        major, minor, _patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (major, minor) >= (8, 137), f"version {major}.{minor} < 8.137"

    def test_state_schema_persists_elite_gate(self):
        p = TM_SRC / "core" / "state.js"
        body = p.read_text()
        assert "eliteGateThreshold" in body
        assert "eliteGateEnforceDirection" in body
        # Schema version bump
        assert "_v: 7" in body or "'_v': 7" in body


# ---------------------------------------------------------------------------
# No-regression from previous iters
# ---------------------------------------------------------------------------
class TestNoRegression:
    def test_iter108_latency_abstain_still_present(self):
        b = TM_BUNDLE.read_text()
        assert "latency-abstain-slider" in b
        assert "latencyAbstain" in b or "latency_abstain" in b

    def test_iter105_microstructure_endpoint_still_wired(self):
        s = (BACKEND_DIR / "server.py").read_text()
        assert "microstructure_router" in s
        assert "screener_router" in s
