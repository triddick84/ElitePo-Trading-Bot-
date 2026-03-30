"""
Test file for bug fixes in iteration 15:
1. GO button (force-generate/asset endpoint) - Fixed by using OANDA as primary data source
2. Strategy toggle - Fixed by adding missing get_strategy_service function import
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestForceGenerateSignalEndpoint:
    """Tests for the GO button backend endpoint - force-generate/asset"""
    
    def test_force_generate_eurusd_otc(self):
        """Test force generate signal for EURUSD_OTC - GO button functionality"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/EURUSD_OTC",
            params={"wait_for_candle": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "signal" in data, "Response should contain 'signal' field"
        assert data["signal"] is not None, "Signal should not be None"
        
        # Verify signal structure
        signal = data["signal"]
        assert "id" in signal, "Signal should have 'id'"
        assert "symbol" in signal, "Signal should have 'symbol'"
        assert "direction" in signal, "Signal should have 'direction'"
        assert "probability" in signal, "Signal should have 'probability'"
        assert signal["direction"] in ["BUY", "SELL", "CALL", "PUT"], f"Invalid direction: {signal['direction']}"
        print(f"✅ EURUSD_OTC signal generated: {signal['direction']} with {signal['probability']}% confidence")
    
    def test_force_generate_gbpusd_otc(self):
        """Test force generate signal for GBPUSD_OTC"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/GBPUSD_OTC",
            params={"wait_for_candle": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "signal" in data, "Response should contain 'signal' field"
        print(f"✅ GBPUSD_OTC signal generated successfully")
    
    def test_force_generate_regular_asset(self):
        """Test force generate signal for regular (non-OTC) asset"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/EURUSD",
            params={"wait_for_candle": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✅ EURUSD (regular) signal generated successfully")


class TestStrategyToggleEndpoint:
    """Tests for strategy toggle endpoint - Fixed missing get_strategy_service function"""
    
    def test_get_custom_strategies(self):
        """Test GET /api/custom-strategies returns list of strategies"""
        response = requests.get(f"{BASE_URL}/api/custom-strategies")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "strategies" in data, "Response should contain 'strategies' field"
        assert isinstance(data["strategies"], list), "Strategies should be a list"
        print(f"✅ Found {len(data['strategies'])} custom strategies")
        return data["strategies"]
    
    def test_toggle_strategy_activate(self):
        """Test activating a strategy via toggle endpoint"""
        # First get a strategy ID
        strategies = self.test_get_custom_strategies()
        if not strategies:
            pytest.skip("No strategies available to test toggle")
        
        strategy_id = strategies[0]["id"]
        strategy_name = strategies[0]["name"]
        
        # Toggle to active
        response = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "strategy" in data, "Response should contain 'strategy' field"
        assert data["strategy"]["is_active"] == True, "Strategy should be active"
        print(f"✅ Strategy '{strategy_name}' activated successfully")
    
    def test_toggle_strategy_deactivate(self):
        """Test deactivating a strategy via toggle endpoint"""
        # First get a strategy ID
        strategies_response = requests.get(f"{BASE_URL}/api/custom-strategies")
        strategies = strategies_response.json().get("strategies", [])
        if not strategies:
            pytest.skip("No strategies available to test toggle")
        
        strategy_id = strategies[0]["id"]
        strategy_name = strategies[0]["name"]
        
        # Toggle to inactive
        response = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "strategy" in data, "Response should contain 'strategy' field"
        assert data["strategy"]["is_active"] == False, "Strategy should be inactive"
        print(f"✅ Strategy '{strategy_name}' deactivated successfully")
    
    def test_toggle_strategy_roundtrip(self):
        """Test toggling strategy on and off (roundtrip)"""
        # Get a strategy
        strategies_response = requests.get(f"{BASE_URL}/api/custom-strategies")
        strategies = strategies_response.json().get("strategies", [])
        if not strategies:
            pytest.skip("No strategies available to test toggle")
        
        strategy_id = strategies[0]["id"]
        original_state = strategies[0].get("is_active", False)
        
        # Toggle to opposite state
        new_state = not original_state
        response1 = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": new_state}
        )
        assert response1.status_code == 200
        assert response1.json()["strategy"]["is_active"] == new_state
        
        # Toggle back to original state
        response2 = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": original_state}
        )
        assert response2.status_code == 200
        assert response2.json()["strategy"]["is_active"] == original_state
        
        print(f"✅ Strategy toggle roundtrip successful: {original_state} -> {new_state} -> {original_state}")


class TestHealthAndBasicEndpoints:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint is working"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health endpoint working")
    
    def test_signals_history(self):
        """Test signals history endpoint"""
        response = requests.get(f"{BASE_URL}/api/signals/history")
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        print(f"✅ Signals history: {len(data['signals'])} signals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
