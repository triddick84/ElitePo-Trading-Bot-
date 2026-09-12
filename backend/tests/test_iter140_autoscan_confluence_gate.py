"""Iter 140 — Auto-scan × Confluence gate wiring tests.

Focus: gate filtering logic + `_confluence_evaluate()` signal-assembly.
We stub Mongo (`_db=None`) and use `unittest.mock` to inject a candle
loader so no live database is required.
"""

import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auto_scan_service import AutoScanService, DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Gate filtering — bench the pure logic inside scan_once() manually
# ---------------------------------------------------------------------------

def _fired_row(asset="EURUSD_OTC", conf=0.8, direction="CALL",
               confluence_fires=True, confluence_score=0.9):
    return {
        "asset": asset,
        "direction": direction,
        "confidence": conf,
        "matched": True,
        "elite_score": 50.0,
        "confluence": {
            "fires": confluence_fires,
            "result": {"confluence_score": confluence_score, "direction": direction,
                       "sources_call": ["a", "b", "c"], "sources_put": []},
            "threshold": 0.65,
            "min_sources": 3,
            "n_signals": 5,
        },
    }


def test_gate_keeps_row_that_fires():
    """When confluence.fires=True, the row survives the gate."""
    rows = [_fired_row(confluence_fires=True)]
    kept = [r for r in rows
            if r.get("confluence") is None or r["confluence"].get("fires", False)]
    assert len(kept) == 1


def test_gate_drops_row_that_does_not_fire():
    rows = [_fired_row(confluence_fires=False)]
    kept = [r for r in rows
            if r.get("confluence") is None or r["confluence"].get("fires", False)]
    assert kept == []


def test_gate_keeps_row_with_no_confluence_result():
    """When confluence evaluation failed (candles unavailable), we KEEP the row
    so the bot doesn't silently stop trading on data outages."""
    row = _fired_row()
    row["confluence"] = None
    kept = [r for r in [row]
            if r.get("confluence") is None or r["confluence"].get("fires", False)]
    assert len(kept) == 1


def test_gate_mixed_rows():
    rows = [
        _fired_row("A", confluence_fires=True),
        _fired_row("B", confluence_fires=False),
        _fired_row("C", confluence_fires=True),
        _fired_row("D", confluence_fires=False),
    ]
    kept = [r for r in rows
            if r.get("confluence") is None or r["confluence"].get("fires", False)]
    assert [r["asset"] for r in kept] == ["A", "C"]


# ---------------------------------------------------------------------------
# _confluence_evaluate signal-assembly (no DB needed — we mock the loader)
# ---------------------------------------------------------------------------

def _build_trending_up_df(n=80, start=100.0, step=0.15):
    rng = np.random.default_rng(11)
    bars = []
    for i in range(n):
        p = start + i * step + rng.uniform(-0.05, 0.05)
        bars.append({"open": p, "high": p + 0.1, "low": p - 0.1, "close": p + 0.05, "volume": 1000.0})
    return pd.DataFrame(bars)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture()
def loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


def test_confluence_evaluate_returns_none_when_no_candles(loop):
    svc = AutoScanService()
    row = {"direction": "CALL", "confidence": 0.8, "matched": True,
           "elite_score": None, "elite_direction": "NEUTRAL"}
    cfg = dict(DEFAULT_CONFIG)
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=pd.DataFrame())):
        result = loop.run_until_complete(
            svc._confluence_evaluate("EURUSD_OTC", row, cfg)
        )
    assert result is None


def test_confluence_evaluate_assembles_signals(loop):
    """With strategy=CALL + elite=CALL, we should get ≥ 2 signals and the
    engine should return a non-None result — regardless of whether patterns
    fire on the synthetic trending frame."""
    svc = AutoScanService()
    row = {"direction": "CALL", "confidence": 0.85, "matched": True,
           "elite_score": 60.0, "elite_direction": "CALL"}
    cfg = dict(DEFAULT_CONFIG)
    df = _build_trending_up_df(80)
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=df)):
        result = loop.run_until_complete(
            svc._confluence_evaluate("EURUSD_OTC", row, cfg)
        )
    assert result is not None
    assert result["n_signals"] >= 2  # strategy + elite at minimum
    assert "result" in result and "fires" in result
    assert result["threshold"] > 0
    assert result["min_sources"] > 0


def test_confluence_evaluate_strategy_only_still_scores(loop):
    """Even if elite is NEUTRAL, the strategy signal alone should be counted."""
    svc = AutoScanService()
    row = {"direction": "PUT", "confidence": 0.7, "matched": True,
           "elite_score": None, "elite_direction": "NEUTRAL"}
    cfg = dict(DEFAULT_CONFIG)
    df = _build_trending_up_df(80)
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=df)):
        result = loop.run_until_complete(
            svc._confluence_evaluate("USDJPY_OTC", row, cfg)
        )
    assert result is not None
    assert result["n_signals"] >= 1
    # PUT strategy alone → won't hit min_sources=3 → fires=False
    assert result["fires"] is False


def test_confluence_evaluate_drops_neutral_elite(loop):
    """elite_direction=NEUTRAL → elite must NOT contribute a signal."""
    svc = AutoScanService()
    row = {"direction": "CALL", "confidence": 0.8, "matched": True,
           "elite_score": 40.0, "elite_direction": "NEUTRAL"}
    cfg = dict(DEFAULT_CONFIG)
    df = _build_trending_up_df(80)
    with patch("routes.confluence_routes._load_candles_from_db",
               new=AsyncMock(return_value=df)):
        result = loop.run_until_complete(
            svc._confluence_evaluate("EURUSD_OTC", row, cfg)
        )
    # Sources must contain "strategy:flexible_crossover" but NOT "elite"
    sources = (result["result"]["sources_call"]
               + result["result"]["sources_put"])
    assert "elite" not in sources
    assert "strategy:flexible_crossover" in sources


# ---------------------------------------------------------------------------
# DEFAULT_CONFIG carries the new gate flags
# ---------------------------------------------------------------------------

def test_default_config_has_gate_flags():
    assert DEFAULT_CONFIG.get("confluence_gate_enabled") is True
    assert DEFAULT_CONFIG.get("confluence_candle_limit") >= 30
