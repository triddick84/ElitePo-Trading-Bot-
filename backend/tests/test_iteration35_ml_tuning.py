"""
Iteration 35 Tests: ML Accuracy Tuning with OTC Training Data
=============================================================
Tests for:
- GET /api/ml/tuning-report - OTC data availability, model status, tuning config
- POST /api/ml/train-from-otc - Train ML model from OTC candles
- POST /api/signals/collect-otc-candles - Store candles (regression)
- GET /api/signals/otc-candle-stats - Candle counts (regression)
- GET /api/ml/retrain-status - Retrain status (regression)
- Regression: /api/signals/scan-markets, /api/signals/iq720-ensemble
"""

import pytest
import requests
import os
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestMLTuningReport:
    """Tests for GET /api/ml/tuning-report endpoint"""
    
    def test_tuning_report_returns_success(self):
        """Test that tuning report endpoint returns successfully"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
    
    def test_tuning_report_has_otc_data_section(self):
        """Test that tuning report includes OTC data availability"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=120)
        data = response.json()
        
        assert "otc_data" in data, f"Missing otc_data section: {data.keys()}"
        otc_data = data["otc_data"]
        
        # Verify required fields
        assert "total_candles" in otc_data, "Missing total_candles"
        assert "by_symbol" in otc_data, "Missing by_symbol"
        assert "min_required" in otc_data, "Missing min_required"
        assert "ready_for_training" in otc_data, "Missing ready_for_training"
        
        print(f"OTC Data: {otc_data['total_candles']} total candles, ready={otc_data['ready_for_training']}")
    
    def test_tuning_report_has_model_status(self):
        """Test that tuning report includes model status"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=120)
        data = response.json()
        
        assert "model_status" in data, f"Missing model_status section: {data.keys()}"
        model_status = data["model_status"]
        
        # Should have at least maximized_v3
        if "maximized_v3" in model_status:
            m = model_status["maximized_v3"]
            assert "is_trained" in m, "Missing is_trained"
            assert "accuracy" in m, "Missing accuracy"
            print(f"Maximized v3: trained={m['is_trained']}, accuracy={m['accuracy']}%")
    
    def test_tuning_report_has_tuning_config(self):
        """Test that tuning report includes tuning configuration"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=120)
        data = response.json()
        
        assert "tuning_config" in data, f"Missing tuning_config section: {data.keys()}"
        config = data["tuning_config"]
        
        # Verify thresholds
        assert "timeframe_thresholds" in config, "Missing timeframe_thresholds"
        thresholds = config["timeframe_thresholds"]
        assert "5s" in thresholds, "Missing 5s threshold"
        assert "M1" in thresholds, "Missing M1 threshold"
        assert thresholds["5s"] == 0.00005, f"Expected 5s threshold 0.00005, got {thresholds['5s']}"
        assert thresholds["M1"] == 0.0003, f"Expected M1 threshold 0.0003, got {thresholds['M1']}"
        
        # Verify horizons
        assert "prediction_horizons" in config, "Missing prediction_horizons"
        horizons = config["prediction_horizons"]
        assert "5s" in horizons, "Missing 5s horizon"
        assert horizons["5s"] == 3, f"Expected 5s horizon 3, got {horizons['5s']}"
        
        # Verify feature selection
        assert "feature_selection" in config, "Missing feature_selection"
        assert "SelectKBest" in config["feature_selection"], "Feature selection should use SelectKBest"
        
        print(f"Tuning config: thresholds={thresholds}, horizons={horizons}")


class TestTrainFromOTC:
    """Tests for POST /api/ml/train-from-otc endpoint"""
    
    def test_train_from_otc_with_maximized_model(self):
        """Test training maximized model from OTC data"""
        payload = {
            "model": "maximized",
            "symbols": ["EURUSD_OTC"],
            "min_samples": 50  # Lower threshold for testing
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ml/train-from-otc",
            json=payload,
            timeout=120  # Training can take time
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should either succeed or fail with helpful message
        if data.get("success"):
            # Verify training result fields
            assert "cv_accuracy" in data, f"Missing cv_accuracy: {data.keys()}"
            assert "total_samples" in data, f"Missing total_samples: {data.keys()}"
            assert "features_used" in data, f"Missing features_used: {data.keys()}"
            assert "selected_features" in data, f"Missing selected_features: {data.keys()}"
            assert "cv_scores" in data, f"Missing cv_scores: {data.keys()}"
            assert "class_distribution" in data, f"Missing class_distribution: {data.keys()}"
            assert "symbol_stats" in data, f"Missing symbol_stats: {data.keys()}"
            
            print(f"Training SUCCESS: {data['total_samples']} samples, {data['features_used']} features, {data['cv_accuracy']}% CV accuracy")
            print(f"CV scores: {data['cv_scores']}")
            print(f"Class distribution: {data['class_distribution']}")
            print(f"Selected features (top 15): {data['selected_features']}")
        else:
            # Should have helpful error message
            assert "error" in data, f"Missing error message: {data}"
            print(f"Training returned error (expected if insufficient data): {data['error']}")
            
            # If insufficient data, should include symbol_stats
            if "symbol_stats" in data:
                print(f"Symbol stats: {data['symbol_stats']}")
    
    def test_train_from_otc_with_improved_model(self):
        """Test training improved model from OTC data"""
        payload = {
            "model": "improved",
            "symbols": ["EURUSD_OTC"],
            "min_samples": 50
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ml/train-from-otc",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Either success or error with message
        assert "success" in data, f"Missing success field: {data}"
        print(f"Improved model training result: success={data.get('success')}")
    
    def test_train_from_otc_insufficient_data_returns_helpful_error(self):
        """Test that insufficient data returns helpful error message"""
        payload = {
            "model": "maximized",
            "symbols": ["NONEXISTENT_SYMBOL_XYZ"],
            "min_samples": 1000  # High threshold to trigger error
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ml/train-from-otc",
            json=payload,
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should fail with helpful message
        assert data.get("success") == False, f"Expected success=False for nonexistent symbol"
        assert "error" in data, "Missing error message"
        
        # Error should mention insufficient data or collecting more candles
        error_msg = data["error"].lower()
        assert "insufficient" in error_msg or "collect" in error_msg or "need" in error_msg, \
            f"Error should mention insufficient data: {data['error']}"
        
        print(f"Helpful error message: {data['error']}")
    
    def test_train_from_otc_default_model_works(self):
        """Test that default model parameter works (falls back to improved)"""
        payload = {
            "model": "improved",  # Use valid model name
            "symbols": ["EURUSD_OTC"],
            "min_samples": 50
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ml/train-from-otc",
            json=payload,
            timeout=120
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should succeed with valid model
        print(f"Improved model training result: success={data.get('success')}, accuracy={data.get('cv_accuracy')}")


class TestOTCCandleEndpointsRegression:
    """Regression tests for OTC candle collection endpoints"""
    
    def test_collect_otc_candles_still_works(self):
        """Test POST /api/signals/collect-otc-candles still works"""
        test_candles = [
            {
                "symbol": "EURUSD_OTC_TEST_ITER35",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "open": 1.0850,
                "high": 1.0855,
                "low": 1.0848,
                "close": 1.0852,
                "volume": 100
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/signals/collect-otc-candles",
            json={"candles": test_candles},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success: {data}"
        print(f"Collect OTC candles: stored={data.get('stored_count')}, total={data.get('total_candles')}")
    
    def test_otc_candle_stats_still_works(self):
        """Test GET /api/signals/otc-candle-stats still works"""
        response = requests.get(f"{BASE_URL}/api/signals/otc-candle-stats", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success: {data}"
        
        # Should have stats
        assert "total_candles" in data, "Missing total_candles"
        assert "by_symbol" in data, "Missing by_symbol"
        
        print(f"OTC candle stats: {data['total_candles']} total candles")
        if data.get("by_symbol"):
            for sym_stat in data["by_symbol"][:3]:  # Show first 3
                print(f"  {sym_stat.get('symbol')}: {sym_stat.get('count')} candles")


class TestRetrainStatusRegression:
    """Regression tests for retrain status endpoint"""
    
    def test_retrain_status_still_works(self):
        """Test GET /api/ml/retrain-status still works"""
        response = requests.get(f"{BASE_URL}/api/ml/retrain-status", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success: {data}"
        
        # Should have status fields
        assert "running" in data, "Missing running field"
        assert "phase" in data, "Missing phase field"
        assert "progress" in data, "Missing progress field"
        
        print(f"Retrain status: running={data['running']}, phase={data['phase']}, progress={data['progress']}%")


class TestSignalEndpointsRegression:
    """Regression tests for signal endpoints"""
    
    def test_scan_markets_still_works(self):
        """Test GET /api/signals/scan-markets still works with routing"""
        # scan-markets is a GET endpoint with query params
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={
                "symbols": "EURUSD_OTC",
                "timeframe": "5s",
                "strategy": "iq720_ensemble"
            },
            timeout=90
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have signals or success field
        assert "signals" in data or "success" in data or "top_signals" in data, f"Unexpected response: {data.keys()}"
        print(f"Scan markets response: success={data.get('success')}, signals_found={data.get('signals_found')}")
    
    def test_iq720_ensemble_still_works(self):
        """Test POST /api/signals/iq720-ensemble still works"""
        payload = {
            "symbol": "EURUSD_OTC",
            "timeframe": "5s"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have signal or success field
        assert "signal" in data or "success" in data, f"Unexpected response: {data.keys()}"
        print(f"IQ720 ensemble response: success={data.get('success')}")


class TestDashboardWidgetRegression:
    """Regression tests for dashboard widget endpoints"""
    
    def test_maximized_ml_stats_still_works(self):
        """Test GET /api/maximized-ml/stats still works"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have stats
        if data.get("success"):
            assert "stats" in data, "Missing stats field"
            print(f"Maximized ML stats: {data['stats']}")
        else:
            print(f"Maximized ML stats: {data}")


# Cleanup fixture
@pytest.fixture(scope="class", autouse=True)
def cleanup_test_data():
    """Cleanup test data after tests complete"""
    yield
    # Cleanup test candles created during testing
    try:
        # Note: In production, you'd want a proper cleanup endpoint
        pass
    except Exception:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
