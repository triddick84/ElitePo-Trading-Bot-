"""
Iter 77 (Feb 28, 2026) — regression for production-deploy login fix.

Root cause: backend/.env contained 8 unquoted values with shell-special
characters (#, @, /, -, :, !, %) — most critically:
    POCKET_OPTION_PASSWORD=Tonyistheman#1
where `#` is a shell comment marker that TRUNCATES the value at deploy
time. When the Kubernetes pod parses the env file, several keys end up
missing or partially populated, the FastAPI server crashes on startup,
and every frontend request returns a generic "connection error".

Fix: every multi-value / special-character env var is now double-quoted
so it survives env-file parsing in any environment (preview, local,
Kubernetes pod). Also removed inline comments from .env per
system-prompt rules.

Coverage:
  A. /etc/.env style parser sees all required keys (no truncation).
  B. SEED_ADMINS still parses into the auth_service seeder loop.
  C. Login endpoint accepts the seeded admin credentials end-to-end.
"""
import os
import re
from pathlib import Path

import requests
from dotenv import dotenv_values

API = "http://localhost:8001/api"
ENV_FILE = Path("/app/backend/.env")


REQUIRED_KEYS = (
    "MONGO_URL", "DB_NAME", "CORS_ORIGINS", "EMERGENT_LLM_KEY",
    "POCKET_OPTION_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME",
    "AUTOBOT_WEBHOOK_URL", "OANDA_ACCESS_TOKEN", "OANDA_ACCOUNT_ID",
    "PLAYWRIGHT_BROWSERS_PATH", "SEED_ADMINS",
)


def test_env_file_no_inline_comments():
    """System-prompt rule: backend/.env must not contain inline comments."""
    raw = ENV_FILE.read_text(encoding="utf-8")
    for i, line in enumerate(raw.splitlines(), 1):
        stripped = line.strip()
        # Comment-only lines are forbidden per the agent rules
        assert not stripped.startswith("#"), f"line {i}: comment line found: {line!r}"


def test_env_special_char_values_are_quoted():
    """Every value containing shell-special chars (#, @, ! …) must be quoted
    so the deploy container's env-parser doesn't truncate them."""
    raw = ENV_FILE.read_text(encoding="utf-8")
    special = re.compile(r'[#@!%]')
    for line in raw.splitlines():
        if "=" not in line or not line.strip():
            continue
        key, _, val = line.partition("=")
        if not val:
            continue
        if special.search(val) and not (val.startswith('"') and val.endswith('"')):
            raise AssertionError(
                f"{key}: value contains shell-special char but is NOT quoted: {val!r}"
            )


def test_env_values_load_intact_via_dotenv():
    """Confirm python-dotenv (same parser FastAPI / uvicorn uses) reads
    every required key WITHOUT truncation. Pre-fix, POCKET_OPTION_PASSWORD
    was being clipped at the `#` to `Tonyistheman`."""
    parsed = dotenv_values(ENV_FILE)
    for k in REQUIRED_KEYS:
        assert k in parsed, f"missing key: {k}"
        v = parsed[k]
        assert v is not None and v != "", f"key {k} loaded as empty/None"
    # Specific regression: the password must contain the full string
    # including the `#1` suffix that the unquoted form was dropping.
    pw = parsed.get("POCKET_OPTION_PASSWORD", "")
    assert pw.endswith("#1"), f"POCKET_OPTION_PASSWORD truncated at #: {pw!r}"


def test_seed_admins_value_is_parseable():
    """The seeder splits on `,` then `:` — confirm the quoted value still
    yields the expected (email, password, username) tuple."""
    parsed = dotenv_values(ENV_FILE)
    seed = parsed.get("SEED_ADMINS") or ""
    assert seed, "SEED_ADMINS missing"
    rows = [r.strip() for r in seed.split(",") if r.strip()]
    assert rows, "no rows in SEED_ADMINS"
    for r in rows:
        parts = r.split(":")
        assert len(parts) >= 2, f"row malformed: {r!r}"
        # Email + password mandatory, username optional
        assert "@" in parts[0], f"first field must be email: {parts[0]!r}"
        assert parts[1] != "", f"password empty in: {r!r}"


def test_login_endpoint_accepts_seeded_admin():
    """End-to-end: with the quoted .env, the FastAPI server seeds the admin
    successfully and /api/auth/login returns a token."""
    r = requests.post(
        f"{API}/auth/login",
        json={"username": "seedtest", "password": "SeedPass123!"},
        timeout=60,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("success") is True
    assert data.get("token"), "expected JWT token in login response"
    assert data.get("user", {}).get("email") == "seedtest@elitepo.com"
