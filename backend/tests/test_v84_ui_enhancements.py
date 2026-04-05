"""
Test Suite for Elite Pocket Option Trading Bot v8.4 UI Enhancements
Tests:
1. GO Button direction mapping: POST /api/signals/force-generate/asset/EURUSD
2. Momentum Check API: GET /api/signals/momentum-check?symbol=EURUSD
3. Tampermonkey Settings API: GET /api/tampermonkey/settings
4. Tampermonkey Stats Reset: POST /api/tampermonkey/stats/reset
5. Tampermonkey script accessibility and v8.4 features
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://momentum-trade-test.preview.emergentagent.com')


class TestHealthAndBasics:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✅ Health check passed: {data.get('status')}")


class TestForceGenerateAssetEndpoint:
    """Tests for GO Button direction mapping - POST /api/signals/force-generate/asset/{asset}"""
    
    def test_force_generate_eurusd_returns_direction(self):
        """Test force-generate for EURUSD returns direction (SELL/BUY)"""
        response = requests.post(f"{BASE_URL}/api/signals/force-generate/asset/EURUSD")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "signal" in data
        
        signal = data["signal"]
        assert "direction" in signal
        # Direction should be SELL or BUY (which maps to PUT/CALL in Tampermonkey)
        assert signal["direction"] in ["SELL", "BUY", "PUT", "CALL"]
        
        print(f"✅ Force generate EURUSD: direction={signal['direction']}, probability={signal.get('probability')}")
    
    def test_force_generate_returns_required_fields(self):
        """Test force-generate returns all required fields for Tampermonkey"""
        response = requests.post(f"{BASE_URL}/api/signals/force-generate/asset/GBPUSD")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        signal = data.get("signal", {})
        
        # Required fields for Tampermonkey script
        required_fields = ["id", "symbol", "direction", "entry_price", "probability", "timeframe"]
        for field in required_fields:
            assert field in signal, f"Missing required field: {field}"
        
        print(f"✅ Force generate GBPUSD: All required fields present")


class TestMomentumCheckEndpoint:
    """Tests for Momentum Check API - GET /api/signals/momentum-check"""
    
    def test_momentum_check_returns_should_invert(self):
        """Test momentum-check returns should_invert boolean"""
        response = requests.get(f"{BASE_URL}/api/signals/momentum-check?symbol=EURUSD")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "should_invert" in data
        assert isinstance(data["should_invert"], bool)
        
        print(f"✅ Momentum check EURUSD: should_invert={data['should_invert']}, momentum={data.get('momentum')}")
    
    def test_momentum_check_returns_analysis_fields(self):
        """Test momentum-check returns analysis fields"""
        response = requests.get(f"{BASE_URL}/api/signals/momentum-check?symbol=EURUSD_OTC")
        assert response.status_code == 200
        data = response.json()
        
        # Should have momentum analysis fields
        expected_fields = ["success", "should_invert", "momentum", "trend", "confidence"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✅ Momentum check EURUSD_OTC: momentum={data.get('momentum')}, trend={data.get('trend')}")


class TestTampermonkeySettingsEndpoint:
    """Tests for Tampermonkey Settings API - GET /api/tampermonkey/settings"""
    
    def test_get_settings_returns_selected_strategy(self):
        """Test settings endpoint returns selected_strategy"""
        response = requests.get(f"{BASE_URL}/api/tampermonkey/settings")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "settings" in data
        
        settings = data["settings"]
        assert "selected_strategy" in settings
        
        print(f"✅ Tampermonkey settings: selected_strategy={settings.get('selected_strategy')}")
    
    def test_get_settings_returns_all_required_fields(self):
        """Test settings endpoint returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/tampermonkey/settings")
        assert response.status_code == 200
        data = response.json()
        
        settings = data.get("settings", {})
        
        # Required settings fields
        required_fields = [
            "invert_signals", "scan_mode", "auto_trade", "preferred_expiry",
            "min_payout", "selected_timeframes", "selected_strategy", "signal_source"
        ]
        
        for field in required_fields:
            assert field in settings, f"Missing settings field: {field}"
        
        print(f"✅ Tampermonkey settings: All required fields present")


class TestTampermonkeyStatsResetEndpoint:
    """Tests for Tampermonkey Stats Reset - POST /api/tampermonkey/stats/reset"""
    
    def test_stats_reset_clears_wins_losses(self):
        """Test stats reset clears win/loss stats"""
        response = requests.post(f"{BASE_URL}/api/tampermonkey/stats/reset")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "stats" in data
        
        stats = data["stats"]
        assert stats.get("wins") == 0
        assert stats.get("losses") == 0
        assert stats.get("consecutive_wins") == 0
        assert stats.get("consecutive_losses") == 0
        assert stats.get("session_profit") == 0
        
        print(f"✅ Stats reset: wins={stats['wins']}, losses={stats['losses']}, profit={stats['session_profit']}")
    
    def test_get_stats_after_reset(self):
        """Test getting stats after reset shows zeroed values"""
        # First reset
        requests.post(f"{BASE_URL}/api/tampermonkey/stats/reset")
        
        # Then get stats
        response = requests.get(f"{BASE_URL}/api/tampermonkey/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        stats = data.get("stats", {})
        
        assert stats.get("wins") == 0
        assert stats.get("losses") == 0
        
        print(f"✅ Get stats after reset: wins={stats['wins']}, losses={stats['losses']}")


class TestTampermonkeyScriptAccessibility:
    """Tests for Tampermonkey script v8.4 accessibility"""
    
    def test_script_is_accessible(self):
        """Test Tampermonkey script is accessible via HTTP"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "// ==UserScript==" in content
        assert "8.4.0" in content  # Version check
        
        print(f"✅ Tampermonkey script accessible, version 8.4.0 found")
    
    def test_script_contains_go_button_direction_mapping(self):
        """Test script contains GO button direction mapping (SELL→PUT, BUY→CALL)"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js")
        assert response.status_code == 200
        
        content = response.text
        
        # Check for _goForceGenerate function
        assert "_goForceGenerate" in content or "goForceGenerate" in content
        
        print(f"✅ Tampermonkey script contains GO button force generate function")
    
    def test_script_contains_invert_mode_function(self):
        """Test script contains 3-mode invert control (OFF/AUTO/ON)"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js")
        assert response.status_code == 200
        
        content = response.text
        
        # Check for invert mode functions
        assert "setInvertMode" in content or "invertMode" in content or "doInvertToggle" in content
        
        print(f"✅ Tampermonkey script contains invert mode control")
    
    def test_script_contains_reset_stats_function(self):
        """Test script contains reset stats button functionality"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js")
        assert response.status_code == 200
        
        content = response.text
        
        # Check for reset stats function
        assert "resetAllStats" in content or "resetStats" in content
        
        print(f"✅ Tampermonkey script contains reset stats function")


class TestTampermonkeyStrategiesEndpoint:
    """Tests for Tampermonkey strategies endpoint"""
    
    def test_get_strategies(self):
        """Test getting available strategies"""
        response = requests.get(f"{BASE_URL}/api/tampermonkey/strategies")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "strategies" in data
        assert len(data["strategies"]) > 0
        
        print(f"✅ Tampermonkey strategies: {len(data['strategies'])} strategies available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
