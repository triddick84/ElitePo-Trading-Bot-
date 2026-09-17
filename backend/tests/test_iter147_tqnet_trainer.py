"""Iter 147 — TQNet training pipeline tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# _make_windows helper
# ---------------------------------------------------------------------------

def test_make_windows_shapes():
    from ml.tqnet_trainer import _make_windows
    closes = np.arange(20, dtype=float)
    X, y = _make_windows(closes, window=5)
    assert X.shape == (15, 5)
    assert y.shape == (15,)
    # First window is closes[0:5], target is closes[5]
    assert np.array_equal(X[0], closes[:5])
    assert y[0] == closes[5]
    # Last window is closes[14:19], target is closes[19]
    assert np.array_equal(X[-1], closes[14:19])
    assert y[-1] == closes[19]


def test_make_windows_too_short():
    from ml.tqnet_trainer import _make_windows
    X, y = _make_windows(np.arange(3, dtype=float), window=5)
    assert X.shape == (0, 5) or X.size == 0
    assert y.size == 0


# ---------------------------------------------------------------------------
# _batched_loss agrees with pointwise .predict() on a random init
# ---------------------------------------------------------------------------

def test_batched_loss_matches_pointwise_forward():
    """Sanity: the vectorised loss must reproduce what the per-window
    .predict() path would give (up to floating tolerance)."""
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import _flatten, _make_windows, _batched_loss, _unflatten

    cfg = TQConfig(channels=1, window=10, period=6, d_model=4, d_hidden=8, seed=1)
    pred = TQNetPredictor(cfg)
    rng = np.random.default_rng(0)
    closes = 1.10 + np.cumsum(rng.normal(0, 0.001, 40))

    X, y = _make_windows(closes, cfg.window)
    ts = np.arange(X.shape[0], dtype=np.int64)

    # Pointwise loss (loop over windows using .predict())
    losses = []
    for i, (w, yt) in enumerate(zip(X, y)):
        r = pred.predict(w, t=int(ts[i]))
        # predict returns signed_drift in *price units*; we need the
        # normalised drift for comparability with the batched loss
        y_norm = (yt - r.features["close_mean"]) / r.features["close_std"]
        err = r.features["yhat_norm"] - y_norm
        losses.append(err ** 2)
    pointwise_mse = float(np.mean(losses))

    vec = _flatten(pred)
    batched = _batched_loss(vec, X, y, ts, cfg, l2=0.0)

    assert abs(batched - pointwise_mse) < 1e-8


# ---------------------------------------------------------------------------
# Full training run reduces loss and (usually) direction accuracy improves
# ---------------------------------------------------------------------------

def test_fit_tqnet_reduces_loss_on_synthetic_signal():
    """A synthetic sinusoid + drift is easy — L-BFGS must at least reduce
    the loss and *not* make direction accuracy worse."""
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import fit_tqnet, _flatten

    cfg = TQConfig(channels=1, window=20, period=24, d_model=4, d_hidden=8, seed=42)
    pred = TQNetPredictor(cfg)
    rng = np.random.default_rng(3)
    t = np.arange(200)
    closes = 1.10 + 0.005 * np.sin(2 * np.pi * t / 24) \
             + np.cumsum(rng.normal(0, 0.0001, 200)) + 0.0001 * t

    x0 = _flatten(pred).copy()
    rep = fit_tqnet(pred, closes, epochs=15, max_windows=60)

    assert rep.ok
    assert rep.final_loss < rep.initial_loss
    assert rep.improvement > 0
    # Direction accuracy must not degrade meaningfully
    assert rep.trained_direction_accuracy >= rep.baseline_direction_accuracy - 0.05
    # Predictor weights must have moved
    assert not np.allclose(_flatten(pred), x0)


def test_fit_tqnet_short_input_returns_ok_false():
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import fit_tqnet
    pred = TQNetPredictor(TQConfig(window=30))
    rep = fit_tqnet(pred, np.arange(10, dtype=float), epochs=3)
    assert rep.ok is False
    assert "need at least" in rep.message.lower()


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------

def test_save_and_load_weights_roundtrip():
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import (
        fit_tqnet, save_weights, load_weights_if_exists, _flatten,
    )

    cfg = TQConfig(channels=1, window=15, period=6, d_model=4, d_hidden=6, seed=5)
    p1 = TQNetPredictor(cfg)
    rng = np.random.default_rng(9)
    closes = 1.10 + np.cumsum(rng.normal(0, 0.0002, 60))
    rep = fit_tqnet(p1, closes, epochs=10, max_windows=40)
    assert rep.ok

    tmpdir = tempfile.mkdtemp(prefix="tqnet_test_")
    try:
        path = os.path.join(tmpdir, "TEST_1m.npz")
        save_weights(p1, path, rep)
        assert os.path.exists(path)
        assert os.path.exists(path + ".meta.json")

        p2 = TQNetPredictor(cfg)
        # Before load, weights differ
        assert not np.allclose(_flatten(p1), _flatten(p2))
        loaded = load_weights_if_exists(p2, path)
        assert loaded
        # After load, weights identical
        assert np.allclose(_flatten(p1), _flatten(p2), atol=1e-10)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_load_weights_shape_mismatch_returns_false():
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import save_weights, load_weights_if_exists

    # Save weights for a small cfg
    small = TQNetPredictor(TQConfig(window=10, d_model=4, d_hidden=4))
    tmp = tempfile.NamedTemporaryFile(suffix=".npz", delete=False)
    tmp.close()
    try:
        save_weights(small, tmp.name)
        # Try loading into a differently-shaped cfg
        big = TQNetPredictor(TQConfig(window=30, d_model=16, d_hidden=32))
        assert load_weights_if_exists(big, tmp.name) is False
    finally:
        os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Predictor cache invalidation
# ---------------------------------------------------------------------------

def test_predictor_cache_invalidate():
    import tqnet_service
    from ml.temporal_query import TQConfig

    tqnet_service._predictor_cache = {}
    tqnet_service._shared_predictor(TQConfig(), asset="EURUSD", timeframe="1m")
    tqnet_service._shared_predictor(TQConfig(), asset="GBPUSD", timeframe="1m")
    assert len(tqnet_service._predictor_cache) == 2

    dropped = tqnet_service.invalidate_predictor_cache(asset="EURUSD", timeframe="1m")
    assert dropped == 1
    assert len(tqnet_service._predictor_cache) == 1

    dropped_all = tqnet_service.invalidate_predictor_cache()
    assert dropped_all == 1
    assert len(tqnet_service._predictor_cache) == 0


# ---------------------------------------------------------------------------
# Route smoke tests — kick off a training job and poll status
# ---------------------------------------------------------------------------

def _minimal_app():
    from fastapi import FastAPI
    from routes.tqnet_routes import router as tqnet_router
    app = FastAPI()
    app.include_router(tqnet_router, prefix="/api")
    return app


def test_train_route_kicks_off_and_completes():
    """POST /tqnet/train → queued; poll /train/status/{id} → done."""
    from fastapi.testclient import TestClient
    client = TestClient(_minimal_app())
    rng = np.random.default_rng(11)
    t = np.arange(120)
    closes = list(1.10 + 0.003 * np.sin(2 * np.pi * t / 24)
                  + np.cumsum(rng.normal(0, 0.0001, 120)))
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("ml.tqnet_trainer.DEFAULT_WEIGHT_DIR", tmpdir):
            r = client.post("/api/tqnet/train", json={
                "closes": closes, "symbol": "UNITTEST", "timeframe": "1m",
                "window": 15, "epochs": 5, "max_windows": 40,
            })
            assert r.status_code == 200
            job_id = r.json()["job_id"]
            # Poll — with maxiter=5 and 40 windows this finishes in seconds
            import time
            for _ in range(60):
                s = client.get(f"/api/tqnet/train/status/{job_id}").json()
                if s["status"] in ("done", "failed"):
                    break
                time.sleep(0.5)
            assert s["status"] == "done"
            assert s["report"]["ok"] is True
            assert s["report"]["improvement"] > 0


def test_train_route_rejects_short_input():
    from fastapi.testclient import TestClient
    client = TestClient(_minimal_app())
    r = client.post("/api/tqnet/train", json={
        "closes": list(range(20)),   # < window (30) + 5
        "symbol": "X", "timeframe": "1m",
    })
    # min_length=50 on the model → 422 (validation), OR our 400 fires
    assert r.status_code in (400, 422)


def test_train_status_unknown_job_returns_404():
    from fastapi.testclient import TestClient
    client = TestClient(_minimal_app())
    r = client.get("/api/tqnet/train/status/does-not-exist")
    assert r.status_code == 404


def test_weights_list_route():
    from fastapi.testclient import TestClient
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("ml.tqnet_trainer.DEFAULT_WEIGHT_DIR", tmpdir):
            # No weights on disk
            client = TestClient(_minimal_app())
            r = client.get("/api/tqnet/weights")
            assert r.status_code == 200
            body = r.json()
            assert body["count"] == 0
            assert body["weights"] == []


def test_drop_weights_route():
    from fastapi.testclient import TestClient
    from ml.temporal_query import TQNetPredictor, TQConfig
    from ml.tqnet_trainer import save_weights, _weight_path

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("ml.tqnet_trainer.DEFAULT_WEIGHT_DIR", tmpdir):
            path = _weight_path("DROPME", "1m")
            save_weights(TQNetPredictor(TQConfig()), path)
            assert os.path.exists(path)

            client = TestClient(_minimal_app())
            r = client.delete("/api/tqnet/weights/DROPME/1m")
            assert r.status_code == 200
            assert r.json()["removed_files"] >= 1
            assert not os.path.exists(path)
