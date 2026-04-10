"""
Test suite for Momentum Indicator feature (Iteration 25)
Tests:
1. GET /api/signals/momentum-indicator - Returns momentum analysis
2. POST /api/signals/evaluate-momentum-condition - Evaluates specific conditions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://momentum-trade-test.preview.emergentagent.com').rstrip('/')


class TestMomentumIndicatorAPI:
    """Tests for the Momentum Indicator API endpoints"""
    
    def test_momentum_indicator_default_params(self):
        """Test GET /api/signals/momentum-indicator with default parameters"""
        response = requests.get(f"{BASE_URL}/api/signals/momentum-indicator")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check response structure
        assert "success" in data, "Response should have 'success' field"
        
        if data.get("success"):
            # Verify momentum values are present
            assert "momentum" in data, "Response should have 'momentum' field"
            assert "signal" in data, "Response should have 'signal' field"
            assert "conditions" in data, "Response should have 'conditions' field"
            
            # Verify momentum structure
            momentum = data["momentum"]
            assert "raw" in momentum, "Momentum should have 'raw' value"
            assert "smoothed" in momentum, "Momentum should have 'smoothed' value"
            assert "slope" in momentum, "Momentum should have 'slope' value"
            
            # Verify signal structure
            signal = data["signal"]
            assert "direction" in signal, "Signal should have 'direction'"
            assert "confidence" in signal, "Signal should have 'confidence'"
            assert "confirmations" in signal, "Signal should have 'confirmations'"
            
            # Verify conditions structure (8 conditions)
            conditions = data["conditions"]
            expected_conditions = [
                'crosses_above_zero', 'crosses_below_zero',
                'strong_positive', 'strong_negative',
                'momentum_increasing', 'momentum_decreasing',
                'bullish_divergence', 'bearish_divergence'
            ]
            for cond in expected_conditions:
                assert cond in conditions, f"Condition '{cond}' should be in response"
                assert "met" in conditions[cond], f"Condition '{cond}' should have 'met' field"
                assert "confidence_boost" in conditions[cond], f"Condition '{cond}' should have 'confidence_boost'"
                assert "description" in conditions[cond], f"Condition '{cond}' should have 'description'"
            
            print(f"✅ Momentum indicator returned: direction={signal['direction']}, confidence={signal['confidence']}")
        else:
            # If not successful, check for expected error fields
            print(f"⚠️ Momentum indicator returned error: {data.get('error', 'Unknown')}")
            assert "error" in data or "candles_available" in data, "Failed response should have error info"
    
    def test_momentum_indicator_with_symbol(self):
        """Test GET /api/signals/momentum-indicator with EUR_USD symbol"""
        response = requests.get(f"{BASE_URL}/api/signals/momentum-indicator?symbol=EUR_USD")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        if data.get("success"):
            assert data.get("symbol") == "EUR_USD", "Symbol should match request"
            print(f"✅ EUR_USD momentum: {data['momentum']['smoothed']:.6f}")
    
    def test_momentum_indicator_custom_params(self):
        """Test GET /api/signals/momentum-indicator with custom parameters"""
        params = {
            "symbol": "EUR_USD",
            "period": 10,
            "threshold": 5,
            "smoothing": 5
        }
        response = requests.get(f"{BASE_URL}/api/signals/momentum-indicator", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        if data.get("success"):
            # Verify parameters are reflected in response
            assert data["parameters"]["period"] == 10, "Period should be 10"
            assert data["parameters"]["threshold"] == 5, "Threshold should be 5"
            assert data["parameters"]["smoothing"] == 5, "Smoothing should be 5"
            print(f"✅ Custom params momentum: period={data['parameters']['period']}, threshold={data['parameters']['threshold']}")
    
    def test_momentum_indicator_returns_all_8_conditions(self):
        """Test that momentum indicator returns all 8 condition types"""
        response = requests.get(f"{BASE_URL}/api/signals/momentum-indicator?symbol=EUR_USD")
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            conditions = data.get("conditions", {})
            expected_conditions = [
                'crosses_above_zero', 'crosses_below_zero',
                'strong_positive', 'strong_negative',
                'momentum_increasing', 'momentum_decreasing',
                'bullish_divergence', 'bearish_divergence'
            ]
            
            assert len(conditions) == 8, f"Expected 8 conditions, got {len(conditions)}"
            
            for cond in expected_conditions:
                assert cond in conditions, f"Missing condition: {cond}"
            
            print(f"✅ All 8 momentum conditions present")


class TestEvaluateMomentumCondition:
    """Tests for POST /api/signals/evaluate-momentum-condition endpoint"""
    
    def test_evaluate_crosses_above_zero(self):
        """Test evaluating 'crosses_above_zero' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "crosses_above_zero",
            "period": 14,
            "threshold": 0,
            "smoothing": 3
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should have 'success' field"
        assert "condition_met" in data, "Response should have 'condition_met' field"
        assert "condition_type" in data, "Response should have 'condition_type' field"
        
        if data.get("success"):
            assert data["condition_type"] == "crosses_above_zero"
            assert isinstance(data["condition_met"], bool), "condition_met should be boolean"
            assert "confidence_boost" in data, "Should have confidence_boost"
            assert "description" in data, "Should have description"
            print(f"✅ crosses_above_zero: met={data['condition_met']}, boost={data['confidence_boost']}")
    
    def test_evaluate_strong_positive(self):
        """Test evaluating 'strong_positive' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "strong_positive",
            "period": 14,
            "threshold": 0,
            "smoothing": 3
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "strong_positive"
            print(f"✅ strong_positive: met={data['condition_met']}")
    
    def test_evaluate_strong_negative(self):
        """Test evaluating 'strong_negative' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "strong_negative",
            "period": 14,
            "threshold": 0,
            "smoothing": 3
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "strong_negative"
            print(f"✅ strong_negative: met={data['condition_met']}")
    
    def test_evaluate_momentum_increasing(self):
        """Test evaluating 'momentum_increasing' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "momentum_increasing"
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "momentum_increasing"
            print(f"✅ momentum_increasing: met={data['condition_met']}")
    
    def test_evaluate_momentum_decreasing(self):
        """Test evaluating 'momentum_decreasing' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "momentum_decreasing"
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "momentum_decreasing"
            print(f"✅ momentum_decreasing: met={data['condition_met']}")
    
    def test_evaluate_bullish_divergence(self):
        """Test evaluating 'bullish_divergence' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "bullish_divergence"
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "bullish_divergence"
            print(f"✅ bullish_divergence: met={data['condition_met']}")
    
    def test_evaluate_bearish_divergence(self):
        """Test evaluating 'bearish_divergence' condition"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "bearish_divergence"
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["condition_type"] == "bearish_divergence"
            print(f"✅ bearish_divergence: met={data['condition_met']}")
    
    def test_evaluate_with_custom_threshold(self):
        """Test evaluating condition with custom threshold"""
        params = {
            "symbol": "EUR_USD",
            "condition_type": "strong_positive",
            "period": 10,
            "threshold": 5,
            "smoothing": 3
        }
        response = requests.post(f"{BASE_URL}/api/signals/evaluate-momentum-condition", params=params)
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get("success"):
            assert data["parameters"]["threshold"] == 5
            print(f"✅ Custom threshold evaluation: threshold={data['parameters']['threshold']}")


class TestMomentumIndicatorClass:
    """Tests for the MomentumIndicator class in high_accuracy_strategies.py"""
    
    def test_health_check(self):
        """Verify backend is healthy before running tests"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, "Backend should be healthy"
        print("✅ Backend health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
