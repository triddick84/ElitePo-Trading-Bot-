"""Iter 145 — Forex TM order-queue endpoints regression."""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.forex_routes import router as forex_router
from forex.engine import get_engine


@pytest.fixture(scope="module")
def app_client():
    """Mount only the forex router — avoids server.py's async-at-import bootstraps."""
    app = FastAPI()
    app.include_router(forex_router, prefix="/api")
    return TestClient(app)


class _FakeAsyncCursor:
    def __init__(self, docs):
        self._docs = docs
    def sort(self, *_a, **_k): return self
    async def to_list(self, length=None):
        return self._docs[: (length or len(self._docs))]


class _FakeColl:
    def __init__(self):
        self._store = {}
        self._pending = []
    async def count_documents(self, q):
        if q == {"status": {"$ne": "picked"}}:
            return sum(1 for d in self._pending if d.get("status") != "picked")
        if q == {"status": "picked"}:
            return sum(1 for d in self._pending if d.get("status") == "picked")
        return len(self._pending)
    def find(self, q):
        if q == {"status": {"$ne": "picked"}}:
            return _FakeAsyncCursor([d for d in self._pending if d.get("status") != "picked"])
        return _FakeAsyncCursor(list(self._pending))
    async def find_one(self, q):
        for d in self._store.values():
            match = True
            for k, v in q.items():
                if d.get(k) != v: match = False; break
            if match: return d
        return None
    async def update_one(self, filt, upd, upsert=False):
        pid = filt.get("position_id")
        target = None
        for i, d in enumerate(self._pending):
            if d.get("position_id") == pid:
                # match {"status": {"$ne": "picked"}} constraint if present
                cond = filt.get("status")
                if isinstance(cond, dict) and "$ne" in cond and d.get("status") == cond["$ne"]:
                    return MagicMock(modified_count=0)
                target = i
                break
        if target is not None:
            self._pending[target].update(upd.get("$set", {}))
            return MagicMock(modified_count=1)
        # positions coll: update entry
        if pid in self._store:
            for k, v in upd.get("$set", {}).items():
                # allow dot-path meta.dom_matches
                if "." in k:
                    root, sub = k.split(".", 1)
                    self._store[pid].setdefault(root, {})[sub] = v
                else:
                    self._store[pid][k] = v
            return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)
    async def delete_one(self, filt):
        pid = filt.get("position_id")
        before = len(self._pending)
        self._pending = [d for d in self._pending if d.get("position_id") != pid]
        return MagicMock(deleted_count=before - len(self._pending))
    async def insert_one(self, doc):
        self._pending.append(doc)
        return MagicMock(inserted_id="fake")


class _FakeDB:
    def __init__(self):
        self.forex_orders_pending = _FakeColl()
        self.forex_positions = _FakeColl()
        self.forex_config = _FakeColl()
        self.forex_signals = _FakeColl()


@pytest.fixture(autouse=True)
def bind_db():
    """Bind a fake DB to the engine singleton before each test."""
    eng = get_engine()
    fake = _FakeDB()
    eng.db = fake
    eng.executor.db = fake
    yield fake
    eng.db = None
    eng.executor.db = None


def _seed_pending(db, position_id: str, symbol="EURUSD", side="BUY", lots=0.05):
    """Push a pending order + its tentative position."""
    order = {
        "position_id": position_id, "symbol": symbol, "side": side,
        "lots": lots, "order_type": "MARKET", "stop_loss": 1.09, "take_profit": 1.11,
        "queued_at": "2026-02-12T00:00:00Z", "signal_id": "sig-" + position_id,
    }
    pos = {
        "position_id": position_id, "signal_id": order["signal_id"],
        "symbol": symbol, "side": side, "lots": lots, "entry": 1.10,
        "status": "PENDING", "surface": "TAMPERMONKEY",
    }
    # Sync insert to avoid any event loop juggling
    db.forex_orders_pending._pending.append(order)
    db.forex_positions._store[position_id] = pos


def test_list_pending_empty(app_client, bind_db):
    r = app_client.get("/api/forex/orders/pending")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0 and body["orders"] == []


def test_pending_then_pick(app_client, bind_db):
    _seed_pending(bind_db, "pos-1")
    r = app_client.get("/api/forex/orders/pending")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["orders"][0]["position_id"] == "pos-1"

    r2 = app_client.post("/api/forex/orders/pos-1/mark-picked")
    assert r2.status_code == 200
    assert r2.json() == {"position_id": "pos-1", "claimed": True}

    # Second pick must fail — a different TM instance shouldn't re-fire it
    r3 = app_client.post("/api/forex/orders/pos-1/mark-picked")
    assert r3.status_code == 200
    assert r3.json()["claimed"] is False


def test_mark_filled_transitions_position(app_client, bind_db):
    _seed_pending(bind_db, "pos-2")
    # claim
    app_client.post("/api/forex/orders/pos-2/mark-picked")
    # report fill
    payload = {"fill_price": 1.10123, "fill_lots": 0.05,
               "dom_matches": {"buy_btn": "button.btn-buy"}}
    r = app_client.post("/api/forex/orders/pos-2/mark-filled", json=payload)
    assert r.status_code == 200
    assert r.json() == {"position_id": "pos-2", "updated": True}

    # The pending row should be gone
    stats = app_client.get("/api/forex/orders/queue-stats").json()
    assert stats["pending"] == 0 and stats["picked"] == 0

    # And the position row should read OPEN + updated entry
    pos = bind_db.forex_positions._store["pos-2"]
    assert pos["status"] == "OPEN"
    assert pos["entry"] == pytest.approx(1.10123, rel=1e-6)


def test_mark_rejected(app_client, bind_db):
    _seed_pending(bind_db, "pos-3")
    app_client.post("/api/forex/orders/pos-3/mark-picked")
    r = app_client.post(
        "/api/forex/orders/pos-3/mark-rejected",
        json={"error": "buy_btn_not_found"},
    )
    assert r.status_code == 200
    assert r.json() == {"position_id": "pos-3", "updated": True}

    pos = bind_db.forex_positions._store["pos-3"]
    assert pos["status"] == "REJECTED"
    assert "buy_btn_not_found" in (pos.get("close_reason") or "")


def test_queue_stats(app_client, bind_db):
    _seed_pending(bind_db, "pos-4")
    _seed_pending(bind_db, "pos-5")
    app_client.post("/api/forex/orders/pos-4/mark-picked")
    stats = app_client.get("/api/forex/orders/queue-stats").json()
    assert stats["pending"] == 1
    assert stats["picked"] == 1
