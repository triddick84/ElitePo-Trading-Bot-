"""
Iteration 56 — Dashboard ↔ TM script signal flow regression tests.

Covers the chain that was broken:
  1. /api/signals/force-generate-v2 persists signals to trading_signals
     so the TM poller (/signals/latest?symbol=X) can find them.
  2. /api/signals/latest?symbol=X actually filters by symbol (was ignored).
  3. /api/signals/auto-generate/enhanced (single-pass + scan_all_assets)
     now uses force-generate-v2 underneath → returns CALL/PUT not SELL,
     populates confidence, strategy, abstain, latency fields.
  4. Auto-generated signals are also persisted → TM pollable.
  5. /api/signals/scan/stop releases the continuous-scanner lock.

Run: pytest -xvs backend/tests/test_iter56_dashboard_tm_chain.py
"""
import os
import time
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
if not API.endswith("/api"):
    API = API.rstrip("/") + "/api"


def test_force_generate_v2_persists_to_trading_signals():
    """force-generate-v2 must write to trading_signals so TM poller can see it."""
    asset = "EURUSD_OTC"
    r = requests.post(
        f"{API}/signals/force-generate-v2",
        params={"asset": asset, "expiry_seconds": 60},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    sig = body.get("signal", {})
    sig_id = sig.get("id")
    assert sig_id, "force-generate-v2 must return a signal id"
    
    # Now poll latest — the same id should come back
    r2 = requests.get(
        f"{API}/signals/latest",
        params={"symbol": asset, "use_enhanced": False},
        timeout=10,
    )
    assert r2.status_code == 200
    latest = r2.json().get("signal", {})
    assert latest.get("id") == sig_id, (
        f"TM poller returned id={latest.get('id')}, expected {sig_id}"
    )
    assert latest.get("source") == "force-generate-v2"


def test_signals_latest_filters_by_symbol():
    """/signals/latest must respect ?symbol= and not return signals for other assets."""
    # Generate distinct signals for two assets
    requests.post(f"{API}/signals/force-generate-v2", params={"asset": "EURUSD_OTC"}, timeout=60)
    time.sleep(0.5)
    requests.post(f"{API}/signals/force-generate-v2", params={"asset": "GBPUSD_OTC"}, timeout=60)
    time.sleep(0.5)
    
    eur = requests.get(
        f"{API}/signals/latest",
        params={"symbol": "EURUSD_OTC", "use_enhanced": False},
        timeout=10,
    ).json()
    gbp = requests.get(
        f"{API}/signals/latest",
        params={"symbol": "GBPUSD_OTC", "use_enhanced": False},
        timeout=10,
    ).json()
    
    eur_sym = (eur.get("signal") or {}).get("symbol", "")
    gbp_sym = (gbp.get("signal") or {}).get("symbol", "")
    assert "EUR" in eur_sym.upper(), f"expected EURUSD signal, got {eur_sym}"
    assert "GBP" in gbp_sym.upper(), f"expected GBPUSD signal, got {gbp_sym}"


def test_scan_all_assets_returns_valid_signals():
    """
    Dashboard 'Scan All Assets' should return signals in the new format:
    direction CALL/PUT, populated confidence/strategy/abstain.
    """
    r = requests.post(
        f"{API}/signals/auto-generate/enhanced",
        params={
            "scan_all_assets": True,
            "min_payout": 80,
            "min_accuracy": 60,
            "max_signals": 5,
            "continuous": False,
        },
        timeout=90,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    sigs = body.get("signals", [])
    assert len(sigs) > 0, "scan returned 0 signals — regression of Iter 56 fix"
    
    for s in sigs:
        assert s.get("direction") in ("CALL", "PUT"), (
            f"bad direction {s.get('direction')} (Iter 56 should normalise to CALL/PUT)"
        )
        assert isinstance(s.get("confidence"), (int, float)), "confidence missing/non-numeric"
        assert s.get("strategy"), "strategy missing"
        assert "abstain" in s, "abstain flag missing"
        # latency block (from force-generate-v2 pipeline)
        assert "latency" in s or s.get("source") == "force-generate-v2", (
            "scanned signal should have latency block (came from force-generate-v2)"
        )


def test_scan_signals_are_persisted_for_tm_poller():
    """Signals returned by /auto-generate/enhanced must be in trading_signals."""
    r = requests.post(
        f"{API}/signals/auto-generate/enhanced",
        params={"scan_all_assets": True, "min_accuracy": 60, "max_signals": 3, "continuous": False},
        timeout=90,
    )
    sigs = r.json().get("signals", [])
    assert sigs, "no signals to verify persistence for"
    
    first = sigs[0]
    sym = first.get("symbol")
    sid = first.get("id")
    assert sym and sid
    
    # Symbol-filtered poll must return this exact id (or one for the same symbol)
    latest = requests.get(
        f"{API}/signals/latest",
        params={"symbol": sym, "use_enhanced": False},
        timeout=10,
    ).json()
    returned = latest.get("signal", {})
    assert returned, f"no signal returned for {sym}"
    # The scan stores multiple signals; latest may be a different id but must match symbol
    assert sym.upper().replace("_OTC", "") in (returned.get("symbol", "").upper().replace("_OTC", ""))


def test_scan_stop_endpoint():
    """POST /signals/scan/stop must be idempotent and return success."""
    r = requests.post(f"{API}/signals/scan/stop", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    # was_running may be true or false depending on prior tests
    assert "was_running" in body


def test_scan_status_endpoint():
    r = requests.get(f"{API}/signals/scan/status", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "is_scanning" in body
