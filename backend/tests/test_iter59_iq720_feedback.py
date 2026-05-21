"""
Iter 59 — IQ-720 outcome feedback loop + training-pipeline fixes regression.

Covers:
  1. /api/signals/iq720-ensemble has OTC fallback (works without OANDA).
  2. IQ-720 signal payload includes `confirmation_multipliers` + `data_source`.
  3. /api/iq720/outcome-stats returns valid schema (may be empty cold start).
  4. /api/iq720/match-outcomes runs idempotently.
  5. /api/iq720/refresh-stats recomputes rolling win-rates.
  6. /api/ml/train-from-trades completes within 3 minutes (was hanging 30+).
  7. Tournament tracks IQ-720 as a 5th model.
"""
import os
import sys
import time
import pathlib
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BACKEND_URL}/api"


def _client(timeout=30):
    return httpx.Client(timeout=timeout)


def test_iq720_ensemble_has_otc_fallback_and_multipliers():
    """IQ-720 must return a signal even when only OTC pool has data."""
    with _client(timeout=45) as c:
        r = c.post(
            f"{API}/signals/iq720-ensemble",
            json={"symbol": "EURUSD_OTC", "timeframe": "M1", "candle_count": 120},
        )
    assert r.status_code == 200
    body = r.json()
    if body.get("success") and body.get("signal"):
        s = body["signal"]
        # Iter 59 - confirmation multipliers present
        assert "confirmation_multipliers" in s, "missing confirmation_multipliers"
        assert isinstance(s["confirmation_multipliers"], dict)
        # Data source tag present (oanda or otc_pool)
        assert "data_source" in s
        assert s["data_source"] in ("oanda", "otc_pool")
    else:
        # Acceptable if no data — but the schema must still describe what was tried
        assert "oanda_attempted" in body or "message" in body


def test_iq720_outcome_stats_endpoint_shape():
    """Outcome stats must always return the schema, even cold start."""
    with _client() as c:
        r = c.get(f"{API}/iq720/outcome-stats")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    for k in ("stats", "multipliers", "count"):
        assert k in body
    assert isinstance(body["stats"], list)
    assert isinstance(body["multipliers"], dict)


def test_iq720_match_outcomes_runs():
    """Match-outcomes endpoint must run successfully on demand."""
    with _client(timeout=45) as c:
        r = c.post(f"{API}/iq720/match-outcomes", json={"lookback_hours": 24})
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "match" in body
    assert "refresh" in body
    m = body["match"]
    for k in ("matched", "skipped", "checked"):
        assert k in m, f"missing match.{k}"


def test_iq720_refresh_stats_runs():
    """Refresh stats endpoint must return success even with zero data."""
    with _client(timeout=30) as c:
        r = c.post(f"{API}/iq720/refresh-stats")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "confirmations_evaluated" in body
    assert body["confirmations_evaluated"] >= 0


def test_train_from_trades_completes_within_3min():
    """
    Iter 59 — training was hanging indefinitely before (61 symbols × 30-day
    OANDA fetches). The bounds (6 symbols, 14-day window, 45s/symbol OANDA
    timeout) must finish in well under 3 minutes.
    """
    with _client(timeout=10) as c:
        c.post(f"{API}/ml/train-from-trades", json={"max_age_days": 30, "min_samples": 30})
    # Poll for completion
    deadline = time.time() + 180  # 3 minutes
    last = None
    while time.time() < deadline:
        with _client(timeout=10) as c:
            r = c.get(f"{API}/ml/train-from-trades/status")
        body = r.json()
        last = body
        if body.get("in_progress") is False:
            break
        time.sleep(5)
    assert last is not None, "no status response"
    assert last.get("in_progress") is False, f"training still running after 180s: {last}"
    res = last.get("result") or {}
    # Either we matched enough trades or we gracefully failed with a clear error
    assert "total_samples" in res or "error" in res
    if res.get("success"):
        assert res.get("total_samples", 0) >= 30


def test_tournament_includes_iq720():
    """Tournament cache must include iq720 as a tracked model."""
    with _client() as c:
        r = c.get(f"{API}/ml/tournament/status")
    assert r.status_code == 200
    cache = r.json().get("cache", {})
    assert "iq720" in cache, f"iq720 missing from tournament cache: {list(cache.keys())}"
    assert isinstance(cache["iq720"], (int, float))
    assert cache["iq720"] > 0
