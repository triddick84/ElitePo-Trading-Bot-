"""
Test Suite for Golden One Moment 30-Second Strategy
====================================================
Tests the new Golden One Moment strategy endpoints and verifies
the strategy is properly registered in the strategy selection service.

Features tested:
- POST /api/strategy/golden-one-moment/signal - Signal generation
- GET /api/strategy/golden-one-moment/stats - Strategy statistics
- GET /api/strategies/available/30s - Strategy registration
- GET /api/strategies/available/15s - Momentum Buster registration (regression)
- POST /api/strategy/momentum-buster-15s/signal - Regression test
- GET /api/strategy/momentum-buster-15s/stats - Regression test
- POST /api/signals/force-generate - Regression test
- GET /api/strategies/available - All timeframes
"""

import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestGoldenOneMomentStrategy:
    """Tests for the Golden One Moment 30-second strategy"""
    
    def test_golden_one_moment_signal_eur_usd(self):
        """Test Golden One Moment signal generation with EUR_USD"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/golden-one-moment/signal",
            params={"symbol": "EUR_USD"},
            timeout=30
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        
        # Signal may be null if market conditions don't meet criteria - this is expected
        if data.get("signal"):
            signal = data["signal"]
            assert "direction" in signal, "Signal should have direction"
            assert signal["direction"] in ["CALL", "PUT"], f"Invalid direction: {signal['direction']}"
            assert "confidence" in signal, "Signal should have confidence"
            assert 0 <= signal["confidence"] <= 100, f"Confidence out of range: {signal['confidence']}"
            assert "strategy" in signal, "Signal should have strategy name"
            assert signal["strategy"] == "Golden One Moment", f"Wrong strategy: {signal['strategy']}"
            assert "timeframe" in signal, "Signal should have timeframe"
            assert signal["timeframe"] == "30s", f"Wrong timeframe: {signal['timeframe']}"
            assert "expiration" in signal, "Signal should have expiration"
            assert signal["expiration"] == 30, f"Wrong expiration: {signal['expiration']}"
            assert "indicators" in signal, "Signal should have indicators"
            assert "rsi_current" in signal["indicators"], "Should have RSI current"
            assert "stoch_k" in signal["indicators"], "Should have Stochastic K"
            print(f"✅ Golden One Moment signal generated: {signal['direction']} @ {signal['confidence']}%")
        else:
            print("✅ No signal generated (market conditions not met) - this is expected behavior")
        
        # Verify strategy name in response
        assert data.get("strategy") == "Golden One Moment", f"Wrong strategy in response: {data.get('strategy')}"
    
    def test_golden_one_moment_signal_eurusd_otc(self):
        """Test Golden One Moment signal generation with EURUSD_OTC"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/golden-one-moment/signal",
            params={"symbol": "EURUSD_OTC"},
            timeout=30
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        # Note: success may be False if data unavailable for OTC - this is acceptable
        print(f"✅ EURUSD_OTC response: success={data.get('success')}, signal={'present' if data.get('signal') else 'null'}")
    
    def test_golden_one_moment_stats(self):
        """Test Golden One Moment strategy statistics endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/golden-one-moment/stats",
            timeout=15
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        assert "stats" in data, "Response should contain 'stats' field"
        
        stats = data["stats"]
        assert stats["name"] == "Golden One Moment", f"Wrong strategy name: {stats['name']}"
        assert stats["timeframe"] == "30s", f"Wrong timeframe: {stats['timeframe']}"
        assert stats["expiration_seconds"] == 30, f"Wrong expiration: {stats['expiration_seconds']}"
        assert "indicators" in stats, "Stats should have indicators info"
        assert stats["indicators"]["rsi_period"] == 2, f"Wrong RSI period: {stats['indicators']['rsi_period']}"
        assert "levels" in stats, "Stats should have levels"
        assert stats["levels"]["overbought"] == 80, f"Wrong overbought level: {stats['levels']['overbought']}"
        assert stats["levels"]["oversold"] == 20, f"Wrong oversold level: {stats['levels']['oversold']}"
        
        print(f"✅ Golden One Moment stats: {stats['name']}, timeframe={stats['timeframe']}")


class TestStrategyRegistration:
    """Tests for strategy registration in strategy selection service"""
    
    def test_golden_one_moment_in_30s_strategies(self):
        """Verify Golden One Moment is registered in 30s strategies"""
        response = requests.get(
            f"{BASE_URL}/api/strategies/available/30s",
            timeout=15
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        assert "strategies" in data, "Response should contain 'strategies' field"
        assert "timeframe" in data, "Response should contain 'timeframe' field"
        assert data["timeframe"] == "30s", f"Wrong timeframe: {data['timeframe']}"
        
        strategies = data["strategies"]
        assert isinstance(strategies, list), "Strategies should be a list"
        assert len(strategies) > 0, "Should have at least one strategy"
        
        # Find golden_one_moment in the list
        strategy_ids = [s["id"] for s in strategies]
        assert "golden_one_moment" in strategy_ids, f"golden_one_moment not found in 30s strategies: {strategy_ids}"
        
        # Verify strategy details
        golden_strategy = next(s for s in strategies if s["id"] == "golden_one_moment")
        assert "Golden One Moment" in golden_strategy["name"], f"Wrong name: {golden_strategy['name']}"
        assert "RSI(2)" in golden_strategy["description"], f"Description should mention RSI(2): {golden_strategy['description']}"
        assert "Stochastic" in golden_strategy["description"], f"Description should mention Stochastic: {golden_strategy['description']}"
        
        print(f"✅ Golden One Moment registered in 30s strategies: {golden_strategy['name']}")
    
    def test_momentum_buster_in_15s_strategies(self):
        """Verify Momentum Buster is registered in 15s strategies (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/strategies/available/15s",
            timeout=15
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        assert "strategies" in data, "Response should contain 'strategies' field"
        
        strategies = data["strategies"]
        strategy_ids = [s["id"] for s in strategies]
        assert "momentum_buster_15s" in strategy_ids, f"momentum_buster_15s not found in 15s strategies: {strategy_ids}"
        
        print(f"✅ Momentum Buster registered in 15s strategies")
    
    def test_all_timeframes_available(self):
        """Verify all timeframes return strategies correctly"""
        response = requests.get(
            f"{BASE_URL}/api/strategies/available",
            timeout=15
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        assert "strategies" in data, "Response should contain 'strategies' field"
        
        strategies = data["strategies"]
        expected_timeframes = ["5s", "15s", "30s", "1m", "2m", "3m", "5m"]
        
        for tf in expected_timeframes:
            assert tf in strategies, f"Timeframe {tf} not found in strategies"
            assert len(strategies[tf]) > 0, f"No strategies for timeframe {tf}"
        
        # Verify golden_one_moment in 30s
        strategy_30s_ids = [s["id"] for s in strategies["30s"]]
        assert "golden_one_moment" in strategy_30s_ids, "golden_one_moment should be in 30s strategies"
        
        # Verify momentum_buster_15s in 15s
        strategy_15s_ids = [s["id"] for s in strategies["15s"]]
        assert "momentum_buster_15s" in strategy_15s_ids, "momentum_buster_15s should be in 15s strategies"
        
        print(f"✅ All timeframes available with strategies: {list(strategies.keys())}")


class TestRegressionMomentumBuster:
    """Regression tests for Momentum Buster 15s strategy"""
    
    def test_momentum_buster_signal(self):
        """Test Momentum Buster signal generation still works"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"},
            timeout=30
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        # Signal may be null if conditions not met
        print(f"✅ Momentum Buster signal endpoint working: success={data.get('success')}")
    
    def test_momentum_buster_stats(self):
        """Test Momentum Buster stats endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/stats",
            timeout=15
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Expected success=True, got {data}"
        assert "stats" in data, "Response should contain 'stats' field"
        
        stats = data["stats"]
        assert stats["name"] == "Momentum Buster 15s", f"Wrong strategy name: {stats['name']}"
        assert stats["timeframe"] == "15s", f"Wrong timeframe: {stats['timeframe']}"
        
        print(f"✅ Momentum Buster stats working: {stats['name']}")


class TestRegressionForceGenerate:
    """Regression tests for force signal generation"""
    
    def test_force_generate_endpoint(self):
        """Test force generate endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/signals/force-generate",
            timeout=60
        )
        
        # Status code assertion - may return 200 or 400 depending on config
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
        
        data = response.json()
        # If 400, it's likely because no assets are selected - this is expected
        if response.status_code == 400:
            print(f"✅ Force generate returned 400 (no assets selected) - expected behavior")
        else:
            print(f"✅ Force generate endpoint working: {data.get('message', 'success')}")


class TestHealthAndBasicEndpoints:
    """Basic health and connectivity tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/health",
            timeout=10
        )
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy", f"API not healthy: {data}"
        print(f"✅ API health check passed")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
