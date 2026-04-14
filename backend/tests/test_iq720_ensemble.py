"""
Test IQ-720 Ensemble Advanced Signal Strategies
================================================
Tests for the new IQ-720 endpoints:
- POST /api/signals/iq720-ensemble - Ensemble signal generation
- GET /api/signals/iq720-market-regime - Market regime detection
- POST /api/signals/iq720-kelly - Kelly Criterion position sizing
- POST /api/signals/iq720-features - 60+ technical feature extraction

Also tests regression for existing endpoints:
- POST /api/signals/keltner-macd-5s
- POST /api/signals/evaluate-momentum-condition
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://momentum-trade-test.preview.emergentagent.com').rstrip('/')


class TestIQ720Ensemble:
    """Tests for IQ-720 Ensemble signal generation endpoint"""
    
    def test_iq720_ensemble_default_symbol(self):
        """Test IQ-720 ensemble with default EUR_USD symbol"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "signal" in data
        
        signal = data["signal"]
        assert signal is not None
        assert "direction" in signal
        assert signal["direction"] in ["CALL", "PUT"]
        assert "confidence" in signal
        assert 0 <= signal["confidence"] <= 100
        assert signal["strategy"] == "IQ720_Ensemble"
        assert "confirmations" in signal
        assert isinstance(signal["confirmations"], list)
        assert "market_regime" in signal
        assert "session" in signal
        
    def test_iq720_ensemble_with_symbol(self):
        """Test IQ-720 ensemble with specific symbol"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json={"symbol": "GBP_USD"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["signal"]["symbol"] == "GBP_USD"
        
    def test_iq720_ensemble_response_structure(self):
        """Test IQ-720 ensemble response has all required fields"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json={"symbol": "EUR_USD"})
        assert response.status_code == 200
        
        data = response.json()
        signal = data["signal"]
        
        # Check all required fields
        required_fields = [
            "direction", "confidence", "raw_confidence", "strategy",
            "confirmations", "market_regime", "session", "call_score",
            "put_score", "features", "expiry", "timestamp", "symbol"
        ]
        for field in required_fields:
            assert field in signal, f"Missing field: {field}"
        
        # Check features sub-structure
        features = signal["features"]
        assert "rsi" in features
        assert "macd_hist" in features
        assert "stoch_k" in features
        assert "bb_position" in features
        assert "kc_position" in features
        assert "adx" in features


class TestIQ720MarketRegime:
    """Tests for IQ-720 Market Regime detection endpoint"""
    
    def test_market_regime_default(self):
        """Test market regime detection with default symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/iq720-market-regime")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "regime" in data
        assert data["regime"] in ["trending_up", "trending_down", "ranging", "high_volatility", "low_volatility", "unknown"]
        assert "session" in data
        assert data["session"] in ["asian", "london", "new_york", "overlap", "off_hours"]
        
    def test_market_regime_with_symbol(self):
        """Test market regime detection with specific symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/iq720-market-regime?symbol=GBP_USD")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        # Symbol can be returned in either format (GBP_USD or GBPUSD)
        assert data["symbol"] in ["GBPUSD", "GBP_USD"]
        
    def test_market_regime_response_structure(self):
        """Test market regime response has all required fields"""
        response = requests.get(f"{BASE_URL}/api/signals/iq720-market-regime")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["success", "symbol", "regime", "session", "session_weight", "regime_adjustments", "timestamp"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Session weight should be a number
        assert isinstance(data["session_weight"], (int, float))
        assert 0 <= data["session_weight"] <= 2.0


class TestIQ720Kelly:
    """Tests for IQ-720 Kelly Criterion position sizing endpoint"""
    
    def test_kelly_basic_calculation(self):
        """Test Kelly Criterion with basic inputs"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-kelly", json={
            "win_rate": 0.65,
            "avg_win": 1.8,
            "avg_loss": 1.0
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "kelly_fraction" in data
        assert "kelly_percent" in data
        assert 0 <= data["kelly_fraction"] <= 0.25  # Capped at 25%
        assert 0 <= data["kelly_percent"] <= 25
        
    def test_kelly_edge_case_low_win_rate(self):
        """Test Kelly with low win rate"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-kelly", json={
            "win_rate": 0.40,
            "avg_win": 1.5,
            "avg_loss": 1.0
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        # Low win rate should result in lower Kelly fraction
        assert data["kelly_fraction"] <= 0.10
        
    def test_kelly_edge_case_high_win_rate(self):
        """Test Kelly with high win rate"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-kelly", json={
            "win_rate": 0.80,
            "avg_win": 2.0,
            "avg_loss": 1.0
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        # High win rate should result in higher Kelly fraction (but capped)
        assert data["kelly_fraction"] <= 0.25  # Half-Kelly cap
        
    def test_kelly_response_structure(self):
        """Test Kelly response has all required fields"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-kelly", json={
            "win_rate": 0.55,
            "avg_win": 1.5,
            "avg_loss": 1.0
        })
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["success", "kelly_fraction", "kelly_percent", "risk_per_trade", "inputs", "note"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestIQ720Features:
    """Tests for IQ-720 60+ technical feature extraction endpoint"""
    
    def test_features_default_symbol(self):
        """Test feature extraction with default symbol"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-features", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "feature_count" in data
        assert data["feature_count"] >= 50  # Should have 50+ features
        assert "features" in data
        assert "categories" in data
        
    def test_features_with_symbol(self):
        """Test feature extraction with specific symbol"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-features", json={"symbol": "USD_JPY"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["symbol"] == "USD_JPY"
        
    def test_features_categories(self):
        """Test that features are properly categorized"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-features", json={"symbol": "EUR_USD"})
        assert response.status_code == 200
        
        data = response.json()
        categories = data["categories"]
        
        # Check all expected categories exist
        expected_categories = ["price", "moving_averages", "momentum", "trend", "volatility", "patterns"]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
            assert isinstance(categories[cat], list)
            assert len(categories[cat]) > 0
            
    def test_features_specific_indicators(self):
        """Test that specific important features are present"""
        response = requests.post(f"{BASE_URL}/api/signals/iq720-features", json={"symbol": "EUR_USD"})
        assert response.status_code == 200
        
        features = response.json()["features"]
        
        # Check key features exist
        key_features = ["rsi_14", "macd", "macd_signal", "macd_hist", "stoch_k", "stoch_d", 
                       "bb_position", "atr", "adx", "ema_aligned_bullish", "ema_aligned_bearish"]
        for feat in key_features:
            assert feat in features, f"Missing feature: {feat}"


class TestRegressionExistingEndpoints:
    """Regression tests for existing endpoints that should still work"""
    
    def test_keltner_macd_5s_still_works(self):
        """Test Keltner-MACD 5s endpoint still works"""
        response = requests.post(f"{BASE_URL}/api/signals/keltner-macd-5s", json={"symbol": "EUR_USD"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "indicators" in data
        assert "keltner" in data["indicators"]
        assert "macd" in data["indicators"]
        
    def test_evaluate_momentum_condition_still_works(self):
        """Test momentum condition evaluation endpoint still works"""
        response = requests.post(
            f"{BASE_URL}/api/signals/evaluate-momentum-condition?symbol=EUR_USD&condition_type=crosses_above_zero"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "condition_met" in data
        assert "confidence_boost" in data
        
    def test_health_endpoint(self):
        """Test health endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"


class TestScanMarketsIQ720Integration:
    """Tests for IQ-720 integration in scan-markets endpoint"""
    
    def test_scan_markets_returns_signals(self):
        """Test scan-markets endpoint returns signals"""
        response = requests.get(f"{BASE_URL}/api/signals/scan-markets?min_confidence=50")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "top_signals" in data
        assert "scanned_assets" in data
        
    def test_scan_markets_with_deep_analysis(self):
        """Test scan-markets with deep analysis enabled"""
        response = requests.get(f"{BASE_URL}/api/signals/scan-markets?use_deep_analysis=true&min_confidence=50")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        # IQ-720 is in the fallback chain, so analysis_type could be various values
        assert "analysis_type" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
