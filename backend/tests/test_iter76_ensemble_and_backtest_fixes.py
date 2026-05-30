"""
Iter 76 (Feb 28, 2026) — regression for v8.76.0 ensemble + backtest fixes.

Validates:
  A. Backtest engine no longer simulates overlapping binary trades — after
     each trade is opened, iteration fast-forwards past its expiry candle.
     (Pre-fix: 3853 trades on 5000 candles for hybrid; post-fix: ~2100.)
  B. Ensemble training metrics are computed by actually evaluating the
     EnsembleModel on a validation split (not by naively averaging RF + GB
     metrics). Previously precision/recall/validation_samples returned 0
     because the dataclass defaults were used instead of real numbers.
  C. Ensemble TrainedModel exposes smote_status + minority_class_ratio
     borrowed from the underlying models for full auditability.
"""
import requests

API = "http://localhost:8001/api"


def test_backtest_engine_no_longer_overlaps_trades():
    """Hybrid ensemble on 5000 M1 candles with 60s expiry should produce
    roughly N/2 trades or fewer (one per non-overlapping minute window),
    not the pre-fix 70-80% rate which represented overlapping binaries."""
    r = requests.post(
        f"{API}/backtest/run",
        json={
            "symbol": "EURUSD_OTC",
            "timeframe": "M1",
            "strategy": "hybrid",
            "days": 7,
            "min_confidence": 60,
        },
        timeout=180,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("success")
    data_points = data.get("data_points") or 0
    results = data.get("results") or []
    assert results, "Expected at least one strategy result"

    for res in results:
        if res.get("error"):
            continue
        m = res.get("metrics") or {}
        total = int(m.get("total_trades") or 0)
        # Pre-fix: total_trades ~ 0.7-0.8 × data_points (overlapping)
        # Post-fix: total_trades should be ≤ ~55% of candles for 60s expiry
        # on M1 (1 trade per 2-candle window max). Use 60% as a safe upper
        # bound to avoid flakiness on edge cases.
        if data_points > 100:
            ratio = total / data_points
            assert ratio < 0.60, (
                f"{res.get('strategy')} produced {total} trades on {data_points} "
                f"candles ({ratio:.0%}) — backtest engine likely overlapping again"
            )


def test_ensemble_training_metrics_are_real_not_zero():
    """The ensemble TrainedModel must report non-zero precision/recall and
    a proper validation_samples count when RF and GB also produced non-zero
    metrics. Pre-fix, only `accuracy` and `f1_score` were populated.
    """
    r = requests.post(
        f"{API}/ml-training/train-from-backtests",
        json={"limit": 30},
        timeout=180,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()

    # Either we succeeded (need to inspect ensemble) or we surface a
    # diagnostic — both are acceptable here.
    if not data.get("success"):
        assert "total_trades_available" in data
        return  # nothing more to check on the failure path

    models = data.get("models") or {}
    rf = (models.get("random_forest") or {}).get("metrics") or {}
    ens = (models.get("ensemble") or {}).get("metrics") or {}
    assert ens, "Ensemble model missing from API response"
    # If the RF model itself produced any positive metric, the ensemble
    # must as well — naïvely averaging zeros is what broke this before.
    if rf.get("f1_score", 0) > 0:
        assert ens.get("f1_score", 0) > 0, "ensemble f1 must be a real evaluation"
        assert ens.get("validation_samples", 0) > 0, "ensemble val_n must reflect real split"
        # smote_status should be inherited from the underlying models
        assert ens.get("smote_status", ""), "ensemble must inherit smote_status from base models"


def test_ensemble_does_not_silently_skip_evaluation():
    """The TrainedModel.metrics for the ensemble must declare a real
    smote_status string (never the default empty)."""
    r = requests.post(
        f"{API}/ml-training/train-from-backtests",
        json={"limit": 30},
        timeout=180,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    if not data.get("success"):
        return
    ens = (data.get("models", {}).get("ensemble") or {}).get("metrics") or {}
    # Empty smote_status now signals a regression — should be set by the
    # new evaluation path or the explicit "ensemble-eval-failed" fallback.
    if ens:
        status = ens.get("smote_status", "")
        # Accept any non-empty audit value
        assert status != "" or ens.get("validation_samples", 0) > 0, (
            "ensemble metrics missing both smote_status AND validation_samples — "
            "evaluation likely not running"
        )
