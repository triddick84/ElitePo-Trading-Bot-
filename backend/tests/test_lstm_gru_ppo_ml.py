"""
Test LSTM/GRU Time-Series System and PPO Reinforcement Learning Agent
======================================================================
Tests for Phase 2 (LSTM/GRU) and Phase 3 (PPO RL) ML endpoints.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLSTMGRUSystem:
    """Tests for LSTM/GRU Time-Series Prediction System"""

    def test_lstm_gru_stats(self):
        """GET /api/lstm-gru/stats - Should return LSTM/GRU system stats"""
        response = requests.get(f"{BASE_URL}/api/lstm-gru/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify stats structure
        assert "model_type" in data, "Missing model_type in stats"
        assert "is_trained" in data, "Missing is_trained in stats"
        assert "accuracy" in data, "Missing accuracy in stats"
        assert "total_predictions" in data, "Missing total_predictions in stats"
        assert "sequence_length" in data, "Missing sequence_length in stats"
        assert "n_features" in data, "Missing n_features in stats"
        
        print(f"✅ LSTM/GRU Stats: model_type={data.get('model_type')}, is_trained={data.get('is_trained')}, accuracy={data.get('accuracy')}")

    def test_lstm_gru_predict(self):
        """POST /api/lstm-gru/predict?symbol=EUR_USD&granularity=M1 - Should return prediction"""
        response = requests.post(f"{BASE_URL}/api/lstm-gru/predict?symbol=EUR_USD&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "symbol" in data, "Missing symbol in response"
        assert "prediction" in data, "Missing prediction in response"
        
        prediction = data.get("prediction", {})
        assert "direction" in prediction, "Missing direction in prediction"
        assert "confidence" in prediction, "Missing confidence in prediction"
        assert prediction.get("direction") in ["BUY", "SELL", "HOLD"], f"Invalid direction: {prediction.get('direction')}"
        
        print(f"✅ LSTM/GRU Prediction: direction={prediction.get('direction')}, confidence={prediction.get('confidence')}, method={prediction.get('method')}")

    def test_lstm_gru_predict_different_symbol(self):
        """POST /api/lstm-gru/predict with GBP_USD symbol"""
        response = requests.post(f"{BASE_URL}/api/lstm-gru/predict?symbol=GBP_USD&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("symbol") == "GBP_USD", f"Expected symbol=GBP_USD, got {data.get('symbol')}"
        
        print(f"✅ LSTM/GRU Prediction for GBP_USD: {data.get('prediction', {}).get('direction')}")

    def test_lstm_gru_train_starts_background(self):
        """POST /api/lstm-gru/train - Should start training in background"""
        response = requests.post(
            f"{BASE_URL}/api/lstm-gru/train?symbol=EUR_USD&granularity=M1&count=500&epochs=5"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "message" in data, "Missing message in response"
        assert data.get("status") == "training_started", f"Expected status=training_started, got {data.get('status')}"
        
        print(f"✅ LSTM/GRU Training started: {data.get('message')}")


class TestPPORLAgent:
    """Tests for PPO Reinforcement Learning Agent"""

    def test_ppo_stats(self):
        """GET /api/ppo-rl/stats - Should return PPO agent stats"""
        response = requests.get(f"{BASE_URL}/api/ppo-rl/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Verify stats structure
        assert "model_type" in data, "Missing model_type in stats"
        assert "is_trained" in data, "Missing is_trained in stats"
        assert "accuracy" in data, "Missing accuracy in stats"
        assert "total_predictions" in data, "Missing total_predictions in stats"
        
        print(f"✅ PPO Stats: model_type={data.get('model_type')}, is_trained={data.get('is_trained')}, accuracy={data.get('accuracy')}")

    def test_ppo_predict(self):
        """POST /api/ppo-rl/predict?symbol=EUR_USD&granularity=M1 - Should return prediction"""
        response = requests.post(f"{BASE_URL}/api/ppo-rl/predict?symbol=EUR_USD&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "symbol" in data, "Missing symbol in response"
        assert "prediction" in data, "Missing prediction in response"
        
        prediction = data.get("prediction", {})
        assert "direction" in prediction, "Missing direction in prediction"
        assert "confidence" in prediction, "Missing confidence in prediction"
        assert prediction.get("direction") in ["BUY", "SELL", "HOLD"], f"Invalid direction: {prediction.get('direction')}"
        
        print(f"✅ PPO Prediction: direction={prediction.get('direction')}, confidence={prediction.get('confidence')}, method={prediction.get('method')}")

    def test_ppo_predict_different_symbol(self):
        """POST /api/ppo-rl/predict with USD_JPY symbol"""
        response = requests.post(f"{BASE_URL}/api/ppo-rl/predict?symbol=USD_JPY&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("symbol") == "USD_JPY", f"Expected symbol=USD_JPY, got {data.get('symbol')}"
        
        print(f"✅ PPO Prediction for USD_JPY: {data.get('prediction', {}).get('direction')}")

    def test_ppo_train_starts_background(self):
        """POST /api/ppo-rl/train - Should start training in background"""
        response = requests.post(
            f"{BASE_URL}/api/ppo-rl/train?symbol=EUR_USD&granularity=M1&count=500&episodes=5"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "message" in data, "Missing message in response"
        assert data.get("status") == "training_started", f"Expected status=training_started, got {data.get('status')}"
        
        print(f"✅ PPO Training started: {data.get('message')}")


class TestAIEnsemblePrediction:
    """Tests for Combined AI/ML Ensemble Prediction"""

    def test_ensemble_predict(self):
        """POST /api/ai-ensemble/predict?symbol=EUR_USD - Combined prediction from all ML systems"""
        response = requests.post(f"{BASE_URL}/api/ai-ensemble/predict?symbol=EUR_USD&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "symbol" in data, "Missing symbol in response"
        assert "ensemble_direction" in data, "Missing ensemble_direction in response"
        assert "ensemble_confidence" in data, "Missing ensemble_confidence in response"
        assert "individual_predictions" in data, "Missing individual_predictions in response"
        
        # Verify ensemble direction is valid
        assert data.get("ensemble_direction") in ["BUY", "SELL", "HOLD"], f"Invalid ensemble_direction: {data.get('ensemble_direction')}"
        
        # Verify individual predictions structure
        individual = data.get("individual_predictions", {})
        print(f"✅ Ensemble Prediction: direction={data.get('ensemble_direction')}, confidence={data.get('ensemble_confidence')}")
        print(f"   Individual predictions: {list(individual.keys())}")
        print(f"   Agreement: {data.get('agreement')}")
        print(f"   Votes: {data.get('votes')}")

    def test_ensemble_predict_different_symbol(self):
        """POST /api/ai-ensemble/predict with GBP_USD symbol"""
        response = requests.post(f"{BASE_URL}/api/ai-ensemble/predict?symbol=GBP_USD&granularity=M1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("symbol") == "GBP_USD", f"Expected symbol=GBP_USD, got {data.get('symbol')}"
        
        print(f"✅ Ensemble Prediction for GBP_USD: {data.get('ensemble_direction')}, confidence={data.get('ensemble_confidence')}")


class TestMLSystemsIntegration:
    """Integration tests for ML systems working together"""

    def test_all_ml_systems_available(self):
        """Verify all ML systems are available and responding"""
        # Check LSTM/GRU
        lstm_response = requests.get(f"{BASE_URL}/api/lstm-gru/stats")
        assert lstm_response.status_code == 200, "LSTM/GRU stats endpoint failed"
        lstm_data = lstm_response.json()
        
        # Check PPO
        ppo_response = requests.get(f"{BASE_URL}/api/ppo-rl/stats")
        assert ppo_response.status_code == 200, "PPO stats endpoint failed"
        ppo_data = ppo_response.json()
        
        # Check Maximized ML (stacking ensemble)
        max_ml_response = requests.get(f"{BASE_URL}/api/maximized-ml/stats")
        assert max_ml_response.status_code == 200, "Maximized ML stats endpoint failed"
        
        print(f"✅ All ML systems available:")
        print(f"   LSTM/GRU: is_trained={lstm_data.get('is_trained')}")
        print(f"   PPO RL: is_trained={ppo_data.get('is_trained')}")

    def test_predictions_return_valid_structure(self):
        """Verify all prediction endpoints return valid structure"""
        endpoints = [
            ("LSTM/GRU", f"{BASE_URL}/api/lstm-gru/predict?symbol=EUR_USD&granularity=M1"),
            ("PPO RL", f"{BASE_URL}/api/ppo-rl/predict?symbol=EUR_USD&granularity=M1"),
            ("Ensemble", f"{BASE_URL}/api/ai-ensemble/predict?symbol=EUR_USD&granularity=M1"),
        ]
        
        for name, url in endpoints:
            response = requests.post(url)
            assert response.status_code == 200, f"{name} prediction failed: {response.status_code}"
            data = response.json()
            assert data.get("success") == True, f"{name} returned success=False: {data}"
            print(f"✅ {name} prediction valid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
