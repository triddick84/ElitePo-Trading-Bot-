"""
Test suite for GPT Signal Bot Auto Signal Generator APIs
Tests the auto signal generation with 15-second intervals for Pocket Option trading

Test Cases:
1. GET /api/signals/latest - Latest signal endpoint for userscript
2. GET /api/signals/auto/status - Auto signal generator status
3. POST /api/signals/auto/start - Start auto signal generation  
4. POST /api/signals/auto/stop - Stop auto signal generation
5. GET /api/health - Health check endpoint
"""
import pytest
import requests
import os
import time

# Use the public URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://ai-broker-dev.preview.emergentagent.com"


class TestHealthEndpoint:
    """Test the health check endpoint"""
    
    def test_health_returns_healthy(self):
        """GET /api/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "healthy", f"Expected healthy status, got {data}"
        assert "service" in data, "Response should contain service name"
        assert "timestamp" in data, "Response should contain timestamp"
        print(f"✅ Health check passed: {data}")


class TestAutoSignalStatus:
    """Test auto signal status endpoint"""
    
    def test_auto_status_returns_correct_interval(self):
        """GET /api/signals/auto/status should show interval_seconds: 15"""
        response = requests.get(f"{BASE_URL}/api/signals/auto/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify interval_seconds is 15
        assert "interval_seconds" in data, "Response should contain interval_seconds"
        assert data["interval_seconds"] == 15, f"Expected interval_seconds=15, got {data['interval_seconds']}"
        
        # Verify other required fields
        assert "enabled" in data, "Response should contain enabled field"
        assert "instruments" in data, "Response should contain instruments field"
        assert "timeframe" in data, "Response should contain timeframe field"
        assert "min_confidence" in data, "Response should contain min_confidence field"
        assert "signals_generated" in data, "Response should contain signals_generated field"
        assert "last_signal_time" in data, "Response should contain last_signal_time field"
        
        print(f"✅ Auto status check passed: interval={data['interval_seconds']}s, enabled={data['enabled']}")
        return data


class TestAutoSignalStartStop:
    """Test auto signal start/stop endpoints"""
    
    def test_start_auto_signal_generation(self):
        """POST /api/signals/auto/start should start auto signal generation with 15s interval"""
        response = requests.post(
            f"{BASE_URL}/api/signals/auto/start",
            params={
                "instruments": "EUR_USD",
                "timeframe": "M1",
                "interval_seconds": 15,
                "min_confidence": 70
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain success field"
        
        # If already running, that's also acceptable
        if data.get("success") == False and "already running" in data.get("message", ""):
            print(f"✅ Auto signal generator was already running")
            return data
        
        # If OANDA not configured, that's acceptable too (indicates endpoint works)
        if data.get("success") == False and "OANDA" in data.get("message", ""):
            print(f"⚠️ OANDA not configured - endpoint works but no signals will be generated")
            return data
        
        if data.get("success"):
            assert "config" in data, "Successful response should contain config"
            config = data["config"]
            assert config["interval_seconds"] == 15, f"Expected interval=15, got {config['interval_seconds']}"
            print(f"✅ Auto signal generator started with config: {config}")
        
        return data
    
    def test_stop_auto_signal_generation(self):
        """POST /api/signals/auto/stop should stop auto signal generation"""
        response = requests.post(f"{BASE_URL}/api/signals/auto/stop")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "message" in data, "Response should contain message"
        assert "stats" in data, "Response should contain stats"
        
        print(f"✅ Auto signal generator stopped. Stats: {data['stats']}")
        return data


class TestLatestSignalEndpoint:
    """Test the latest signal endpoint used by the Tampermonkey userscript"""
    
    def test_latest_signal_endpoint_structure(self):
        """GET /api/signals/latest should return proper structure for userscript"""
        response = requests.get(f"{BASE_URL}/api/signals/latest")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should always have success and message fields
        assert "success" in data, "Response should contain success field"
        
        if data.get("success"):
            # Successful response should have signal with required fields for userscript
            signal = data.get("signal")
            assert signal is not None, "Successful response should have signal"
            
            # Verify signal structure for userscript compatibility
            required_fields = ["id", "symbol", "direction", "timestamp"]
            for field in required_fields:
                assert field in signal, f"Signal should contain {field}"
            
            # Verify direction is normalized (CALL/PUT for userscript)
            direction = signal.get("direction")
            assert direction in ["CALL", "PUT", "BUY", "SELL"], f"Invalid direction: {direction}"
            
            # Verify confidence/probability exists
            assert "confidence" in signal or "probability" in signal, "Signal should have confidence/probability"
            
            print(f"✅ Latest signal available: {signal['direction']} {signal['symbol']} ({signal.get('confidence', signal.get('probability', 'N/A'))}%)")
        else:
            # No signal available is also valid - just means no recent signals
            assert "message" in data, "Response should contain message"
            print(f"⚠️ No signal available: {data['message']}")
        
        return data
    
    def test_latest_signal_with_enhanced_mode(self):
        """GET /api/signals/latest?use_enhanced=true should work"""
        response = requests.get(f"{BASE_URL}/api/signals/latest?use_enhanced=true")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "success" in data, "Response should contain success field"
        
        print(f"✅ Latest signal with enhanced mode: success={data['success']}")
        return data


class TestAutoSignalIntegration:
    """Integration tests for the auto signal generator workflow"""
    
    def test_full_start_status_stop_cycle(self):
        """Test the complete cycle: start -> check status -> stop"""
        
        # Step 1: Check initial status
        status_response = requests.get(f"{BASE_URL}/api/signals/auto/status")
        assert status_response.status_code == 200
        initial_status = status_response.json()
        print(f"Initial status: enabled={initial_status['enabled']}")
        
        # Step 2: Stop first to ensure clean state
        stop_response = requests.post(f"{BASE_URL}/api/signals/auto/stop")
        assert stop_response.status_code == 200
        print("Stopped auto generator to ensure clean state")
        
        # Step 3: Start with 15 second interval
        start_response = requests.post(
            f"{BASE_URL}/api/signals/auto/start",
            params={
                "instruments": "EUR_USD",
                "timeframe": "M1", 
                "interval_seconds": 15,
                "min_confidence": 70
            }
        )
        assert start_response.status_code == 200
        start_data = start_response.json()
        
        # If OANDA not configured, skip the running test
        if not start_data.get("success") and "OANDA" in start_data.get("message", ""):
            print("⚠️ OANDA not configured - skipping running status check")
            return
        
        if start_data.get("success"):
            # Step 4: Verify running status shows enabled=true and interval=15
            time.sleep(1)  # Brief wait for state to update
            running_status = requests.get(f"{BASE_URL}/api/signals/auto/status")
            assert running_status.status_code == 200
            running_data = running_status.json()
            
            assert running_data["enabled"] == True, f"Expected enabled=True, got {running_data}"
            assert running_data["interval_seconds"] == 15, f"Expected interval=15, got {running_data['interval_seconds']}"
            print(f"✅ Auto generator running with interval={running_data['interval_seconds']}s")
        
        # Step 5: Stop the generator
        final_stop = requests.post(f"{BASE_URL}/api/signals/auto/stop")
        assert final_stop.status_code == 200
        print("✅ Full cycle complete: start -> status -> stop")
    
    def test_default_interval_is_15_seconds(self):
        """Verify the default interval_seconds is 15 (not 60)"""
        
        # First stop any running instance
        requests.post(f"{BASE_URL}/api/signals/auto/stop")
        
        # Check status - default interval should be 15
        status_response = requests.get(f"{BASE_URL}/api/signals/auto/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["interval_seconds"] == 15, f"Default interval should be 15s, got {data['interval_seconds']}s"
        
        print(f"✅ Default interval_seconds verified: {data['interval_seconds']}s")


class TestSignalStructureForUserscript:
    """Test signal structure matches what the Tampermonkey userscript expects"""
    
    def test_signal_has_required_userscript_fields(self):
        """Verify signal structure matches userscript expectations"""
        response = requests.get(f"{BASE_URL}/api/signals/latest")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("success") and data.get("signal"):
            signal = data["signal"]
            
            # Required by userscript: id, symbol, direction, timestamp, confidence
            assert "id" in signal, "Signal must have id for userscript tracking"
            assert "symbol" in signal, "Signal must have symbol for display"
            assert "direction" in signal, "Signal must have direction (CALL/PUT)"
            assert "timestamp" in signal, "Signal must have timestamp for age calculation"
            
            # Confidence/probability for display
            has_confidence = "confidence" in signal or "probability" in signal
            assert has_confidence, "Signal must have confidence or probability"
            
            # Direction should be normalized
            direction = signal["direction"].upper()
            valid_directions = ["CALL", "PUT", "BUY", "SELL"]
            assert direction in valid_directions, f"Direction {direction} not valid for userscript"
            
            print(f"✅ Signal structure verified for userscript compatibility")
            print(f"   - id: {signal['id']}")
            print(f"   - symbol: {signal['symbol']}")
            print(f"   - direction: {signal['direction']}")
            print(f"   - confidence: {signal.get('confidence', signal.get('probability'))}")
        else:
            print("⚠️ No signal available to test structure")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
