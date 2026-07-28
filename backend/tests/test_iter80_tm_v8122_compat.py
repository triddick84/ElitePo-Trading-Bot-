"""
Iter 80 (Jul 2026) — TM v8.122.0 compat sweep.

The user restored the compiled `AI's Elite PO Traders Bot-8.122.0.user.js`
after a codebase rollback. This test locks in the three backend endpoints the
v8.122.0 bundle depends on that weren't covered by any other route module:

- GET  /api/settings/chart       (chart type/timeframe indicator)
- GET  /api/tampermonkey/script  (serves compiled userscript for @updateURL)
- POST /api/diag/ws-frames       (WS frame diagnostic sink)

Also asserts:
- The served userscript byte-matches the on-disk compiled bundle.
- The served userscript declares @version 8.122.0.
- /api/health still returns 200 (regression guard on the router include order).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
USERSCRIPT_ONDISK = Path(
    "/app/frontend/public/pocket-option-auto-trader.user.js"
)


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=15, **kwargs)


def _post(path: str, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=15, **kwargs)


# ---------------------------------------------------------------------------
# /api/settings/chart
# ---------------------------------------------------------------------------
def test_settings_chart_returns_defaults():
    r = _get("/api/settings/chart")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("chart_type"), str) and body["chart_type"]
    assert isinstance(body.get("chart_timeframe"), str) and body["chart_timeframe"]


# ---------------------------------------------------------------------------
# /api/tampermonkey/script — served userscript is byte-identical & v8.122.0+
# ---------------------------------------------------------------------------
def test_tampermonkey_script_served():
    r = _get("/api/tampermonkey/script")
    assert r.status_code == 200, r.text
    # Content-type must be JS so Tampermonkey accepts the update
    ct = r.headers.get("content-type", "")
    assert "javascript" in ct.lower(), f"unexpected content-type: {ct}"

    body = r.text
    # Header integrity
    assert "// ==UserScript==" in body
    m = re.search(r"@version\s+(\S+)", body)
    assert m, "no @version header in served userscript"
    version = m.group(1)
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    assert parts and parts[0] >= 8 and parts >= [8, 122, 0], (
        f"served userscript version {version} is older than 8.122.0"
    )


def test_tampermonkey_script_matches_disk():
    if not USERSCRIPT_ONDISK.exists():
        pytest.skip("no on-disk userscript to compare against")
    r = _get("/api/tampermonkey/script")
    assert r.status_code == 200
    served = r.content
    on_disk = USERSCRIPT_ONDISK.read_bytes()
    assert served == on_disk, (
        f"served bytes ({len(served)}) != on-disk bytes ({len(on_disk)})"
    )


# ---------------------------------------------------------------------------
# /api/diag/ws-frames
# ---------------------------------------------------------------------------
def test_diag_ws_frames_post_accepts_batch():
    payload = {
        "frames": [{"raw": "test", "ts": 1}, {"raw": "test2", "ts": 2}],
        "meta": {"url": "https://pocketoption.com", "v": "8.122.0"},
    }
    r = _post("/api/diag/ws-frames", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("stored") == 2


def test_diag_ws_frames_post_empty_frames_is_ok():
    r = _post("/api/diag/ws-frames", json={})
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_diag_ws_frames_get_returns_recent():
    # Push one so we always have something to list
    _post("/api/diag/ws-frames", json={"frames": [{"raw": "a"}], "meta": {}})
    r = _get("/api/diag/ws-frames?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("batches"), list)


# ---------------------------------------------------------------------------
# Regression guard on unrelated core endpoints
# ---------------------------------------------------------------------------
def test_health_still_ok():
    r = _get("/api/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_signals_latest_still_ok():
    r = _get("/api/signals/latest?asset=EURUSD_OTC&timeframe=5s")
    assert r.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
