"""
Test suite for refactored backend routes after server.py split into modular route files.
Tests all endpoints mentioned in the review request to verify they work correctly.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from environment
TEST_USERNAME = os.environ.get('TEST_USERNAME', 'testuser')
TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'test123')


class TestAuthRoutes:
    """Test authentication endpoints in /app/backend/routes/auth.py"""
    
    def test_login_success(self):
        """POST /api/auth/login with valid credentials should return success=true with token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Login not successful: {data}"
        assert "token" in data, f"No token in response: {data}"
        print(f"✅ Login successful, token received")
    
    def test_auth_me_with_token(self):
        """GET /api/auth/me with valid Bearer token should return user info"""
        # First login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json().get("token")
        
        # Now test /auth/me
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200, f"Auth/me failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Auth/me not successful: {data}"
        assert "user" in data, f"No user in response: {data}"
        print(f"✅ Auth/me returned user info: {data['user'].get('username')}")


class TestSignalRoutes:
    """Test signal endpoints in /app/backend/routes/signals.py"""
    
    def test_signals_active(self):
        """GET /api/signals/active should return a list of signals"""
        response = requests.get(f"{BASE_URL}/api/signals/active")
        assert response.status_code == 200, f"Signals active failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"✅ Signals active returned {len(data)} signals")
    
    def test_signals_history(self):
        """GET /api/signals/history should return signals array"""
        response = requests.get(f"{BASE_URL}/api/signals/history")
        assert response.status_code == 200, f"Signals history failed: {response.text}"
        data = response.json()
        assert "signals" in data, f"No signals key in response: {data}"
        print(f"✅ Signals history returned {len(data.get('signals', []))} signals")
    
    def test_scan_markets(self):
        """GET /api/signals/scan-markets should return success=true"""
        response = requests.get(f"{BASE_URL}/api/signals/scan-markets")
        assert response.status_code == 200, f"Scan markets failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Scan markets not successful: {data}"
        print(f"✅ Scan markets successful")
    
    def test_invert_status(self):
        """GET /api/signals/invert-status should return success=true"""
        response = requests.get(f"{BASE_URL}/api/signals/invert-status")
        assert response.status_code == 200, f"Invert status failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Invert status not successful: {data}"
        print(f"✅ Invert status: {data.get('invert_signals')}")
    
    def test_toggle_invert(self):
        """POST /api/signals/toggle-invert should return success=true"""
        response = requests.post(f"{BASE_URL}/api/signals/toggle-invert")
        assert response.status_code == 200, f"Toggle invert failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Toggle invert not successful: {data}"
        print(f"✅ Toggle invert successful, now: {data.get('invert_signals')}")
    
    def test_auto_generate_status(self):
        """GET /api/signals/auto-generate/status should return status info"""
        response = requests.get(f"{BASE_URL}/api/signals/auto-generate/status")
        assert response.status_code == 200, f"Auto generate status failed: {response.text}"
        data = response.json()
        assert "status" in data or "auto_generation_active" in data, f"No status in response: {data}"
        print(f"✅ Auto generate status: {data.get('status', data.get('auto_generation_active'))}")


class TestStrategyRoutes:
    """Test strategy endpoints in /app/backend/routes/strategies.py"""
    
    def test_strategies_available(self):
        """GET /api/strategies/available should return success=true with strategies"""
        response = requests.get(f"{BASE_URL}/api/strategies/available")
        assert response.status_code == 200, f"Strategies available failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Strategies available not successful: {data}"
        assert "strategies" in data, f"No strategies in response: {data}"
        print(f"✅ Strategies available returned {len(data.get('strategies', {}))} timeframes")
    
    def test_strategies_selected(self):
        """GET /api/strategies/selected should return success=true"""
        response = requests.get(f"{BASE_URL}/api/strategies/selected")
        assert response.status_code == 200, f"Strategies selected failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Strategies selected not successful: {data}"
        print(f"✅ Strategies selected returned")


class TestTradingRoutes:
    """Test trading endpoints in /app/backend/routes/trading.py"""
    
    def test_money_management_status(self):
        """GET /api/money-management/status should return success=true"""
        response = requests.get(f"{BASE_URL}/api/money-management/status")
        assert response.status_code == 200, f"Money management status failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Money management status not successful: {data}"
        print(f"✅ Money management status returned")
    
    def test_auto_trade_status(self):
        """GET /api/auto-trade/status should return status info"""
        response = requests.get(f"{BASE_URL}/api/auto-trade/status")
        assert response.status_code == 200, f"Auto trade status failed: {response.text}"
        data = response.json()
        # Check for is_running field or success field
        assert "is_running" in data or "success" in data, f"No status info in response: {data}"
        print(f"✅ Auto trade status: is_running={data.get('is_running', 'N/A')}")


class TestMLRoutes:
    """Test ML endpoints in /app/backend/routes/ml.py"""
    
    def test_maximized_ml_stats(self):
        """GET /api/maximized-ml/stats should return success=true"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        assert response.status_code == 200, f"Maximized ML stats failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Maximized ML stats not successful: {data}"
        print(f"✅ Maximized ML stats returned")
    
    def test_enhanced_ml_stats(self):
        """GET /api/enhanced-ml/stats should return response"""
        response = requests.get(f"{BASE_URL}/api/enhanced-ml/stats")
        assert response.status_code == 200, f"Enhanced ML stats failed: {response.text}"
        data = response.json()
        # May return success=false if ML not available, but should not 500
        print(f"✅ Enhanced ML stats returned: success={data.get('success')}")


class TestIntegrationRoutes:
    """Test integration endpoints in /app/backend/routes/integrations.py"""
    
    def test_oanda_status(self):
        """GET /api/oanda/status should return configuration status"""
        response = requests.get(f"{BASE_URL}/api/oanda/status")
        assert response.status_code == 200, f"OANDA status failed: {response.text}"
        data = response.json()
        # Should have some status info
        print(f"✅ OANDA status returned: {data}")
    
    def test_telegram_status(self):
        """GET /api/telegram/status should return configuration status"""
        response = requests.get(f"{BASE_URL}/api/telegram/status")
        assert response.status_code == 200, f"Telegram status failed: {response.text}"
        data = response.json()
        # Should have configured field
        print(f"✅ Telegram status: configured={data.get('configured')}")


class TestPocketOptionRoutes:
    """Test Pocket Option endpoints in /app/backend/routes/pocket_option.py"""
    
    def test_pocket_option_status(self):
        """GET /api/pocket-option/status should return connection status"""
        response = requests.get(f"{BASE_URL}/api/pocket-option/status")
        assert response.status_code == 200, f"Pocket Option status failed: {response.text}"
        data = response.json()
        # Expected: success=false because SSID is not connected - that's expected behavior
        print(f"✅ Pocket Option status: connected={data.get('connected', False)}")


class TestBacktestRoutes:
    """Test backtest endpoints in /app/backend/routes/backtest.py"""
    
    def test_backtest_strategies(self):
        """GET /api/backtest/strategies should return success=true"""
        response = requests.get(f"{BASE_URL}/api/backtest/strategies")
        assert response.status_code == 200, f"Backtest strategies failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Backtest strategies not successful: {data}"
        print(f"✅ Backtest strategies returned {len(data.get('strategies', []))} strategies")
    
    def test_backtest_history(self):
        """GET /api/backtest/history should return list/dict"""
        response = requests.get(f"{BASE_URL}/api/backtest/history")
        assert response.status_code == 200, f"Backtest history failed: {response.text}"
        data = response.json()
        assert "results" in data, f"No results in response: {data}"
        print(f"✅ Backtest history returned {len(data.get('results', []))} results")


class TestHealthAndBotRoutes:
    """Test health and bot status endpoints"""
    
    def test_health(self):
        """GET /api/health should return status=healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Health status not healthy: {data}"
        print(f"✅ Health check: status={data.get('status')}")
    
    def test_bot_status(self):
        """GET /api/bot/status should return is_running field"""
        response = requests.get(f"{BASE_URL}/api/bot/status")
        assert response.status_code == 200, f"Bot status failed: {response.text}"
        data = response.json()
        assert "is_running" in data, f"No is_running in response: {data}"
        print(f"✅ Bot status: is_running={data.get('is_running')}")


class TestCustomStrategies:
    """Test custom strategies endpoint"""
    
    def test_custom_strategies(self):
        """GET /api/custom-strategies should return success=true"""
        response = requests.get(f"{BASE_URL}/api/custom-strategies")
        assert response.status_code == 200, f"Custom strategies failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Custom strategies not successful: {data}"
        print(f"✅ Custom strategies returned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
