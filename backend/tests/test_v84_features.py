"""
Test v8.4 Features: Balance Sync, Momentum-Aware Auto-Invert, Code Quality Fixes
Tests the following:
1. GET /api/signals/momentum-check - momentum analysis for auto-invert
2. GET /api/health - health check
3. POST /api/auth/login - backward-compatible HMAC-SHA256 auth
4. GET /api/strategies/available/5s - strategies list
5. GET /api/signals/scan-markets - market scanning
6. POST /api/signals/record-premium-result - premium result recording
7. GET /api/risk-management/metrics - risk metrics
8. GET /api/maximized-ml/stats - ML stats
9. Tampermonkey script accessibility and v8.4 functions
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auto-invert-engine.preview.emergentagent.com')

# Test credentials from test_credentials.md
TEST_USERNAME = "triddick84"
TEST_PASSWORD = "Fallinone#1"


class TestHealthAndBasics:
    """Basic health and connectivity tests"""
    
    def test_health_endpoint(self):
        """GET /api/health - returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") in ["healthy", "ok", True], f"Unexpected health status: {data}"
        print(f"✅ Health check passed: {data}")


class TestAuthentication:
    """Authentication tests with backward-compatible HMAC-SHA256"""
    
    def test_login_success(self):
        """POST /api/auth/login - returns success and token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Login not successful: {data}"
        assert "token" in data, f"No token in response: {data}"
        assert "user" in data, f"No user in response: {data}"
        print(f"✅ Login successful for {TEST_USERNAME}, token received")
        return data.get("token")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - returns error for invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "invalid_user", "password": "wrong_password"},
            timeout=10
        )
        # Should return 200 with success=false or 401
        data = response.json()
        assert data.get("success") == False or response.status_code == 401, f"Should fail for invalid creds: {data}"
        print(f"✅ Invalid credentials correctly rejected")


class TestMomentumCheck:
    """Tests for momentum-check endpoint (v8.4 feature)"""
    
    def test_momentum_check_default(self):
        """GET /api/signals/momentum-check - returns momentum analysis"""
        response = requests.get(
            f"{BASE_URL}/api/signals/momentum-check?symbol=EURUSD_OTC",
            timeout=10
        )
        assert response.status_code == 200, f"Momentum check failed: {response.status_code}"
        data = response.json()
        
        # Verify required fields
        assert "success" in data, f"Missing 'success' field: {data}"
        assert "should_invert" in data, f"Missing 'should_invert' field: {data}"
        assert "momentum" in data, f"Missing 'momentum' field: {data}"
        assert "trend" in data, f"Missing 'trend' field: {data}"
        assert "confidence" in data, f"Missing 'confidence' field: {data}"
        assert "rsi" in data, f"Missing 'rsi' field: {data}"
        assert "ema_slope" in data, f"Missing 'ema_slope' field: {data}"
        assert "price_velocity" in data, f"Missing 'price_velocity' field: {data}"
        
        # Verify data types
        assert isinstance(data["should_invert"], bool), f"should_invert should be bool: {data}"
        assert data["momentum"] in ["INTACT", "WEAKENING", "SHIFTED", "NEUTRAL", "ERROR"], f"Invalid momentum: {data}"
        assert data["trend"] in ["BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"], f"Invalid trend: {data}"
        
        print(f"✅ Momentum check passed: should_invert={data['should_invert']}, momentum={data['momentum']}, trend={data['trend']}")
    
    def test_momentum_check_with_timeframe(self):
        """GET /api/signals/momentum-check with timeframe parameter"""
        response = requests.get(
            f"{BASE_URL}/api/signals/momentum-check?symbol=EURUSD_OTC&timeframe=5s",
            timeout=10
        )
        assert response.status_code == 200, f"Momentum check with timeframe failed: {response.status_code}"
        data = response.json()
        assert data.get("success") == True, f"Momentum check not successful: {data}"
        print(f"✅ Momentum check with timeframe passed")


class TestStrategies:
    """Tests for strategy endpoints"""
    
    def test_strategies_available_5s(self):
        """GET /api/strategies/available/5s - returns strategies list"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/5s", timeout=10)
        assert response.status_code == 200, f"Strategies endpoint failed: {response.status_code}"
        data = response.json()
        
        # Should return a list of strategies or a dict with strategies
        if isinstance(data, list):
            assert len(data) > 0, f"No strategies returned: {data}"
            print(f"✅ Strategies available (5s): {len(data)} strategies")
        elif isinstance(data, dict):
            strategies = data.get("strategies", data.get("available", []))
            print(f"✅ Strategies available (5s): {data}")
        else:
            print(f"✅ Strategies response: {data}")


class TestSignalScanning:
    """Tests for signal scanning endpoints"""
    
    def test_scan_markets(self):
        """GET /api/signals/scan-markets - returns signals"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets?assets=EURUSD_OTC&min_confidence=50",
            timeout=30
        )
        assert response.status_code == 200, f"Scan markets failed: {response.status_code}"
        data = response.json()
        
        # Should return signals or a success response
        assert "signals" in data or "success" in data, f"Unexpected response: {data}"
        print(f"✅ Scan markets passed: {data.get('message', 'signals returned')}")
    
    def test_record_premium_result(self):
        """POST /api/signals/record-premium-result - records trade result"""
        response = requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json={
                "symbol": "EURUSD_OTC",
                "direction": "CALL",
                "is_win": True,
                "confidence": 85
            },
            timeout=10
        )
        # Should return 200 or 201
        assert response.status_code in [200, 201], f"Record premium result failed: {response.status_code} - {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Record not successful: {data}"
        print(f"✅ Record premium result passed")


class TestRiskManagement:
    """Tests for risk management endpoints"""
    
    def test_risk_metrics(self):
        """GET /api/risk-management/metrics - returns risk metrics"""
        response = requests.get(f"{BASE_URL}/api/risk-management/metrics", timeout=10)
        assert response.status_code == 200, f"Risk metrics failed: {response.status_code}"
        data = response.json()
        
        # Data may be nested under 'metrics' key
        metrics = data.get("metrics", data)
        
        # Verify expected fields
        expected_fields = ["sharpe_ratio", "sortino_ratio", "max_drawdown_pct", "profit_factor", "win_rate_pct"]
        for field in expected_fields:
            assert field in metrics, f"Missing field '{field}' in risk metrics: {data}"
        
        print(f"✅ Risk metrics passed: sharpe={metrics.get('sharpe_ratio')}, win_rate={metrics.get('win_rate_pct')}%")


class TestMLStats:
    """Tests for ML statistics endpoints"""
    
    def test_maximized_ml_stats(self):
        """GET /api/maximized-ml/stats - returns ML stats"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats", timeout=10)
        assert response.status_code == 200, f"ML stats failed: {response.status_code}"
        data = response.json()
        
        # Should have model info
        assert "model_accuracy" in data or "accuracy" in data or "stats" in data, f"Missing accuracy info: {data}"
        print(f"✅ ML stats passed: {data}")


class TestTampermonkeyScript:
    """Tests for Tampermonkey script accessibility and v8.4 functions"""
    
    def test_script_accessible(self):
        """Tampermonkey script is accessible at /pocket-option-auto-trader.user.js"""
        response = requests.get(
            f"{BASE_URL}/pocket-option-auto-trader.user.js",
            timeout=10
        )
        assert response.status_code == 200, f"Script not accessible: {response.status_code}"
        content = response.text
        assert len(content) > 1000, f"Script content too short: {len(content)} bytes"
        print(f"✅ Tampermonkey script accessible: {len(content)} bytes")
    
    def test_script_contains_balance_sync(self):
        """Script contains startBalanceSync function"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=10)
        content = response.text
        assert "startBalanceSync" in content, "Missing startBalanceSync function"
        print(f"✅ Script contains startBalanceSync")
    
    def test_script_contains_recalculate_bet_size(self):
        """Script contains recalculateBetSize function"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=10)
        content = response.text
        assert "recalculateBetSize" in content, "Missing recalculateBetSize function"
        print(f"✅ Script contains recalculateBetSize")
    
    def test_script_contains_local_momentum_check(self):
        """Script contains localMomentumCheck function"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=10)
        content = response.text
        assert "localMomentumCheck" in content, "Missing localMomentumCheck function"
        print(f"✅ Script contains localMomentumCheck")
    
    def test_script_contains_backend_momentum_check(self):
        """Script contains backendMomentumCheck function"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=10)
        content = response.text
        assert "backendMomentumCheck" in content, "Missing backendMomentumCheck function"
        print(f"✅ Script contains backendMomentumCheck")
    
    def test_script_contains_do_invert_toggle(self):
        """Script contains doInvertToggle function"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=10)
        content = response.text
        assert "doInvertToggle" in content, "Missing doInvertToggle function"
        print(f"✅ Script contains doInvertToggle")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
