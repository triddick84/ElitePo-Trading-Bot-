"""
Iter 75 (Feb 28, 2026) — regression for v8.75.0 SMOTE + class-weight balancing.

Validates that:
  A. _maybe_smote_balance is wired and exposes a useful status string.
  B. Severely imbalanced training data (≤25% minority class) gets oversampled.
  C. Already-balanced data is left alone (no spurious SMOTE).
  D. ModelMetrics dataclass surfaces `smote_status` + `minority_class_ratio`
     so the UI can audit what happened during training.
  E. End-to-end /api/ml-training/train-from-backtests returns the new fields.
"""
import numpy as np
import requests

API = "http://localhost:8001/api"


def test_maybe_smote_balance_oversamples_imbalanced_data():
    from ml_training_service import _maybe_smote_balance, IMBLEARN_AVAILABLE
    assert IMBLEARN_AVAILABLE, "imbalanced-learn must be installed for SMOTE"
    rng = np.random.RandomState(0)
    X = rng.randn(200, 5)
    # 90/10 imbalance — minority is just 20 samples
    y = np.array([1] * 180 + [0] * 20)
    Xn, yn, status = _maybe_smote_balance(X, y)
    assert "smote-applied" in status, f"Expected SMOTE to fire, got: {status}"
    unique, counts = np.unique(yn, return_counts=True)
    assert len(unique) == 2
    # After SMOTE, both classes should be the same count
    assert counts.min() == counts.max(), "SMOTE must rebalance to equal counts"


def test_maybe_smote_balance_skips_balanced_data():
    from ml_training_service import _maybe_smote_balance
    rng = np.random.RandomState(0)
    X = rng.randn(100, 4)
    # 50/50 split — no need to SMOTE
    y = np.array([0] * 50 + [1] * 50)
    Xn, yn, status = _maybe_smote_balance(X, y)
    assert "skipped" in status and "balanced" in status, f"Expected skip on balanced, got: {status}"
    assert len(Xn) == len(X), "SMOTE must NOT inflate balanced data"


def test_maybe_smote_balance_handles_tiny_minority():
    from ml_training_service import _maybe_smote_balance
    rng = np.random.RandomState(0)
    X = rng.randn(50, 4)
    # 49/1 — minority is too small for default k=5
    y = np.array([1] * 49 + [0] * 1)
    Xn, yn, status = _maybe_smote_balance(X, y)
    # Either SMOTE clamps k automatically (status: smote-failed or smote-applied k=0 → falls back)
    # or it gracefully reports the failure. Either way: must not raise and must return arrays.
    assert isinstance(Xn, np.ndarray) and isinstance(yn, np.ndarray)
    assert "smote" in status.lower(), f"status must mention SMOTE state, got: {status}"


def test_model_metrics_carries_smote_audit_fields():
    from ml_training_service import ModelMetrics
    m = ModelMetrics()
    assert hasattr(m, "smote_status"), "ModelMetrics must expose smote_status"
    assert hasattr(m, "minority_class_ratio"), "ModelMetrics must expose minority_class_ratio"


def test_train_from_backtests_returns_smote_audit_in_response():
    """End-to-end: trainer must surface smote_status + minority_class_ratio
    in the response payload so the frontend can display imbalance info."""
    r = requests.post(
        f"{API}/ml-training/train-from-backtests",
        json={"limit": 50},
        timeout=180,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    # Either we trained models (audit fields present) or we surface a clear
    # diagnostic about insufficient samples.
    if data.get("success") and data.get("models"):
        models = data["models"]
        for name, m in models.items():
            if name == "ensemble":
                continue  # ensemble aggregates so it has no SMOTE field itself
            mt = m.get("metrics", {})
            assert "smote_status" in mt, f"{name} metrics missing smote_status"
            assert "minority_class_ratio" in mt, f"{name} metrics missing minority_class_ratio"
    else:
        assert "total_trades_available" in data, "diagnostic field required on failure"
