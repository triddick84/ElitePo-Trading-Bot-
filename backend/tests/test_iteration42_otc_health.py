"""
Iteration 42: OTC Data Health widget + TM modular script deprecation.
Tests:
- GET /api/signals/otc-candle-stats returns all required fields
- GET /pocket-option-auto-trader.user.js (legacy) returns 200
- GET /pocket-option-auto-trader-modular.user.js (modular) returns 200
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

assert BASE_URL, "REACT_APP_BACKEND_URL not set"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- OTC Candle Stats endpoint ----
class TestOTCCandleStats:
    def test_endpoint_returns_200_and_success(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True, data

    def test_top_level_fields(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        data = r.json()
        required = ["success", "total_candles", "by_symbol", "overall_health", "summary", "server_time"]
        for k in required:
            assert k in data, f"Missing top-level key: {k}"
        assert isinstance(data["total_candles"], int)
        assert isinstance(data["by_symbol"], list)
        assert isinstance(data["overall_health"], str)
        assert isinstance(data["summary"], dict)
        assert isinstance(data["server_time"], str)

    def test_summary_fields(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        summary = r.json()["summary"]
        for k in ["total_symbols", "healthy", "stale", "offline"]:
            assert k in summary, f"Missing summary key: {k}"
            assert isinstance(summary[k], int)

    def test_by_symbol_row_fields(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        rows = r.json()["by_symbol"]
        if not rows:
            pytest.skip("No OTC candles present in DB — cannot test per-symbol schema")
        required = ["symbol", "candle_count", "last_scrape_age_seconds",
                   "recent_hour_count", "ingestion_rate_per_min", "gap_ratio", "health"]
        for row in rows:
            for k in required:
                assert k in row, f"Row missing key '{k}': {row}"
            assert isinstance(row["symbol"], str)
            assert isinstance(row["candle_count"], int)
            assert isinstance(row["recent_hour_count"], int)
            assert isinstance(row["ingestion_rate_per_min"], (int, float))
            assert isinstance(row["gap_ratio"], (int, float))
            assert row["health"] in ["healthy", "stale", "offline", "unknown"]

    def test_total_candles_consistent(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        data = r.json()
        # Sum of per-symbol counts should equal total_candles (or less if symbols beyond list)
        sum_symbols = sum(row["candle_count"] for row in data["by_symbol"])
        assert sum_symbols <= data["total_candles"]

    def test_overall_health_valid(self, session):
        r = session.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        data = r.json()
        assert data["overall_health"] in ["healthy", "stale", "offline", "degraded", "unknown"]


# ---- Tampermonkey script downloads ----
class TestTampermonkeyScripts:
    def test_legacy_script_available(self, session):
        r = session.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=30)
        assert r.status_code == 200
        assert len(r.text) > 100  # Should be non-trivial JS
        # UserScript headers should exist
        assert "==UserScript==" in r.text

    def test_modular_script_available(self, session):
        r = session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=30)
        assert r.status_code == 200
        assert len(r.text) > 100
        assert "==UserScript==" in r.text


# ---- Regression: basic health ----
class TestHealthRegression:
    def test_api_health(self, session):
        r = session.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
