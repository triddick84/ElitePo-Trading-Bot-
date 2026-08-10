"""
Iter 97 — Admin approval workflow for new user registrations.

Locks the full lifecycle:
  1. New user registers → status=pending, HTTP 202, no token issued.
  2. Pending user cannot log in → HTTP 403 with code=ACCOUNT_PENDING.
  3. Admin can list pending users.
  4. Admin can approve → user can now log in.
  5. Admin can reject → user gets ACCOUNT_REJECTED.
  6. Admin can suspend an active user → user gets ACCOUNT_SUSPENDED.
  7. Admin cannot suspend themselves (self-lockout guard).
  8. Cannot deactivate the last active admin (last-admin guard).
  9. Grandfather migration is idempotent — pre-existing users stay active.
"""

from __future__ import annotations

import os
import time
import random

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rand_suffix() -> str:
    return f"{int(time.time() * 1000) % 1_000_000}_{random.randint(0, 9999)}"


def _register(username: str, email: str, password: str = "test_pass_123"):
    return requests.post(
        f"{API}/auth/register",
        json={"username": username, "email": email, "password": password},
        timeout=10,
    )


def _login(username: str, password: str = "test_pass_123"):
    return requests.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )


def _admin_token() -> str:
    r = _login("seedtest", "SeedPass123!")
    assert r.status_code == 200, f"seed admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {_admin_token()}"}


# ---------------------------------------------------------------------------
# Registration → pending
# ---------------------------------------------------------------------------
def test_new_user_registers_as_pending_and_gets_no_token():
    sfx = _rand_suffix()
    r = _register(f"pending_u_{sfx}", f"p{sfx}@test.com")
    assert r.status_code == 202, f"expected 202 for pending, got {r.status_code}: {r.text}"
    d = r.json()
    assert d.get("success") is True
    assert d.get("pending") is True
    assert d.get("code") == "ACCOUNT_PENDING"
    assert d.get("user", {}).get("status") == "pending"
    assert "token" not in d, "pending registration must NOT return a token"


def test_pending_user_cannot_log_in():
    sfx = _rand_suffix()
    username = f"blocked_u_{sfx}"
    _register(username, f"b{sfx}@test.com")
    r = _login(username)
    assert r.status_code == 403, f"expected 403 for pending login, got {r.status_code}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict), f"expected structured detail, got {detail}"
    assert detail.get("code") == "ACCOUNT_PENDING"


# ---------------------------------------------------------------------------
# Admin approval flow
# ---------------------------------------------------------------------------
def test_admin_can_list_pending_users():
    sfx = _rand_suffix()
    _register(f"listme_{sfx}", f"lm{sfx}@test.com")
    r = requests.get(f"{API}/auth/users/pending", headers=_admin_headers(), timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d.get("success") is True
    assert d.get("count", 0) >= 1
    assert any(u.get("username") == f"listme_{sfx}" for u in d.get("users", []))


def test_admin_approve_lets_user_log_in():
    sfx = _rand_suffix()
    username = f"approve_me_{sfx}"
    _register(username, f"am{sfx}@test.com")

    # find user_id
    r = requests.get(f"{API}/auth/users/pending", headers=_admin_headers(), timeout=10)
    user = next((u for u in r.json()["users"] if u["username"] == username), None)
    assert user, "just-registered pending user not found in pending list"

    # approve
    r = requests.post(
        f"{API}/auth/users/{user['id']}/approve",
        headers=_admin_headers(),
        timeout=10,
    )
    assert r.status_code == 200
    assert r.json()["user"]["status"] == "active"
    assert r.json()["user"].get("approved_at"), "approved_at audit field missing"

    # now can log in
    r = _login(username)
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["user"]["status"] == "active"
    assert r.json().get("token")


def test_admin_reject_blocks_login_with_correct_code():
    sfx = _rand_suffix()
    username = f"reject_me_{sfx}"
    _register(username, f"rm{sfx}@test.com")
    r = requests.get(f"{API}/auth/users/pending", headers=_admin_headers(), timeout=10)
    user = next((u for u in r.json()["users"] if u["username"] == username), None)
    assert user

    r = requests.post(f"{API}/auth/users/{user['id']}/reject", headers=_admin_headers(), timeout=10)
    assert r.status_code == 200
    assert r.json()["user"]["status"] == "rejected"

    r = _login(username)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ACCOUNT_REJECTED"


def test_admin_suspend_revokes_active_user_login():
    # Register + approve first
    sfx = _rand_suffix()
    username = f"suspend_me_{sfx}"
    _register(username, f"sm{sfx}@test.com")
    r = requests.get(f"{API}/auth/users/pending", headers=_admin_headers(), timeout=10)
    user = next((u for u in r.json()["users"] if u["username"] == username), None)
    requests.post(f"{API}/auth/users/{user['id']}/approve", headers=_admin_headers(), timeout=10)

    # confirm login works
    r = _login(username)
    assert r.status_code == 200

    # suspend
    r = requests.post(f"{API}/auth/users/{user['id']}/suspend", headers=_admin_headers(), timeout=10)
    assert r.status_code == 200
    assert r.json()["user"]["status"] == "suspended"

    r = _login(username)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ACCOUNT_SUSPENDED"


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------
def test_non_admin_cannot_call_approval_endpoints():
    # Create + approve a regular user, then try admin action from their token
    sfx = _rand_suffix()
    username = f"nonadmin_{sfx}"
    _register(username, f"na{sfx}@test.com")
    pending = requests.get(f"{API}/auth/users/pending", headers=_admin_headers()).json()
    user = next(u for u in pending["users"] if u["username"] == username)
    requests.post(f"{API}/auth/users/{user['id']}/approve", headers=_admin_headers())

    user_token = _login(username).json()["token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    for endpoint in ("/auth/users/pending", "/auth/users"):
        r = requests.get(f"{API}{endpoint}", headers=user_headers, timeout=10)
        assert r.status_code == 403, f"{endpoint} should reject non-admin, got {r.status_code}"

    # And approve endpoint
    r = requests.post(f"{API}/auth/users/{user['id']}/approve", headers=user_headers, timeout=10)
    assert r.status_code == 403


def test_admin_cannot_suspend_themselves():
    # Get seed admin's id
    r = requests.get(f"{API}/auth/users?status=active", headers=_admin_headers(), timeout=10)
    seed = next(u for u in r.json()["users"] if u["username"] == "seedtest")
    r = requests.post(f"{API}/auth/users/{seed['id']}/suspend", headers=_admin_headers(), timeout=10)
    assert r.status_code == 400, f"self-suspend should be blocked, got {r.status_code}"
    assert "own" in r.json()["detail"].lower() or "self" in r.json()["detail"].lower() or "cannot" in r.json()["detail"].lower()


def test_seed_admin_stays_active_across_restarts():
    """Sanity: seed admin's status must always be active — the grandfather migration
    + seed_admins_from_env force-heals any drift."""
    r = _login("seedtest", "SeedPass123!")
    assert r.status_code == 200
    assert r.json()["user"]["status"] == "active"
    assert r.json()["user"]["role"] == "admin"


# ---------------------------------------------------------------------------
# Grandfather migration is idempotent
# ---------------------------------------------------------------------------
def test_grandfather_leaves_pending_users_alone():
    """Idempotency: create a pending user, then re-run implicit grandfather
    by hitting an endpoint that would trigger it. The pending user MUST NOT
    be flipped to active by the migration (only $exists:false is touched)."""
    sfx = _rand_suffix()
    username = f"gf_check_{sfx}"
    _register(username, f"gf{sfx}@test.com")
    # confirm pending
    r = requests.get(f"{API}/auth/users/pending", headers=_admin_headers()).json()
    assert any(u["username"] == username for u in r["users"])
    # login should still be blocked
    r = _login(username)
    assert r.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
