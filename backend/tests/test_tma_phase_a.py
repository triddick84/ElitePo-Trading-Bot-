"""
TMA Phase A backend tests.

Covers:
- /api/tma/health
- /api/tma/auth (dev-mode, admin, real HMAC signed, invalid hash)
- /api/tma/me
- /api/tma/onboarding/state, /update
- /api/tma/kyc/upload, /kyc/status
- /api/tma/admin/kyc/queue, review (approve/reject)
- /api/tma/admin/users
- /api/tma/packages
- JWT invalid signature
- KYC file type validation
- Regression: /api/strategies/selected, /api/strategies/available
- Regression: Tampermonkey script content
"""
import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://auto-invert-engine.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"
BOT_TOKEN = "8342619832:AAEdHnS_HKKariaDQaKHH6OT_pnLfp9dfIQ"
ADMIN_TG_ID = 6434316177


def _build_signed_init_data(user_id: int, username: str = "hmac_user") -> str:
    """Build a real HMAC-signed initData per Telegram spec."""
    user_json = (
        '{"id":' + str(user_id) + ',"first_name":"HMAC","username":"' + username + '"}'
    )
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAF_test",
        "user": user_json,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = h
    return urlencode(fields)


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------------- Health ----------------
def test_tma_health(s):
    r = s.get(f"{API}/tma/health", timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["success"] is True
    assert d["dev_mode"] is True
    assert d["bot_configured"] is True
    assert d["jwt_configured"] is True
    assert ADMIN_TG_ID in d["admin_ids"]


# ---------------- Auth ----------------
@pytest.fixture(scope="module")
def user_auth(s):
    r = s.post(f"{API}/tma/auth", json={"init_data": "dev:555111:demo_user"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_dev_user_returns_valid_shape(user_auth):
    assert user_auth["success"] is True
    assert isinstance(user_auth["token"], str) and user_auth["token"]
    u = user_auth["user"]
    assert u["role"] == "user"
    assert u["referral_code"]
    for step in ("po_signup", "kyc", "package", "access"):
        assert u["onboarding"][step]["completed"] is False


@pytest.fixture(scope="module")
def admin_auth(s):
    r = s.post(
        f"{API}/tma/auth",
        json={"init_data": f"dev:{ADMIN_TG_ID}:admin"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_admin_role(admin_auth):
    assert admin_auth["user"]["role"] == "admin"


def test_auth_real_hmac_signed(s):
    init_data = _build_signed_init_data(777888999, "hmac_user")
    r = s.post(f"{API}/tma/auth", json={"init_data": init_data}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["telegram_user_id"] == 777888999


def test_auth_invalid_hash_returns_401(s):
    init_data = _build_signed_init_data(777888999, "hmac_user")
    # Tamper the hash
    tampered = init_data.replace("hash=", "hash=deadbeef")
    r = s.post(f"{API}/tma/auth", json={"init_data": tampered}, timeout=15)
    assert r.status_code == 401


def test_me_endpoint(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    r = s.get(f"{API}/tma/me", headers=h, timeout=15)
    assert r.status_code == 200
    assert r.json()["user"]["id"] == user_auth["user"]["id"]


def test_me_invalid_jwt_returns_401(s):
    h = {"Authorization": "Bearer not.a.valid.jwt"}
    r = s.get(f"{API}/tma/me", headers=h, timeout=15)
    assert r.status_code == 401


# ---------------- Onboarding ----------------
def test_onboarding_state_fresh(s):
    # Use a brand-new user
    r = s.post(f"{API}/tma/auth", json={"init_data": "dev:555222:fresh_user"}, timeout=15)
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    st = s.get(f"{API}/tma/onboarding/state", headers=h, timeout=15).json()
    assert st["next_step"] == "po_signup"


def test_onboarding_update_po_signup(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    r = s.post(
        f"{API}/tma/onboarding/update",
        headers=h,
        json={"step": "po_signup"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["user"]["onboarding"]["po_signup"]["completed"] is True


def test_onboarding_update_package(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    r = s.post(
        f"{API}/tma/onboarding/update",
        headers=h,
        json={"step": "package", "value": "pro_weekly"},
        timeout=15,
    )
    assert r.status_code == 200
    on = r.json()["user"]["onboarding"]
    assert on["package"]["completed"] is True
    assert on["package"]["package_id"] == "pro_weekly"


# ---------------- KYC ----------------
# 1x1 transparent PNG
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def kyc_upload(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    files = {"file": ("test.png", _PNG, "image/png")}
    r = s.post(f"{API}/tma/kyc/upload", headers=h, files=files, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kyc_id"]
    assert d["status"] == "pending"
    return d


def test_kyc_status_pending(s, user_auth, kyc_upload):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    r = s.get(f"{API}/tma/kyc/status", headers=h, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_kyc_rejects_txt(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    files = {"file": ("evil.txt", b"hello", "text/plain")}
    r = s.post(f"{API}/tma/kyc/upload", headers=h, files=files, timeout=15)
    assert r.status_code == 400


# ---------------- Admin ----------------
def test_admin_kyc_queue(s, admin_auth, kyc_upload):
    h = {"Authorization": f"Bearer {admin_auth['token']}"}
    r = s.get(
        f"{API}/tma/admin/kyc/queue?status_filter=pending", headers=h, timeout=15
    )
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert kyc_upload["kyc_id"] in ids


def test_non_admin_forbidden(s, user_auth):
    h = {"Authorization": f"Bearer {user_auth['token']}"}
    r = s.get(f"{API}/tma/admin/kyc/queue", headers=h, timeout=15)
    assert r.status_code == 403


def test_admin_approve_grants_access(s, admin_auth, kyc_upload, user_auth):
    h = {"Authorization": f"Bearer {admin_auth['token']}"}
    r = s.post(
        f"{API}/tma/admin/kyc/{kyc_upload['kyc_id']}/review",
        headers=h,
        json={"action": "approve"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # Re-fetch onboarding state as user
    uh = {"Authorization": f"Bearer {user_auth['token']}"}
    st = s.get(f"{API}/tma/onboarding/state", headers=uh, timeout=15).json()
    assert st["kyc_status"] == "approved"
    assert st["access_granted"] is True
    assert st["onboarding"]["kyc"]["completed"] is True
    assert st["onboarding"]["access"]["completed"] is True


def test_admin_reject_flow(s, admin_auth):
    # Create a fresh user + KYC to reject
    r = s.post(f"{API}/tma/auth", json={"init_data": "dev:555333:rej_user"}, timeout=15)
    ut = r.json()["token"]
    uh = {"Authorization": f"Bearer {ut}"}
    files = {"file": ("x.png", _PNG, "image/png")}
    up = s.post(f"{API}/tma/kyc/upload", headers=uh, files=files, timeout=15).json()
    ah = {"Authorization": f"Bearer {admin_auth['token']}"}
    rev = s.post(
        f"{API}/tma/admin/kyc/{up['kyc_id']}/review",
        headers=ah,
        json={"action": "reject", "reason": "blurry"},
        timeout=15,
    )
    assert rev.status_code == 200
    assert rev.json()["kyc"]["status"] == "rejected"


def test_admin_users_list(s, admin_auth):
    h = {"Authorization": f"Bearer {admin_auth['token']}"}
    r = s.get(f"{API}/tma/admin/users", headers=h, timeout=15)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0


def test_packages(s):
    r = s.get(f"{API}/tma/packages", timeout=15)
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["packages"]}
    assert {"basic_weekly", "pro_weekly", "pro_monthly", "elite_monthly", "elite_annual"} <= ids


# ---------------- Regression: Strategies ----------------
def test_strategies_selected(s):
    r = s.get(f"{API}/strategies/selected", timeout=15)
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_strategies_available(s):
    r = s.get(f"{API}/strategies/available", timeout=15)
    assert r.status_code == 200
    assert r.json().get("success") is True


# ---------------- Regression: Tampermonkey bundle ----------------
def test_tampermonkey_script(s):
    r = s.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=20)
    assert r.status_code == 200
    body = r.text
    assert "5s_heikin_fractal" in body
    assert "falling back" in body
    assert "@version" in body
    # Verify version 8.75.0 is present
    assert "8.75.0" in body
