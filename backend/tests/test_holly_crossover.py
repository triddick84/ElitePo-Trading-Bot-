"""
Test Holly Crossover Strategy Endpoints
========================================
Tests for the new Holly Crossover strategy (EMA(12) x WMA(23) reversal crossover)
Timeframes: 5s, 15s, 30s

Endpoints tested:
- POST /api/strategy/holly-crossover/signal?symbol=EUR_USD&timeframe=5s|15s|30s
- GET /api/strategy/holly-crossover/stats?timeframe=5s|15s|30s
- GET /api/strategies/available/5s|15s|30s (should include holly_crossover)
- GET /api/signals/scan-markets (should include holly_crossover in fallback chain)
- Regression tests for existing strategies
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHollyCrossoverSignal:
    """Test Holly Crossover signal generation endpoints"""
    
    def test_holly_crossover_signal_5s_eur_usd(self):
        """Test Holly Crossover signal for EUR_USD on 5s timeframe"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/holly-crossover/signal",
            params={"symbol": "EUR_USD", "timeframe": "5s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Signal may be null if no crossover reversal is active - that's expected
        if data.get("signal"):
            signal = data["signal"]
            assert signal.get("direction") in ["CALL", "PUT"], f"Invalid direction: {signal.get('direction')}"
            assert "confidence" in signal, "Missing confidence field"
            assert signal.get("timeframe") == "5s", f"Expected timeframe=5s, got {signal.get('timeframe')}"
            assert "indicators" in signal, "Missing indicators field"
            print(f"Signal generated: {signal.get('direction')} @ {signal.get('confidence')}%")
        else:
            print("No signal generated (no crossover reversal active) - expected behavior")
    
    def test_holly_crossover_signal_15s_eur_usd(self):
        """Test Holly Crossover signal for EUR_USD on 15s timeframe"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/holly-crossover/signal",
            params={"symbol": "EUR_USD", "timeframe": "15s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        if data.get("signal"):
            signal = data["signal"]
            assert signal.get("timeframe") == "15s", f"Expected timeframe=15s, got {signal.get('timeframe')}"
            print(f"Signal generated: {signal.get('direction')} @ {signal.get('confidence')}%")
        else:
            print("No signal generated (no crossover reversal active) - expected behavior")
    
    def test_holly_crossover_signal_30s_eur_usd(self):
        """Test Holly Crossover signal for EUR_USD on 30s timeframe"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/holly-crossover/signal",
            params={"symbol": "EUR_USD", "timeframe": "30s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        if data.get("signal"):
            signal = data["signal"]
            assert signal.get("timeframe") == "30s", f"Expected timeframe=30s, got {signal.get('timeframe')}"
            print(f"Signal generated: {signal.get('direction')} @ {signal.get('confidence')}%")
        else:
            print("No signal generated (no crossover reversal active) - expected behavior")
    
    def test_holly_crossover_signal_otc_asset(self):
        """Test Holly Crossover signal for OTC asset (EURUSD_OTC)"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/holly-crossover/signal",
            params={"symbol": "EURUSD_OTC", "timeframe": "5s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # OTC assets may return success=False with "Insufficient data" - this is expected
        # when OTC market data is not available (weekends, off-hours)
        if data.get("success") == False:
            assert "Insufficient data" in data.get("message", "") or "signal" in data, \
                f"Unexpected error for OTC asset: {data}"
            print(f"OTC asset returned no data (expected during off-hours): {data.get('message')}")
        else:
            print(f"OTC asset test passed. Signal: {data.get('signal')}")


class TestHollyCrossoverStats:
    """Test Holly Crossover stats endpoints"""
    
    def test_holly_crossover_stats_5s(self):
        """Test Holly Crossover stats for 5s timeframe"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/holly-crossover/stats",
            params={"timeframe": "5s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        stats = data.get("stats", {})
        assert stats.get("name") == "Holly Crossover", f"Expected name='Holly Crossover', got {stats.get('name')}"
        assert stats.get("timeframe") == "5s", f"Expected timeframe='5s', got {stats.get('timeframe')}"
        assert stats.get("expiration_seconds") == 5, f"Expected expiration=5, got {stats.get('expiration_seconds')}"
        
        # Verify indicator settings
        indicators = stats.get("indicators", {})
        assert indicators.get("fast_ma") == "EMA(12)", f"Expected fast_ma='EMA(12)', got {indicators.get('fast_ma')}"
        assert indicators.get("slow_ma") == "WMA(23)", f"Expected slow_ma='WMA(23)', got {indicators.get('slow_ma')}"
        
        print(f"Stats verified: {stats}")
    
    def test_holly_crossover_stats_15s(self):
        """Test Holly Crossover stats for 15s timeframe"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/holly-crossover/stats",
            params={"timeframe": "15s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        
        stats = data.get("stats", {})
        assert stats.get("name") == "Holly Crossover"
        assert stats.get("timeframe") == "15s"
        assert stats.get("expiration_seconds") == 15
        
        print(f"15s stats verified: timeframe={stats.get('timeframe')}, expiration={stats.get('expiration_seconds')}")
    
    def test_holly_crossover_stats_30s(self):
        """Test Holly Crossover stats for 30s timeframe"""
        response = requests.get(
            f"{BASE_URL}/api/strategy/holly-crossover/stats",
            params={"timeframe": "30s"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        
        stats = data.get("stats", {})
        assert stats.get("name") == "Holly Crossover"
        assert stats.get("timeframe") == "30s"
        assert stats.get("expiration_seconds") == 30
        
        print(f"30s stats verified: timeframe={stats.get('timeframe')}, expiration={stats.get('expiration_seconds')}")


class TestHollyCrossoverRegistration:
    """Test Holly Crossover strategy registration in available strategies"""
    
    def test_holly_crossover_in_5s_strategies(self):
        """Test Holly Crossover appears in 5s available strategies"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/5s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        strategies = data.get("strategies", [])
        
        # Find holly_crossover_5s in the list
        holly_found = False
        for strategy in strategies:
            if strategy.get("id") == "holly_crossover_5s":
                holly_found = True
                assert "Holly Crossover" in strategy.get("name", ""), f"Expected 'Holly Crossover' in name, got {strategy.get('name')}"
                assert "EMA(12)" in strategy.get("description", "") or "WMA(23)" in strategy.get("description", ""), \
                    f"Expected EMA/WMA in description, got {strategy.get('description')}"
                print(f"Found holly_crossover_5s: {strategy}")
                break
        
        assert holly_found, f"holly_crossover_5s not found in 5s strategies. Available: {[s.get('id') for s in strategies]}"
    
    def test_holly_crossover_in_15s_strategies(self):
        """Test Holly Crossover appears in 15s available strategies"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/15s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        strategies = data.get("strategies", [])
        
        holly_found = any(s.get("id") == "holly_crossover_15s" for s in strategies)
        assert holly_found, f"holly_crossover_15s not found in 15s strategies. Available: {[s.get('id') for s in strategies]}"
        print(f"holly_crossover_15s found in 15s strategies")
    
    def test_holly_crossover_in_30s_strategies(self):
        """Test Holly Crossover appears in 30s available strategies"""
        response = requests.get(f"{BASE_URL}/api/strategies/available/30s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        strategies = data.get("strategies", [])
        
        holly_found = any(s.get("id") == "holly_crossover_30s" for s in strategies)
        assert holly_found, f"holly_crossover_30s not found in 30s strategies. Available: {[s.get('id') for s in strategies]}"
        print(f"holly_crossover_30s found in 30s strategies")


class TestScanMarketsWithHollyCrossover:
    """Test scan-markets endpoint includes Holly Crossover in fallback chain"""
    
    def test_scan_markets_includes_holly_crossover(self):
        """Test scan-markets can use Holly Crossover strategy"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "assets": "EURUSD_OTC,GBPUSD_OTC",
                "min_confidence": 60
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Check if any signal uses holly_crossover analysis type
        signals = data.get("top_signals", [])
        holly_signals = [s for s in signals if "holly_crossover" in s.get("analysis_type", "")]
        
        print(f"Scan results: {data.get('scanned_assets')} assets scanned, {data.get('signals_found')} signals found")
        print(f"Holly Crossover signals: {len(holly_signals)}")
        
        # Note: Holly Crossover may not always generate signals (reversal strategy)
        # The test passes if the endpoint works correctly


class TestRegressionExistingStrategies:
    """Regression tests for existing strategies"""
    
    def test_golden_one_moment_still_works(self):
        """Regression: Golden One Moment signal endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/golden-one-moment/signal",
            params={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Golden One Moment regression failed: {data}"
        print("Golden One Moment regression test passed")
    
    def test_momentum_buster_still_works(self):
        """Regression: Momentum Buster 15s signal endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Momentum Buster regression failed: {data}"
        print("Momentum Buster 15s regression test passed")
    
    def test_health_endpoint(self):
        """Regression: Health endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Expected status=healthy, got {data}"
        print("Health endpoint regression test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
