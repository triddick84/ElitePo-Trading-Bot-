"""
GPT Signal Bot API Tests
Tests login, dashboard APIs, high-accuracy strategies, and scan-markets endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://ai-broker-dev.preview.emergentagent.com"

# Test credentials provided
TEST_USERNAME = "triddick84"
TEST_PASSWORD = "Fallinone#1"


class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test API health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert data["service"] == "GPT Signal Bot API"
        print(f"✅ Health check passed: {data}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == TEST_USERNAME
        assert len(data["token"]) > 0
        print(f"✅ Login successful for user: {data['user']['username']}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "wronguser", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        print("✅ Invalid credentials correctly rejected")
    
    def test_get_current_user(self):
        """Test get current user with valid token"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        token = login_response.json()["token"]
        
        # Then get current user
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["user"]["username"] == TEST_USERNAME
        print(f"✅ Current user retrieved: {data['user']['username']}")


class TestBotStatus:
    """Bot status and control endpoint tests"""
    
    def test_get_bot_status(self):
        """Test getting bot status"""
        response = requests.get(f"{BASE_URL}/api/bot/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "current_mode" in data
        assert "active_strategies" in data
        print(f"✅ Bot status: running={data['is_running']}, mode={data['current_mode']}")
    
    def test_get_config(self):
        """Test getting bot configuration"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "trading_mode" in data
        assert "selected_expirations" in data
        print(f"✅ Config retrieved: mode={data.get('trading_mode')}")


class TestHighAccuracyStrategies:
    """High accuracy strategies endpoint tests"""
    
    def test_get_strategies_list(self):
        """Test /api/signals/high-accuracy/strategies returns strategies list"""
        response = requests.get(f"{BASE_URL}/api/signals/high-accuracy/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "strategies" in data
        assert len(data["strategies"]) > 0
        
        # Verify strategy structure
        strategy = data["strategies"][0]
        assert "id" in strategy
        assert "name" in strategy
        assert "description" in strategy
        assert "timeframes" in strategy
        assert "target_accuracy" in strategy
        
        print(f"✅ Strategies returned: {len(data['strategies'])} strategies")
        for s in data["strategies"]:
            print(f"   - {s['name']}: {s['timeframes']} ({s['target_accuracy']})")
    
    def test_strategies_have_expected_ids(self):
        """Test strategies have expected IDs"""
        response = requests.get(f"{BASE_URL}/api/signals/high-accuracy/strategies")
        data = response.json()
        strategy_ids = [s["id"] for s in data["strategies"]]
        
        expected_ids = ["ultra_scalper", "micro_trend", "reversal_hunter", "momentum_burst"]
        for expected_id in expected_ids:
            assert expected_id in strategy_ids, f"Missing strategy: {expected_id}"
        print(f"✅ All expected strategy IDs present: {expected_ids}")


class TestScanMarkets:
    """Scan markets endpoint tests"""
    
    def test_scan_markets_basic(self):
        """Test /api/signals/scan-markets basic functionality"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 50, "max_signals": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "scanned_assets" in data
        assert "signals_found" in data
        assert "top_signals" in data
        assert data["scanned_assets"] >= 1
        print(f"✅ Scan markets: scanned={data['scanned_assets']}, found={data['signals_found']}")
    
    def test_scan_markets_multiple_assets(self):
        """Test scanning multiple assets"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC", "min_confidence": 50, "max_signals": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["scanned_assets"] == 3
        print(f"✅ Multi-asset scan: scanned={data['scanned_assets']} assets")
    
    def test_scan_markets_confidence_filter(self):
        """Test confidence filter parameter"""
        # Test with high confidence threshold
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 90, "max_signals": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned signals should meet confidence threshold
        for signal in data.get("top_signals", []):
            assert signal.get("confidence", 0) >= 90
        print(f"✅ Confidence filter working correctly")


class TestPerformanceMetrics:
    """Performance metrics endpoint tests"""
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        response = requests.get(f"{BASE_URL}/api/performance/metrics")
        assert response.status_code == 200
        data = response.json()
        # Just verify endpoint returns data (may be empty initially)
        print(f"✅ Performance metrics endpoint working")


class TestSignalsEndpoints:
    """Signals endpoint tests"""
    
    def test_get_active_signals(self):
        """Test getting active signals"""
        response = requests.get(f"{BASE_URL}/api/signals/active")
        assert response.status_code == 200
        # Returns array of signals (may be empty)
        assert isinstance(response.json(), list)
        print(f"✅ Active signals endpoint working")
    
    def test_get_signal_history(self):
        """Test getting signal history"""
        response = requests.get(f"{BASE_URL}/api/signals/history")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        print(f"✅ Signal history endpoint working, signals count: {len(data.get('signals', []))}")
    
    def test_get_invert_status(self):
        """Test getting signal inversion status"""
        response = requests.get(f"{BASE_URL}/api/signals/invert-status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "invert_signals" in data
        print(f"✅ Invert status: {data.get('invert_signals')}")


class TestLatencyEndpoints:
    """Latency configuration endpoint tests"""
    
    def test_get_latency_status(self):
        """Test getting latency status"""
        response = requests.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        print(f"✅ Latency status: mode={data.get('mode')}")


class TestMarketData:
    """Market data endpoint tests"""
    
    def test_get_market_data(self):
        """Test getting market data"""
        response = requests.get(f"{BASE_URL}/api/market/data")
        assert response.status_code == 200
        print(f"✅ Market data endpoint working")


# Pytest fixtures
@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
