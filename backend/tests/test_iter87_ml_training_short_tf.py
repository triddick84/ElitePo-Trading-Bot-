"""
Iter 87 (Aug 2026) — AI/ML "Train on Price Data" + "Train from Backtests"
must accept 5s / 10s / 15s / 30s timeframes AND lowercase `_otc` asset codes
(the frontend passes lowercase because the legacy `<Select>` values were
written that way).

Guards:
1. Lowercase `_otc` symbol + short-TF → training succeeds (asset must be
   normalised uppercase before hitting OTC pool + OANDA fallback).
2. Thin OTC pool triggers OANDA fallback (raw_len < 400 threshold).
3. Backend `train-from-backtests` accepts `timeframe` and filters
   `backtest_results` by TF before training.
"""

from __future__ import annotations

import os
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _post_train_price(asset: str, tf: str, days: int = 3) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/ml-training/train-on-price-data",
        json={"asset": asset, "timeframe": tf, "days": days},
        timeout=45,
    )
    return r.json()


def _post_train_backtests(asset: str, tf: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/ml-training/train-from-backtests",
        json={"asset": asset, "timeframe": tf, "limit": 200},
        timeout=60,
    )
    return r.json()


# ---------------------------------------------------------------------------
# 1) Lowercase OTC + short-TF must succeed (asset normalisation)
# ---------------------------------------------------------------------------
def test_train_price_lowercase_otc_5s():
    d = _post_train_price("EURUSD_otc", "5s")
    assert d.get("success") is True, f"Expected success, got: {d.get('error')}"
    assert d.get("candles_used", 0) >= 100
    assert d.get("data_source") in ("otc_pool_or_oanda", "oanda")


def test_train_price_lowercase_otc_30s():
    d = _post_train_price("USDJPY_otc", "30s", days=7)
    assert d.get("success") is True, f"Expected success, got: {d.get('error')}"
    # USDJPY_otc 30s used to fail with "zero models" due to thin OTC pool +
    # feature-shrink. OANDA fallback (raw_len<400 threshold) now covers it.
    assert d.get("candles_used", 0) >= 500


def test_train_price_short_tf_variants_supported():
    # 5s / 10s / 15s / 30s must all resolve via the tf_map (backend never 400s)
    for tf in ("5s", "10s", "15s", "30s"):
        d = _post_train_price("EURUSD_otc", tf, days=3)
        assert d.get("success") is True, f"tf={tf} failed: {d.get('error')}"


# ---------------------------------------------------------------------------
# 2) Train-from-backtests scoping by asset + timeframe
# ---------------------------------------------------------------------------
def test_train_from_backtests_accepts_timeframe_filter():
    # 1m has plenty of stored backtests → should succeed
    d = _post_train_backtests("all", "1m")
    assert d.get("success") is True, f"1m all failed: {d.get('error')}"
    assert d.get("timeframe_filter") == "1m"
    # All 3 models trained
    models = d.get("models") or {}
    assert set(models.keys()) >= {"random_forest", "gradient_boosting", "ensemble"}
    # Real metrics, not defaults
    for name in ("random_forest", "gradient_boosting", "ensemble"):
        met = models[name].get("metrics") or {}
        assert met.get("validation_samples", 0) > 0, f"{name} val_n=0"


def test_train_from_backtests_rejects_empty_scope():
    d = _post_train_backtests("all", "999h")  # bogus TF
    assert d.get("success") is False
    assert "Insufficient" in (d.get("error") or "")
    assert d.get("timeframe_filter") == "999h"


def test_train_from_backtests_all_timeframe_works():
    d = _post_train_backtests("all", "all")
    assert d.get("success") is True
    assert d.get("timeframe_filter") == "all"


# ---------------------------------------------------------------------------
# 3) Error surface — clearer message on zero-models failure
# ---------------------------------------------------------------------------
def test_train_price_error_message_actionable():
    # Pick an impossibly narrow window to force "not enough candles"
    d = _post_train_price("NEVER_TRADED_XYZ", "5s", days=1)
    assert d.get("success") is False
    err = d.get("error") or ""
    # Should NOT be the old generic "zero models" wording
    assert "Insufficient REAL price data" in err or "raw candles" in err


# ---------------------------------------------------------------------------
# 4) Iter 88 — train-on-price-data must register an ensemble alongside RF+GB
# ---------------------------------------------------------------------------
def test_train_price_registers_ensemble():
    d = _post_train_price("EURUSD_otc", "30s", days=3)
    assert d.get("success") is True, f"Setup failed: {d.get('error')}"
    models = d.get("models") or {}
    # All three models must be present
    assert set(models.keys()) >= {"random_forest", "gradient_boosting", "ensemble"}, \
        f"Missing models — got {list(models.keys())}"
    # Ensemble must have real metrics (not defaults)
    ens_met = (models["ensemble"] or {}).get("metrics") or {}
    assert ens_met.get("validation_samples", 0) > 0, "Ensemble val_n=0"
    assert ens_met.get("training_samples", 0) > 0, "Ensemble train_n=0"
    # Ensemble should have plausible metric values (not all zero)
    assert ens_met.get("accuracy", 0.0) > 0.0, "Ensemble accuracy=0"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
