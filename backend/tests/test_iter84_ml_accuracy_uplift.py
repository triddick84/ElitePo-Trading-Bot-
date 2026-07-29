"""
Iter 84 (Jul 2026) — ML accuracy uplift regression suite.

Locks in Tier 1 + Tier 2 improvements to the AI/ML ensemble:
- `/api/ai-ensemble/predict` returns the new `ensemble_weights`,
  `excluded_models`, `live_accuracies`, `degraded`, and `regime` fields.
- Sub-45% models are correctly EXCLUDED from voting (PPO in current state).
- Regime classifier returns one of the four expected regimes with a
  confidence score.
- `apply_regime_bias` renormalises correctly.
- `compute_weights` handles the "all models trained but below threshold"
  degraded case with the equal-weight fallback documented in the module.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=60, **kwargs)


def _post(path: str, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=60, **kwargs)


# ---------------------------------------------------------------------------
# 1) /api/ai-ensemble/predict returns the new fields
# ---------------------------------------------------------------------------
def test_ensemble_response_shape():
    r = _post("/api/ai-ensemble/predict")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    for key in ("ensemble_weights", "excluded_models", "exclusion_reasons",
                "live_accuracies", "degraded", "regime"):
        assert key in body, f"missing new field: {key}"
    assert isinstance(body["ensemble_weights"], dict)
    assert isinstance(body["excluded_models"], list)
    assert isinstance(body["live_accuracies"], dict)


def test_ensemble_weights_normalise_or_are_zero():
    """The sum of trusted-model weights must be ~1.0 unless all models are
    excluded (in which case they can be all-zero)."""
    body = _post("/api/ai-ensemble/predict").json()
    weights = body["ensemble_weights"] or {}
    total = sum(float(v) for v in weights.values())
    assert (abs(total - 1.0) < 0.02) or (total == 0.0), (
        f"weights must normalise to 1.0 (or all-zero if degraded); got {weights}"
    )


def test_ensemble_excludes_low_accuracy_models():
    """If any model reports accuracy below the min-trusted threshold (45%),
    it must appear in `excluded_models` and its weight must be 0."""
    body = _post("/api/ai-ensemble/predict").json()
    acc = body["live_accuracies"] or {}
    weights = body["ensemble_weights"] or {}
    excluded = set(body["excluded_models"] or [])

    for model_name, a in acc.items():
        if a < 45.0:
            assert model_name in excluded, (
                f"{model_name} @ {a}% should be excluded"
            )
            assert weights.get(model_name, 0.0) == 0.0, (
                f"excluded model {model_name} still has weight {weights.get(model_name)}"
            )


def test_ensemble_regime_field_populated():
    body = _post("/api/ai-ensemble/predict").json()
    regime = body.get("regime") or {}
    assert regime.get("regime") in {
        "trend_up", "trend_down", "range", "high_volatility", "unknown"
    }, f"unexpected regime: {regime.get('regime')}"
    conf = regime.get("confidence")
    assert conf is None or (0 <= float(conf) <= 100)


# ---------------------------------------------------------------------------
# 2) regime_classifier direct unit tests
# ---------------------------------------------------------------------------
def _synth_trend_candles(n: int = 60, up: bool = True):
    price = 1.0
    out = []
    for i in range(n):
        step = 0.001 if up else -0.001
        # Small noise
        noise = 0.0001 * ((i % 5) - 2)
        new = price + step + noise
        out.append({
            "open":  price,
            "close": new,
            "high":  max(price, new) + 0.00005,
            "low":   min(price, new) - 0.00005,
            "volume": 100,
        })
        price = new
    return out


def _synth_range_candles(n: int = 60):
    price = 1.0
    out = []
    for i in range(n):
        # oscillate around 1.0
        delta = 0.0005 if (i % 2 == 0) else -0.0005
        new = price + delta
        out.append({
            "open":  price,
            "close": new,
            "high":  max(price, new) + 0.001,   # big wicks → indecision
            "low":   min(price, new) - 0.001,
            "volume": 100,
        })
        price = new
    return out


def test_regime_classifier_detects_trend_up():
    from regime_classifier import classify_regime
    out = classify_regime(_synth_trend_candles(60, up=True), lookback=50)
    assert out["regime"] in ("trend_up", "trend_down"), out
    # Should be up
    assert out["regime"] == "trend_up", out
    assert out["confidence"] > 40


def test_regime_classifier_detects_trend_down():
    from regime_classifier import classify_regime
    out = classify_regime(_synth_trend_candles(60, up=False), lookback=50)
    assert out["regime"] == "trend_down", out


def test_regime_classifier_detects_range():
    from regime_classifier import classify_regime
    out = classify_regime(_synth_range_candles(60), lookback=50)
    assert out["regime"] in ("range", "high_volatility"), out
    # With big wicks it should classify as range (high_volatility only when
    # the vol_pct or atr_pct clears the threshold — our synthetic sample
    # isn't that violent).


def test_apply_regime_bias_renormalises():
    from regime_classifier import apply_regime_bias
    w = {"stacking": 0.30, "lstm_gru": 0.50, "ppo": 0.20}
    for regime in ("trend_up", "trend_down", "range", "high_volatility"):
        out = apply_regime_bias(w, regime)
        total = sum(out.values())
        assert abs(total - 1.0) < 0.02, f"{regime}: {out} sum={total}"


# ---------------------------------------------------------------------------
# 3) ensemble_weights degraded-case fallback
# ---------------------------------------------------------------------------
class _FakeModel:
    """Test double with a configurable get_stats()."""
    def __init__(self, is_trained: bool, accuracy: float):
        self._t = is_trained
        self._a = accuracy
    def get_stats(self):
        return {"is_trained": self._t, "accuracy": self._a}


def test_compute_weights_all_below_threshold_falls_back_equal():
    from ensemble_weights import compute_weights
    a = _FakeModel(True, 35.0)
    b = _FakeModel(True, 40.0)
    c = _FakeModel(True, 30.0)
    out = compute_weights(stacking_model=a, lstm_gru=b, ppo=c,
                          min_trusted_acc=45.0)
    assert out["degraded"] is True
    total = sum(out["weights"].values())
    assert abs(total - 1.0) < 0.02
    # All three should be exactly equal in the fallback
    vals = list(out["weights"].values())
    assert max(vals) - min(vals) < 0.01


def test_compute_weights_prefers_higher_accuracy():
    from ensemble_weights import compute_weights
    poor = _FakeModel(True, 46.0)   # just above threshold
    great = _FakeModel(True, 70.0)  # strong
    ok = _FakeModel(True, 55.0)
    out = compute_weights(stacking_model=poor, lstm_gru=great, ppo=ok)
    assert out["degraded"] is False
    w = out["weights"]
    assert w["lstm_gru"] > w["ppo"] > w["stacking"], (
        f"weights should be ordered by accuracy: got {w}"
    )


def test_compute_weights_untrained_model_is_excluded():
    from ensemble_weights import compute_weights
    untrained = _FakeModel(False, 80.0)  # high accuracy but not trained
    good = _FakeModel(True, 60.0)
    out = compute_weights(stacking_model=untrained, lstm_gru=good, ppo=None)
    assert "stacking" in out["excluded"]
    assert out["reason"]["stacking"] == "not_trained"
    assert out["weights"]["stacking"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
