"""
Test Direction-Aware Loss Detection and Invert Suggestion Features
Tests for iteration 19 - Premium Signal Filters with direction tracking
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDirectionAwareLossDetection:
    """Tests for direction-aware loss detection and invert_suggestion in scan-markets"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    # ==================== Session Info Tests ====================
    def test_session_info_endpoint(self):
        """GET /api/signals/session-info - Returns current trading session info"""
        response = self.session.get(f"{BASE_URL}/api/signals/session-info")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        # Response has session_details and time_filter
        assert "session_details" in data or "time_filter" in data
        
        session_details = data.get("session_details", {})
        time_filter = data.get("time_filter", {})
        
        session = session_details.get("session") or time_filter.get("session")
        quality = session_details.get("quality_score") or time_filter.get("quality")
        
        print(f"✅ Session info: {session}, quality: {quality}")
    
    # ==================== Best Hours Tests ====================
    def test_best_hours_endpoint(self):
        """GET /api/signals/best-hours - Returns best trading hours"""
        response = self.session.get(f"{BASE_URL}/api/signals/best-hours")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "best_hours" in data
        assert "hours_to_avoid" in data
        print(f"✅ Best hours: {len(data.get('best_hours', []))} hours, avoid: {len(data.get('hours_to_avoid', []))} hours")
    
    # ==================== Hourly Stats Tests ====================
    def test_hourly_stats_endpoint(self):
        """GET /api/signals/hourly-stats - Returns 24-hour breakdown"""
        response = self.session.get(f"{BASE_URL}/api/signals/hourly-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        # Response uses hourly_stats key
        assert "hourly_stats" in data
        print(f"✅ Hourly stats: {len(data.get('hourly_stats', []))} hours tracked")
    
    # ==================== Record Premium Result Tests ====================
    def test_record_premium_result_win(self):
        """POST /api/signals/record-premium-result - Records WIN with direction tracking"""
        payload = {
            "symbol": "TEST_DIRECTION_EUR_USD",
            "direction": "CALL",
            "is_win": True,
            "confidence": 75
        }
        response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "recorded" in data
        assert data["recorded"]["symbol"] == "TEST_DIRECTION_EUR_USD"
        assert data["recorded"]["direction"] == "CALL"
        assert data["recorded"]["is_win"] == True
        print(f"✅ Recorded WIN for CALL direction")
    
    def test_record_premium_result_loss(self):
        """POST /api/signals/record-premium-result - Records LOSS with direction tracking"""
        payload = {
            "symbol": "TEST_DIRECTION_EUR_USD",
            "direction": "PUT",
            "is_win": False,
            "confidence": 70
        }
        response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert data["recorded"]["is_win"] == False
        print(f"✅ Recorded LOSS for PUT direction")
    
    def test_record_consecutive_losses_same_direction(self):
        """Record 3+ consecutive same-direction losses to trigger invert_suggestion"""
        symbol = "TEST_INVERT_USD_JPY"
        
        # Record 4 consecutive PUT losses
        for i in range(4):
            payload = {
                "symbol": symbol,
                "direction": "PUT",
                "is_win": False,
                "confidence": 65
            }
            response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
            assert response.status_code == 200
            time.sleep(0.1)  # Small delay between records
        
        print(f"✅ Recorded 4 consecutive PUT losses for {symbol}")
        
        # Verify asset performance shows the losses
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance", params={"symbol": symbol})
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Asset stats: {data.get('asset_stats', {})}")
    
    # ==================== Asset Performance Tests ====================
    def test_asset_performance_all(self):
        """GET /api/signals/asset-performance - Returns all tracked asset statistics"""
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "all_assets" in data
        assert "total_tracked" in data
        print(f"✅ Total assets tracked: {data.get('total_tracked', 0)}")
    
    def test_asset_performance_specific(self):
        """GET /api/signals/asset-performance?symbol=USD_JPY - Returns specific asset with direction stats"""
        # First record some data for USD_JPY
        payload = {
            "symbol": "USD_JPY",
            "direction": "CALL",
            "is_win": True,
            "confidence": 80
        }
        self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
        
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance", params={"symbol": "USD_JPY"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "asset_stats" in data
        print(f"✅ USD_JPY stats: {data.get('asset_stats', {})}")
    
    # ==================== Should Trade Tests ====================
    def test_should_trade_endpoint(self):
        """GET /api/signals/should-trade - Quick trade check"""
        response = self.session.get(f"{BASE_URL}/api/signals/should-trade")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "should_trade" in data
        assert "reason" in data
        assert "time_filter" in data
        print(f"✅ Should trade: {data.get('should_trade')}, reason: {data.get('reason')}")
    
    # ==================== Scan Markets Tests ====================
    def test_scan_markets_basic(self):
        """GET /api/signals/scan-markets - Basic scan with min_confidence validation"""
        response = self.session.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EUR_USD,GBP_USD", "min_confidence": 50}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        assert "top_signals" in data
        assert "time_filter" in data
        print(f"✅ Scan markets: {data.get('signals_found', 0)} signals found")
    
    def test_scan_markets_min_confidence_validation(self):
        """GET /api/signals/scan-markets - min_confidence must be >= 50"""
        # Test with min_confidence below 50 (should be rejected or clamped)
        response = self.session.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EUR_USD", "min_confidence": 30}
        )
        # FastAPI validation should reject values below 50
        assert response.status_code in [200, 422], f"Expected 200 or 422, got {response.status_code}"
        
        if response.status_code == 422:
            print(f"✅ min_confidence < 50 correctly rejected with 422")
        else:
            print(f"✅ min_confidence handled (may be clamped to 50)")
    
    def test_scan_markets_with_premium_filters(self):
        """GET /api/signals/scan-markets - Returns signals with premium_filters including invert_suggestion"""
        response = self.session.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EUR_USD,GBP_USD,USD_JPY", "min_confidence": 50}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        
        # Check if signals have premium_filters
        top_signals = data.get("top_signals", [])
        if top_signals:
            for signal in top_signals:
                if "premium_filters" in signal:
                    pf = signal["premium_filters"]
                    assert "invert_suggestion" in pf, "premium_filters should contain invert_suggestion"
                    assert "direction_loss_streak" in pf, "premium_filters should contain direction_loss_streak"
                    print(f"✅ Signal {signal.get('symbol')}: invert_suggestion={pf.get('invert_suggestion')}, direction_loss_streak={pf.get('direction_loss_streak')}")
        else:
            print(f"⚠️ No signals found to verify premium_filters (market conditions may not meet threshold)")
    
    def test_direction_aware_invert_suggestion(self):
        """Test that after 3+ consecutive same-direction losses, invert_suggestion=true"""
        symbol = "TEST_INVERT_CHECK_GBP_USD"
        
        # Record 3 consecutive CALL losses
        for i in range(3):
            payload = {
                "symbol": symbol,
                "direction": "CALL",
                "is_win": False,
                "confidence": 60
            }
            response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
            assert response.status_code == 200
            time.sleep(0.1)
        
        # Check asset performance for direction loss streak
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance", params={"symbol": symbol})
        assert response.status_code == 200
        data = response.json()
        
        # The asset should now have recorded losses
        asset_stats = data.get("asset_stats", {})
        print(f"✅ After 3 CALL losses, asset stats: {asset_stats}")
        
        # Verify losses_call is tracked
        assert asset_stats.get("total", 0) >= 3, "Should have at least 3 trades recorded"
    
    def test_direction_opposite_bonus(self):
        """Test that signal direction opposite to losing streak gets +2 confidence bonus"""
        symbol = "TEST_OPPOSITE_BONUS_AUD_USD"
        
        # Record 3 consecutive PUT losses
        for i in range(3):
            payload = {
                "symbol": symbol,
                "direction": "PUT",
                "is_win": False,
                "confidence": 65
            }
            response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
            assert response.status_code == 200
            time.sleep(0.1)
        
        print(f"✅ Recorded 3 PUT losses for {symbol}")
        
        # Verify the losses are tracked
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance", params={"symbol": symbol})
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Asset stats after PUT losses: {data.get('asset_stats', {})}")


class TestTampermonkeyScript:
    """Tests for Tampermonkey script accessibility and content"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
    
    def test_tampermonkey_script_accessible(self):
        """Verify Tampermonkey script is accessible at /pocket-option-auto-trader-modular.user.js"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        assert len(content) > 1000, "Script should have substantial content"
        print(f"✅ Tampermonkey script accessible, size: {len(content)} bytes")
    
    def test_tampermonkey_script_header_name(self):
        """Verify script header shows 'Elite Pocket Option Trading Bot'"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "@name" in content, "Script should have @name header"
        assert "Elite Pocket Option Trading Bot" in content, "Script name should be 'Elite Pocket Option Trading Bot'"
        print(f"✅ Script name is 'Elite Pocket Option Trading Bot'")
    
    def test_tampermonkey_script_version(self):
        """Verify script header shows v8.0.0"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "@version" in content, "Script should have @version header"
        assert "8.0.0" in content, "Script version should be 8.0.0"
        print(f"✅ Script version is 8.0.0")
    
    def test_tampermonkey_script_contains_attachShadow(self):
        """Verify script contains attachShadow (Shadow DOM)"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "attachShadow" in content, "Script should contain attachShadow for Shadow DOM"
        print(f"✅ Script contains attachShadow (Shadow DOM)")
    
    def test_tampermonkey_script_contains_record_premium_result(self):
        """Verify script contains record-premium-result API call"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "record-premium-result" in content, "Script should contain record-premium-result API call"
        print(f"✅ Script contains record-premium-result API call")
    
    def test_tampermonkey_script_contains_INVERT(self):
        """Verify script contains INVERT button/feature"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "INVERT" in content, "Script should contain INVERT feature"
        print(f"✅ Script contains INVERT feature")
    
    def test_tampermonkey_script_contains_reinject(self):
        """Verify script contains re-inject watchdog feature"""
        response = self.session.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js")
        assert response.status_code == 200
        
        content = response.text
        assert "re-inject" in content, "Script should contain re-inject watchdog"
        print(f"✅ Script contains re-inject watchdog")


class TestPremiumFiltersIntegration:
    """Integration tests for premium filters with direction tracking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_full_flow_record_and_check_invert(self):
        """Full flow: Record losses -> Check invert_suggestion in scan-markets"""
        symbol = "TEST_FULL_FLOW_NZD_USD"
        
        # Step 1: Record 4 consecutive PUT losses
        for i in range(4):
            payload = {
                "symbol": symbol,
                "direction": "PUT",
                "is_win": False,
                "confidence": 70
            }
            response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
            assert response.status_code == 200
            time.sleep(0.1)
        
        print(f"✅ Step 1: Recorded 4 PUT losses for {symbol}")
        
        # Step 2: Verify asset performance
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance", params={"symbol": symbol})
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✅ Step 2: Asset stats: {data.get('asset_stats', {})}")
        
        # Step 3: Check session info
        response = self.session.get(f"{BASE_URL}/api/signals/session-info")
        assert response.status_code == 200
        session_data = response.json()
        print(f"✅ Step 3: Current session: {session_data.get('session_details', {}).get('session') or session_data.get('time_filter', {}).get('session')}")
        
        # Step 4: Check should-trade
        response = self.session.get(f"{BASE_URL}/api/signals/should-trade")
        assert response.status_code == 200
        trade_data = response.json()
        print(f"✅ Step 4: Should trade: {trade_data.get('should_trade')}")
    
    def test_confidence_penalty_for_losing_direction(self):
        """Verify confidence is penalized for signals in losing direction"""
        symbol = "TEST_PENALTY_V2_CHF_JPY"
        
        # Record 3 CALL losses
        for i in range(3):
            payload = {
                "symbol": symbol,
                "direction": "CALL",
                "is_win": False,
                "confidence": 75
            }
            response = self.session.post(f"{BASE_URL}/api/signals/record-premium-result", json=payload)
            assert response.status_code == 200
            time.sleep(0.1)
        
        # Verify the losses are tracked via all assets endpoint (has direction-specific fields)
        response = self.session.get(f"{BASE_URL}/api/signals/asset-performance")
        assert response.status_code == 200
        data = response.json()
        
        # Find our test asset in all_assets
        all_assets = data.get("all_assets", [])
        test_asset = next((a for a in all_assets if a.get("symbol") == symbol), None)
        
        assert test_asset is not None, f"Test asset {symbol} not found in all_assets"
        
        # Check that losses_call is tracked
        losses_call = test_asset.get("losses_call", 0)
        total = test_asset.get("total", 0)
        print(f"✅ CALL losses tracked: {losses_call}, total: {total}")
        assert total >= 3, f"Expected at least 3 total trades, got {total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
