"""
Test IQ-720 Dashboard Widget Backend Endpoints
Tests for iteration 27 - IQ-720 real-time dashboard widget
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auto-invert-engine.preview.emergentagent.com')

class TestIQ720WidgetEndpoints:
    """Test IQ-720 Widget backend endpoints used by the dashboard widget"""
    
    def test_health_endpoint(self):
        """Test health endpoint is working"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health endpoint working")
    
    def test_iq720_market_regime_default(self):
        """Test IQ-720 market regime endpoint with default symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/iq720-market-regime")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "regime" in data
        assert "session" in data
        assert data["regime"] in ["trending_up", "trending_down", "ranging", "high_volatility", "low_volatility", "unknown"]
        assert data["session"] in ["asian", "london", "new_york", "overlap", "off_hours"]
        print(f"✅ Market regime: {data['regime']}, Session: {data['session']}")
    
    def test_iq720_market_regime_with_symbol(self):
        """Test IQ-720 market regime endpoint with specific symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/iq720-market-regime?symbol=EURUSD")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "regime" in data
        assert "session" in data
        assert "session_weight" in data
        assert "regime_adjustments" in data
        print(f"✅ Market regime for EURUSD: {data['regime']}")
    
    def test_iq720_ensemble_signal_default(self):
        """Test IQ-720 ensemble signal generation with default parameters"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EUR_USD", "timeframe": "M1", "candle_count": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "signal" in data
        signal = data["signal"]
        assert "direction" in signal
        assert signal["direction"] in ["CALL", "PUT", "HOLD"]
        assert "confidence" in signal
        assert "market_regime" in signal
        assert "session" in signal
        print(f"✅ IQ-720 Ensemble signal: {signal['direction']} @ {signal['confidence']}%")
    
    def test_iq720_ensemble_signal_with_confirmations(self):
        """Test IQ-720 ensemble signal includes confirmations"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EUR_USD", "timeframe": "M1", "candle_count": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        signal = data["signal"]
        assert "confirmations" in signal
        assert isinstance(signal["confirmations"], list)
        print(f"✅ IQ-720 Ensemble confirmations: {signal['confirmations']}")
    
    def test_iq720_kelly_position_sizing(self):
        """Test IQ-720 Kelly position sizing calculation"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-kelly",
            json={"win_rate": 0.65, "avg_win": 0.82, "avg_loss": 1.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "kelly_fraction" in data
        assert "kelly_percent" in data
        assert data["kelly_percent"] > 0
        assert data["kelly_percent"] <= 12.5  # Capped at 12.5%
        print(f"✅ Kelly position size: {data['kelly_percent']}%")
    
    def test_iq720_kelly_low_win_rate(self):
        """Test IQ-720 Kelly with low win rate returns 0"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-kelly",
            json={"win_rate": 0.40, "avg_win": 1.5, "avg_loss": 1.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        # Low win rate should result in 0 or very low Kelly
        assert data["kelly_percent"] >= 0
        print(f"✅ Kelly with low win rate: {data['kelly_percent']}%")
    
    def test_iq720_kelly_high_win_rate(self):
        """Test IQ-720 Kelly with high win rate is capped"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-kelly",
            json={"win_rate": 0.80, "avg_win": 2.0, "avg_loss": 1.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        # High win rate should be capped at 12.5%
        assert data["kelly_percent"] <= 12.5
        print(f"✅ Kelly with high win rate (capped): {data['kelly_percent']}%")
    
    def test_iq720_features_endpoint(self):
        """Test IQ-720 features extraction endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-features",
            json={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "feature_count" in data
        assert "features" in data
        assert data["feature_count"] >= 50  # Should have 55+ features
        print(f"✅ IQ-720 features extracted: {data['feature_count']} features")
    
    def test_iq720_features_categories(self):
        """Test IQ-720 features include all categories"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-features",
            json={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "categories" in data
        expected_categories = ["price", "moving_averages", "momentum", "trend", "volatility", "patterns"]
        for cat in expected_categories:
            assert cat in data["categories"], f"Missing category: {cat}"
        print(f"✅ IQ-720 feature categories: {list(data['categories'].keys())}")


class TestDashboardExistingEndpoints:
    """Test existing dashboard endpoints still work (regression tests)"""
    
    def test_config_endpoint(self):
        """Test config endpoint"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "trading_mode" in data
        print("✅ Config endpoint working")
    
    def test_bot_status_endpoint(self):
        """Test bot status endpoint"""
        response = requests.get(f"{BASE_URL}/api/bot/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        print("✅ Bot status endpoint working")
    
    def test_candle_sync_status(self):
        """Test candle sync status endpoint"""
        response = requests.get(f"{BASE_URL}/api/bot/candle-sync/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        print("✅ Candle sync status endpoint working")
    
    def test_performance_metrics(self):
        """Test performance metrics endpoint"""
        response = requests.get(f"{BASE_URL}/api/performance/metrics")
        assert response.status_code == 200
        print("✅ Performance metrics endpoint working")
    
    def test_latency_status(self):
        """Test latency status endpoint"""
        response = requests.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✅ Latency status endpoint working")


class TestKeltnerMACD5sRegression:
    """Regression tests for Keltner-MACD 5s endpoint"""
    
    def test_keltner_macd_5s_endpoint(self):
        """Test Keltner-MACD 5s endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/signals/keltner-macd-5s",
            json={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "indicators" in data
        print("✅ Keltner-MACD 5s endpoint working")
    
    def test_evaluate_momentum_condition(self):
        """Test evaluate momentum condition endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/signals/evaluate-momentum-condition",
            params={"symbol": "EUR_USD", "condition_type": "crosses_above_zero", "period": 14, "threshold": 0, "smoothing": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "condition_met" in data
        print("✅ Evaluate momentum condition endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
