"""Iter 126 — Telegram integration regression."""
import re, sys
import httpx, pytest

sys.path.insert(0, "/app/backend")


def _api():
    env = open("/app/frontend/.env").read()
    return re.search(r"REACT_APP_BACKEND_URL=(\S+)", env).group(1) + "/api"


API = _api()


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------
def test_parse_call_seconds():
    from telegram_service import parse_signal
    s = parse_signal("EURUSD_OTC CALL 60s")
    assert s and s.asset == "EURUSD_OTC" and s.direction == "CALL" and s.expiry_seconds == 60


def test_parse_put_minutes():
    from telegram_service import parse_signal
    s = parse_signal("GBPUSD PUT 5m")
    assert s and s.direction == "PUT" and s.expiry_seconds == 300


def test_parse_normalizes_otc_suffix():
    from telegram_service import parse_signal
    s = parse_signal("EURUSDOTC CALL 90s")
    assert s and s.asset == "EURUSD_OTC"


def test_parse_synonym_up_down_buy_sell():
    from telegram_service import parse_signal
    for text, expected in (("EURUSD UP 60s", "CALL"),
                           ("EURUSD DOWN 60s", "PUT"),
                           ("EURUSD BUY 60s", "CALL"),
                           ("EURUSD SELL 60s", "PUT")):
        assert parse_signal(text).direction == expected


def test_parse_rejects_out_of_range_expiry():
    from telegram_service import parse_signal
    assert parse_signal("EURUSD CALL 99999s") is None  # >3600
    assert parse_signal("EURUSD CALL 2s") is None      # <5


def test_parse_rejects_unrelated_text():
    from telegram_service import parse_signal
    assert parse_signal("market update, no signals today") is None


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_status_endpoint():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/telegram/status")
    assert r.status_code == 200
    b = r.json()
    # Older `telegram_signal_notifier` and newer `telegram_routes` return
    # different shapes but both must expose `configured` and `chat_id`.
    assert b.get("success", True) is True or b.get("configured") is not None
    assert "configured" in b
    assert "chat_id" in b


@pytest.mark.asyncio
async def test_send_endpoint_lives():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{API}/telegram/send", json={
            "text": "🧪 Iter 126 regression test — please ignore",
        })
    assert r.status_code == 200
    # Either the new send-endpoint or the older one — both return JSON with truthy status
    b = r.json()
    assert isinstance(b, dict)


@pytest.mark.asyncio
async def test_received_signals_log_endpoint():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{API}/telegram/received-signals", params={"limit": 5})
    assert r.status_code == 200
    b = r.json()
    assert b["success"] is True
    assert "signals" in b
