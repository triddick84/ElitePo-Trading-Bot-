"""
Premium Signal Filter Endpoints Tests
Tests for session-info, best-hours, hourly-stats, record-premium-result, 
asset-performance, should-trade, and scan-markets premium filter integration.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSessionInfo:
    """Tests for GET /api/signals/session-info endpoint"""
    
    def test_session_info_basic(self):
        """Test basic session info without symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/session-info")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "time_filter" in data
        assert "session_details" in data
        
        # Validate time_filter structure
        tf = data["time_filter"]
        assert "hour_utc" in tf
        assert "session" in tf
        assert "quality" in tf
        assert "is_good_time" in tf
        assert "historical_win_rate" in tf
        assert "recommendation" in tf
        
        # Validate session_details structure
        sd = data["session_details"]
        assert "session" in sd
        assert "is_active" in sd
        assert "quality_score" in sd
        assert "recommended_pairs" in sd
        assert "avoid_pairs" in sd
        assert "notes" in sd
        
        print(f"✅ Session info: {sd['session']}, quality: {sd['quality_score']}")
    
    def test_session_info_with_symbol(self):
        """Test session info with symbol compatibility check"""
        response = requests.get(f"{BASE_URL}/api/signals/session-info?symbol=EUR_USD")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "time_filter" in data
        
        print(f"✅ Session info with EUR_USD: quality={data['time_filter']['quality']}")


class TestBestHours:
    """Tests for GET /api/signals/best-hours endpoint"""
    
    def test_best_hours_default(self):
        """Test best hours with default top_n"""
        response = requests.get(f"{BASE_URL}/api/signals/best-hours")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "best_hours" in data
        assert "hours_to_avoid" in data
        assert "total_hours_tracked" in data
        assert "note" in data
        
        # best_hours should be a list
        assert isinstance(data["best_hours"], list)
        # hours_to_avoid should be a list
        assert isinstance(data["hours_to_avoid"], list)
        
        print(f"✅ Best hours: {len(data['best_hours'])} best, {len(data['hours_to_avoid'])} to avoid")
    
    def test_best_hours_custom_top_n(self):
        """Test best hours with custom top_n parameter"""
        response = requests.get(f"{BASE_URL}/api/signals/best-hours?top_n=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert len(data["best_hours"]) <= 5
        
        print(f"✅ Best hours (top 5): {data['best_hours']}")


class TestHourlyStats:
    """Tests for GET /api/signals/hourly-stats endpoint"""
    
    def test_hourly_stats(self):
        """Test 24-hour breakdown of win rates"""
        response = requests.get(f"{BASE_URL}/api/signals/hourly-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "hourly_stats" in data
        
        stats = data["hourly_stats"]
        assert isinstance(stats, list)
        assert len(stats) == 24  # Should have all 24 hours
        
        # Validate structure of each hour entry
        for stat in stats:
            assert "hour_utc" in stat
            assert "session" in stat
            assert "session_quality" in stat
            assert "total_trades" in stat
            assert "wins" in stat
            assert "is_best_hour" in stat
            assert "is_bad_hour" in stat
        
        # Check hour range
        hours = [s["hour_utc"] for s in stats]
        assert min(hours) == 0
        assert max(hours) == 23
        
        print(f"✅ Hourly stats: 24 hours returned with session info")


class TestRecordPremiumResult:
    """Tests for POST /api/signals/record-premium-result endpoint"""
    
    def test_record_win_result(self):
        """Test recording a winning trade result"""
        payload = {
            "symbol": "TEST_EURUSD_OTC",
            "direction": "CALL",
            "is_win": True,
            "confidence": 75.0
        }
        response = requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "recorded" in data
        assert "updated_stats" in data
        
        recorded = data["recorded"]
        assert recorded["symbol"] == "TEST_EURUSD_OTC"
        assert recorded["direction"] == "CALL"
        assert recorded["is_win"] == True
        
        updated = data["updated_stats"]
        assert "asset_win_rate" in updated
        assert "asset_total_trades" in updated
        assert "hour_win_rate" in updated
        assert "hour_total_trades" in updated
        
        print(f"✅ Recorded WIN: asset_wr={updated['asset_win_rate']}%, total={updated['asset_total_trades']}")
    
    def test_record_loss_result(self):
        """Test recording a losing trade result"""
        payload = {
            "symbol": "TEST_EURUSD_OTC",
            "direction": "PUT",
            "is_win": False,
            "confidence": 65.0
        }
        response = requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data["recorded"]["is_win"] == False
        
        print(f"✅ Recorded LOSS: asset_wr={data['updated_stats']['asset_win_rate']}%")
    
    def test_record_with_custom_hour(self):
        """Test recording result with custom hour_utc"""
        payload = {
            "symbol": "TEST_GBPUSD_OTC",
            "direction": "CALL",
            "is_win": True,
            "hour_utc": 14  # London-NY overlap
        }
        response = requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data["recorded"]["hour_utc"] == 14
        
        print(f"✅ Recorded with custom hour 14 UTC")
    
    def test_record_multiple_and_verify_winrate(self):
        """Record multiple results and verify win rate updates correctly"""
        symbol = "TEST_WINRATE_CHECK"
        
        # Record 3 wins
        for _ in range(3):
            requests.post(
                f"{BASE_URL}/api/signals/record-premium-result",
                json={"symbol": symbol, "direction": "CALL", "is_win": True}
            )
        
        # Record 1 loss
        response = requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json={"symbol": symbol, "direction": "PUT", "is_win": False}
        )
        
        data = response.json()
        # 3 wins out of 4 = 75%
        assert data["updated_stats"]["asset_total_trades"] == 4
        assert data["updated_stats"]["asset_win_rate"] == 75.0
        
        print(f"✅ Win rate calculation verified: 3/4 = 75%")


class TestAssetPerformance:
    """Tests for GET /api/signals/asset-performance endpoint"""
    
    def test_all_assets_performance(self):
        """Test getting all tracked asset statistics"""
        response = requests.get(f"{BASE_URL}/api/signals/asset-performance")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "all_assets" in data
        assert "worst_assets" in data
        assert "total_tracked" in data
        
        print(f"✅ All assets: {data['total_tracked']} tracked, {len(data['worst_assets'])} worst")
    
    def test_specific_asset_performance(self):
        """Test getting specific asset performance with hourly breakdown"""
        # First record some data for this asset
        symbol = "TEST_EURUSD_OTC"
        requests.post(
            f"{BASE_URL}/api/signals/record-premium-result",
            json={"symbol": symbol, "direction": "CALL", "is_win": True}
        )
        
        response = requests.get(f"{BASE_URL}/api/signals/asset-performance?symbol={symbol}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "asset_stats" in data
        assert "hourly_breakdown" in data
        
        asset_stats = data["asset_stats"]
        assert asset_stats["symbol"] == symbol
        assert "win_rate" in asset_stats
        assert "total" in asset_stats
        
        print(f"✅ Asset {symbol}: win_rate={asset_stats['win_rate']}%, total={asset_stats['total']}")


class TestShouldTrade:
    """Tests for GET /api/signals/should-trade endpoint"""
    
    def test_should_trade_basic(self):
        """Test basic should-trade check"""
        response = requests.get(f"{BASE_URL}/api/signals/should-trade")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "should_trade" in data
        assert "reason" in data
        assert "time_filter" in data
        
        assert isinstance(data["should_trade"], bool)
        
        print(f"✅ Should trade: {data['should_trade']}, reason: {data['reason'][:50]}...")
    
    def test_should_trade_with_symbol(self):
        """Test should-trade with symbol parameter"""
        response = requests.get(f"{BASE_URL}/api/signals/should-trade?symbol=EUR_USD")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        print(f"✅ Should trade EUR_USD: {data['should_trade']}")
    
    def test_should_trade_with_min_quality(self):
        """Test should-trade with custom min_quality threshold"""
        response = requests.get(f"{BASE_URL}/api/signals/should-trade?symbol=EUR_USD&min_quality=50")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        # Also test with high threshold
        response_high = requests.get(f"{BASE_URL}/api/signals/should-trade?min_quality=90")
        data_high = response_high.json()
        
        print(f"✅ Should trade (min_quality=50): {data['should_trade']}, (min_quality=90): {data_high['should_trade']}")


class TestScanMarketsIntegration:
    """Tests for scan-markets endpoints with premium filter integration"""
    
    def test_scan_markets_includes_time_filter(self):
        """Test that scan-markets response includes time_filter"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets?assets=EURUSD_OTC,GBPUSD_OTC&min_confidence=60"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "time_filter" in data, "scan-markets should include time_filter"
        
        tf = data["time_filter"]
        assert "hour_utc" in tf
        assert "session" in tf
        assert "quality" in tf
        
        print(f"✅ scan-markets includes time_filter: session={tf['session']}, quality={tf['quality']}")
    
    def test_scan_markets_signals_have_premium_filters(self):
        """Test that signals from scan-markets have premium_filters applied"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets?assets=EURUSD_OTC&min_confidence=50&max_signals=5"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        
        if data.get("top_signals") and len(data["top_signals"]) > 0:
            signal = data["top_signals"][0]
            assert "premium_filters" in signal, "Signal should have premium_filters"
            
            pf = signal["premium_filters"]
            assert "session" in pf
            assert "session_quality" in pf
            assert "is_good_time" in pf
            assert "confidence_adjustment" in pf
            assert "filter_notes" in pf
            
            print(f"✅ Signal has premium_filters: session={pf['session']}, adj={pf['confidence_adjustment']}")
        else:
            print(f"⚠️ No signals found (may be off-hours), but endpoint works")
    
    def test_scan_markets_deep_includes_time_filter(self):
        """Test that scan-markets-deep response includes time_filter"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets-deep?assets=EURUSD_OTC&min_confidence=60"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "time_filter" in data, "scan-markets-deep should include time_filter"
        
        print(f"✅ scan-markets-deep includes time_filter")


class TestPremiumFilterConfidenceAdjustment:
    """Tests for premium filter confidence adjustment logic"""
    
    def test_low_quality_session_reduces_confidence(self):
        """Verify that signals during low-quality sessions have reduced confidence"""
        # Get current session info
        session_response = requests.get(f"{BASE_URL}/api/signals/session-info")
        session_data = session_response.json()
        session_quality = session_data["session_details"]["quality_score"]
        
        # Get a signal from scan-markets
        scan_response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets?assets=EURUSD_OTC&min_confidence=40&max_signals=1"
        )
        scan_data = scan_response.json()
        
        if scan_data.get("top_signals") and len(scan_data["top_signals"]) > 0:
            signal = scan_data["top_signals"][0]
            
            if "premium_filters" in signal and "original_confidence" in signal:
                original = signal.get("original_confidence", signal["confidence"])
                adjusted = signal["confidence"]
                adjustment = signal["premium_filters"]["confidence_adjustment"]
                
                # If session quality is low (<55), adjustment should be negative
                if session_quality < 55:
                    assert adjustment < 0, f"Low quality session ({session_quality}) should reduce confidence"
                    print(f"✅ Low quality session ({session_quality}) reduced confidence by {adjustment}")
                else:
                    print(f"✅ Session quality is {session_quality}, adjustment: {adjustment}")
            else:
                print(f"⚠️ Signal doesn't have original_confidence field")
        else:
            print(f"⚠️ No signals found to test confidence adjustment")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
