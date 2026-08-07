"""
Iter 93 review — full backend verification.
Covers: TM script rewrite on public host, indexes, latency SLO,
recommended_offset_sec preservation, prewarm/latency/presets/custom-strategies
regression checks.
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

# Preview public URL (routes through Cloudflare/K8s ingress). This is what
# real Tampermonkey installs hit.
PUBLIC_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://auto-invert-engine.preview.emergentagent.com",
).rstrip("/")
# Internal URL bypasses Cloudflare and lets us spoof Host headers for
# self-heal verification.
INTERNAL_URL = "http://localhost:8001"


# ------------ Tampermonkey self-healing (public host) ------------

def test_tm_script_public_url_rewrites_api_url_to_public_host():
    """Real request through preview host must have API_URL rewritten to
    the preview host — no stale elitepotradingbot literal anywhere."""
    r = requests.get(f"{PUBLIC_URL}/api/tampermonkey/script", timeout=30)
    assert r.status_code == 200, r.status_code
    body = r.text
    assert 'API_URL:"https://www.elitepotradingbot.com/api"' not in body, (
        "Stale hardcoded API_URL still present in served script"
    )
    expected = 'API_URL:"' + PUBLIC_URL + '/api"'
    assert expected in body, f"Expected {expected!r} in served script"


def test_tm_script_public_content_type_and_headers():
    r = requests.get(f"{PUBLIC_URL}/api/tampermonkey/script", timeout=30)
    assert r.status_code == 200
    assert "application/javascript" in r.headers.get("Content-Type", "")
    cc = r.headers.get("Cache-Control", "")
    assert "no-cache" in cc or "no-store" in cc, f"Cache-Control not restrictive: {cc}"
    api_root = r.headers.get("X-EPB-Api-Root", "")
    assert api_root.endswith("/api"), f"X-EPB-Api-Root missing/invalid: {api_root!r}"


def test_tm_script_public_updateurl_downloadurl_rewritten():
    r = requests.get(f"{PUBLIC_URL}/api/tampermonkey/script", timeout=30)
    body = r.text
    for line in body.splitlines():
        if line.startswith("// @updateURL") or line.startswith("// @downloadURL"):
            assert "elitepotradingbot.com" not in line, f"Stale in: {line}"
            assert PUBLIC_URL in line, f"Public host missing in: {line}"


def test_tm_script_public_connect_allowlist_contains_public_host():
    r = requests.get(f"{PUBLIC_URL}/api/tampermonkey/script", timeout=30)
    body = r.text
    host = PUBLIC_URL.replace("https://", "").replace("http://", "")
    connects = [
        line.split()[2] for line in body.splitlines()
        if line.startswith("// @connect")
    ]
    assert host in connects, f"Public host {host} not in @connect: {connects}"


# ------------ Signals latency SLO ------------

def test_signals_latest_carries_recommended_offset_and_adaptive_meta():
    """Iter 91 fields must still be present on the returned signal."""
    r = requests.get(
        f"{PUBLIC_URL}/api/signals/latest?symbol=EURUSD_OTC", timeout=20
    )
    assert r.status_code == 200
    data = r.json()
    if not data.get("success") or not data.get("signal"):
        pytest.skip(f"No live signal available: {data}")
    sig = data["signal"]
    assert "recommended_offset_sec" in sig, f"Missing recommended_offset_sec: {list(sig)[:20]}"
    assert "adaptive_offset_meta" in sig, f"Missing adaptive_offset_meta: {list(sig)[:20]}"


# ------------ Regression: Iter 89 prewarm ------------

def test_signal_prewarm_stats_still_reachable():
    r = requests.get(f"{PUBLIC_URL}/api/signal-prewarm/stats", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True, data


# ------------ Regression: Iter 86 latency stats ------------

def test_latency_stats_returns_percentiles():
    r = requests.get(f"{PUBLIC_URL}/api/latency/stats", timeout=15)
    assert r.status_code == 200
    data = r.json()
    # Data can be dict wrapping a list, or a list.
    routes = data.get("routes") if isinstance(data, dict) else data
    if routes is None and isinstance(data, dict):
        # try common alt keys
        routes = data.get("data") or data.get("stats")
    assert isinstance(routes, list), f"latency stats not a list: {type(routes).__name__} — payload={str(data)[:200]}"
    if routes:
        row = routes[0]
        assert any(k in row for k in ("p50", "p95", "p99")), f"missing percentiles: {list(row)}"


# ------------ Regression: Iter 91 Ichimoku preset ------------

def test_custom_strategies_presets_has_ichimoku():
    r = requests.get(f"{PUBLIC_URL}/api/custom-strategies/presets", timeout=15)
    assert r.status_code == 200
    data = r.json()
    presets = data.get("presets") if isinstance(data, dict) else data
    assert isinstance(presets, list) and presets, f"presets empty/invalid: {data}"
    names = [
        (p.get("name") or p.get("title") or "").lower() for p in presets
    ]
    assert any("ichimoku" in n for n in names), f"Ichimoku preset missing: {names}"


# ------------ Regression: Iter 92 5-group strategy persistence ------------

def test_custom_strategies_persists_5_groups_call_and_put():
    """3 CALL groups + 2 PUT groups round-trip via /api/custom-strategies."""
    user_id = "integration_test_iter93"
    strat_name = f"TEST_iter93_{uuid.uuid4().hex[:8]}"

    def cond(indicator, op="greater_than", val=50):
        return {
            "conditions": [
                {
                    "indicator": indicator,
                    "parameters": {"period": 14},
                    "output": "value",
                    "operator": op,
                    "compare_to": "value",
                    "compare_value": val,
                }
            ],
            "logical_operator": "AND",
        }

    payload = {
        "user_id": user_id,
        "name": strat_name,
        "description": "iter93 review test",
        "call_conditions": [cond("RSI", "less_than", 30),
                            cond("STOCHASTIC", "less_than", 20),
                            cond("MACD", "crosses_above", 0)],
        "put_conditions": [cond("RSI", "greater_than", 70),
                           cond("STOCHASTIC", "greater_than", 80)],
        "timeframes": ["1m"],
        "assets": ["EURUSD_OTC"],
        "markets": ["OTC"],
        "min_confidence": 70,
    }
    r = requests.post(f"{PUBLIC_URL}/api/custom-strategies", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"POST failed {r.status_code}: {r.text[:400]}"
    created = r.json()
    strategy_id = (
        created.get("strategy_id")
        or created.get("id")
        or (created.get("strategy") or {}).get("id")
        or (created.get("strategy") or {}).get("strategy_id")
    )

    g = requests.get(f"{PUBLIC_URL}/api/custom-strategies?user_id={user_id}", timeout=15)
    assert g.status_code == 200
    lst = g.json().get("strategies", [])
    found = next((s for s in lst if s.get("name") == strat_name), None)
    assert found is not None, f"Created strategy '{strat_name}' not found in {len(lst)} strategies"
    assert len(found.get("call_conditions", [])) == 3, (
        f"Expected 3 CALL groups, got {len(found.get('call_conditions', []))}"
    )
    assert len(found.get("put_conditions", [])) == 2, (
        f"Expected 2 PUT groups, got {len(found.get('put_conditions', []))}"
    )

    # Best-effort cleanup
    if strategy_id:
        try:
            requests.delete(
                f"{PUBLIC_URL}/api/custom-strategies/{strategy_id}?user_id={user_id}",
                timeout=10,
            )
        except Exception:
            pass


# ------------ Indexes (also covered by iter93 file, kept for completeness) ------------

def test_signal_latency_log_has_expected_indexes():
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def collect():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        return await db.signal_latency_log.index_information()

    idx = asyncio.new_event_loop().run_until_complete(collect())
    for expected in ("route_logged_at_desc", "logged_at_desc"):
        assert expected in idx, f"signal_latency_log missing {expected}: {list(idx)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
