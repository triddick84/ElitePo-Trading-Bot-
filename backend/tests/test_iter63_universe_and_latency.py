"""
Iter 63 — Expanded Asset Universe + Latency-Offset wiring
=========================================================

Confirms:
  A1. /api/backtest/assets-universe returns 10 classes with grand_total >= 300
  A2. /api/backtest/assets-universe includes a stocks_otc class
  A3. /api/backtest/assets (legacy endpoint) returns the expanded universe
       (forex_otc, commodities_otc, crypto_otc, indices_otc, stocks_otc present)
  A4. OTC OANDA mapping covers commodities (XAU, XAG, WTI, BRENT)
  A5. /api/backtest/run still works for a freshly added pair (USDDKK_OTC)
"""
import os
import requests
import pytest

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"


def test_universe_endpoint_returns_10_classes():
    r = requests.get(f"{API}/api/backtest/assets-universe", timeout=15)
    assert r.status_code == 200
    j = r.json()
    classes = {c["id"]: c for c in j.get("classes", [])}
    expected = {
        "forex", "forex_otc",
        "commodities", "commodities_otc",
        "crypto", "crypto_otc",
        "indices", "indices_otc",
        "stocks", "stocks_otc",
    }
    assert expected.issubset(classes.keys()), f"missing classes: {expected - set(classes.keys())}"
    assert j.get("totals", {}).get("grand_total", 0) >= 300


def test_universe_includes_us_stocks_otc():
    r = requests.get(f"{API}/api/backtest/assets-universe", timeout=15)
    j = r.json()
    stocks_otc = next((c for c in j["classes"] if c["id"] == "stocks_otc"), None)
    assert stocks_otc is not None
    assert "AAPL_OTC" in stocks_otc["symbols"]
    assert "TSLA_OTC" in stocks_otc["symbols"]


def test_legacy_assets_endpoint_returns_expanded_universe():
    r = requests.get(f"{API}/api/backtest/assets", timeout=15)
    assert r.status_code == 200
    a = (r.json() or {}).get("assets", {})
    for k in ("forex_otc", "commodities_otc", "crypto_otc", "indices_otc", "stocks_otc"):
        assert k in a, f"missing category {k}"
        assert len(a[k]) > 0


def test_otc_oanda_map_includes_commodities():
    """Sanity: /api/ml/backfill-otc-from-oanda accepts XAUUSD_OTC + WTI_OTC."""
    # We don't actually trigger the backfill (would hit OANDA);
    # we just confirm the symbol is recognised by importing the map directly.
    import sys
    sys.path.insert(0, "/app/backend")
    from routes.ml import OTC_TO_OANDA
    for sym in ("XAUUSD_OTC", "XAGUSD_OTC", "WTI_OTC", "BRENT_OTC", "NGAS_OTC"):
        assert sym in OTC_TO_OANDA, f"{sym} missing from OTC_TO_OANDA"


def test_backtest_run_accepts_newly_added_otc_pair():
    """USDDKK_OTC was added in Iter 63 — make sure backtest doesn't crash."""
    r = requests.post(
        f"{API}/api/backtest/run",
        json={
            "strategy": "deep_confluence",
            "symbol": "USDDKK_OTC",
            "timeframe": "5s",
            "days": 1,
        },
        timeout=60,
    )
    # Either succeeds with synthetic/local data, or returns a clean 400
    # ("no historical data") — never a 500.
    assert r.status_code in (200, 400), r.text
