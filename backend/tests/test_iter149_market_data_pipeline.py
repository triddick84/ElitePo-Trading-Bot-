"""Iter 149 — Market data ingestion + RF audit multiplier fix regression."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# RF audit multiplier — the silent bug that zeroed all ML sources
# ---------------------------------------------------------------------------

def test_rf_audit_multiplier_only_targets_ml_rf():
    """Only ml:rf sources get the RF audit multiplier — ml:tqnet, ml:xgb, etc
    must not be silently zeroed by legacy audit weights."""
    from confluence_service import _rf_audit_multiplier

    # ml:tqnet must return 1.0 regardless of any DB state
    assert _rf_audit_multiplier("ml:tqnet", "EURUSD_OTC", "1m") == 1.0
    # ml:xgboost future-proofing
    assert _rf_audit_multiplier("ml:xgboost", "EURUSD_OTC", "1m") == 1.0
    # Non-ml sources always return 1.0
    assert _rf_audit_multiplier("smart_money:liquidity_sweep", "EURUSD_OTC", "1m") == 1.0
    assert _rf_audit_multiplier("pattern:head_shoulders", "EURUSD_OTC", "1m") == 1.0


def test_rf_audit_multiplier_still_applies_to_ml_rf():
    """The audit STILL works for its intended target — ml:rf."""
    from confluence_service import _rf_audit_multiplier
    with patch("rf_audit_service.rf_audit_service.get_effective_weight",
               return_value=0.5):
        assert _rf_audit_multiplier("ml:rf", "EURUSD_OTC", "1m") == 0.5


def test_score_confluence_tqnet_contributes():
    """The bug: put_score used to be 0 despite tqnet PUT signal. Regression."""
    from confluence_service import score_confluence
    signals = [
        {"source": "smart_money:liquidity_sweep", "direction": "CALL",
         "confidence": 0.6, "asset": "EURUSD_OTC", "timeframe": "1m"},
        {"source": "ml:tqnet", "direction": "PUT", "confidence": 1.0,
         "asset": "EURUSD_OTC", "timeframe": "1m"},
    ]
    # Even if the DB has a stale rf_audit entry (weight=0) for this pair,
    # score_confluence must NOT apply it to ml:tqnet.
    with patch("rf_audit_service.rf_audit_service.get_effective_weight",
               return_value=0.0):
        r = score_confluence(signals, min_sources=2)
    assert r["put_score"] > 0.0, "tqnet PUT must contribute even with legacy audit=0"
    assert r["direction"] == "PUT"


# ---------------------------------------------------------------------------
# Ingester provider chain selection
# ---------------------------------------------------------------------------

def test_pick_chain_major_fx_prefers_oanda():
    from market_data_ingester import _pick_chain, _oanda, _twelvedata, _yfinance
    chain = _pick_chain("EURUSD")
    assert chain == [_oanda, _twelvedata, _yfinance]


def test_pick_chain_otc_skips_oanda():
    """OTC pairs don't exist on Oanda — must not appear in the chain."""
    from market_data_ingester import _pick_chain, _oanda
    chain = _pick_chain("EURUSD_OTC")
    assert _oanda not in chain
    chain2 = _pick_chain("BHDCNY_OTC")
    assert _oanda not in chain2


def test_pick_chain_minor_fx_skips_oanda():
    """Non-major FX shouldn't waste an Oanda call — Twelvedata first."""
    from market_data_ingester import _pick_chain, _oanda
    chain = _pick_chain("GBPCAD")  # minor cross
    assert _oanda not in chain


# ---------------------------------------------------------------------------
# _normalise_df / persistence shape
# ---------------------------------------------------------------------------

def test_normalise_df_produces_historical_candles_schema():
    from market_data_ingester import _normalise_df
    now = datetime.now(timezone.utc)
    raw = pd.DataFrame({
        "timestamp": [now - timedelta(minutes=2), now - timedelta(minutes=1), now],
        "open":   [1.10, 1.11, 1.12],
        "high":   [1.115, 1.121, 1.125],
        "low":    [1.099, 1.109, 1.119],
        "close":  [1.11, 1.12, 1.124],
        "volume": [100.0, 150.0, 200.0],
    })
    docs = _normalise_df(raw, "EURUSD_OTC", "1m")
    assert len(docs) == 3
    for d in docs:
        assert d["asset"] == "EURUSD_OTC"
        assert d["timeframe"] == "1m"
        assert isinstance(d["timestamp"], datetime)
        assert d["timestamp"].tzinfo is not None    # timezone-aware
        assert isinstance(d["close"], float)
    # Order preserved
    assert docs[0]["close"] < docs[-1]["close"]


def test_normalise_df_handles_string_timestamps():
    from market_data_ingester import _normalise_df
    raw = pd.DataFrame({
        "timestamp": ["2026-02-12T00:00:00Z", "2026-02-12T00:01:00Z"],
        "open": [1.1, 1.2], "high": [1.2, 1.3],
        "low": [1.0, 1.1], "close": [1.15, 1.25],
        "volume": [0, 0],
    })
    docs = _normalise_df(raw, "X", "1m")
    assert len(docs) == 2
    assert all(isinstance(d["timestamp"], datetime) for d in docs)


# ---------------------------------------------------------------------------
# Ingester coalescing lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingester_coalesces_parallel_fetches(monkeypatch):
    """Two parallel calls for the same (asset, tf) must share ONE HTTP round-trip."""
    from market_data_ingester import ingester, IngestReport
    call_count = {"n": 0}

    async def fake_do_fetch(asset, timeframe, limit):
        call_count["n"] += 1
        # simulate slow provider
        import asyncio
        await asyncio.sleep(0.05)
        return IngestReport(
            asset=asset, timeframe=timeframe, ok=True,
            provider="fake", rows=10, latency_ms=50,
        )

    ingester._inflight = {}
    monkeypatch.setattr(ingester, "_do_fetch", fake_do_fetch)
    import asyncio
    r1, r2, r3 = await asyncio.gather(
        ingester.fetch_and_persist("EURUSD", "1m"),
        ingester.fetch_and_persist("EURUSD", "1m"),
        ingester.fetch_and_persist("EURUSD", "1m"),
    )
    # All three callers see the same result (or an equivalent), but only
    # one _do_fetch was actually executed thanks to coalescing.
    assert call_count["n"] == 1
    assert all(r.ok for r in (r1, r2, r3))


# ---------------------------------------------------------------------------
# ensure_fresh — cache_hit vs refetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_fresh_cache_hit_when_recent(monkeypatch):
    from market_data_ingester import ingester
    ingester._inflight = {}
    ingester._freshness_cache = {}
    ingester.db = None
    # Seed a very recent entry with db_rows > 0 so the freshness check
    # trusts the cache. Iter 149.1: db_rows==0 always triggers a refetch.
    now = datetime.now(timezone.utc)
    ingester._freshness_cache[("EURUSD", "1m")] = {
        "asset": "EURUSD", "timeframe": "1m", "provider": "twelvedata",
        "rows": 200, "written": 100, "db_rows": 200,
        "last_fetch_iso": now.isoformat(),
        "last_bar_ts": (now - timedelta(seconds=10)).isoformat(),
        "latency_ms": 100,
    }
    called = {"n": 0}

    async def fake_fetch(*a, **kw):
        called["n"] += 1
    monkeypatch.setattr(ingester, "fetch_and_persist", fake_fetch)
    r = await ingester.ensure_fresh("EURUSD", "1m", max_age_s=300)
    assert r["fresh"] is True
    assert r["action"] == "cache_hit"
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_ensure_fresh_refetches_when_db_rows_zero(monkeypatch):
    """Iter 149.1 — even if cache says fresh, refetch when DB is empty."""
    from market_data_ingester import ingester, IngestReport
    ingester._inflight = {}
    ingester._freshness_cache = {}
    ingester.db = None
    now = datetime.now(timezone.utc)
    ingester._freshness_cache[("EURUSD", "1m")] = {
        "asset": "EURUSD", "timeframe": "1m", "provider": "twelvedata",
        "rows": 200, "written": 0, "db_rows": 0,     # persist failed → 0 in DB
        "last_fetch_iso": now.isoformat(),
        "last_bar_ts": (now - timedelta(seconds=5)).isoformat(),
        "latency_ms": 100,
    }
    called = {"n": 0}

    async def fake_fetch(asset, tf, limit=500):
        called["n"] += 1
        return IngestReport(asset=asset, timeframe=tf, ok=True,
                            provider="fake", rows=10, latency_ms=1)
    monkeypatch.setattr(ingester, "fetch_and_persist", fake_fetch)
    r = await ingester.ensure_fresh("EURUSD", "1m", max_age_s=300)
    assert r["action"] == "refetched"
    assert called["n"] == 1


@pytest.mark.asyncio
async def test_ensure_fresh_refetches_when_stale(monkeypatch):
    from market_data_ingester import ingester, IngestReport
    ingester._inflight = {}
    ingester._freshness_cache = {}
    ingester.db = None
    # Seed a very old entry
    now = datetime.now(timezone.utc)
    ingester._freshness_cache[("EURUSD", "1m")] = {
        "asset": "EURUSD", "timeframe": "1m", "provider": "twelvedata",
        "rows": 0, "written": 0,
        "last_fetch_iso": (now - timedelta(hours=1)).isoformat(),
        "last_bar_ts": (now - timedelta(hours=1)).isoformat(),
        "latency_ms": 0,
    }
    called = {"n": 0}

    async def fake_fetch(asset, tf, limit=500):
        called["n"] += 1
        ingester._freshness_cache[(asset, tf)] = {
            "asset": asset, "timeframe": tf, "provider": "fake",
            "rows": 100, "written": 100,
            "last_fetch_iso": now.isoformat(),
            "last_bar_ts": now.isoformat(),
            "latency_ms": 10,
        }
        return IngestReport(asset=asset, timeframe=tf, ok=True,
                            provider="fake", rows=100, latency_ms=10)
    monkeypatch.setattr(ingester, "fetch_and_persist", fake_fetch)
    r = await ingester.ensure_fresh("EURUSD", "1m", max_age_s=60)
    assert r["fresh"] is True
    assert r["action"] == "refetched"
    assert called["n"] == 1


# ---------------------------------------------------------------------------
# Freshness policy table
# ---------------------------------------------------------------------------

def test_freshness_policy_covers_common_timeframes():
    from market_data_ingester import FRESHNESS_S
    for tf in ("1m", "5m", "15m", "1h", "1d"):
        assert tf in FRESHNESS_S
        assert FRESHNESS_S[tf] > 0
    # Sanity: 1m fresher than 15m
    assert FRESHNESS_S["1m"] < FRESHNESS_S["15m"]
