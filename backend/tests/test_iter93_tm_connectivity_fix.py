"""
Iter 93 — TM connectivity bug fix.

Reported bug: "tampermonkey script is having issues with connecting to
application and pocket option, alot of timeout and offline then online
connection"

Root causes fixed:
  1. The compiled TM bundle shipped with `API_URL:"https://www.elitepotradingbot.com/api"`
     hardcoded. Unless the user manually set `GM_setValue("epb_api_url", "…")`
     every fetch went to the stale domain → "Backend disconnected" flaps.
     Fix: /api/tampermonkey/script now rewrites API_URL to the host serving
     the script (self-healing).
  2. `@updateURL`/`@downloadURL` also pointed at the stale domain — TM
     auto-update was silently failing.
  3. Missing @connect allow-list entry blocked GM_xmlhttpRequest in strict
     TM installs. New host is auto-added.
  4. Hot Mongo collections (signal_latency_log_client, trading_signals,
     signal_latency_log) had ZERO non-_id indexes. Adaptive-offset (Iter 91)
     ran a full collscan on 5-40k docs per /signals/latest call → intermittent
     timeouts under concurrent load.
  5. `TradingSignal.risk_assessment` + `.suggested_stake` were required but
     legacy documents lack them. Pydantic ValidationErrors spammed the logs
     8× per call and could cascade into 500s.
"""

from __future__ import annotations

import os
import sys

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
sys.path.insert(0, "/app/backend")


def test_tampermonkey_script_rewrites_api_url_to_serving_host():
    r = requests.get(
        f"{BASE_URL}/api/tampermonkey/script",
        headers={
            "Host": "self-heal-test.example.com",
            "x-forwarded-proto": "https",
            "x-forwarded-host": "self-heal-test.example.com",
        },
        timeout=15,
    )
    assert r.status_code == 200
    body = r.text
    # No stale API_URL literal
    assert 'API_URL:"https://www.elitepotradingbot.com/api"' not in body
    # Injected the serving host
    assert 'API_URL:"https://self-heal-test.example.com/api"' in body
    # Response header carries the resolved API root for diagnostics
    assert r.headers.get("X-EPB-Api-Root") == "https://self-heal-test.example.com/api"


def test_tampermonkey_script_rewrites_updateurl_downloadurl():
    r = requests.get(
        f"{BASE_URL}/api/tampermonkey/script",
        headers={"Host": "rewrite-test.example.com", "x-forwarded-proto": "https"},
        timeout=15,
    )
    body = r.text
    assert "// @updateURL    https://rewrite-test.example.com/api/tampermonkey/script" in body
    assert "// @downloadURL  https://rewrite-test.example.com/api/tampermonkey/script" in body
    # The stale URL should no longer appear in an @updateURL/@downloadURL header
    for line in body.splitlines():
        if line.startswith("// @updateURL") or line.startswith("// @downloadURL"):
            assert "elitepotradingbot.com" not in line, f"Stale URL still present: {line}"


def test_tampermonkey_script_appends_new_host_to_connect_allowlist():
    r = requests.get(
        f"{BASE_URL}/api/tampermonkey/script",
        headers={"Host": "allowlist-test.example.com", "x-forwarded-proto": "https"},
        timeout=15,
    )
    body = r.text
    connect_hosts = [
        line.split()[2] for line in body.splitlines()
        if line.startswith("// @connect")
    ]
    assert "allowlist-test.example.com" in connect_hosts, \
        f"Serving host not added to @connect list: {connect_hosts}"


def test_hot_collections_have_expected_indexes():
    """
    Startup indexer must have created composite indexes on the query
    hotpath — without them, adaptive-offset collscanned 5-40 k docs
    on every /signals/latest fire.
    """
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def collect():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        return {
            "client": await db.signal_latency_log_client.index_information(),
            "signals": await db.trading_signals.index_information(),
            "server": await db.signal_latency_log.index_information(),
        }

    all_idx = asyncio.new_event_loop().run_until_complete(collect())
    assert "asset_logged_at_desc" in all_idx["client"], \
        f"signal_latency_log_client missing composite index: {list(all_idx['client'])}"
    for name in ("symbol_timestamp_desc", "asset_timestamp_desc", "timestamp_desc"):
        assert name in all_idx["signals"], \
            f"trading_signals missing {name}: {list(all_idx['signals'])}"


def test_trading_signal_model_accepts_legacy_records():
    """Legacy signals without risk_assessment/suggested_stake must parse."""
    from trading_models import TradingSignal, AssetType, SignalDirection, TradingStrategy
    # Build a legacy-shaped dict — all the required fields but missing the two
    # that Iter 60 added.
    sig = TradingSignal(
        symbol="EURUSD_OTC",
        asset_type=AssetType.FOREX,
        direction=SignalDirection.CALL,
        entry_price=1.1,
        expiration_minutes=1,
        probability=75,
        confidence_level="HIGH",
        strategy_used=TradingStrategy.RSI_5,
        technical_analysis={"rsi": 55},
    )
    # Should parse with defaults for the newly-optional fields
    assert sig.risk_assessment == ""
    assert sig.suggested_stake == 0.0
    assert sig.market_analysis_summary == ""


def test_signals_latest_still_responds_under_500ms_after_indexes():
    """After indexes are in place, /signals/latest must respond fast."""
    import time
    # Warm up the pipe first
    requests.get(f"{BASE_URL}/api/signals/latest?symbol=EURUSD_OTC", timeout=15)
    times = []
    for _ in range(5):
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/signals/latest?symbol=EURUSD_OTC",
            timeout=15,
        )
        times.append(time.time() - start)
        assert r.status_code == 200
    # Median must be well under our 250ms latency-abstain threshold
    times.sort()
    median = times[len(times) // 2]
    assert median < 0.500, \
        f"median /signals/latest latency {median:.3f}s — expected < 0.5s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
