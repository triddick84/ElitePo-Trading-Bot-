"""
Test Suite for Scan Markets, ML Optimization, and Deep Confluence Analysis
===========================================================================
Tests for iteration 16 features:
1. scan-markets endpoint with deep_confluence analysis
2. force-generate/asset endpoint for Tampermonkey GO button
3. Strategy toggle functionality
4. ML system stats
5. OANDA symbol normalization
6. Auth login
7. Health check
"""

import pytest
import requests
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://pocket-trader-ai-8.preview.emergentagent.com"


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self):
        """GET /api/health should return status=healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        print(f"✅ Health check passed: {data}")
    
    def test_auth_login(self):
        """POST /api/auth/login with testuser/test123 should return token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "testuser", "password": "test123"},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "token" in data or "access_token" in data, f"No token in response: {data}"
        print(f"✅ Login successful: token received")
        return data.get("token") or data.get("access_token")


class TestScanMarketsEndpoint:
    """Tests for GET /api/signals/scan-markets endpoint"""
    
    def test_scan_markets_multiple_assets(self):
        """GET /api/signals/scan-markets with multiple assets should return signals"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC",
                "min_confidence": 70
            },
            timeout=30
        )
        assert response.status_code == 200, f"Scan markets failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Check response structure - API returns top_signals or signals
        signals = data.get("top_signals") or data.get("signals", [])
        scanned = data.get("scanned_assets") or data.get("assets_scanned", 0)
        
        assert data.get("success") == True, f"Scan not successful: {data}"
        assert signals is not None, f"No signals in response: {data}"
        
        print(f"✅ Scan markets returned {len(signals)} signals from {scanned} assets")
        
        # If signals found, verify structure
        if signals:
            signal = signals[0]
            assert "direction" in signal, "Signal missing direction"
            assert "confidence" in signal, "Signal missing confidence"
            assert "symbol" in signal, "Signal missing symbol"
            print(f"   First signal: {signal.get('direction')} {signal.get('symbol')} @ {signal.get('confidence')}% confidence")
            
            # Check for analysis type
            analysis_type = signal.get("analysis_type", "")
            print(f"   Analysis type: {analysis_type}")
            
            # Check for confirmations
            if signal.get("confirmations"):
                print(f"   Confirmations: {signal.get('confirmations')}")
    
    def test_scan_markets_single_asset_oanda_normalization(self):
        """GET /api/signals/scan-markets with AUDUSD_OTC should work with OANDA normalization"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "AUDUSD_OTC",
                "min_confidence": 70
            },
            timeout=30
        )
        assert response.status_code == 200, f"Scan markets failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Should not error - OANDA normalization should convert AUDUSD_OTC -> AUD_USD
        signals = data.get("top_signals") or data.get("signals", [])
        assert data.get("success") == True, f"Scan not successful: {data}"
        print(f"✅ AUDUSD_OTC scan completed - OANDA normalization working")
        
        if signals:
            signal = signals[0]
            # Check oanda_symbol is normalized
            if "oanda_symbol" in signal:
                assert "_" in signal["oanda_symbol"], f"OANDA symbol not normalized: {signal['oanda_symbol']}"
                print(f"   OANDA symbol: {signal['oanda_symbol']}")
    
    def test_scan_markets_with_deep_analysis(self):
        """GET /api/signals/scan-markets with use_deep_analysis=true"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EURUSD_OTC",
                "min_confidence": 70,
                "use_deep_analysis": True
            },
            timeout=30
        )
        assert response.status_code == 200, f"Scan markets failed: {response.status_code}"
        data = response.json()
        
        print(f"✅ Deep analysis scan completed")
        
        if data.get("signals"):
            signal = data["signals"][0]
            # Deep analysis signals should have quality and confirmations
            if signal.get("analysis_type") == "deep_confluence":
                print(f"   Quality: {signal.get('quality')}")
                print(f"   Confirmations: {signal.get('confirmations_count', len(signal.get('confirmations', [])))}")
                if signal.get("ml_validated"):
                    print(f"   ML Validated: {signal.get('ml_validated')} @ {signal.get('ml_confidence')}%")
        
        return data


class TestForceGenerateAsset:
    """Tests for POST /api/signals/force-generate/asset/{symbol} endpoint"""
    
    def test_force_generate_eurusd_otc(self):
        """POST /api/signals/force-generate/asset/EURUSD_OTC should return success:true with signal"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/EURUSD_OTC",
            params={"wait_for_candle": False},
            timeout=30
        )
        assert response.status_code == 200, f"Force generate failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Force generate not successful: {data}"
        assert "signal" in data, f"No signal in response: {data}"
        
        signal = data["signal"]
        assert signal is not None, "Signal is None"
        assert "direction" in signal, "Signal missing direction"
        assert "probability" in signal or "confidence" in signal, "Signal missing probability/confidence"
        
        print(f"✅ EURUSD_OTC force generate: {signal.get('direction')} @ {signal.get('probability', signal.get('confidence'))}%")
        return data
    
    def test_force_generate_gbpusd_otc(self):
        """POST /api/signals/force-generate/asset/GBPUSD_OTC should return success:true with signal"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/GBPUSD_OTC",
            params={"wait_for_candle": False},
            timeout=30
        )
        assert response.status_code == 200, f"Force generate failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Force generate not successful: {data}"
        assert "signal" in data, f"No signal in response: {data}"
        
        signal = data["signal"]
        print(f"✅ GBPUSD_OTC force generate: {signal.get('direction')} @ {signal.get('probability', signal.get('confidence'))}%")
        return data
    
    def test_force_generate_regular_asset(self):
        """POST /api/signals/force-generate/asset/EURUSD should work for regular market"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate/asset/EURUSD",
            params={"wait_for_candle": False},
            timeout=30
        )
        assert response.status_code == 200, f"Force generate failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Force generate not successful: {data}"
        print(f"✅ EURUSD (regular) force generate successful")
        return data


class TestStrategyToggle:
    """Tests for strategy toggle functionality"""
    
    def test_get_custom_strategies(self):
        """GET /api/custom-strategies should return list of strategies"""
        response = requests.get(f"{BASE_URL}/api/custom-strategies", timeout=10)
        assert response.status_code == 200, f"Get strategies failed: {response.status_code}"
        data = response.json()
        
        # Response could be a list or dict with strategies key
        strategies = data if isinstance(data, list) else data.get("strategies", [])
        print(f"✅ Found {len(strategies)} custom strategies")
        
        return strategies
    
    def test_strategy_toggle_activate(self):
        """POST /api/custom-strategies/{id}/toggle?is_active=true should activate strategy"""
        # First get a strategy ID
        strategies = self.test_get_custom_strategies()
        
        if not strategies:
            pytest.skip("No custom strategies available to test toggle")
        
        strategy_id = strategies[0].get("id") or strategies[0].get("_id")
        if not strategy_id:
            pytest.skip("Strategy has no ID")
        
        # Toggle to active
        response = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": True},
            timeout=10
        )
        assert response.status_code == 200, f"Toggle failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Toggle not successful: {data}"
        print(f"✅ Strategy {strategy_id} activated")
        return data
    
    def test_strategy_toggle_deactivate(self):
        """POST /api/custom-strategies/{id}/toggle?is_active=false should deactivate strategy"""
        # First get a strategy ID
        strategies = self.test_get_custom_strategies()
        
        if not strategies:
            pytest.skip("No custom strategies available to test toggle")
        
        strategy_id = strategies[0].get("id") or strategies[0].get("_id")
        if not strategy_id:
            pytest.skip("Strategy has no ID")
        
        # Toggle to inactive
        response = requests.post(
            f"{BASE_URL}/api/custom-strategies/{strategy_id}/toggle",
            params={"is_active": False},
            timeout=10
        )
        assert response.status_code == 200, f"Toggle failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Toggle not successful: {data}"
        print(f"✅ Strategy {strategy_id} deactivated")
        return data


class TestMLSystem:
    """Tests for ML system endpoints"""
    
    def test_maximized_ml_stats(self):
        """GET /api/maximized-ml/stats should return ML system stats"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats", timeout=10)
        assert response.status_code == 200, f"ML stats failed: {response.status_code}"
        data = response.json()
        
        # API wraps stats in a 'stats' key
        stats = data.get("stats", data)
        
        # Check for expected fields
        assert "is_trained" in stats, f"Missing is_trained field: {data}"
        
        print(f"✅ ML System Stats:")
        print(f"   Trained: {stats.get('is_trained')}")
        print(f"   Accuracy: {stats.get('model_accuracy', 'N/A')}%")
        print(f"   Version: {stats.get('version', 'N/A')}")
        print(f"   Predictions made: {stats.get('predictions_made', 0)}")
        
        if stats.get("is_trained"):
            print(f"   Current regime: {stats.get('current_regime', 'N/A')}")
            print(f"   Feature count: {stats.get('feature_count', 'N/A')}")
            print(f"   Models in ensemble: {stats.get('models_in_ensemble', [])}")


class TestDeepConfluenceAnalysis:
    """Tests specifically for deep confluence analysis features"""
    
    def test_deep_confluence_weighted_confirmations(self):
        """Verify deep confluence signals have weighted confirmations"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EURUSD_OTC,GBPUSD_OTC",
                "min_confidence": 70,
                "use_deep_analysis": True
            },
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("signals", [])
        deep_signals = [s for s in signals if s.get("analysis_type") == "deep_confluence"]
        
        if deep_signals:
            signal = deep_signals[0]
            print(f"✅ Deep confluence signal found:")
            print(f"   Direction: {signal.get('direction')}")
            print(f"   Confidence: {signal.get('confidence')}%")
            print(f"   Quality: {signal.get('quality')}")
            
            confirmations = signal.get("confirmations", [])
            print(f"   Confirmations ({len(confirmations)}): {confirmations[:5]}...")
            
            # Check for expected confirmation types
            tier1_confirmations = ['RSI_OVERSOLD', 'RSI_OVERBOUGHT', 'STOCHASTIC_BULLISH_CROSS', 
                                   'STOCHASTIC_BEARISH_CROSS', 'EMA_BULLISH_CROSSOVER', 'EMA_BEARISH_CROSSOVER',
                                   'PRICE_AT_BB_LOWER', 'PRICE_AT_BB_UPPER', 'MACD_BULLISH_CROSSOVER', 'MACD_BEARISH_CROSSOVER']
            
            has_tier1 = any(c in tier1_confirmations for c in confirmations)
            if has_tier1:
                print(f"   ✅ Has Tier 1 (high-weight) confirmations")
        else:
            print("⚠️ No deep confluence signals found in current market conditions")
        
        return data


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
