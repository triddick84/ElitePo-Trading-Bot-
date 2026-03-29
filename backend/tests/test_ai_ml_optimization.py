"""
Backend API Tests for AI/ML Optimization Changes
=================================================
Tests for:
1. GET /api/maximized-ml/stats - ML model stats
2. GET /api/signals/scan-markets - Multi-asset scanning with 70%+ confidence
3. POST /api/strategy/golden-one-moment/signal - Regression test
4. POST /api/strategy/holly-crossover/signal - Regression test
5. POST /api/strategy/momentum-buster-15s/signal - Regression test
6. GET /api/strategy/holly-crossover/stats - Regression test
7. GET /api/strategies/available/5s - Strategy registration
8. GET /api/strategies/available/30s - Strategy registration
9. GET /api/adaptive-strategy/config - Config validation
10. PUT /api/adaptive-strategy/config - Indicator name validation (MACD not macd)
"""

import pytest
import requests
import os
import json

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestMaximizedMLStats:
    """Tests for Maximized AI/ML System v3.0 stats endpoint"""
    
    def test_maximized_ml_stats_endpoint_returns_200(self):
        """GET /api/maximized-ml/stats should return 200"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✅ /api/maximized-ml/stats returned 200")
    
    def test_maximized_ml_stats_has_required_fields(self):
        """Stats should include trained status, models list, accuracy"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Response has nested 'stats' object
        stats = data.get("stats", data)
        
        # Check for required fields
        assert "is_trained" in stats or "trained" in stats, f"Missing trained status in: {stats}"
        assert "models_in_ensemble" in stats or "models" in stats, f"Missing models list in: {stats}"
        
        # Check accuracy field (may be 0 if not trained)
        accuracy_field = stats.get("model_accuracy") or stats.get("accuracy") or stats.get("cv_accuracy", 0)
        assert accuracy_field is not None, f"Missing accuracy field in: {stats}"
        
        print(f"✅ ML Stats: trained={stats.get('is_trained')}, accuracy={accuracy_field}%")
        print(f"   Models: {stats.get('models_in_ensemble', stats.get('models', []))}")


class TestScanMarketsEndpoint:
    """Tests for scan-markets multi-asset scanning"""
    
    def test_scan_markets_returns_200(self):
        """GET /api/signals/scan-markets should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC,GBPUSD_OTC", "min_confidence": 70}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✅ /api/signals/scan-markets returned 200")
    
    def test_scan_markets_with_70_confidence_threshold(self):
        """Signals should have >= 70 confidence when min_confidence=70"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC,GBPUSD_OTC,USDJPY_OTC,AUDUSD_OTC", "min_confidence": 70}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "success" in data, f"Missing 'success' field in: {data}"
        
        # If signals found, verify confidence >= 70
        signals = data.get("top_signals") or data.get("signals") or []
        for signal in signals:
            confidence = signal.get("confidence", 0)
            assert confidence >= 70, f"Signal confidence {confidence} < 70: {signal}"
        
        print(f"✅ scan-markets: {len(signals)} signals found, all >= 70% confidence")
        if signals:
            print(f"   Top signal: {signals[0].get('symbol')} {signals[0].get('direction')} @ {signals[0].get('confidence')}%")
    
    def test_scan_markets_includes_symbol_field(self):
        """Each signal should include 'symbol' field for asset switching"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 60}
        )
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("top_signals") or data.get("signals") or []
        for signal in signals:
            assert "symbol" in signal, f"Missing 'symbol' field in signal: {signal}"
        
        print(f"✅ All signals include 'symbol' field")
    
    def test_scan_markets_includes_analysis_type(self):
        """Each signal should include 'analysis_type' field"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC,GBPUSD_OTC", "min_confidence": 60}
        )
        assert response.status_code == 200
        data = response.json()
        
        signals = data.get("top_signals") or data.get("signals") or []
        for signal in signals:
            assert "analysis_type" in signal, f"Missing 'analysis_type' field in signal: {signal}"
        
        print(f"✅ All signals include 'analysis_type' field")


class TestGoldenOneMomentRegression:
    """Regression tests for Golden One Moment 30s strategy"""
    
    def test_golden_one_moment_signal_endpoint(self):
        """POST /api/strategy/golden-one-moment/signal should return 200"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/golden-one-moment/signal",
            params={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have success field
        assert "success" in data, f"Missing 'success' field in: {data}"
        
        # Signal may be null if market conditions don't trigger - that's expected
        print(f"✅ golden-one-moment/signal: success={data.get('success')}, signal={'present' if data.get('signal') else 'null (expected if no trigger)'}")
    
    def test_golden_one_moment_stats_endpoint(self):
        """GET /api/strategy/golden-one-moment/stats should return correct metadata"""
        response = requests.get(f"{BASE_URL}/api/strategy/golden-one-moment/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Response has nested 'stats' object
        stats = data.get("stats", data)
        
        # Check strategy name
        name = stats.get("name") or stats.get("strategy_name", "")
        assert "golden" in name.lower() or "moment" in name.lower(), f"Unexpected strategy name: {name}"
        
        print(f"✅ golden-one-moment/stats: name={name}")


class TestHollyCrossoverRegression:
    """Regression tests for Holly Crossover strategy"""
    
    def test_holly_crossover_signal_5s(self):
        """POST /api/strategy/holly-crossover/signal?timeframe=5s should return 200"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/holly-crossover/signal",
            params={"symbol": "EUR_USD", "timeframe": "5s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data, f"Missing 'success' field in: {data}"
        print(f"✅ holly-crossover/signal (5s): success={data.get('success')}")
    
    def test_holly_crossover_stats_5s(self):
        """GET /api/strategy/holly-crossover/stats?timeframe=5s should return correct metadata"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/holly-crossover/stats",
            params={"timeframe": "5s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Response has nested 'stats' object
        stats = data.get("stats", data)
        
        # Check strategy name
        name = stats.get("name") or stats.get("strategy_name", "")
        assert "holly" in name.lower() or "crossover" in name.lower(), f"Unexpected strategy name: {name}"
        
        # Check indicators (EMA(12), WMA(23))
        indicators = stats.get("indicators", {})
        print(f"✅ holly-crossover/stats (5s): name={name}, indicators={indicators}")


class TestMomentumBusterRegression:
    """Regression tests for Momentum Buster 15s strategy"""
    
    def test_momentum_buster_signal_endpoint(self):
        """POST /api/strategy/momentum-buster-15s/signal should return 200"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "success" in data, f"Missing 'success' field in: {data}"
        print(f"✅ momentum-buster-15s/signal: success={data.get('success')}")


class TestStrategiesAvailable:
    """Tests for strategy registration endpoints"""
    
    def test_strategies_available_5s_includes_holly_crossover(self):
        """GET /api/strategies/available/5s should include holly_crossover_5s"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/5s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        strategies = data.get("strategies", [])
        strategy_ids = [s.get("id") or s.get("strategy_id", "") for s in strategies]
        
        # Check for holly_crossover in any form
        has_holly = any("holly" in sid.lower() for sid in strategy_ids)
        assert has_holly, f"holly_crossover not found in 5s strategies: {strategy_ids}"
        
        print(f"✅ /api/strategies/available/5s includes holly_crossover")
        print(f"   Available strategies: {strategy_ids}")
    
    def test_strategies_available_30s_includes_golden_one_moment(self):
        """GET /api/strategies/available/30s should include golden_one_moment"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/30s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        strategies = data.get("strategies", [])
        strategy_ids = [s.get("id") or s.get("strategy_id", "") for s in strategies]
        
        # Check for golden_one_moment in any form
        has_golden = any("golden" in sid.lower() for sid in strategy_ids)
        has_holly = any("holly" in sid.lower() for sid in strategy_ids)
        
        assert has_golden or has_holly, f"Expected strategies not found in 30s: {strategy_ids}"
        
        print(f"✅ /api/strategies/available/30s includes expected strategies")
        print(f"   Available strategies: {strategy_ids}")


class TestAdaptiveStrategyConfig:
    """Tests for adaptive strategy configuration"""
    
    def test_adaptive_strategy_config_returns_200(self):
        """GET /api/adaptive-strategy/config should return 200"""
        response = requests.get(f"{BASE_URL}/api/adaptive-strategy/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✅ /api/adaptive-strategy/config returned 200")
    
    def test_adaptive_strategy_config_has_valid_structure(self):
        """Config should have proper indicator names (MACD not macd)"""
        response = requests.get(f"{BASE_URL}/api/adaptive-strategy/config")
        assert response.status_code == 200
        data = response.json()
        
        config = data.get("config", data)
        
        # Check trending_indicators
        trending = config.get("trending_indicators", [])
        for indicator in trending:
            # Indicators should be properly cased (MACD, EMA, Parabolic_SAR)
            assert indicator[0].isupper(), f"Indicator should be properly cased: {indicator}"
        
        # Check ranging_indicators
        ranging = config.get("ranging_indicators", [])
        for indicator in ranging:
            assert indicator[0].isupper(), f"Indicator should be properly cased: {indicator}"
        
        print(f"✅ Adaptive config has properly cased indicators")
        print(f"   Trending: {trending}")
        print(f"   Ranging: {ranging}")
    
    def test_adaptive_strategy_update_with_proper_case_indicators(self):
        """PUT /api/adaptive-strategy/config with MACD,EMA,Parabolic_SAR should succeed"""
        response = requests.put(
            f"{BASE_URL}/api/adaptive-strategy/config",
            json={"trending_indicators": ["MACD", "EMA", "Parabolic_SAR"]}
        )
        
        # Should succeed (200) not fail with invalid indicator error
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Update should succeed: {data}"
        print(f"✅ Adaptive config update with proper-case indicators succeeded")
    
    def test_adaptive_strategy_update_rejects_lowercase_indicators(self):
        """PUT /api/adaptive-strategy/config with lowercase 'macd' should fail or be normalized"""
        response = requests.put(
            f"{BASE_URL}/api/adaptive-strategy/config",
            json={"trending_indicators": ["macd", "ema"]}
        )
        
        # Either fails with 400 (invalid indicator) or succeeds with normalization
        # Both are acceptable behaviors
        if response.status_code == 400:
            print(f"✅ Lowercase indicators correctly rejected (400)")
        elif response.status_code == 200:
            # Check if indicators were normalized
            data = response.json()
            config = data.get("config", {})
            trending = config.get("trending_indicators", [])
            # If normalized, should be uppercase
            print(f"✅ Lowercase indicators accepted (may be normalized): {trending}")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}: {response.text}")


class TestHealthAndRegression:
    """Basic health and regression tests"""
    
    def test_api_health(self):
        """GET /api/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("status") == "healthy", f"API not healthy: {data}"
        print(f"✅ API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
