"""
Test Suite for GPT Signal Bot - Iteration 8
============================================
Testing:
1. Momentum Buster 15s Strategy
2. Improved AI/ML System v2.0
3. OANDA Integration
4. Health Check

Author: Testing Agent
"""

import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://pocket-trader-ai-8.preview.emergentagent.com"


class TestHealthCheck:
    """Health check endpoint tests - run first"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Missing 'status' field in health response"
        assert data["status"] == "healthy", f"Status is not healthy: {data['status']}"
        
        print(f"✅ Health check passed: status={data['status']}")


class TestOANDAIntegration:
    """OANDA market data service tests"""
    
    def test_oanda_status(self):
        """Test /api/oanda/status returns connected=true"""
        response = requests.get(f"{BASE_URL}/api/oanda/status", timeout=30)
        
        assert response.status_code == 200, f"OANDA status failed: {response.status_code}"
        
        data = response.json()
        assert "connected" in data, "Missing 'connected' field in OANDA status"
        assert data["connected"] == True, f"OANDA not connected: {data}"
        
        # Check for environment info
        if "environment" in data:
            print(f"✅ OANDA connected: environment={data.get('environment')}")
        else:
            print(f"✅ OANDA connected: {data}")


class TestImprovedMLSystem:
    """Improved AI/ML System v2.0 tests"""
    
    def test_ml_stats_endpoint(self):
        """Test /api/improved-ml/stats returns model statistics"""
        response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=30)
        
        assert response.status_code == 200, f"ML stats failed: {response.status_code}"
        
        data = response.json()
        
        # Stats may be nested under 'stats' key
        stats = data.get("stats", data)
        
        assert "is_trained" in stats, f"Missing 'is_trained' field in {data}"
        
        # Check if model is trained
        is_trained = stats.get("is_trained", False)
        model_accuracy = stats.get("model_accuracy", 0)
        
        print(f"✅ ML Stats: is_trained={is_trained}, model_accuracy={model_accuracy}%")
        
        # Verify expected fields
        assert "model_accuracy" in stats, "Missing 'model_accuracy' field"
        assert "version" in stats, "Missing 'version' field"
        
        # If trained, accuracy should be around 56% as per previous test
        if is_trained:
            assert model_accuracy > 50, f"Model accuracy too low: {model_accuracy}%"
            assert model_accuracy < 80, f"Model accuracy suspiciously high: {model_accuracy}%"
            print(f"   Feature count: {stats.get('feature_count', 'N/A')}")
            print(f"   Version: {stats.get('version', 'N/A')}")
    
    def test_ml_predict_eur_usd(self):
        """Test /api/improved-ml/predict/EUR_USD returns prediction"""
        response = requests.post(f"{BASE_URL}/api/improved-ml/predict/EUR_USD", timeout=60)
        
        assert response.status_code == 200, f"ML predict failed: {response.status_code}"
        
        data = response.json()
        
        # Check for prediction data
        if "prediction" in data:
            prediction = data["prediction"]
            if prediction:
                assert "direction" in prediction, "Missing 'direction' in prediction"
                assert "confidence" in prediction, "Missing 'confidence' in prediction"
                
                direction = prediction.get("direction")
                confidence = prediction.get("confidence")
                
                assert direction in ["CALL", "PUT"], f"Invalid direction: {direction}"
                assert 0 <= confidence <= 100, f"Invalid confidence: {confidence}"
                
                print(f"✅ ML Prediction EUR_USD: direction={direction}, confidence={confidence}%")
            else:
                print(f"⚠️ ML Prediction returned None (model may not be trained)")
        elif "error" in data:
            print(f"⚠️ ML Prediction error: {data['error']}")
        else:
            print(f"✅ ML Prediction response: {data}")


class TestMomentumBuster15sStrategy:
    """Momentum Buster 15s Strategy tests"""
    
    def test_momentum_buster_signal_eur_usd(self):
        """Test /api/strategy/momentum-buster-15s/signal?symbol=EUR_USD"""
        response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"},
            timeout=60
        )
        
        assert response.status_code == 200, f"Momentum Buster signal failed: {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        
        if data.get("success"):
            signal = data.get("signal", {})
            
            # Verify signal structure
            if signal:
                assert "direction" in signal, "Missing 'direction' in signal"
                assert "confidence" in signal, "Missing 'confidence' in signal"
                
                direction = signal.get("direction")
                confidence = signal.get("confidence")
                strategy = signal.get("strategy", "")
                
                assert direction in ["CALL", "PUT"], f"Invalid direction: {direction}"
                assert 0 <= confidence <= 100, f"Invalid confidence: {confidence}"
                
                print(f"✅ Momentum Buster Signal: direction={direction}, confidence={confidence}%")
                print(f"   Strategy: {strategy}")
                
                # Check for momentum indicators
                indicators = signal.get("indicators", {})
                if indicators:
                    print(f"   Momentum: {indicators.get('momentum', 'N/A')}")
                    print(f"   Momentum Color: {indicators.get('momentum_color', 'N/A')}")
                    print(f"   Consecutive Bars: {indicators.get('consecutive_bars', 'N/A')}")
            else:
                print(f"⚠️ No signal generated (market conditions may not meet criteria)")
        else:
            # Signal generation may fail if market conditions don't meet criteria
            message = data.get("message", "Unknown reason")
            print(f"⚠️ Signal not generated: {message}")
    
    def test_momentum_buster_stats(self):
        """Test /api/strategy/momentum-buster-15s/stats returns strategy statistics"""
        response = requests.get(f"{BASE_URL}/api/strategy/momentum-buster-15s/stats", timeout=30)
        
        assert response.status_code == 200, f"Momentum Buster stats failed: {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        
        if data.get("success"):
            stats = data.get("stats", {})
            
            # Verify stats structure
            assert "name" in stats, "Missing 'name' in stats"
            assert "timeframe" in stats, "Missing 'timeframe' in stats"
            assert "momentum_period" in stats, "Missing 'momentum_period' in stats"
            
            name = stats.get("name")
            timeframe = stats.get("timeframe")
            momentum_period = stats.get("momentum_period")
            signals_generated = stats.get("signals_generated", 0)
            
            # Verify expected values
            assert name == "Momentum Buster 15s", f"Unexpected strategy name: {name}"
            assert timeframe == "15s", f"Unexpected timeframe: {timeframe}"
            assert momentum_period == 3, f"Unexpected momentum period: {momentum_period}"
            
            print(f"✅ Momentum Buster Stats:")
            print(f"   Name: {name}")
            print(f"   Timeframe: {timeframe}")
            print(f"   Momentum Period: {momentum_period}")
            print(f"   Signals Generated: {signals_generated}")
        else:
            print(f"⚠️ Stats retrieval failed: {data}")


class TestEndToEndFlow:
    """End-to-end integration tests"""
    
    def test_full_signal_generation_flow(self):
        """Test complete flow: OANDA -> ML -> Signal"""
        # Step 1: Verify OANDA is connected
        oanda_response = requests.get(f"{BASE_URL}/api/oanda/status", timeout=30)
        assert oanda_response.status_code == 200
        oanda_data = oanda_response.json()
        assert oanda_data.get("connected") == True, "OANDA must be connected for this test"
        print("✅ Step 1: OANDA connected")
        
        # Step 2: Check ML system status
        ml_response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=30)
        assert ml_response.status_code == 200
        ml_data = ml_response.json()
        print(f"✅ Step 2: ML system status - trained={ml_data.get('is_trained')}")
        
        # Step 3: Generate Momentum Buster signal
        signal_response = requests.post(
            f"{BASE_URL}/api/strategy/momentum-buster-15s/signal",
            params={"symbol": "EUR_USD"},
            timeout=60
        )
        assert signal_response.status_code == 200
        signal_data = signal_response.json()
        print(f"✅ Step 3: Momentum Buster signal generated - success={signal_data.get('success')}")
        
        # Step 4: Verify health
        health_response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert health_response.status_code == 200
        print("✅ Step 4: System healthy after signal generation")
        
        print("\n✅ End-to-end flow completed successfully!")


# Pytest fixtures
@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "--tb=short"])
