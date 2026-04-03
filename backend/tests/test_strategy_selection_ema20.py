"""
Test Suite for Strategy Selection and EMA 20 Pullback Reversal Strategy
Tests:
1. GET /api/strategies/available/5s - EMA 20 Pullback Reversal in list
2. POST /api/strategies/select - Select ema20_pullback_reversal for 5s
3. GET /api/strategies/selected - Verify selection persisted
4. GET /api/signals/scan-markets - With selected strategy (active_strategy field)
5. GET /api/signals/scan-markets - With explicit strategy_id override
6. POST /api/strategies/select - Reset to default
7. GET /api/signals/scan-markets - With default strategy (deep_confluence)
8. Regression: session-info, should-trade, record-premium-result
9. Tampermonkey script verification
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestStrategyAvailable:
    """Test GET /api/strategies/available/5s endpoint"""
    
    def test_available_5s_strategies_includes_ema20(self):
        """Verify ema20_pullback_reversal is in 5s available strategies"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/5s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert data.get("timeframe") == "5s"
        
        strategies = data.get("strategies", [])
        assert len(strategies) > 0, "No strategies returned for 5s timeframe"
        
        # Find ema20_pullback_reversal
        ema20_strategy = None
        for s in strategies:
            if s.get("id") == "ema20_pullback_reversal":
                ema20_strategy = s
                break
        
        assert ema20_strategy is not None, f"ema20_pullback_reversal not found in 5s strategies: {[s.get('id') for s in strategies]}"
        assert ema20_strategy.get("name") == "EMA 20 Pullback Reversal", f"Wrong name: {ema20_strategy.get('name')}"
        assert ema20_strategy.get("win_rate") == "80-90%", f"Wrong win_rate: {ema20_strategy.get('win_rate')}"
        print(f"✅ ema20_pullback_reversal found with name='{ema20_strategy.get('name')}', win_rate='{ema20_strategy.get('win_rate')}'")
    
    def test_available_all_strategies(self):
        """Verify GET /api/strategies/available returns all timeframes"""
        response = requests.get(f"{BASE_URL}/api/strategies/available")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        
        strategies = data.get("strategies", {})
        assert "5s" in strategies, "5s timeframe missing"
        assert "15s" in strategies, "15s timeframe missing"
        assert "30s" in strategies, "30s timeframe missing"
        assert "1m" in strategies, "1m timeframe missing"
        
        # Verify ema20 is in 5s list
        strategies_5s = strategies.get("5s", [])
        ema20_ids = [s.get("id") for s in strategies_5s]
        assert "ema20_pullback_reversal" in ema20_ids, f"ema20_pullback_reversal not in 5s: {ema20_ids}"
        print(f"✅ All timeframes present with ema20_pullback_reversal in 5s")


class TestStrategySelection:
    """Test strategy selection endpoints"""
    
    def test_select_ema20_pullback_reversal(self):
        """POST /api/strategies/select with ema20_pullback_reversal for 5s"""
        payload = {
            "timeframe": "5s",
            "strategy_id": "ema20_pullback_reversal"
        }
        response = requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert data.get("timeframe") == "5s"
        assert data.get("strategy_id") == "ema20_pullback_reversal"
        print(f"✅ Successfully selected ema20_pullback_reversal for 5s")
    
    def test_get_selected_strategies_shows_ema20(self):
        """GET /api/strategies/selected should show 5s = ema20_pullback_reversal"""
        # First ensure it's selected
        payload = {"timeframe": "5s", "strategy_id": "ema20_pullback_reversal"}
        requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        
        response = requests.get(f"{BASE_URL}/api/strategies/selected")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        
        selections = data.get("selections", {})
        assert selections.get("5s") == "ema20_pullback_reversal", f"5s selection is {selections.get('5s')}, expected ema20_pullback_reversal"
        print(f"✅ Selected strategies: {selections}")
    
    def test_select_invalid_strategy_fails(self):
        """POST /api/strategies/select with invalid strategy should fail"""
        payload = {
            "timeframe": "5s",
            "strategy_id": "nonexistent_strategy_xyz"
        }
        response = requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid strategy, got {response.status_code}"
        print(f"✅ Invalid strategy correctly rejected with 400")
    
    def test_reset_to_default(self):
        """POST /api/strategies/select with 'default' should reset"""
        payload = {
            "timeframe": "5s",
            "strategy_id": "default"
        }
        response = requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        assert data.get("strategy_id") == "default"
        print(f"✅ Successfully reset 5s to default strategy")


class TestScanMarketsWithStrategy:
    """Test scan-markets endpoint with strategy selection"""
    
    def test_scan_markets_with_selected_ema20_strategy(self):
        """GET /api/signals/scan-markets with preferred_expiry=5 should use selected ema20 strategy"""
        # First select ema20_pullback_reversal for 5s
        payload = {"timeframe": "5s", "strategy_id": "ema20_pullback_reversal"}
        select_resp = requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        assert select_resp.status_code == 200
        
        # Now scan markets with preferred_expiry=5 (maps to 5s timeframe)
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EUR_USD,GBP_USD,USD_JPY",
                "min_confidence": 50,
                "preferred_expiry": 5
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        
        # Verify active_strategy field
        active_strategy = data.get("active_strategy")
        assert active_strategy == "ema20_pullback_reversal", f"active_strategy is {active_strategy}, expected ema20_pullback_reversal"
        
        # Check if any signal has analysis_type=selected_ema20_pullback_reversal
        top_signals = data.get("top_signals", [])
        print(f"Found {len(top_signals)} signals with active_strategy={active_strategy}")
        
        # Note: Not all assets may generate a signal from EMA20 strategy (depends on market conditions)
        # The important thing is that active_strategy is correctly set
        if top_signals:
            analysis_types = [s.get("analysis_type") for s in top_signals]
            print(f"Analysis types: {analysis_types}")
            # At least one should be from selected strategy or fallback
            has_selected = any("selected_ema20" in str(at) for at in analysis_types)
            has_deep = any("deep_confluence" in str(at) for at in analysis_types)
            assert has_selected or has_deep, f"Expected selected_ema20 or deep_confluence, got {analysis_types}"
        
        print(f"✅ scan-markets returned active_strategy=ema20_pullback_reversal")
    
    def test_scan_markets_with_explicit_strategy_id(self):
        """GET /api/signals/scan-markets with explicit strategy_id parameter"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EUR_USD",
                "min_confidence": 50,
                "strategy_id": "ema20_pullback_reversal"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        
        # Explicit strategy_id should override selection
        active_strategy = data.get("active_strategy")
        assert active_strategy == "ema20_pullback_reversal", f"active_strategy is {active_strategy}"
        print(f"✅ Explicit strategy_id override works: active_strategy={active_strategy}")
    
    def test_scan_markets_with_default_strategy(self):
        """GET /api/signals/scan-markets with default strategy uses deep_confluence"""
        # Reset to default
        payload = {"timeframe": "5s", "strategy_id": "default"}
        requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EUR_USD,GBP_USD",
                "min_confidence": 50,
                "preferred_expiry": 5
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        
        active_strategy = data.get("active_strategy")
        assert active_strategy == "default", f"active_strategy is {active_strategy}, expected default"
        
        # With default strategy, signals should use deep_confluence analysis
        top_signals = data.get("top_signals", [])
        if top_signals:
            analysis_types = [s.get("analysis_type") for s in top_signals]
            print(f"Default strategy analysis types: {analysis_types}")
            # Should be deep_confluence or other fallback strategies
            has_deep = any("deep_confluence" in str(at) or "holly" in str(at) or "golden" in str(at) or "momentum" in str(at) for at in analysis_types)
            assert has_deep, f"Expected deep_confluence or fallback, got {analysis_types}"
        
        print(f"✅ Default strategy uses deep_confluence analysis")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_session_info_still_works(self):
        """GET /api/signals/session-info should still work"""
        response = requests.get(f"{BASE_URL}/api/signals/session-info")
        assert response.status_code == 200
        
        data = response.json()
        assert "session_details" in data or "session" in data
        print(f"✅ session-info endpoint works")
    
    def test_should_trade_still_works(self):
        """GET /api/signals/should-trade should still work"""
        response = requests.get(f"{BASE_URL}/api/signals/should-trade")
        assert response.status_code == 200
        
        data = response.json()
        assert "should_trade" in data
        print(f"✅ should-trade endpoint works: should_trade={data.get('should_trade')}")
    
    def test_record_premium_result_still_works(self):
        """POST /api/signals/record-premium-result should still work"""
        payload = {
            "symbol": "TEST_EUR_USD",
            "direction": "CALL",
            "is_win": True,
            "confidence": 75
        }
        response = requests.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "recorded" in data
        assert data["recorded"]["is_win"] is True
        print(f"✅ record-premium-result endpoint works")


class TestTampermonkeyScript:
    """Test Tampermonkey script accessibility and content"""
    
    def test_tampermonkey_script_accessible(self):
        """Tampermonkey script should be accessible at /pocket-option-auto-trader-modular.user.js"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200, f"Script not accessible: {response.status_code}"
        
        content = response.text
        assert len(content) > 1000, "Script content too short"
        print(f"✅ Tampermonkey script accessible ({len(content)} bytes)")
    
    def test_tampermonkey_has_ema20_strategy(self):
        """Tampermonkey script should reference EMA 20 Pullback strategy"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        # Check for EMA 20 Pullback Reversal references
        has_ema20 = "EMA 20 Pullback" in content or "ema20_pullback" in content or "EMA20Pullback" in content
        assert has_ema20, "EMA 20 Pullback strategy not found in Tampermonkey script"
        print(f"✅ Tampermonkey script contains EMA 20 Pullback strategy")
    
    def test_tampermonkey_has_sync_from_app(self):
        """Tampermonkey script should have syncFromApp feature"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        has_sync = "syncFromApp" in content or "sync" in content.lower()
        # Also check for strategy selection API call
        has_strategy_api = "/strategies/selected" in content or "strategies" in content
        
        assert has_sync or has_strategy_api, "syncFromApp or strategy API not found in script"
        print(f"✅ Tampermonkey script has sync/strategy features")


class TestScanMarketsResponseStructure:
    """Test scan-markets response structure"""
    
    def test_scan_markets_response_has_required_fields(self):
        """Verify scan-markets response has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EUR_USD",
                "min_confidence": 50
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields
        assert "success" in data
        assert "active_strategy" in data, "active_strategy field missing"
        assert "scanned_assets" in data
        assert "signals_found" in data
        assert "top_signals" in data
        assert "preferred_expiry" in data
        assert "time_filter" in data
        
        print(f"✅ scan-markets response has all required fields including active_strategy")
    
    def test_scan_markets_min_confidence_validation(self):
        """Verify min_confidence < 50 is rejected"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EUR_USD",
                "min_confidence": 30  # Below minimum of 50
            }
        )
        assert response.status_code == 422, f"Expected 422 for min_confidence < 50, got {response.status_code}"
        print(f"✅ min_confidence < 50 correctly rejected with 422")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    """Reset strategy selection after tests"""
    yield
    # Reset to default after all tests
    try:
        payload = {"timeframe": "5s", "strategy_id": "default"}
        requests.post(f"{BASE_URL}/api/strategies/select", json=payload)
    except Exception:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
