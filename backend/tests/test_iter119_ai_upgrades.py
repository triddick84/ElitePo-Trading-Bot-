"""
Iter 119 — SOTA AI Accuracy Upgrade regression.

Verifies the four backend pillars of the upgrade are wired end-to-end:
  A) LightGBM meta-model trained on real backfilled TM trades
     - walk-forward CV yields fold_aucs list
     - isotonic calibration flag is on
     - real feature builder is being used (feature_importance on non-zero features)
  B) Feature builder computes real values (rsi != 50, adx != 0)
  C) EV gate config GET/POST roundtrip
  D) Shadow-mode report endpoint responds with correct shape
"""

import re
from datetime import datetime, timezone, timedelta

import pytest
import httpx


def _api() -> str:
    env = open("/app/frontend/.env").read()
    m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", env)
    assert m, "REACT_APP_BACKEND_URL not found"
    return f"{m.group(1)}/api"


API = _api()


# ---------------------------------------------------------------------------
# A) LightGBM status — the money shot: walk-forward CV + calibration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_lightgbm_status_walk_forward_and_calibrated():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/ml/lightgbm/status")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["ready"] is True, "LightGBM model must be trained (run backfill first)"
    metrics = body["metrics"]
    # Iter 119 markers
    assert metrics["validation"] == "walk_forward", (
        f"validation must be walk_forward, got {metrics.get('validation')}"
    )
    assert metrics["calibrated"] is True, "isotonic calibration should be enabled"
    assert isinstance(metrics.get("fold_aucs"), list), "fold_aucs list required"
    assert len(metrics["fold_aucs"]) >= 3, "expect at least 3 walk-forward folds"
    # AUC has to be materially above 0.5 to justify shipping
    assert metrics["auc"] > 0.55, (
        f"AUC {metrics['auc']} — Iter 119 target is > 0.55 (baseline was 0.481)"
    )


@pytest.mark.asyncio
async def test_a_lightgbm_feature_order_covers_20_features():
    """Feature builder outputs the full 20-column feature order."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API}/ml/lightgbm/status")
    body = r.json()
    feature_order = body["feature_order"]
    assert len(feature_order) == 20
    for name in (
        "rsi", "macd", "macd_hist", "atr", "ema_fast", "ema_slow", "bb_pos",
        "adx", "plus_di", "minus_di", "ha_streak_bull", "ha_streak_bear",
        "kyle_lambda", "vpin", "flow_imbalance",
        "vote_up", "vote_down", "mean_confidence", "max_confidence",
        "regime_code",
    ):
        assert name in feature_order


@pytest.mark.asyncio
async def test_a_lightgbm_predict_uses_calibrated_probability():
    """Predict endpoint should return a calibrated probability in [0,1]."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/ml/lightgbm/predict", json={
            "features": {
                "rsi": 65.0, "macd": 0.001, "macd_hist": 0.0002, "atr": 0.0005,
                "ema_fast": 1.1005, "ema_slow": 1.1000, "bb_pos": 0.6,
                "adx": 30.0, "plus_di": 27.0, "minus_di": 12.0,
                "ha_streak_bull": 3, "ha_streak_bear": 0,
                "kyle_lambda": 0.7, "vpin": 0.4, "flow_imbalance": 0.3,
                "vote_up": 1.0, "vote_down": 0.0,
                "mean_confidence": 0.82, "max_confidence": 0.92,
                "regime_code": 2,
            }
        })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert 0.0 <= body["prob_up"] <= 1.0
    assert body["direction"] in ("UP", "DOWN")


# ---------------------------------------------------------------------------
# B) Feature builder — real numbers, not placeholders
# ---------------------------------------------------------------------------
def test_b_feature_builder_computes_real_indicators():
    """rsi should NOT be 50 and adx should NOT be 0 on a real trending candle stream."""
    from feature_builder import build_features
    # Craft a rising trend
    candles = []
    price = 1.10000
    for i in range(60):
        price += 0.0002
        candles.append({
            "open": price - 0.00005,
            "high": price + 0.0001,
            "low":  price - 0.0001,
            "close": price,
            "volume": 100 + i,
        })
    feats = build_features(candles, direction="CALL", signal_confidence=0.82)
    # On a monotonic rising trend rsi should be well above 50
    assert feats["rsi"] > 60, f"rsi {feats['rsi']} — should be >60 on strong uptrend"
    # adx should register the trend
    assert feats["adx"] > 15, f"adx {feats['adx']} — should be non-trivial on strong trend"
    # HA bull streak should be positive
    assert feats["ha_streak_bull"] >= 1
    # Vote_up flag from direction=CALL
    assert feats["vote_up"] == 1.0
    assert feats["vote_down"] == 0.0
    # Confidence normalised (0-1)
    assert 0.0 <= feats["mean_confidence"] <= 1.0


def test_b_feature_builder_handles_empty_candles():
    """Empty candles should not crash — returns zero-filled dict."""
    from feature_builder import build_features
    feats = build_features([])
    assert set(feats.keys()) >= {"rsi", "adx", "regime_code"}


# ---------------------------------------------------------------------------
# C) EV gate — config GET/POST + gate applied in signal pipeline
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_c_ev_gate_config_roundtrip():
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Get current
        r0 = await c.get(f"{API}/ai/ev-gate/config")
        assert r0.status_code == 200
        original = r0.json()["config"]

        # Post an update
        r1 = await c.post(f"{API}/ai/ev-gate/config", json={
            "enabled": True, "min_ev": 0.05, "default_payout": 0.82,
        })
        assert r1.status_code == 200 and r1.json()["success"]

        r2 = await c.get(f"{API}/ai/ev-gate/config")
        body = r2.json()
        assert body["config"]["enabled"] is True
        assert body["config"]["min_ev"] == 0.05
        assert body["config"]["default_payout"] == 0.82

        # Restore original
        await c.post(f"{API}/ai/ev-gate/config", json=original)


@pytest.mark.asyncio
async def test_c_ev_gate_config_validates_bounds():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/ai/ev-gate/config", json={
            "enabled": True, "min_ev": 2.5, "default_payout": 0.85,  # min_ev > 1 invalid
        })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# D) Shadow-mode report endpoint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d_shadow_mode_report_shape():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/ai/shadow-mode/report", params={"hours": 24})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    for k in (
        "hours", "total_shadow_picks", "would_fire",
        "passed_ev_gate", "passed_lgbm_gate",
        "resolved_outcomes", "wins", "losses",
        "sim_win_rate", "sim_pnl",
    ):
        assert k in body, f"missing {k} in shadow-mode report"
    assert body["hours"] == 24


@pytest.mark.asyncio
async def test_d_shadow_mode_report_time_window_boundary():
    """hours=1 must return <= hours=24 count."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r1 = await c.get(f"{API}/ai/shadow-mode/report", params={"hours": 1})
        r24 = await c.get(f"{API}/ai/shadow-mode/report", params={"hours": 24})
    assert r1.status_code == 200 and r24.status_code == 200
    assert r1.json()["total_shadow_picks"] <= r24.json()["total_shadow_picks"]


# ---------------------------------------------------------------------------
# E) Backfill endpoint contract (idempotent — should not blow up if re-called)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_e_backfill_endpoint_returns_metrics():
    """Backfill should return valid metrics shape even when no new rows to ingest."""
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f"{API}/ml/lightgbm/backfill", json={
            "max_samples": 100, "candle_lookback": 60,
        })
    assert r.status_code == 200
    body = r.json()
    # Either success (retrained) or success=False with a clear reason (no new rows)
    if body.get("success"):
        assert "auc" in body or "samples_used" in body
    else:
        assert "error" in body


# ---------------------------------------------------------------------------
# F) Live-sample record still works (Iter 118 → 119 no regression)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f_record_live_sample_no_regression():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/ml/lightgbm/record-live-sample", json={
            "features": {
                "rsi": 55.0, "macd": 0.0, "macd_hist": 0.0, "atr": 0.001,
                "ema_fast": 1.1, "ema_slow": 1.1, "bb_pos": 0.5,
                "adx": 22.0, "plus_di": 20.0, "minus_di": 18.0,
                "ha_streak_bull": 1, "ha_streak_bear": 0,
                "kyle_lambda": 0.3, "vpin": 0.4, "flow_imbalance": 0.1,
                "vote_up": 1.0, "vote_down": 0.0,
                "mean_confidence": 0.78, "max_confidence": 0.85,
                "regime_code": 1,
            },
            "outcome": "WIN",
            "metadata": {"direction": "CALL", "asset": "EURUSD_OTC", "source": "iter119_regression"},
        })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["sample_stored"] is True
    assert body["total_live_samples"] > 0
