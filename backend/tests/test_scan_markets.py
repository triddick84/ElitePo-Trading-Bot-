"""
Test suite for scan-markets endpoint - Multi-asset scanning feature
Tests the SCAN feature that scans ALL favorites when AUTO OFF + SCAN ON

Key features tested:
- Multi-asset scanning with strategy fallback chain (deep_confluence → golden_one_moment → momentum_buster_15s)
- Single asset scanning
- Signal response includes 'symbol' field for asset switching
- Signal response includes 'analysis_type' showing strategy used
- Regression tests for Golden One Moment and Momentum Buster strategies
"""

import pytest
import requests
import os

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback for local testing
    BASE_URL = "https://momentum-trade-test.preview.emergentagent.com"


class TestScanMarketsEndpoint:
    """Tests for GET /api/signals/scan-markets endpoint"""
    
    def test_health_check(self):
        """Verify API is healthy before running other tests"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"API not healthy: {data}"
        print(f"✅ Health check passed: {data}")
    
    def test_scan_markets_multiple_assets(self):
        """
        Test scanning multiple assets (EURUSD_OTC, GBPUSD_OTC, USDJPY_OTC, AUDUSD_OTC)
        This is the main use case for SCAN feature when AUTO OFF + SCAN ON
        """
        assets = "EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC"
        min_confidence = 60
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"Scan markets failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data, "Response missing 'success' field"
        assert data["success"] == True, f"Scan not successful: {data}"
        assert "scanned_assets" in data, "Response missing 'scanned_assets' field"
        assert "signals_found" in data, "Response missing 'signals_found' field"
        assert "top_signals" in data, "Response missing 'top_signals' field"
        
        # Verify correct number of assets scanned
        assert data["scanned_assets"] == 4, f"Expected 4 assets scanned, got {data['scanned_assets']}"
        
        print(f"✅ Multi-asset scan: scanned {data['scanned_assets']} assets, found {data['signals_found']} signals")
        print(f"   Analysis type: {data.get('analysis_type', 'N/A')}")
        
        # If signals found, verify structure
        if data["top_signals"]:
            signal = data["top_signals"][0]
            assert "symbol" in signal, "Signal missing 'symbol' field for asset switching"
            assert "confidence" in signal, "Signal missing 'confidence' field"
            print(f"   Top signal: {signal.get('symbol')} - {signal.get('direction')} @ {signal.get('confidence')}%")
    
    def test_scan_markets_single_asset(self):
        """Test scanning a single asset"""
        assets = "EURUSD_OTC"
        min_confidence = 60
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"Single asset scan failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Scan not successful: {data}"
        assert data["scanned_assets"] == 1, f"Expected 1 asset scanned, got {data['scanned_assets']}"
        
        print(f"✅ Single asset scan: scanned {data['scanned_assets']} asset, found {data['signals_found']} signals")
    
    def test_scan_markets_symbol_field_present(self):
        """Verify signals include 'symbol' field for asset switching"""
        assets = "EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC"
        min_confidence = 60
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"Scan failed: {response.text}"
        data = response.json()
        
        # Check all signals have symbol field
        for signal in data.get("top_signals", []):
            assert "symbol" in signal, f"Signal missing 'symbol' field: {signal}"
            assert signal["symbol"], f"Signal 'symbol' field is empty: {signal}"
            # Symbol should be one of the scanned assets
            assert any(asset in signal["symbol"] for asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]), \
                f"Signal symbol '{signal['symbol']}' not in scanned assets"
        
        print(f"✅ All {len(data.get('top_signals', []))} signals have valid 'symbol' field")
    
    def test_scan_markets_analysis_type_present(self):
        """Verify signals include 'analysis_type' showing strategy used"""
        assets = "EURUSD_OTC,GBPUSD_OTC"
        min_confidence = 60
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"Scan failed: {response.text}"
        data = response.json()
        
        # Valid analysis types from the fallback chain
        valid_analysis_types = ["deep_confluence", "golden_one_moment", "momentum_buster_15s", "high_accuracy"]
        
        # Check all signals have analysis_type field
        for signal in data.get("top_signals", []):
            assert "analysis_type" in signal, f"Signal missing 'analysis_type' field: {signal}"
            assert signal["analysis_type"] in valid_analysis_types, \
                f"Invalid analysis_type '{signal['analysis_type']}', expected one of {valid_analysis_types}"
        
        print(f"✅ All {len(data.get('top_signals', []))} signals have valid 'analysis_type' field")
        
        # Show breakdown of analysis types used
        analysis_types_used = {}
        for signal in data.get("top_signals", []):
            at = signal.get("analysis_type", "unknown")
            analysis_types_used[at] = analysis_types_used.get(at, 0) + 1
        print(f"   Analysis types breakdown: {analysis_types_used}")
    
    def test_scan_markets_with_preferred_expiry(self):
        """Test scanning with preferred expiry parameter"""
        assets = "EURUSD_OTC"
        min_confidence = 60
        preferred_expiry = 30  # 30 seconds
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": assets, 
                "min_confidence": min_confidence,
                "preferred_expiry": preferred_expiry
            },
            timeout=60
        )
        
        assert response.status_code == 200, f"Scan with expiry failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Scan not successful: {data}"
        assert data.get("preferred_expiry") == preferred_expiry, \
            f"Expected preferred_expiry={preferred_expiry}, got {data.get('preferred_expiry')}"
        
        print(f"✅ Scan with preferred_expiry={preferred_expiry}s: found {data['signals_found']} signals")


class TestGoldenOneMomentRegression:
    """Regression tests for Golden One Moment strategy"""
    
    def test_golden_one_moment_signal_endpoint(self):
        """POST /api/strategy/golden-one-moment/signal?symbol=EUR_USD - regression test"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/golden-one-moment/signal",
            params={"symbol": "EUR_USD"},
            timeout=60
        )
        
        assert response.status_code == 200, f"Golden One Moment signal failed: {response.text}"
        data = response.json()
        
        assert "success" in data, "Response missing 'success' field"
        # Signal may be null if market conditions don't meet criteria
        if data.get("signal"):
            signal = data["signal"]
            assert "direction" in signal, "Signal missing 'direction'"
            assert "confidence" in signal, "Signal missing 'confidence'"
            print(f"✅ Golden One Moment signal: {signal.get('direction')} @ {signal.get('confidence')}%")
        else:
            print(f"✅ Golden One Moment endpoint working (no signal due to market conditions)")
    
    def test_golden_one_moment_stats_endpoint(self):
        """GET /api/strategy/golden-one-moment/stats - regression test"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/golden-one-moment/stats",
            timeout=30
        )
        
        assert response.status_code == 200, f"Golden One Moment stats failed: {response.text}"
        data = response.json()
        
        # Stats are nested under 'stats' key
        stats = data.get("stats", data)  # Fallback to data if no nested stats
        assert stats.get("name") == "Golden One Moment", f"Expected name='Golden One Moment', got {stats.get('name')}"
        assert stats.get("timeframe") == "30s", f"Expected timeframe='30s', got {stats.get('timeframe')}"
        
        print(f"✅ Golden One Moment stats: name={stats.get('name')}, timeframe={stats.get('timeframe')}")


class TestMomentumBusterRegression:
    """Regression tests for Momentum Buster 15s strategy"""
    
    def test_momentum_buster_signal_endpoint(self):
        """POST /api/strategy/momentum-buster-15s/signal?symbol=EUR_USD - regression test"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"},
            timeout=60
        )
        
        assert response.status_code == 200, f"Momentum Buster signal failed: {response.text}"
        data = response.json()
        
        assert "success" in data, "Response missing 'success' field"
        # Signal may be null if market conditions don't meet criteria
        if data.get("signal"):
            signal = data["signal"]
            assert "direction" in signal, "Signal missing 'direction'"
            assert "confidence" in signal, "Signal missing 'confidence'"
            print(f"✅ Momentum Buster signal: {signal.get('direction')} @ {signal.get('confidence')}%")
        else:
            print(f"✅ Momentum Buster endpoint working (no signal due to market conditions)")


class TestEdgeCases:
    """Edge case tests for scan-markets endpoint"""
    
    def test_scan_markets_high_confidence_threshold(self):
        """Test with high confidence threshold (90%)"""
        assets = "EURUSD_OTC,GBPUSD_OTC"
        min_confidence = 90
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"High confidence scan failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True, f"Scan not successful: {data}"
        
        # All returned signals should meet the threshold
        for signal in data.get("top_signals", []):
            assert signal.get("confidence", 0) >= min_confidence, \
                f"Signal confidence {signal.get('confidence')} below threshold {min_confidence}"
        
        print(f"✅ High confidence scan (>={min_confidence}%): found {data['signals_found']} signals")
    
    def test_scan_markets_empty_assets(self):
        """Test with empty assets parameter"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "", "min_confidence": 60},
            timeout=30
        )
        
        # Should return 200 with 0 assets scanned
        assert response.status_code == 200, f"Empty assets scan failed: {response.text}"
        data = response.json()
        
        assert data["scanned_assets"] == 0, f"Expected 0 assets scanned, got {data['scanned_assets']}"
        print(f"✅ Empty assets handled correctly: scanned {data['scanned_assets']} assets")
    
    def test_scan_markets_invalid_asset(self):
        """Test with invalid asset symbol - should gracefully skip"""
        assets = "INVALID_ASSET,EURUSD_OTC"
        min_confidence = 60
        
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": assets, "min_confidence": min_confidence},
            timeout=60
        )
        
        assert response.status_code == 200, f"Invalid asset scan failed: {response.text}"
        data = response.json()
        
        # Should still succeed, just skip the invalid asset
        assert data["success"] == True, f"Scan not successful: {data}"
        assert data["scanned_assets"] == 2, f"Expected 2 assets scanned (including invalid), got {data['scanned_assets']}"
        
        print(f"✅ Invalid asset handled gracefully: scanned {data['scanned_assets']} assets")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
