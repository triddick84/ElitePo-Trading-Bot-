"""Iter 146 — RevIN + Temporal Query + TQNet accuracy boosters."""

from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# RevIN
# ---------------------------------------------------------------------------

def test_revin_zero_mean_unit_std_1d():
    from ml.revin import RevIn
    x = np.array([1.10, 1.11, 1.12, 1.11, 1.13, 1.09, 1.15, 1.10])
    st = RevIn().fit_transform(x)
    assert abs(st.x_norm.mean()) < 1e-10
    assert abs(st.x_norm.std() - 1.0) < 1e-10
    # invert round-trip
    recovered = st.invert(st.x_norm)
    assert np.allclose(recovered, x, atol=1e-8)


def test_revin_per_channel_2d():
    from ml.revin import RevIn
    rng = np.random.default_rng(1)
    x = rng.normal([1.0, 100.0, -3.0], [0.1, 5.0, 1.0], size=(64, 3))
    st = RevIn().fit_transform(x)
    for c in range(3):
        assert abs(st.x_norm[:, c].mean()) < 1e-10
        assert abs(st.x_norm[:, c].std() - 1.0) < 1e-10
    recovered = st.invert(st.x_norm)
    assert np.allclose(recovered, x, atol=1e-8)


def test_revin_handles_flat_window():
    """Flat window (std=0) mustn't NaN — clamped to eps."""
    from ml.revin import RevIn
    x = np.ones(30) * 1.234
    st = RevIn(eps=1e-6).fit_transform(x)
    assert not np.any(np.isnan(st.x_norm))
    assert st.std == pytest.approx(1e-6, abs=1e-10) or float(st.std) == pytest.approx(1e-6)


# ---------------------------------------------------------------------------
# Temporal Query layer
# ---------------------------------------------------------------------------

def test_tq_layer_identity_zero_theta_returns_input():
    """With zero-initialised θ and any weights, Q=0 → softmax uniform,
    output = V·W_O broadcasted. But the residual x is added back — so the
    output is the SAME shape and finite."""
    from ml.temporal_query import TemporalQueryLayer, TQConfig
    cfg = TQConfig(channels=1, window=20, period=6, d_model=8)
    layer = TemporalQueryLayer(cfg)
    rng = np.random.default_rng(3)
    x = rng.normal(size=(20, 1))
    h = layer.forward(x, t=0)
    assert h.shape == (20, 1)
    assert np.all(np.isfinite(h))


def test_tq_layer_cycle_phase_dependency():
    """Different `t` (via t mod W) must sample a different theta slice —
    result must differ once θ is populated."""
    from ml.temporal_query import TemporalQueryLayer, TQConfig
    cfg = TQConfig(channels=1, window=8, period=4, d_model=4)
    layer = TemporalQueryLayer(cfg)
    # Populate theta with a distinctive phase pattern
    theta = np.arange((cfg.period + cfg.window) * cfg.channels).reshape(cfg.period + cfg.window, cfg.channels).astype(float)
    layer.set_theta(theta)
    rng = np.random.default_rng(2)
    x = rng.normal(size=(cfg.window, cfg.channels))
    h0 = layer.forward(x, t=0)
    h1 = layer.forward(x, t=1)
    # Different cycle phase must produce different output
    assert not np.allclose(h0, h1)
    # But going one full period ahead lands on the same phase
    h_wrap = layer.forward(x, t=cfg.period)
    assert np.allclose(h0, h_wrap, atol=1e-10)


# ---------------------------------------------------------------------------
# TQNetPredictor
# ---------------------------------------------------------------------------

def test_tqnet_uptrend_produces_bounded_signal():
    from ml.temporal_query import TQNetPredictor, TQConfig
    rng = np.random.default_rng(7)
    # Steady uptrend + noise
    closes = 1.10 + np.cumsum(rng.normal(0, 0.0001, 60)) + np.linspace(0, 0.002, 60)
    pred = TQNetPredictor(TQConfig(channels=1, window=30, period=24))
    r = pred.predict(closes, t=0)
    assert r.direction in ("CALL", "PUT", "NEUTRAL")
    assert 0.0 <= r.confidence <= 1.0
    assert np.isfinite(r.signed_drift)
    assert np.isfinite(r.signed_drift_norm)
    assert 0 <= r.attn_focus_idx < 30
    assert r.cycle_phase == 0


def test_tqnet_reject_short_window():
    from ml.temporal_query import TQNetPredictor, TQConfig
    pred = TQNetPredictor(TQConfig(window=30))
    with pytest.raises(ValueError):
        pred.predict(np.arange(10), t=0)


def test_tqnet_confidence_scales_with_magnitude():
    """A bigger signed drift should give higher confidence (mag-based)."""
    from ml.temporal_query import TQNetPredictor, TQConfig
    cfg = TQConfig(channels=1, window=20, period=6, d_model=4, d_hidden=8, seed=99)
    pred = TQNetPredictor(cfg)
    rng = np.random.default_rng(5)
    weak = 1.10 + rng.normal(0, 1e-5, 30)
    strong = 1.10 + np.linspace(0, 0.05, 30)   # 5% move — huge for forex
    r_weak = pred.predict(weak, t=0)
    r_strong = pred.predict(strong, t=0)
    assert r_strong.confidence >= r_weak.confidence


# ---------------------------------------------------------------------------
# tqnet_service (confluence signal shape)
# ---------------------------------------------------------------------------

def test_tqnet_service_produces_confluence_signal():
    import pandas as pd
    from tqnet_service import tqnet_score_for_df
    rng = np.random.default_rng(11)
    closes = 1.10 + np.cumsum(rng.normal(0, 0.0002, 60)) - np.linspace(0, 0.001, 60)
    df = pd.DataFrame({"close": closes})
    sig = tqnet_score_for_df(df, t=0, asset="EURUSD", timeframe="1m", window=30)
    assert sig["source"] == "ml:tqnet"
    assert sig["direction"] in ("CALL", "PUT", "NEUTRAL")
    assert 0.0 <= sig["confidence"] <= 1.0
    assert sig["asset"] == "EURUSD"
    assert sig["timeframe"] == "1m"
    assert "meta" in sig and "signed_drift" in sig["meta"]


def test_tqnet_service_short_df_returns_neutral():
    import pandas as pd
    from tqnet_service import tqnet_score_for_df
    df = pd.DataFrame({"close": [1.1, 1.2, 1.3]})
    sig = tqnet_score_for_df(df, timeframe="1m", window=30)
    assert sig["direction"] == "NEUTRAL"
    assert sig["confidence"] == 0.0


def test_tqnet_service_handles_missing_close():
    import pandas as pd
    from tqnet_service import tqnet_score_for_df
    df = pd.DataFrame({"open": [1, 2, 3]})
    sig = tqnet_score_for_df(df, timeframe="1m", window=30)
    assert sig["direction"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# Confluence weight registration
# ---------------------------------------------------------------------------

def test_confluence_weight_tqnet_is_recognised():
    from confluence_service import _base_weight_for
    w = _base_weight_for("ml:tqnet")
    # Must resolve to the SPECIFIC ml:tqnet key rather than the ml family default
    assert w == 1.25


def test_confluence_score_picks_up_tqnet_source():
    """Feeding a tqnet signal alongside two other CALL signals must fire."""
    from confluence_service import score_confluence, should_fire
    signals = [
        {"source": "pattern:hs", "direction": "CALL", "confidence": 0.8, "asset": "EURUSD", "timeframe": "1m"},
        {"source": "smart_money:ob", "direction": "CALL", "confidence": 0.7, "asset": "EURUSD", "timeframe": "1m"},
        {"source": "ml:tqnet", "direction": "CALL", "confidence": 0.6, "asset": "EURUSD", "timeframe": "1m"},
    ]
    result = score_confluence(signals, min_sources=3)
    assert result["direction"] == "CALL"
    assert should_fire(result, threshold=0.6, min_sources=3)


# ---------------------------------------------------------------------------
# End-to-end route smoke test
# ---------------------------------------------------------------------------

def test_tqnet_health_route():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.tqnet_routes import router as tqnet_router
    app = FastAPI()
    app.include_router(tqnet_router, prefix="/api")
    client = TestClient(app)
    r = client.get("/api/tqnet/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["sample_signal"]["source"] == "ml:tqnet"


def test_tqnet_predict_route():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.tqnet_routes import router as tqnet_router
    app = FastAPI()
    app.include_router(tqnet_router, prefix="/api")
    client = TestClient(app)
    rng = np.random.default_rng(0)
    closes = list(1.10 + np.cumsum(rng.normal(0, 0.0002, 60)))
    r = client.post("/api/tqnet/predict", json={
        "closes": closes, "asset": "EURUSD", "timeframe": "1m", "window": 30,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "ml:tqnet"
    assert body["direction"] in ("CALL", "PUT", "NEUTRAL")
