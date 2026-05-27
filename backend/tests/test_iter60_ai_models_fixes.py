"""
Iter 60 — AI Models page (ml-training) regression tests.

Covers the 3 broken flows reported by the user May 27, 2026:
  1. /api/ml-training/train-from-backtests must NOT inject noise_1/noise_2
     features (which previously had 81% combined feature importance and
     randomized every prediction).
  2. /api/ml-training/train-on-price-data must use real OTC/OANDA data,
     not synthetic random-walk fallback that poisoned every model.
  3. /api/ml-training/run-optimization must NOT recommend money-losing
     strategies as HIGH. Loss-makers tagged AVOID_LOSS_MAKER and ranked
     below MEDIUM/LOW.
"""
import os
import sys
import pathlib
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BACKEND_URL}/api"


def _client(timeout=45):
    return httpx.Client(timeout=timeout)


def test_train_from_backtests_no_noise_features():
    """train-from-backtests must NOT have noise_1 / noise_2 in feature_importance."""
    with _client() as c:
        r = c.post(f"{API}/ml-training/train-from-backtests", json={"limit": 100})
    assert r.status_code == 200
    body = r.json()
    if not body.get("success"):
        # Acceptable if there aren't enough backtests yet
        assert "error" in body
        return
    models = body.get("models", {})
    for name, m in models.items():
        fi = m.get("feature_importance", {})
        # The actual bug fix — these strings cannot appear
        assert not any(k.startswith("noise_") for k in fi.keys()), (
            f"model {name} still has noise features: {list(fi.keys())}"
        )


def test_train_on_price_data_uses_real_source():
    """train-on-price-data must NOT silently fall back to synthetic data."""
    with _client() as c:
        r = c.post(
            f"{API}/ml-training/train-on-price-data",
            json={"asset": "EURUSD_OTC", "timeframe": "M1", "days": 14},
        )
    assert r.status_code == 200
    body = r.json()
    # Either we got real data, or we failed with a clear error mentioning real-data scarcity
    if body.get("success"):
        ds = body.get("data_source", "")
        assert "synthetic" not in ds.lower(), (
            f"train-on-price-data fell back to synthetic data: {ds}"
        )
        assert body.get("candles_used", 0) >= 100
    else:
        # Iter 60 — synthetic fallback DISABLED, so failure on dry data is correct
        assert "Insufficient REAL price data" in body.get("error", "") or "Synthetic" in body.get("error", "")


def test_run_optimization_does_not_recommend_loss_makers():
    """run-optimization best_strategy MUST be profitable; losers tagged AVOID_LOSS_MAKER."""
    with _client() as c:
        r = c.post(f"{API}/ml-training/run-optimization")
    assert r.status_code == 200
    body = r.json()
    if not body.get("success"):
        return  # not enough backtests
    best = body.get("best_strategy")
    if best:
        # The "best" strategy must NOT be flagged as a loss-maker / AVOID
        assert best.get("recommendation") in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA"), (
            f"best_strategy got bad tier: {best.get('recommendation')}"
        )
        # If profit is negative, the tier must reflect that
        if best.get("total_profit", 0) < 0:
            assert best.get("recommendation") == "AVOID_LOSS_MAKER", (
                f"loss-making best_strategy not flagged: {best}"
            )

    # Verify ordering: no AVOID_LOSS_MAKER appears before any HIGH/MEDIUM/LOW
    recs = body.get("all_recommendations", [])
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INSUFFICIENT_DATA": 3, "AVOID": 4, "AVOID_LOSS_MAKER": 5}
    last_rank = -1
    for r in recs:
        cur_rank = rank.get(r["recommendation"], 99)
        assert cur_rank >= last_rank, (
            f"sort order broken — {r['recommendation']} ({r['strategy']}) appears "
            f"after a higher-tier strategy in the list"
        )
        last_rank = max(last_rank, cur_rank)

    # Verify composite_score is on every row
    for r in recs:
        assert "composite_score" in r, f"missing composite_score: {r}"
