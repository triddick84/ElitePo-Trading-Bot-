"""
Iteration 44 — SSID Bridge backend tests.

Covers:
- POST /api/po/ssid/update (valid, invalid, dedup/idempotent heartbeat, new session replace)
- GET  /api/po/ssid/status (present, absent, no raw SSID leak)
- POST /api/po/ssid/connect (fake session → graceful error)
- Mongo collections po_ssid_state (single _id='current') + po_ssid_history audit
- Tampermonkey modular bundle (v8.10.0, @run-at document-start, SSID markers)
"""
import os
import json
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "trading_bot_db")

SESSION_A = "TESTsessionAAAAAAAAAAAAAAAAAAAAA_itr44_aaaa"
SESSION_B = "TESTsessionBBBBBBBBBBBBBBBBBBBBB_itr44_bbbb"


def _auth_frame(session: str, uid: int = 54321, is_demo: int = 1, platform: int = 1) -> str:
    inner = {"session": session, "isDemo": is_demo, "uid": uid, "platform": platform}
    return f'42["auth",{json.dumps(inner)}]'


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module", autouse=True)
def clean_before_tests(mongo):
    # Clean slate for SSID collections
    mongo["po_ssid_state"].delete_many({})
    mongo["po_ssid_history"].delete_many({"session_preview": {"$regex": "^TESTsess"}})
    yield
    # Cleanup at end
    mongo["po_ssid_state"].delete_many({})
    mongo["po_ssid_history"].delete_many({"session_preview": {"$regex": "^TESTsess"}})


# ------------------------------------------------------------------
# POST /api/po/ssid/update
# ------------------------------------------------------------------
class TestSsidUpdate:
    def test_update_valid_returns_updated_true(self):
        body = {"auth_message": _auth_frame(SESSION_A, uid=54321, is_demo=1), "source": "pytest", "ua": "pytest-ua"}
        r = requests.post(f"{BASE_URL}/api/po/ssid/update", json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        assert d["updated"] is True
        assert d["uid"] == 54321
        assert d["is_demo"] is True
        assert d["session_preview"].startswith(SESSION_A[:10])
        assert "extracted_at" in d and "expires_at" in d

    def test_update_invalid_returns_400(self):
        body = {"auth_message": '40["not-auth"]', "source": "pytest"}
        r = requests.post(f"{BASE_URL}/api/po/ssid/update", json=body, timeout=15)
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert 'auth_message must start with 42["auth"' in detail

    def test_update_dedup_same_session(self):
        # Second post of same session → updated:false, heartbeat behaviour
        body = {"auth_message": _auth_frame(SESSION_A, uid=54321, is_demo=1), "source": "pytest"}
        r = requests.post(f"{BASE_URL}/api/po/ssid/update", json=body, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["updated"] is False
        assert d["message"] == "SSID unchanged"
        assert "last_seen_at" in d

    def test_update_new_session_replaces(self, mongo):
        body = {"auth_message": _auth_frame(SESSION_B, uid=77777, is_demo=0), "source": "pytest"}
        r = requests.post(f"{BASE_URL}/api/po/ssid/update", json=body, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["updated"] is True
        assert d["uid"] == 77777
        assert d["is_demo"] is False
        # Verify DB
        doc = mongo["po_ssid_state"].find_one({"_id": "current"})
        assert doc is not None
        assert doc["session"] == SESSION_B
        assert doc["uid"] == 77777
        assert doc["is_demo"] is False


# ------------------------------------------------------------------
# GET /api/po/ssid/status
# ------------------------------------------------------------------
class TestSsidStatus:
    def test_status_after_update(self):
        # A fresh post so we know last_seen is now; use existing SESSION_B (already current)
        requests.post(
            f"{BASE_URL}/api/po/ssid/update",
            json={"auth_message": _auth_frame(SESSION_B, uid=77777, is_demo=0), "source": "pytest"},
            timeout=15,
        )
        r = requests.get(f"{BASE_URL}/api/po/ssid/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True
        assert d["has_ssid"] is True
        assert d["health"] == "healthy"
        assert d["uid"] == 77777
        assert d["is_demo"] is False
        assert 0 <= d["age_seconds"] < 60
        # ~3600 with a tolerance
        assert 3500 <= d["expires_in_seconds"] <= 3610
        # Must NOT leak session / auth_message
        assert "session" not in d
        assert "auth_message" not in d

    def test_status_when_missing(self, mongo):
        mongo["po_ssid_state"].delete_many({})
        r = requests.get(f"{BASE_URL}/api/po/ssid/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["has_ssid"] is False
        assert d["health"] == "missing"
        assert "Tampermonkey" in d.get("message", "")


# ------------------------------------------------------------------
# POST /api/po/ssid/connect
# ------------------------------------------------------------------
class TestSsidConnect:
    def test_connect_without_ssid_returns_404(self, mongo):
        mongo["po_ssid_state"].delete_many({})
        r = requests.post(f"{BASE_URL}/api/po/ssid/connect", timeout=20)
        assert r.status_code == 404

    def test_connect_with_fake_session_graceful(self, mongo):
        # Insert a fake SSID then attempt connect
        requests.post(
            f"{BASE_URL}/api/po/ssid/update",
            json={"auth_message": _auth_frame(SESSION_A, uid=12345, is_demo=1), "source": "pytest"},
            timeout=15,
        )
        r = requests.post(f"{BASE_URL}/api/po/ssid/connect", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        # With a fake session the real PO WS should refuse/fail — endpoint must NOT crash
        assert d["success"] in (True, False)
        assert d["connected"] in (True, False)
        # Must be graceful with a fake session (either connected=False, or explicit error field)
        assert d["connected"] is False
        assert d["success"] is False
        # Endpoint should include session_preview for diagnostics
        assert "session_preview" in d


# ------------------------------------------------------------------
# Mongo collection invariants
# ------------------------------------------------------------------
class TestMongoCollections:
    def test_po_ssid_state_single_doc(self, mongo):
        # Make sure current state has exactly one doc and _id='current'
        requests.post(
            f"{BASE_URL}/api/po/ssid/update",
            json={"auth_message": _auth_frame(SESSION_A, uid=12345, is_demo=1), "source": "pytest"},
            timeout=15,
        )
        docs = list(mongo["po_ssid_state"].find({}))
        assert len(docs) == 1
        assert docs[0]["_id"] == "current"

    def test_po_ssid_history_has_entries(self, mongo):
        # Two distinct session updates earlier → at least 2 history rows in this run
        count = mongo["po_ssid_history"].count_documents({"source": "pytest"})
        assert count >= 2


# ------------------------------------------------------------------
# Tampermonkey modular bundle
# ------------------------------------------------------------------
class TestTampermonkeyBundle:
    BUNDLE_URL = None

    @classmethod
    def setup_class(cls):
        cls.BUNDLE_URL = f"{BASE_URL}/pocket-option-auto-trader-modular.user.js"
        cls.resp = requests.get(cls.BUNDLE_URL, timeout=30)

    def test_bundle_served_200(self):
        assert self.resp.status_code == 200
        assert len(self.resp.text) > 50_000

    def test_bundle_version_8_10_0(self):
        header = self.resp.text[:2000]
        assert "@version      8.10.0" in header or "@version 8.10.0" in header

    def test_bundle_run_at_document_start(self):
        header = self.resp.text[:2000]
        assert "document-start" in header
        assert "@run-at" in header

    def test_bundle_contains_ssid_markers(self):
        text = self.resp.text
        assert "SSID-Bridge" in text
        assert "po/ssid/update" in text
        # Minified — exposed global
        assert "eliteBotSsidBridge" in text
