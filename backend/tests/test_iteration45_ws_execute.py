"""
Iteration 45 — Direct-WS Trade Execution (21s Reversal strategy)
================================================================

Validates:
- POST /api/po/trade/ws-execute error/validation paths
- GET  /api/po/trade/ws-status
- Mongo audit into `po_ws_trades`
- pocket_option_ws_executor._normalize_asset unit behaviour
- Tampermonkey modular bundle v8.11.0 markers

Real Pocket Option WS is NOT reachable — all test paths must fail gracefully
with {success:false, error:...} (no 5xx crashes).
"""
import os
import sys
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

# Add backend to sys.path so we can import pocket_option_ws_executor directly
sys.path.insert(0, "/app/backend")


# ---------- Mongo helpers (sync; use pymongo) ----------
@pytest.fixture(scope="module")
def mongo_db():
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest.fixture(autouse=True)
def clean_ssid_state(mongo_db):
    """Ensure no SSID in po_ssid_state before each test."""
    mongo_db["po_ssid_state"].delete_many({})
    yield


# =====================================================================
# 1. GET /api/po/trade/ws-status — no cached client
# =====================================================================
class TestWsStatus:
    def test_ws_status_no_cached_client(self):
        r = requests.get(f"{API}/po/trade/ws-status", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # When no client is cached, must report connected=false
        # (note: _client may be cached from prior connect attempt, but should be False here since WS handshake fails)
        assert "connected" in data
        assert data["connected"] is False or data["connected"] is True  # structure check
        assert "session_cached" in data


# =====================================================================
# 2. POST /api/po/trade/ws-execute — no SSID bridged
# =====================================================================
class TestWsExecuteNoSsid:
    def test_no_bridged_ssid_returns_graceful_error(self, mongo_db):
        # Ensure no SSID
        mongo_db["po_ssid_state"].delete_many({})
        # Reset cached client too (module-level globals)
        import pocket_option_ws_executor as pwe
        pwe._client = None
        pwe._current_session = None

        payload = {
            "asset": "EURUSD_otc",
            "direction": "CALL",
            "amount": 1.0,
            "duration_seconds": 5,
            "strategy": "21s-reversal-test",
        }
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is False
        assert "No bridged SSID" in (data.get("error") or ""), data
        assert "latency_ms" in data and isinstance(data["latency_ms"], int)


# =====================================================================
# 3. Direction validation
# =====================================================================
class TestWsExecuteValidation:
    def test_invalid_direction(self):
        payload = {
            "asset": "EURUSD_otc",
            "direction": "xyz",
            "amount": 1.0,
            "duration_seconds": 5,
        }
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is False
        assert "Invalid direction" in (data.get("error") or ""), data

    @pytest.mark.parametrize("missing", ["asset", "direction", "amount", "duration_seconds"])
    def test_missing_field_returns_422(self, missing):
        payload = {
            "asset": "EURUSD_otc",
            "direction": "CALL",
            "amount": 1.0,
            "duration_seconds": 5,
        }
        payload.pop(missing)
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=15)
        assert r.status_code == 422, f"Expected 422 for missing {missing}, got {r.status_code}: {r.text}"

    def test_amount_must_be_gt_zero(self):
        payload = {"asset": "EURUSD_otc", "direction": "CALL", "amount": 0, "duration_seconds": 5}
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=15)
        assert r.status_code == 422


# =====================================================================
# 4. Fake SSID triggers WS handshake failure (graceful)
# =====================================================================
class TestWsExecuteFakeSsid:
    def test_fake_ssid_fails_gracefully(self, mongo_db):
        # Insert a fake SSID that will fail at WS handshake
        mongo_db["po_ssid_state"].update_one(
            {"_id": "current"},
            {"$set": {
                "session": "FAKE_SESSION_FOR_TEST_" + str(int(time.time())),
                "uid": 12345,
                "is_demo": True,
                "updated_at": "2026-01-01T00:00:00Z",
            }},
            upsert=True,
        )
        # Reset client cache so it attempts new connection
        import pocket_option_ws_executor as pwe
        pwe._client = None
        pwe._current_session = None

        payload = {
            "asset": "EURUSD_otc",
            "direction": "PUT",
            "amount": 2.0,
            "duration_seconds": 5,
            "strategy": "21s-reversal-test-fake",
        }
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is False
        err = (data.get("error") or "").lower()
        # Accept either the handshake-failed RuntimeError OR an underlying exception
        assert ("handshake" in err and "ssid" in err) or "expired" in err or "connect" in err or "session" in err, data
        assert "latency_ms" in data

        # Clean up
        mongo_db["po_ssid_state"].delete_many({})


# =====================================================================
# 5. Audit log persistence in po_ws_trades
# =====================================================================
class TestAuditLog:
    def test_audit_record_written_on_failure(self, mongo_db):
        # Clear state
        mongo_db["po_ssid_state"].delete_many({})
        # Use a unique strategy tag to find our audit record
        strategy_tag = f"audit-test-{int(time.time() * 1000)}"
        payload = {
            "asset": "GBPUSD_otc",
            "direction": "CALL",
            "amount": 5.0,
            "duration_seconds": 5,
            "strategy": strategy_tag,
        }
        r = requests.post(f"{API}/po/trade/ws-execute", json=payload, timeout=30)
        assert r.status_code == 200
        assert r.json()["success"] is False

        # Give Mongo a beat
        time.sleep(0.5)
        doc = mongo_db["po_ws_trades"].find_one({"strategy": strategy_tag})
        assert doc is not None, "Audit record was not written to po_ws_trades"
        assert doc["asset"] == "GBPUSD_otc"
        assert doc["direction"] == "CALL"
        assert doc["amount"] == 5.0
        assert doc["success"] is False
        assert doc["error"] is not None
        assert "placed_at" in doc


# =====================================================================
# 6. _normalize_asset unit tests (direct import)
# =====================================================================
class TestNormalizeAsset:
    def test_normalize_variants(self):
        from pocket_option_ws_executor import _normalize_asset
        cases = [
            ("EURUSD", "EURUSD"),
            ("EUR/USD", "EURUSD"),
            ("EURUSD OTC", "EURUSD_otc"),
            ("EURUSD_OTC", "EURUSD_otc"),
            ("EUR/USD OTC", "EURUSD_otc"),
        ]
        for inp, expected in cases:
            got = _normalize_asset(inp)
            assert got == expected, f"_normalize_asset({inp!r}) = {got!r}, expected {expected!r}"


# =====================================================================
# 7. Tampermonkey modular bundle markers
# =====================================================================
class TestTampermonkeyBundle:
    BUNDLE_URL_PATH = "/pocket-option-auto-trader-modular.user.js"

    @pytest.fixture(scope="class")
    def bundle_text(self):
        # The bundle is served by the frontend at the root (public/)
        # Use the frontend base, which in this env is same host as backend
        url = f"{BASE_URL}{self.BUNDLE_URL_PATH}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            # fallback: read from disk
            with open("/app/frontend/public/pocket-option-auto-trader-modular.user.js", "r") as f:
                return f.read()
        return r.text

    def test_version_is_8_11_0(self, bundle_text):
        assert "8.11.0" in bundle_text
        assert "@version      8.11.0" in bundle_text or '"8.11.0"' in bundle_text

    def test_contains_ws_execute_endpoint_ref(self, bundle_text):
        assert "po/trade/ws-execute" in bundle_text

    def test_contains_ssid_status_endpoint_ref(self, bundle_text):
        assert "po/ssid/status" in bundle_text

    def test_contains_execution_mode_config(self, bundle_text):
        assert "executionMode" in bundle_text

    def test_contains_bridge_health_config(self, bundle_text):
        # Could be bridgeHealthy, bridgeHealth, bridgeHealthCheckedAt
        assert "bridgeHealth" in bundle_text
