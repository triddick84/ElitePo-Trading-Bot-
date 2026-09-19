"""Iter 152 — Backtest Asset Picker: "Only with data" filter.

Kills typo-based / empty backtests by only exposing symbols that actually
have candles in `historical_candles`. Backend exposes a new endpoint the
AssetPicker fetches at mount time.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


FRONTEND_PICKER = Path("/app/frontend/src/components/shared/AssetPicker.jsx")


# ---------------------------------------------------------------------------
# Test doubles — a tiny async aggregation cursor and a db-like namespace
# ---------------------------------------------------------------------------

class _FakeAggCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._rows:
            raise StopAsyncIteration
        return self._rows.pop(0)


class _FakeCandles:
    def __init__(self, rows):
        self._rows = rows

    def aggregate(self, _pipeline, allowDiskUse=False):
        # Second $group flattens (asset, tf) → per-asset. We return the
        # already-flattened rows since the endpoint just consumes them.
        return _FakeAggCursor(self._rows)


def _mount(monkeypatch, db_ns):
    import routes.backtest as bt_mod
    monkeypatch.setattr(bt_mod, "db", db_ns, raising=False)
    app = FastAPI()
    app.include_router(bt_mod.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Backend endpoint contract
# ---------------------------------------------------------------------------

def test_assets_with_data_returns_available_symbols(monkeypatch):
    rows = [
        {"_id": "EURUSD",     "count": 3,  "timeframes": ["M1"]},
        {"_id": "GBPUSD_OTC", "count": 2,  "timeframes": ["M1"]},
        {"_id": "BTCUSD",     "count": 5,  "timeframes": ["M5"]},
    ]
    db = SimpleNamespace(historical_candles=_FakeCandles(rows))
    client = _mount(monkeypatch, db)
    r = client.get("/api/backtest/assets-with-data")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert set(body["available"]) == {"EURUSD", "GBPUSD_OTC", "BTCUSD"}
    assert body["counts"] == {"EURUSD": 3, "GBPUSD_OTC": 2, "BTCUSD": 5}
    assert body["total_assets"] == 3
    assert body["total_candles"] == 10
    assert body["timeframes"]["EURUSD"] == ["M1"]
    assert body["timeframes"]["BTCUSD"] == ["M5"]


def test_assets_with_data_empty_db(monkeypatch):
    db = SimpleNamespace(historical_candles=_FakeCandles([]))
    client = _mount(monkeypatch, db)
    r = client.get("/api/backtest/assets-with-data")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["available"] == []
    assert body["counts"] == {}
    assert body["total_assets"] == 0
    assert body["total_candles"] == 0


def test_assets_with_data_no_db_gracefully_degrades(monkeypatch):
    client = _mount(monkeypatch, None)
    r = client.get("/api/backtest/assets-with-data")
    # Should degrade to empty, not 500 — the UI filter simply becomes
    # unavailable.
    assert r.status_code == 200
    body = r.json()
    assert body["available"] == []
    assert body.get("note") == "database unavailable"


def test_assets_with_data_survives_aggregation_error(monkeypatch):
    class _BrokenCandles:
        def aggregate(self, *_a, **_kw):
            raise RuntimeError("mongo boom")
    db = SimpleNamespace(historical_candles=_BrokenCandles())
    client = _mount(monkeypatch, db)
    r = client.get("/api/backtest/assets-with-data")
    # Endpoint MUST NOT raise 500 — a broken DB shouldn't kill the picker.
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["available"] == []
    assert "mongo boom" in body.get("error", "")


# ---------------------------------------------------------------------------
# Frontend AssetPicker wiring — source-level assertions
# ---------------------------------------------------------------------------

def test_asset_picker_fetches_with_data_endpoint():
    s = FRONTEND_PICKER.read_text()
    assert "/api/backtest/assets-with-data" in s, (
        "AssetPicker must fetch the new with-data endpoint"
    )
    # Must handle the fetch failure gracefully — the picker still works
    # even when the with-data endpoint is offline.
    assert ".catch(() => ({ data: null }))" in s


def test_asset_picker_defines_only_with_data_state_and_filter():
    s = FRONTEND_PICKER.read_text()
    assert "onlyWithData" in s
    assert "dataAssets" in s
    # Filter applies BEFORE search so counts stay consistent.
    assert "if (onlyWithData && dataAssets.set.size > 0)" in s


def test_asset_picker_renders_only_with_data_toggle_button():
    s = FRONTEND_PICKER.read_text()
    assert 'only-with-data' in s
    # Button surfaces the total-available count so the user knows the
    # scope of the filter.
    assert "dataAssets.total" in s
    # Disabled when zero symbols have data — otherwise clicking the
    # button would hide every symbol and be confusing.
    assert "dataAssets.set.size === 0" in s


def test_asset_picker_renders_candle_count_badge():
    s = FRONTEND_PICKER.read_text()
    assert "candleCount" in s
    assert "-candles`" in s   # data-testid template literal
    # Formats large counts as "12k" for compactness.
    assert "candleCount >= 1000" in s
