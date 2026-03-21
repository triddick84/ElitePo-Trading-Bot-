"""
Test Suite for Improved AI/ML System v2.0
==========================================
Tests the improved ML model training, prediction, and stats endpoints.
Features: 62 features, optimized ensemble (RF+GB+AdaBoost), OANDA data integration.
"""

import pytest
import requests
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestOANDAStatus:
    """Test OANDA API connection status - prerequisite for ML training"""
    
    def test_oanda_status_endpoint(self):
        """GET /api/oanda/status - verify OANDA API is connected"""
        response = requests.get(f"{BASE_URL}/api/oanda/status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"OANDA Status Response: {data}")
        
        # Verify response structure
        assert "configured" in data, "Response should contain 'configured' field"
        assert "connected" in data, "Response should contain 'connected' field"
        
        # OANDA should be configured and connected for ML training to work
        assert data["configured"] == True, "OANDA should be configured"
        assert data["connected"] == True, "OANDA should be connected"
        
        # Check environment
        if "environment" in data:
            assert data["environment"] in ["live", "practice"], f"Invalid environment: {data['environment']}"
            print(f"OANDA Environment: {data['environment']}")


class TestImprovedMLStats:
    """Test ML system statistics endpoint"""
    
    def test_get_ml_stats_before_training(self):
        """GET /api/improved-ml/stats - should return ML system statistics"""
        response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"ML Stats Response: {data}")
        
        # Verify response structure
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, "Stats request should succeed"
        
        # Verify stats structure
        assert "stats" in data, "Response should contain 'stats' field"
        stats = data["stats"]
        
        # Required fields in stats
        required_fields = ["is_trained", "model_accuracy", "feature_count", "ml_available", "version"]
        for field in required_fields:
            assert field in stats, f"Stats should contain '{field}' field"
        
        # Verify ML is available
        assert stats["ml_available"] == True, "ML libraries should be available"
        
        # Verify version
        assert stats["version"] == "2.0.0", f"Expected version 2.0.0, got {stats['version']}"
        
        print(f"ML Trained: {stats['is_trained']}")
        print(f"Model Accuracy: {stats['model_accuracy']}%")
        print(f"Feature Count: {stats['feature_count']}")


class TestImprovedMLTraining:
    """Test ML model training endpoint"""
    
    def test_train_ml_model(self):
        """POST /api/improved-ml/train - should train the model with OANDA data"""
        # Training can take time, increase timeout
        response = requests.post(f"{BASE_URL}/api/improved-ml/train", timeout=120)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Training Response: {data}")
        
        # Verify training success
        assert "success" in data, "Response should contain 'success' field"
        assert data["success"] == True, f"Training should succeed. Error: {data.get('error', 'Unknown')}"
        
        # Verify training results
        assert "cv_accuracy" in data, "Response should contain 'cv_accuracy' (cross-validation accuracy)"
        assert "samples_used" in data, "Response should contain 'samples_used'"
        assert "feature_count" in data, "Response should contain 'feature_count'"
        
        # Validate accuracy is reasonable (should be > 50% for binary classification)
        cv_accuracy = data["cv_accuracy"]
        assert cv_accuracy > 50, f"CV accuracy should be > 50%, got {cv_accuracy}%"
        print(f"Cross-Validation Accuracy: {cv_accuracy}%")
        
        # Validate feature count (should be around 62 features)
        feature_count = data["feature_count"]
        assert feature_count >= 50, f"Feature count should be >= 50, got {feature_count}"
        print(f"Feature Count: {feature_count}")
        
        # Validate samples used
        samples_used = data["samples_used"]
        assert samples_used >= 50, f"Samples used should be >= 50, got {samples_used}"
        print(f"Samples Used: {samples_used}")
        
        # Check class distribution
        if "class_distribution" in data:
            class_dist = data["class_distribution"]
            print(f"Class Distribution: CALL={class_dist.get('CALL', 0)}, PUT={class_dist.get('PUT', 0)}")
        
        # Check top features
        if "top_features" in data:
            print(f"Top Features: {list(data['top_features'].keys())[:5]}")


class TestImprovedMLPrediction:
    """Test ML prediction endpoints for multiple symbols"""
    
    def test_predict_eur_usd(self):
        """POST /api/improved-ml/predict/EUR_USD - should return prediction"""
        response = requests.post(f"{BASE_URL}/api/improved-ml/predict/EUR_USD", timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"EUR_USD Prediction Response: {data}")
        
        # Verify response structure
        assert "success" in data, "Response should contain 'success' field"
        
        if data["success"]:
            assert "prediction" in data, "Response should contain 'prediction' field"
            prediction = data["prediction"]
            
            # Verify prediction structure
            assert "direction" in prediction, "Prediction should contain 'direction'"
            assert "confidence" in prediction, "Prediction should contain 'confidence'"
            assert "call_probability" in prediction, "Prediction should contain 'call_probability'"
            assert "put_probability" in prediction, "Prediction should contain 'put_probability'"
            
            # Validate direction
            assert prediction["direction"] in ["CALL", "PUT"], f"Invalid direction: {prediction['direction']}"
            
            # Validate confidence (should be between 50-100%)
            confidence = prediction["confidence"]
            assert 50 <= confidence <= 100, f"Confidence should be 50-100%, got {confidence}%"
            
            # Validate probabilities sum to ~100%
            call_prob = prediction["call_probability"]
            put_prob = prediction["put_probability"]
            total_prob = call_prob + put_prob
            assert 99 <= total_prob <= 101, f"Probabilities should sum to ~100%, got {total_prob}%"
            
            print(f"Direction: {prediction['direction']}")
            print(f"Confidence: {confidence}%")
            print(f"CALL Probability: {call_prob}%")
            print(f"PUT Probability: {put_prob}%")
        else:
            # If prediction fails, it might be because model needs training
            error = data.get("error", "Unknown error")
            print(f"Prediction failed (may need training): {error}")
            # Don't fail the test if model just needs training
            if "training" in error.lower() or "trained" in error.lower():
                pytest.skip("Model needs training first")
            else:
                pytest.fail(f"Prediction failed: {error}")
    
    def test_predict_gbp_usd(self):
        """POST /api/improved-ml/predict/GBP_USD - verify predictions work for multiple symbols"""
        response = requests.post(f"{BASE_URL}/api/improved-ml/predict/GBP_USD", timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"GBP_USD Prediction Response: {data}")
        
        assert "success" in data, "Response should contain 'success' field"
        
        if data["success"]:
            prediction = data["prediction"]
            assert prediction["direction"] in ["CALL", "PUT"], f"Invalid direction: {prediction['direction']}"
            print(f"GBP_USD Direction: {prediction['direction']}, Confidence: {prediction['confidence']}%")
        else:
            error = data.get("error", "Unknown error")
            if "training" in error.lower() or "trained" in error.lower():
                pytest.skip("Model needs training first")
    
    def test_predict_usd_jpy(self):
        """POST /api/improved-ml/predict/USD_JPY - verify predictions work for USD_JPY"""
        response = requests.post(f"{BASE_URL}/api/improved-ml/predict/USD_JPY", timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"USD_JPY Prediction Response: {data}")
        
        assert "success" in data, "Response should contain 'success' field"
        
        if data["success"]:
            prediction = data["prediction"]
            assert prediction["direction"] in ["CALL", "PUT"], f"Invalid direction: {prediction['direction']}"
            print(f"USD_JPY Direction: {prediction['direction']}, Confidence: {prediction['confidence']}%")
        else:
            error = data.get("error", "Unknown error")
            if "training" in error.lower() or "trained" in error.lower():
                pytest.skip("Model needs training first")


class TestMLStatsAfterTraining:
    """Test ML stats after training to verify model state"""
    
    def test_stats_after_training(self):
        """GET /api/improved-ml/stats - verify stats reflect trained model"""
        response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Stats After Training: {data}")
        
        assert data["success"] == True
        stats = data["stats"]
        
        # After training, model should be trained
        if stats["is_trained"]:
            # Verify accuracy is set
            assert stats["model_accuracy"] > 0, "Model accuracy should be > 0 after training"
            print(f"Model Accuracy: {stats['model_accuracy']}%")
            
            # Verify feature count
            assert stats["feature_count"] > 0, "Feature count should be > 0 after training"
            print(f"Feature Count: {stats['feature_count']}")
            
            # Check last training time
            if stats.get("last_training"):
                print(f"Last Training: {stats['last_training']}")
            
            # Check top features
            if stats.get("top_features"):
                print(f"Top Features: {list(stats['top_features'].keys())[:5]}")
        else:
            print("Model not yet trained - run training test first")


class TestEndToEndMLWorkflow:
    """End-to-end test of the ML workflow: train -> stats -> predict"""
    
    def test_full_ml_workflow(self):
        """Test complete ML workflow: verify OANDA -> train -> check stats -> predict"""
        
        # Step 1: Verify OANDA is connected
        print("\n=== Step 1: Verify OANDA Connection ===")
        oanda_response = requests.get(f"{BASE_URL}/api/oanda/status", timeout=30)
        assert oanda_response.status_code == 200
        oanda_data = oanda_response.json()
        assert oanda_data.get("connected") == True, "OANDA must be connected for ML training"
        print(f"OANDA Connected: {oanda_data.get('connected')}")
        
        # Step 2: Train the model
        print("\n=== Step 2: Train ML Model ===")
        train_response = requests.post(f"{BASE_URL}/api/improved-ml/train", timeout=120)
        assert train_response.status_code == 200
        train_data = train_response.json()
        assert train_data.get("success") == True, f"Training failed: {train_data.get('error')}"
        print(f"Training Success: CV Accuracy = {train_data.get('cv_accuracy')}%")
        
        # Step 3: Check stats
        print("\n=== Step 3: Verify ML Stats ===")
        stats_response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=30)
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["stats"]["is_trained"] == True, "Model should be trained"
        print(f"Model Trained: {stats_data['stats']['is_trained']}")
        print(f"Model Accuracy: {stats_data['stats']['model_accuracy']}%")
        
        # Step 4: Make predictions
        print("\n=== Step 4: Make Predictions ===")
        symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
        for symbol in symbols:
            pred_response = requests.post(f"{BASE_URL}/api/improved-ml/predict/{symbol}", timeout=60)
            assert pred_response.status_code == 200
            pred_data = pred_response.json()
            
            if pred_data.get("success"):
                prediction = pred_data["prediction"]
                print(f"{symbol}: {prediction['direction']} ({prediction['confidence']:.1f}%)")
            else:
                print(f"{symbol}: Prediction failed - {pred_data.get('error')}")
        
        print("\n=== ML Workflow Complete ===")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
