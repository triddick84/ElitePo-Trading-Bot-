"""
Iter 82 (Jul 2026) — Strategy Publish/Unpublish flow.

Locks in:
- Newly-created custom strategies default to `is_published=False` (Draft).
- `POST /api/custom-strategies/{id}/publish` sets `is_published=True`.
- `POST /api/custom-strategies/{id}/unpublish` sets it back to False.
- `POST /api/custom-strategies/{id}/toggle-publish` flips the flag.
- Published customs appear in `/api/strategies/available/{tf}` with a
  `custom: true` tag and a 🛠 name prefix.
- Draft (unpublished) customs are NEVER surfaced in
  `/api/strategies/available/{tf}` even when their timeframe matches.
- `/api/strategies/select` accepts a published-custom id for a timeframe
  that the custom strategy declares support for.
- `is_active` and `is_published` are independent fields:
  a Draft strategy can still be Active (it just won't be exposed to the
  timeframe picker); an Off strategy can still be Published (visible but
  not firing).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=15, **kwargs)


def _post(path: str, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=15, **kwargs)


def _delete(path: str, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", timeout=15, **kwargs)


@pytest.fixture
def new_strategy():
    """Create a fresh strategy for a test; delete it on teardown."""
    payload = {
        "name": "Iter82 Regression Test Strategy",
        "description": "Automatic regression suite probe",
        "user_id": "iter82_regression",
        "call_conditions": [],
        "put_conditions": [],
        "timeframes": ["1m", "5s"],
        "assets": ["EURUSD"],
        "markets": ["otc"],
        "min_confidence": 70,
    }
    r = _post("/api/custom-strategies", json=payload)
    assert r.status_code == 200, r.text
    strat = r.json()["strategy"]
    strat_id = strat["id"]
    try:
        yield strat
    finally:
        _delete(f"/api/custom-strategies/{strat_id}")


def _find(entries: List[Dict[str, Any]], sid: str) -> Dict[str, Any] | None:
    for e in entries:
        if e.get("id") == sid:
            return e
    return None


# ---------------------------------------------------------------------------
# 1) Defaults + schema
# ---------------------------------------------------------------------------
def test_new_strategy_defaults_to_draft(new_strategy):
    assert new_strategy["is_active"] is True   # legacy default
    assert new_strategy["is_published"] is False  # new field default


# ---------------------------------------------------------------------------
# 2) Draft is hidden from timeframe picker
# ---------------------------------------------------------------------------
def test_draft_strategy_not_in_available(new_strategy):
    r = _get(f"/api/strategies/available/1m")
    assert r.status_code == 200
    entries = r.json()["strategies"]
    assert _find(entries, new_strategy["id"]) is None


# ---------------------------------------------------------------------------
# 3) Publish → appears with `custom: true` marker
# ---------------------------------------------------------------------------
def test_publish_makes_strategy_visible(new_strategy):
    r = _post(f"/api/custom-strategies/{new_strategy['id']}/publish")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["strategy"]["is_published"] is True

    for tf in ("1m", "5s"):
        entries = _get(f"/api/strategies/available/{tf}").json()["strategies"]
        found = _find(entries, new_strategy["id"])
        assert found is not None, f"strategy missing from {tf} list after publish"
        assert found.get("custom") is True
        assert "🛠" in found.get("name", "")

    # But it should NOT appear in a timeframe it doesn't declare support for
    r15s = _get("/api/strategies/available/15s").json()["strategies"]
    assert _find(r15s, new_strategy["id"]) is None


# ---------------------------------------------------------------------------
# 4) /strategies/select accepts a published custom id
# ---------------------------------------------------------------------------
def test_select_published_custom_for_timeframe(new_strategy):
    _post(f"/api/custom-strategies/{new_strategy['id']}/publish")
    r = _post(
        "/api/strategies/select",
        json={"timeframe": "1m", "strategy_id": new_strategy["id"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["strategy_id"] == new_strategy["id"]

    selections = _get("/api/strategies/selected").json()["selections"]
    assert selections["1m"] == new_strategy["id"]

    # Cleanup: revert to default so we don't leave a broken selection
    _post("/api/strategies/select",
          json={"timeframe": "1m", "strategy_id": "default"})


# ---------------------------------------------------------------------------
# 5) Selecting an UNpublished custom must be rejected
# ---------------------------------------------------------------------------
def test_select_unpublished_custom_rejected(new_strategy):
    r = _post(
        "/api/strategies/select",
        json={"timeframe": "1m", "strategy_id": new_strategy["id"]},
    )
    # `update_strategy_selection` returns False → route raises 400
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 6) Unpublish removes from picker
# ---------------------------------------------------------------------------
def test_unpublish_removes_from_available(new_strategy):
    _post(f"/api/custom-strategies/{new_strategy['id']}/publish")
    # Confirm visible first
    e1 = _get("/api/strategies/available/1m").json()["strategies"]
    assert _find(e1, new_strategy["id"]) is not None

    r = _post(f"/api/custom-strategies/{new_strategy['id']}/unpublish")
    assert r.status_code == 200
    assert r.json()["strategy"]["is_published"] is False

    e2 = _get("/api/strategies/available/1m").json()["strategies"]
    assert _find(e2, new_strategy["id"]) is None


# ---------------------------------------------------------------------------
# 7) toggle-publish flips
# ---------------------------------------------------------------------------
def test_toggle_publish_flips(new_strategy):
    r1 = _post(f"/api/custom-strategies/{new_strategy['id']}/toggle-publish")
    assert r1.json()["strategy"]["is_published"] is True
    r2 = _post(f"/api/custom-strategies/{new_strategy['id']}/toggle-publish")
    assert r2.json()["strategy"]["is_published"] is False


# ---------------------------------------------------------------------------
# 8) is_active and is_published are independent
# ---------------------------------------------------------------------------
def test_active_and_published_are_independent(new_strategy):
    sid = new_strategy["id"]
    # Publish while active
    _post(f"/api/custom-strategies/{sid}/publish")
    # Turn OFF is_active
    r = _post(f"/api/custom-strategies/{sid}/toggle?is_active=false")
    assert r.status_code == 200
    latest = r.json()["strategy"]
    assert latest["is_active"] is False
    assert latest["is_published"] is True  # publish flag untouched

    # Still visible in picker even though it's Off
    entries = _get("/api/strategies/available/1m").json()["strategies"]
    found = _find(entries, sid)
    assert found is not None
    assert found.get("is_active") is False


# ---------------------------------------------------------------------------
# 9) /strategies/available (all TFs) also includes customs
# ---------------------------------------------------------------------------
def test_all_available_includes_customs(new_strategy):
    sid = new_strategy["id"]
    _post(f"/api/custom-strategies/{sid}/publish")
    r = _get("/api/strategies/available")
    assert r.status_code == 200
    all_map = r.json()["strategies"]
    # Should appear under every declared TF
    for tf in new_strategy.get("timeframes", []):
        assert tf in all_map, f"TF {tf} missing from response"
        assert _find(all_map[tf], sid) is not None, f"custom not in {tf} list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
