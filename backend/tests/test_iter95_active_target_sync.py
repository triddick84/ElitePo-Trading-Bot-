"""
Iter 95 — App→TM active-target sync + asset-switch verification.

Fixes the bug: "TM script fires trades on whatever asset PO's chart shows,
not on the asset selected in the application".

Locks:
  * GET  /api/tampermonkey/active-target returns {asset, timeframe, expiry_seconds}
    with correct precedence (override > config > fallback).
  * POST /api/tampermonkey/active-target sets/clears an explicit override.
  * `/api/signals/latest` falls back to active_target when no ?symbol is passed.
  * Compiled TM userscript v8.125.0+ contains the new call paths:
    fetchActiveTarget, asset_switch_failed abort branch, _verifyAssetSwitched.
"""

from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------------------------------------------------------------------
# Active target endpoints
# ---------------------------------------------------------------------------
def _clear_override():
    requests.post(f"{API}/tampermonkey/active-target", json={"asset": None}, timeout=10)


def test_active_target_returns_shape_and_fallback_to_config():
    _clear_override()
    r = requests.get(f"{API}/tampermonkey/active-target", timeout=10).json()
    assert r.get("success") is True
    for k in ("asset", "timeframe", "expiry_seconds", "source"):
        assert k in r, f"missing key {k}"
    # Source is 'config' if user has selected_assets, else 'fallback'
    assert r["source"] in ("config", "fallback", "override"), r
    # Asset shape sanity — canonical OTC form
    assert r["asset"], "asset must be non-empty"


def test_active_target_override_takes_precedence():
    _clear_override()
    r = requests.post(
        f"{API}/tampermonkey/active-target",
        json={"asset": "GBPJPY_OTC", "timeframe": "30s"},
        timeout=10,
    ).json()
    assert r.get("success") is True
    assert r["active_target"]["asset"] == "GBPJPY_OTC"
    assert r["active_target"]["expiry_seconds"] == 30

    r = requests.get(f"{API}/tampermonkey/active-target", timeout=10).json()
    assert r["source"] == "override"
    assert r["asset"] == "GBPJPY_OTC"
    assert r["timeframe"] == "30s"
    assert r["expiry_seconds"] == 30
    _clear_override()


def test_active_target_normalises_lowercase_and_missing_underscore():
    _clear_override()
    r = requests.post(
        f"{API}/tampermonkey/active-target",
        json={"asset": "eurusdotc", "timeframe": "1m"},
        timeout=10,
    ).json()
    assert r["active_target"]["asset"] == "EURUSD_OTC", r
    _clear_override()


def test_active_target_clear_removes_override():
    requests.post(
        f"{API}/tampermonkey/active-target",
        json={"asset": "USDJPY_OTC", "timeframe": "5s"},
        timeout=10,
    )
    requests.post(f"{API}/tampermonkey/active-target", json={"asset": None}, timeout=10)
    r = requests.get(f"{API}/tampermonkey/active-target", timeout=10).json()
    assert r["source"] != "override", f"override still present: {r}"


# ---------------------------------------------------------------------------
# /signals/latest active_target fallback
# ---------------------------------------------------------------------------
def test_signals_latest_falls_back_to_active_target():
    """
    When TM polls /signals/latest without ?symbol=X, the endpoint should
    scope to the app's active_target asset rather than returning signals
    for arbitrary assets.
    """
    _clear_override()
    requests.post(
        f"{API}/tampermonkey/active-target",
        json={"asset": "AUDCAD_OTC", "timeframe": "1m"},
        timeout=10,
    )
    # Seed a signal for AUDCAD_OTC so /signals/latest has something matching
    requests.post(
        f"{API}/signals/force-generate-v2",
        params={"asset": "AUDCAD_OTC", "expiry_seconds": 60},
        timeout=45,
    )
    # Small settle
    time.sleep(1)
    r = requests.get(f"{API}/signals/latest", timeout=15).json()
    # Response may be success/no_recent depending on DB, but if it returns a
    # signal it MUST be scoped to AUDCAD_OTC (or its variants).
    sig = r.get("signal") or {}
    if sig:
        sym = str(sig.get("symbol") or sig.get("asset") or "").upper().replace(" ", "")
        assert "AUDCAD" in sym, f"expected AUDCAD in symbol, got: {sym} · full response: {r}"
    _clear_override()


# ---------------------------------------------------------------------------
# TM userscript v8.125.0 compat: new markers must be present
# ---------------------------------------------------------------------------
def test_tampermonkey_script_contains_active_target_wiring():
    r = requests.get(f"{API}/tampermonkey/script", timeout=15)
    assert r.status_code == 200
    body = r.text
    # New Iter 95 markers must appear in the compiled bundle
    assert "active-target" in body, "compiled userscript missing /active-target fetch"
    assert "asset_switch_failed" in body, "compiled userscript missing abort-on-switch-fail branch"
    assert "_verifyAssetSwitched" in body, "compiled userscript missing verification helper"


def test_tampermonkey_script_version_is_at_least_8_125():
    r = requests.get(f"{API}/tampermonkey/script", timeout=15)
    assert r.status_code == 200
    import re
    m = re.search(r"@version\s+([\d.]+)", r.text)
    assert m, "no @version line found in served userscript"
    parts = [int(x) for x in m.group(1).split(".")]
    assert parts >= [8, 125, 0], f"served version {m.group(1)} is older than 8.125.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
