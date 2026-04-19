"""
Iteration 36 Tests: OTC Tuning Panel UI and Backend APIs
=========================================================
Tests for the new '5s OTC Tuning' tab in AI Models page.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestOTCTuningAPIs:
    """Test OTC Tuning backend endpoints"""
    
    def test_tuning_report_returns_success(self):
        """GET /api/ml/tuning-report should return success"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"PASS: tuning-report returns success")
    
    def test_tuning_report_has_otc_data_section(self):
        """Tuning report should have otc_data section with total_candles, by_symbol, ready_for_training"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "otc_data" in data, "Missing otc_data section"
        otc_data = data["otc_data"]
        
        assert "total_candles" in otc_data, "Missing total_candles"
        assert "by_symbol" in otc_data, "Missing by_symbol"
        assert "ready_for_training" in otc_data, "Missing ready_for_training"
        assert "min_required" in otc_data, "Missing min_required"
        
        print(f"PASS: otc_data section complete - {otc_data['total_candles']} candles, ready={otc_data['ready_for_training']}")
    
    def test_tuning_report_has_model_status(self):
        """Tuning report should have model_status with maximized_v3 and improved_v2"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "model_status" in data, "Missing model_status section"
        model_status = data["model_status"]
        
        # Check for maximized_v3 and improved_v2
        assert "maximized_v3" in model_status or "improved_v2" in model_status, "Missing model entries"
        
        for model_name, model_info in model_status.items():
            assert "is_trained" in model_info, f"Missing is_trained for {model_name}"
            assert "accuracy" in model_info, f"Missing accuracy for {model_name}"
            print(f"  {model_name}: trained={model_info['is_trained']}, accuracy={model_info['accuracy']}%")
        
        print(f"PASS: model_status section complete")
    
    def test_tuning_report_has_tuning_config(self):
        """Tuning report should have tuning_config with thresholds and horizons"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert "tuning_config" in data, "Missing tuning_config section"
        config = data["tuning_config"]
        
        assert "timeframe_thresholds" in config, "Missing timeframe_thresholds"
        assert "prediction_horizons" in config, "Missing prediction_horizons"
        assert "feature_selection" in config, "Missing feature_selection"
        assert "cross_validation" in config, "Missing cross_validation"
        
        # Verify 5s threshold exists
        thresholds = config["timeframe_thresholds"]
        assert "5s" in thresholds or "S5" in thresholds, "Missing 5s threshold"
        
        print(f"PASS: tuning_config section complete")
    
    def test_train_from_otc_endpoint_exists(self):
        """POST /api/ml/train-from-otc should be accessible"""
        # Test with minimal payload - may fail due to insufficient data but endpoint should exist
        response = requests.post(
            f"{BASE_URL}/api/ml/train-from-otc",
            json={"model": "maximized", "min_samples": 50},
            timeout=120  # Training can take time
        )
        # Should return 200 even if training fails due to insufficient data
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Either success or error with helpful message
        if data.get("success"):
            print(f"PASS: train-from-otc succeeded - cv_accuracy={data.get('cv_accuracy')}%")
        else:
            # Should have helpful error message
            assert "error" in data, "Missing error message"
            print(f"PASS: train-from-otc returns helpful error: {data.get('error')[:100]}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_dashboard_health(self):
        """Dashboard health check"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("PASS: /api/health returns 200")
    
    def test_scan_markets_endpoint(self):
        """Scan markets endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/scan-markets", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "signals" in data or "opportunities" in data
        print("PASS: /api/scan-markets returns 200")
    
    def test_signal_routing_rules(self):
        """Signal routing rules endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/rules", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data or isinstance(data, list)
        print("PASS: /api/signal-routing/rules returns 200")
    
    def test_maximized_ml_stats(self):
        """Maximized ML stats endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/maximized-ml/stats", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        print("PASS: /api/maximized-ml/stats returns 200")
    
    def test_improved_ml_stats(self):
        """Improved ML stats endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/improved-ml/stats", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        print("PASS: /api/improved-ml/stats returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
