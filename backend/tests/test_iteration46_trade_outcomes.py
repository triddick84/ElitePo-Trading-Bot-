"""
Iteration 46 — Real-accuracy tracking loop.

Validates:
- POST /api/signals/force-generate-v2 (quality tier + confidence clamps)
- POST /api/trades/report (audit ingest → tm_trade_reports)
- POST /api/trades/outcome (WIN/LOSS match or orphan insert; rejects bad outcome)
- GET  /api/signals/win-rate-stats (rolling buckets + by_strategy)
- End-to-end: report → outcome WIN → win-rate-stats increments
"""
import os
import time
import uuid
import pytest
import requests
from pathlib import Path


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        env = Path("/app/frontend/.env")
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return url.rstrip("/")


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------------------------------------------------------------------
# force-generate-v2
# ---------------------------------------------------------------------------
class TestForceGenerateV2:
    REQUIRED = ["direction", "confidence", "quality", "agreeing_strategies",
                "confluence_score", "components", "votes"]

    @pytest.mark.parametrize("asset", ["EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC"])
    def test_returns_signal_with_all_fields(self, client, asset):
        r = client.post(f"{API}/signals/force-generate-v2",
                        params={"asset": asset, "expiry_seconds": 60}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True, j
        sig = j.get("signal")
        assert sig, "signal missing"

        for f in self.REQUIRED:
            assert f in sig, f"field {f} missing in signal: {sig.keys()}"

        assert sig["direction"] in ("CALL", "PUT"), sig["direction"]
        assert isinstance(sig["confidence"], (int, float))
        assert sig["quality"] in ("HIGH", "MEDIUM", "LOW"), sig["quality"]
        assert isinstance(sig["agreeing_strategies"], int)
        cs = sig["confluence_score"]
        assert isinstance(cs, (int, float)) and 0 <= cs <= 1, cs
        assert isinstance(sig["components"], dict)
        assert isinstance(sig["votes"], dict)
        assert "call" in sig["votes"] and "put" in sig["votes"]

    @pytest.mark.parametrize("asset", ["EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC"])
    def test_confidence_ceiling_and_quality_clamp(self, client, asset):
        r = client.post(f"{API}/signals/force-generate-v2",
                        params={"asset": asset, "expiry_seconds": 60}, timeout=30)
        assert r.status_code == 200
        sig = r.json()["signal"]
        conf = float(sig["confidence"])
        q = sig["quality"]

        # Global ceiling
        assert conf <= 82.0 + 1e-6, f"confidence {conf} exceeded realistic ceiling 82"
        # Tier-specific clamps
        if q == "MEDIUM":
            assert conf <= 75.0 + 1e-6, f"MEDIUM confidence {conf} exceeds 75"
        elif q == "LOW":
            assert conf <= 65.0 + 1e-6, f"LOW confidence {conf} exceeds 65"
        # HIGH: still capped at 82 by the 52 + 30*confluence transform

    def test_never_empty(self, client):
        r = client.post(f"{API}/signals/force-generate-v2",
                        params={"asset": "EURUSD_OTC", "expiry_seconds": 60}, timeout=30)
        assert r.status_code == 200
        sig = r.json().get("signal")
        assert sig and sig.get("direction") in ("CALL", "PUT")


# ---------------------------------------------------------------------------
# /api/trades/report
# ---------------------------------------------------------------------------
class TestTradesReport:
    def test_report_stores(self, client):
        payload = {
            "asset": "EURUSD_OTC",
            "direction": "CALL",
            "amount": 1.0,
            "strategy": f"TEST_strat_{uuid.uuid4().hex[:6]}",
            "confidence": 70.0,
            "source": "pytest-iter46",
        }
        r = client.post(f"{API}/trades/report", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True
        assert j.get("stored") is True
        assert "server_received_at" in j


# ---------------------------------------------------------------------------
# /api/trades/outcome
# ---------------------------------------------------------------------------
class TestTradesOutcome:
    def test_outcome_rejects_bad_value(self, client):
        r = client.post(f"{API}/trades/outcome",
                        json={"outcome": "MAYBE"}, timeout=15)
        # Endpoint returns 200 with success:false for invalid outcome
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is False
        assert "outcome" in (j.get("error") or "").lower()

    def test_outcome_matches_pending_trade(self, client):
        asset = "EURUSD_OTC"
        strategy = f"TEST_match_{uuid.uuid4().hex[:6]}"
        # 1) Report a trade
        rep = client.post(f"{API}/trades/report", json={
            "asset": asset, "direction": "CALL", "amount": 1.0,
            "strategy": strategy, "confidence": 70.0, "source": "pytest-iter46",
        }, timeout=15)
        assert rep.status_code == 200 and rep.json().get("stored")

        # 2) Record WIN outcome
        out = client.post(f"{API}/trades/outcome", json={
            "outcome": "WIN", "asset": asset,
            "strategy": strategy, "profit": 0.8,
        }, timeout=15)
        assert out.status_code == 200, out.text
        jo = out.json()
        assert jo.get("success") is True
        assert jo.get("matched_trade") is True, jo
        assert jo.get("trade_asset") in (asset, asset.replace("_OTC", "OTC"))

    def test_outcome_orphan_when_no_pending(self, client):
        # Use a synthetic asset that should have no pending trade
        unique_asset = f"ZZZTEST{uuid.uuid4().hex[:4].upper()}_OTC"
        r = client.post(f"{API}/trades/outcome", json={
            "outcome": "LOSS", "asset": unique_asset,
            "strategy": "TEST_orphan", "profit": -1.0,
        }, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True
        assert j.get("stored") is True
        assert j.get("matched_trade") is False


# ---------------------------------------------------------------------------
# /api/signals/win-rate-stats
# ---------------------------------------------------------------------------
class TestWinRateStats:
    def test_shape(self, client):
        r = client.get(f"{API}/signals/win-rate-stats", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True
        for key in ("total_with_outcome", "last_50", "last_100", "last_500", "by_strategy"):
            assert key in j, f"{key} missing"
        for bucket in ("last_50", "last_100", "last_500"):
            b = j[bucket]
            assert set(["trades", "wins", "losses", "win_rate"]).issubset(b.keys()), b


# ---------------------------------------------------------------------------
# End-to-end: report → outcome WIN → win-rate-stats increments
# ---------------------------------------------------------------------------
class TestEndToEnd:
    def test_full_flow_increments_wins(self, client):
        # Baseline
        base = client.get(f"{API}/signals/win-rate-stats", timeout=15).json()
        base_wins_50 = base["last_50"]["wins"]
        base_total = base["total_with_outcome"]

        asset = "EURUSD_OTC"
        strategy = f"TEST_e2e_{uuid.uuid4().hex[:6]}"

        # Report
        rep = client.post(f"{API}/trades/report", json={
            "asset": asset, "direction": "PUT", "amount": 1.0,
            "strategy": strategy, "confidence": 68.0, "source": "pytest-e2e",
        }, timeout=15)
        assert rep.status_code == 200 and rep.json().get("stored")

        # Outcome WIN
        out = client.post(f"{API}/trades/outcome", json={
            "outcome": "WIN", "asset": asset,
            "strategy": strategy, "profit": 0.85,
        }, timeout=15)
        assert out.status_code == 200
        assert out.json().get("matched_trade") is True

        # Small delay to allow mongo visibility
        time.sleep(0.5)

        after = client.get(f"{API}/signals/win-rate-stats", timeout=15).json()
        assert after["total_with_outcome"] >= base_total + 1, (
            f"total_with_outcome did not increment: {base_total} -> {after['total_with_outcome']}"
        )
        assert after["last_50"]["wins"] >= base_wins_50 + 1, (
            f"last_50 wins did not increment: {base_wins_50} -> {after['last_50']['wins']}"
        )

        # Strategy should appear in by_strategy
        by_strat = after.get("by_strategy", {})
        assert strategy in by_strat, f"strategy {strategy} not reported in by_strategy"
        assert by_strat[strategy]["wins"] >= 1
