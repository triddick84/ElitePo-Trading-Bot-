"""
Iter 57 — Out-of-Sample (OOS) validation regression tests.

Verifies:
  1. `train_from_otc` returns OOS fields (cv_accuracy, test_accuracy,
     overfit_gap, overfit_warning, headline_accuracy, train_samples,
     test_samples).
  2. The OOS test_size is 15% of the input.
  3. `model_status.<id>.oos` is exposed via /api/ml/tuning-report.
  4. ml_system instance carries `tuner_oos_metrics` after training.
"""
import os
import asyncio
import sys
import pathlib
import numpy as np
import httpx
from dotenv import load_dotenv

# Allow `import ml_accuracy_tuner` etc. from /app/backend
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BACKEND_URL}/api"


class _FakeMLSystem:
    """Minimal sklearn-compatible stub that mimics ml_system attributes."""

    def __init__(self):
        from sklearn.ensemble import GradientBoostingClassifier
        self.model = GradientBoostingClassifier(n_estimators=20, max_depth=3, random_state=42)
        self.is_trained = False
        self.model_accuracy = 0.0
        self.scaler = None
        self.last_training_time = None
        self.tuner_feature_names = None
        self.tuner_selected_mask = None
        self.tuner_oos_metrics = None

    def _save_model(self):
        pass  # no-op for tests


def _make_synthetic_otc_df(n=500, seed=42):
    import pandas as pd
    rng = np.random.default_rng(seed)
    base = 1.10 + rng.standard_normal(n).cumsum() * 0.0001
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="5s"),
        "open": base,
        "high": base + np.abs(rng.standard_normal(n)) * 0.00005,
        "low": base - np.abs(rng.standard_normal(n)) * 0.00005,
        "close": base + rng.standard_normal(n) * 0.00003,
        "volume": rng.integers(50, 500, n),
        "symbol": "EURUSD_OTC",
    })
    return df


def _run_train(n=500):
    """Helper — runs a single train_from_otc cycle and returns (result, ml_system)."""
    from ml_accuracy_tuner import MLAccuracyTuner
    from unittest.mock import AsyncMock, MagicMock

    fake_db = MagicMock()
    fake_db.__getitem__.return_value = MagicMock()
    tuner = MLAccuracyTuner(fake_db)
    tuner.get_otc_training_data = AsyncMock(return_value=_make_synthetic_otc_df(n))

    ml_system = _FakeMLSystem()
    result = asyncio.run(
        tuner.train_from_otc(ml_system=ml_system, symbols=["EURUSD_OTC"], min_samples=100)
    )
    return result, ml_system


def test_train_from_otc_returns_oos_fields():
    """train_from_otc result must include the OOS metric block."""
    result, _ = _run_train(500)
    assert result.get("success") is True, f"train failed: {result.get('error')}"

    for k in (
        "cv_accuracy", "cv_std", "train_accuracy", "test_accuracy",
        "overfit_gap", "overfit_warning", "headline_accuracy",
        "train_samples", "test_samples", "total_samples",
    ):
        assert k in result, f"missing OOS field: {k}"

    # 15% hold-out invariant
    total = result["total_samples"]
    expected_test = max(1, int(total * 0.15))
    assert result["test_samples"] == expected_test
    assert result["train_samples"] == total - expected_test

    assert 0 <= result["test_accuracy"] <= 100
    assert 0 <= result["cv_accuracy"] <= 100
    assert isinstance(result["overfit_warning"], bool)
    # Headline accuracy is the honest OOS test_accuracy
    assert result["headline_accuracy"] == result["test_accuracy"]


def test_ml_system_persists_oos_metrics():
    """After training, ml_system.tuner_oos_metrics must be populated."""
    _, ml_system = _run_train(400)
    oos = ml_system.tuner_oos_metrics
    assert oos is not None
    for k in ("cv_accuracy", "test_accuracy", "overfit_gap", "overfit_warning", "source"):
        assert k in oos, f"oos missing key {k}"
    assert oos["source"] == "otc_candles_5s"
    assert isinstance(oos["overfit_warning"], bool)


def test_tuning_report_exposes_oos_block():
    """GET /api/ml/tuning-report must include `oos` key in model_status."""
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{API}/ml/tuning-report")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    ms = body.get("model_status", {})
    assert "maximized_v3" in ms or "improved_v2" in ms
    for mid in ("maximized_v3", "improved_v2"):
        if mid in ms:
            assert "oos" in ms[mid], f"{mid} missing oos block"
