"""
Test High-Accuracy Trading Strategies API Endpoints
====================================================

Tests for:
- POST /api/ai-learning/config - Save AI learning config
- GET /api/ai-learning/config - Get AI learning config
- GET /api/ml-training/models - Get ML models list
- POST /api/signals/high-accuracy/generate - Generate high accuracy signal with expiry 60
- GET /api/signals/high-accuracy/strategies - Get list of available strategies
- GET /api/signals/high-accuracy/performance - Get performance stats
- POST /api/signals/auto/start - Start auto signal generator
- GET /api/signals/auto/status - Check auto generator status
- POST /api/signals/auto/stop - Stop auto signal generator
- GET /api/pocket-option/realtime/status - Check PO connection status
"""

import pytest
import requests
import os
import time

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthCheck:
    """Basic health check to ensure API is available"""
    
    def test_api_health(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✅ API Health: {data.get('status')}")


class TestAILearningConfig:
    """Test AI Learning configuration endpoints"""
    
    def test_get_ai_learning_config(self, api_client):
        """GET /api/ai-learning/config - Should return AI learning configuration"""
        response = api_client.get(f"{BASE_URL}/api/ai-learning/config")
        assert response.status_code == 200
        data = response.json()
        
        # Verify config structure
        assert "model_config" in data or "learning_config" in data
        print(f"✅ GET AI Learning Config: {data}")
    
    def test_save_ai_learning_config(self, api_client):
        """POST /api/ai-learning/config - Should save AI learning configuration"""
        config_payload = {
            "model_config": {
                "primary_model": "enhanced_rsi_bb_volume",
                "secondary_model": "support_resistance",
                "use_ensemble": True,
                "ensemble_method": "weighted_average",
                "min_model_agreement": 2,
                "confidence_threshold": 75
            },
            "learning_config": {
                "enabled": True,
                "learning_rate": 0.01,
                "adaptation_speed": "medium",
                "use_market_regime": True,
                "use_volatility_filter": True,
                "lookback_periods": 100,
                "min_samples_for_update": 50
            }
        }
        
        response = api_client.post(f"{BASE_URL}/api/ai-learning/config", json=config_payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify success response
        assert data.get("success") == True
        assert "message" in data
        print(f"✅ POST AI Learning Config: {data}")
    
    def test_get_ai_learning_config_after_save(self, api_client):
        """Verify config was persisted after POST"""
        response = api_client.get(f"{BASE_URL}/api/ai-learning/config")
        assert response.status_code == 200
        data = response.json()
        
        # Verify saved data exists
        assert data.get("model_config", {}).get("primary_model") == "enhanced_rsi_bb_volume"
        print(f"✅ Config Persistence Verified: primary_model = {data.get('model_config', {}).get('primary_model')}")


class TestMLTrainingModels:
    """Test ML Training models endpoint"""
    
    def test_get_ml_models(self, api_client):
        """GET /api/ml-training/models - Should return ML models list"""
        response = api_client.get(f"{BASE_URL}/api/ml-training/models")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "models" in data
        assert isinstance(data["models"], list)
        print(f"✅ GET ML Models: {data.get('count', len(data['models']))} models found")


class TestHighAccuracySignals:
    """Test High-Accuracy Signal Generation endpoints"""
    
    def test_get_high_accuracy_strategies(self, api_client):
        """GET /api/signals/high-accuracy/strategies - Get available strategies"""
        response = api_client.get(f"{BASE_URL}/api/signals/high-accuracy/strategies")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get("success") == True
        assert "strategies" in data
        strategies = data["strategies"]
        assert isinstance(strategies, list)
        assert len(strategies) >= 4  # Should have at least 4 strategies
        
        # Verify strategy names
        strategy_names = [s["name"] for s in strategies]
        assert "ultra_scalping_5s" in strategy_names
        assert "momentum_breakout_15s" in strategy_names
        assert "mean_reversion_30s" in strategy_names
        assert "trend_confirmation_1m" in strategy_names
        
        print(f"✅ High Accuracy Strategies: {strategy_names}")
    
    def test_generate_high_accuracy_signal_60s_expiry(self, api_client):
        """POST /api/signals/high-accuracy/generate - Generate signal with 60s expiry"""
        # Use EUR_USD with 60 second expiry (trend_confirmation_1m strategy)
        response = api_client.post(
            f"{BASE_URL}/api/signals/high-accuracy/generate",
            params={"symbol": "EURUSD", "expiry": 60, "use_pocket_option": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should indicate success or no signal available (both valid)
        assert "success" in data
        assert "message" in data
        
        if data["success"]:
            # If signal generated, verify structure
            signal = data.get("signal", {})
            assert "direction" in signal  # CALL or PUT
            assert "confidence" in signal
            assert "strategy_name" in signal
            assert "confirmations" in signal
            assert "confirmations_count" in signal
            assert signal["confirmations_count"] >= 1
            print(f"✅ Signal Generated: {signal.get('direction')} with {signal.get('confirmations_count')} confirmations, confidence: {signal.get('confidence')}")
        else:
            # No high-probability setup - this is valid
            print(f"✅ No high-probability signal (expected in low-confidence markets): {data['message']}")
    
    def test_get_high_accuracy_performance(self, api_client):
        """GET /api/signals/high-accuracy/performance - Get performance statistics"""
        response = api_client.get(f"{BASE_URL}/api/signals/high-accuracy/performance")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data.get("success") == True
        assert "strategies" in data
        assert "total_signals_generated" in data
        
        print(f"✅ High Accuracy Performance: {data.get('total_signals_generated')} total signals")


class TestAutoSignalGenerator:
    """Test Auto Signal Generator endpoints"""
    
    def test_get_auto_signal_status_initial(self, api_client):
        """GET /api/signals/auto/status - Check initial status"""
        response = api_client.get(f"{BASE_URL}/api/signals/auto/status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify status structure
        assert "enabled" in data
        assert "instruments" in data
        assert "interval_seconds" in data
        assert "signals_generated" in data
        
        print(f"✅ Auto Signal Status: enabled={data.get('enabled')}, interval={data.get('interval_seconds')}s")
    
    def test_start_auto_signal_generator(self, api_client):
        """POST /api/signals/auto/start - Start auto signal generator"""
        # First ensure it's stopped
        api_client.post(f"{BASE_URL}/api/signals/auto/stop")
        time.sleep(1)
        
        # Start with EUR_USD
        response = api_client.post(
            f"{BASE_URL}/api/signals/auto/start",
            params={
                "instruments": "EUR_USD",
                "timeframe": "M1",
                "interval_seconds": 15,
                "min_confidence": 70
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return success or indicate OANDA not configured
        assert "success" in data
        
        if data["success"]:
            assert "message" in data
            assert "config" in data
            config = data["config"]
            assert config.get("interval_seconds") == 15
            print(f"✅ Auto Signal Generator Started: {data['message']}")
        else:
            # OANDA may not be configured - valid scenario
            print(f"✅ Auto Signal Generator: {data.get('message', 'Could not start - check OANDA config')}")
    
    def test_get_auto_signal_status_running(self, api_client):
        """GET /api/signals/auto/status - Check status while running"""
        response = api_client.get(f"{BASE_URL}/api/signals/auto/status")
        assert response.status_code == 200
        data = response.json()
        
        # Status should reflect current state
        assert "enabled" in data
        assert "interval_seconds" in data
        
        print(f"✅ Auto Signal Status After Start: enabled={data.get('enabled')}, interval={data.get('interval_seconds')}s")
    
    def test_stop_auto_signal_generator(self, api_client):
        """POST /api/signals/auto/stop - Stop auto signal generator"""
        response = api_client.post(f"{BASE_URL}/api/signals/auto/stop")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "stats" in data
        
        print(f"✅ Auto Signal Generator Stopped: {data.get('stats', {})}")
    
    def test_get_auto_signal_status_after_stop(self, api_client):
        """GET /api/signals/auto/status - Verify stopped status"""
        response = api_client.get(f"{BASE_URL}/api/signals/auto/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("enabled") == False
        print(f"✅ Auto Signal Status After Stop: enabled={data.get('enabled')}")


class TestPocketOptionRealtimeStatus:
    """Test Pocket Option real-time connection status"""
    
    def test_get_pocket_option_realtime_status(self, api_client):
        """GET /api/pocket-option/realtime/status - Check PO connection status"""
        response = api_client.get(f"{BASE_URL}/api/pocket-option/realtime/status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "connected" in data
        
        if data.get("success"):
            assert "authenticated" in data
            assert "subscribed_assets" in data
            print(f"✅ PO Realtime Status: connected={data.get('connected')}, authenticated={data.get('authenticated')}")
        else:
            # Not connected - valid scenario
            print(f"✅ PO Realtime Status: {data.get('message', 'Not connected')}")


class TestAdditionalHighAccuracyFeatures:
    """Additional tests for high-accuracy signal features"""
    
    def test_generate_signal_with_different_expiries(self, api_client):
        """Test signal generation with various expiry times"""
        expiries = [5, 15, 30, 60]
        
        for expiry in expiries:
            response = api_client.post(
                f"{BASE_URL}/api/signals/high-accuracy/generate",
                params={"symbol": "EUR_USD", "expiry": expiry, "use_pocket_option": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            
            if data["success"] and data.get("signal"):
                assert data["signal"]["expiry_seconds"] == expiry
                print(f"✅ {expiry}s Expiry: Signal generated with strategy {data['signal'].get('strategy_name')}")
            else:
                print(f"✅ {expiry}s Expiry: No signal (market conditions)")
    
    def test_high_accuracy_strategies_have_required_fields(self, api_client):
        """Verify all strategies have required fields"""
        response = api_client.get(f"{BASE_URL}/api/signals/high-accuracy/strategies")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["name", "expiry", "description", "min_confirmations", "best_market", "indicators"]
        
        for strategy in data.get("strategies", []):
            for field in required_fields:
                assert field in strategy, f"Strategy {strategy.get('name')} missing field: {field}"
        
        print(f"✅ All strategies have required fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
