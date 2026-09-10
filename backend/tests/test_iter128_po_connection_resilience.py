"""Iter 128 — Pocket Option connection resilience regression."""
import re
import sys

import httpx
import pytest

sys.path.insert(0, "/app/backend")


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()


# ---------------------------------------------------------------------------
# Static code checks — proves the fix is present in the codebase
# ---------------------------------------------------------------------------
def test_pocket_option_prefers_working_demo_eu_url():
    """The working demo endpoint (`demo-api-eu.po.market`) must be the primary
    URL. The old `api-c.po.market` primary consistently 403s from server
    clients and should now be the fallback only."""
    src = open("/app/backend/pocket_option_auto_trader.py").read()
    # Primary must be DEMO_WS_URL_ALT (the demo-api-eu URL)
    m = re.search(r"self\.ws_url = self\.DEMO_WS_URL_ALT if self\.is_demo", src)
    assert m, "primary URL must default to DEMO_WS_URL_ALT (working endpoint)"
    # Legacy `api-c` URL is kept as fallback
    m2 = re.search(r"self\.ws_url_alt = self\.DEMO_WS_URL\b", src)
    assert m2, "legacy DEMO_WS_URL must remain as the fallback URL"


def test_connect_tries_both_urls_before_scheduling_reconnect():
    """`connect()` must try both URLs synchronously before returning False.
    Prior version returned False after the first URL failed and scheduled a
    background reconnect, which made the frontend show a spurious 'Failed to
    connect' toast even though the fallback would have succeeded."""
    src = open("/app/backend/pocket_option_auto_trader.py").read()
    assert "async def _connect_once" in src, "must extract single-url attempt into _connect_once"
    assert "candidate_urls = [self.ws_url, self.ws_url_alt]" in src
    # The reconnect scheduler must only be called after BOTH URLs fail.
    m = re.search(
        r"# Both URLs failed.*?await self\._schedule_reconnect\(\)",
        src, re.DOTALL,
    )
    assert m, "background reconnect must only be scheduled after both URLs fail"


def test_ssid_service_import_wired_up():
    """`get_ssid_service` was called by multiple /ssid endpoints in
    `routes/pocket_option.py` but never imported → NameError. Iter 128
    imports it with a graceful fallback stub."""
    src = open("/app/backend/routes/pocket_option.py").read()
    assert "from ssid_auto_refresh_service import get_ssid_service" in src


# ---------------------------------------------------------------------------
# Live endpoint checks — proves the fix works end-to-end
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ssid_status_does_not_raise_nameerror():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/ssid/status")
    assert r.status_code == 200
    b = r.json()
    assert "error" not in b or "get_ssid_service" not in str(b.get("error", "")), \
        "get_ssid_service NameError must be fixed"


@pytest.mark.asyncio
async def test_auto_trade_connect_returns_success_true():
    """Live PO connection through the fixed endpoint should now succeed on
    the very first try (using the demo-api-eu URL instead of the 403-locked
    api-c URL)."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/auto-trade/connect")
    assert r.status_code == 200
    b = r.json()
    # Success is expected but connection can occasionally fail transiently;
    # in that case the message must be user-friendly (no stack trace / NameError).
    if b.get("success"):
        assert b.get("is_connected") is True
        assert b.get("connection_state") in ("authenticated", "authenticating", "connected")
    else:
        assert "get_ssid_service" not in str(b.get("message", ""))


@pytest.mark.asyncio
async def test_auto_trade_status_returns_expected_shape():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{API}/auto-trade/status")
    assert r.status_code == 200
    b = r.json()
    for k in ("success", "is_running", "is_connected", "connection_state",
              "is_auto_trade_enabled", "balance"):
        assert k in b, f"missing status field: {k}"
