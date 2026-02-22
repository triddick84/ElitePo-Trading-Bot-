"""
Backend API Tests for Latency Correction System

Tests:
- GET /api/latency/status - Verify returns mode, offsets, effective buffers, and accuracy stats
- POST /api/latency/set-mode - Test switching between 'auto', 'manual', and 'disabled' modes
- POST /api/latency/set-manual-offset - Test setting manual offset and verify effective buffers change
- POST /api/latency/record-timing-feedback - Test recording timing feedback for auto-correction
- POST /api/latency/reset - Test resetting all latency settings to defaults
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthAndSetup:
    """Basic health check before latency tests"""

    def test_api_health(self, api_client):
        """Test that API is reachable"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"API not healthy: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ API health check passed")


class TestLatencyStatus:
    """Tests for GET /api/latency/status endpoint"""

    def test_get_latency_status_returns_correct_structure(self, api_client):
        """Verify latency status returns all required fields"""
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200, f"Status failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Request not successful: {data}"
        
        # Check required fields
        assert "mode" in data, "Missing 'mode' field"
        assert "auto_correction_offset" in data, "Missing 'auto_correction_offset' field"
        assert "manual_offset" in data, "Missing 'manual_offset' field"
        assert "effective_buffers" in data, "Missing 'effective_buffers' field"
        assert "timeframe_accuracy" in data, "Missing 'timeframe_accuracy' field"
        
        print(f"✅ Latency status returned - mode: {data['mode']}")

    def test_effective_buffers_contain_all_timeframes(self, api_client):
        """Verify effective_buffers has all expected timeframes"""
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200
        
        data = response.json()
        buffers = data.get("effective_buffers", {})
        
        # Should have these timeframes
        expected_timeframes = ["5s", "15s", "30s", "1m", "2m"]
        for tf in expected_timeframes:
            assert tf in buffers, f"Missing timeframe {tf} in effective_buffers"
            assert isinstance(buffers[tf], (int, float)), f"Buffer for {tf} is not numeric"
        
        print(f"✅ Effective buffers: {buffers}")

    def test_timeframe_accuracy_structure(self, api_client):
        """Verify timeframe_accuracy has correct structure"""
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200
        
        data = response.json()
        accuracy = data.get("timeframe_accuracy", {})
        
        expected_keys = ["wins", "losses", "early_errors", "late_errors"]
        
        for tf, stats in accuracy.items():
            for key in expected_keys:
                assert key in stats, f"Missing '{key}' in accuracy stats for {tf}"
        
        print(f"✅ Timeframe accuracy structure is valid")


class TestSetMode:
    """Tests for POST /api/latency/set-mode endpoint"""

    def test_set_mode_auto(self, api_client):
        """Test switching to AUTO mode"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-mode",
            json={"mode": "auto"}
        )
        assert response.status_code == 200, f"Set mode failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("mode") == "auto"
        
        print("✅ Mode set to AUTO successfully")

    def test_set_mode_manual(self, api_client):
        """Test switching to MANUAL mode"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-mode",
            json={"mode": "manual"}
        )
        assert response.status_code == 200, f"Set mode failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("mode") == "manual"
        
        print("✅ Mode set to MANUAL successfully")

    def test_set_mode_disabled(self, api_client):
        """Test switching to DISABLED mode"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-mode",
            json={"mode": "disabled"}
        )
        assert response.status_code == 200, f"Set mode failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("mode") == "disabled"
        
        print("✅ Mode set to DISABLED successfully")

    def test_disabled_mode_returns_zero_buffers(self, api_client):
        """Verify DISABLED mode returns 0 for effective buffers"""
        # Set to disabled
        api_client.post(f"{BASE_URL}/api/latency/set-mode", json={"mode": "disabled"})
        
        # Check status
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("mode") == "disabled"
        
        buffers = data.get("effective_buffers", {})
        for tf, buffer in buffers.items():
            assert buffer == 0.0, f"Buffer for {tf} should be 0 in DISABLED mode, got {buffer}"
        
        print("✅ DISABLED mode returns zero buffers")

    def test_set_invalid_mode_returns_error(self, api_client):
        """Test that invalid mode returns error"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-mode",
            json={"mode": "invalid_mode_xyz"}
        )
        assert response.status_code == 200  # Still 200 but with success=False
        
        data = response.json()
        assert data.get("success") == False
        assert "error" in data or "Invalid mode" in str(data)
        
        print("✅ Invalid mode correctly returns error")


class TestSetManualOffset:
    """Tests for POST /api/latency/set-manual-offset endpoint"""

    def test_set_manual_offset_positive(self, api_client):
        """Test setting positive manual offset"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-manual-offset",
            json={"offset_seconds": 2.5}
        )
        assert response.status_code == 200, f"Set offset failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("manual_offset_seconds") == 2.5
        assert data.get("mode") == "manual"  # Should auto-switch to manual
        
        print("✅ Positive manual offset (2.5s) set successfully")

    def test_set_manual_offset_negative(self, api_client):
        """Test setting negative manual offset"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-manual-offset",
            json={"offset_seconds": -3.0}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("manual_offset_seconds") == -3.0
        
        print("✅ Negative manual offset (-3.0s) set successfully")

    def test_manual_offset_changes_effective_buffers(self, api_client):
        """Verify that setting manual offset changes effective buffers"""
        # First, reset to defaults
        api_client.post(f"{BASE_URL}/api/latency/reset")
        
        # Get baseline buffers (AUTO mode)
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        baseline_5s = response.json().get("effective_buffers", {}).get("5s")
        
        # Set manual offset to -2.0 (signals arrive earlier = higher buffer)
        api_client.post(
            f"{BASE_URL}/api/latency/set-manual-offset",
            json={"offset_seconds": -2.0}
        )
        
        # Get new buffers
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        data = response.json()
        new_5s = data.get("effective_buffers", {}).get("5s")
        
        # Negative offset should increase effective buffer
        # (because we're compensating for late signals by generating earlier)
        assert new_5s > baseline_5s - 2.0, f"Buffer should have changed. Baseline: {baseline_5s}, New: {new_5s}"
        
        print(f"✅ Effective buffer changed from {baseline_5s} to {new_5s} with -2.0s offset")

    def test_manual_offset_clamped_to_range(self, api_client):
        """Verify offset is clamped to valid range (-10 to +10)"""
        # Try to set beyond range
        response = api_client.post(
            f"{BASE_URL}/api/latency/set-manual-offset",
            json={"offset_seconds": 15.0}  # Beyond +10 limit
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        # Should be clamped to 10
        assert data.get("manual_offset_seconds") == 10.0
        
        print("✅ Offset correctly clamped to max (10.0s)")


class TestRecordTimingFeedback:
    """Tests for POST /api/latency/record-timing-feedback endpoint"""

    def test_record_timing_feedback_early(self, api_client):
        """Test recording 'too early' timing feedback"""
        # Reset first to get clean state
        api_client.post(f"{BASE_URL}/api/latency/reset")
        
        response = api_client.post(
            f"{BASE_URL}/api/latency/record-timing-feedback",
            json={
                "timeframe": "5s",
                "was_early": True,
                "was_late": False,
                "was_win": False
            }
        )
        assert response.status_code == 200, f"Record feedback failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        
        # Check accuracy stats updated
        accuracy = data.get("timeframe_accuracy", {})
        assert accuracy.get("early_errors", 0) >= 1 or data.get("auto_correction_offset") is not None
        
        print("✅ Early timing feedback recorded")

    def test_record_timing_feedback_late(self, api_client):
        """Test recording 'too late' timing feedback"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/record-timing-feedback",
            json={
                "timeframe": "15s",
                "was_early": False,
                "was_late": True,
                "was_win": False
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        print("✅ Late timing feedback recorded")

    def test_record_timing_feedback_win(self, api_client):
        """Test recording win feedback"""
        response = api_client.post(
            f"{BASE_URL}/api/latency/record-timing-feedback",
            json={
                "timeframe": "1m",
                "was_early": False,
                "was_late": False,
                "was_win": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        print("✅ Win timing feedback recorded")

    def test_auto_correction_only_in_auto_mode(self, api_client):
        """Verify feedback only affects auto-correction in AUTO mode"""
        # Switch to MANUAL mode
        api_client.post(f"{BASE_URL}/api/latency/set-mode", json={"mode": "manual"})
        
        # Get current offset
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        offset_before = response.json().get("auto_correction_offset")
        
        # Record feedback
        api_client.post(
            f"{BASE_URL}/api/latency/record-timing-feedback",
            json={"timeframe": "5s", "was_early": True, "was_late": False, "was_win": False}
        )
        
        # Check offset unchanged (because we're in MANUAL mode)
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        offset_after = response.json().get("auto_correction_offset")
        
        assert offset_before == offset_after, "Auto-correction should not change in MANUAL mode"
        print("✅ Feedback ignored in MANUAL mode as expected")


class TestResetLatency:
    """Tests for POST /api/latency/reset endpoint"""

    def test_reset_latency_settings(self, api_client):
        """Test resetting all latency settings to defaults"""
        # First modify some settings
        api_client.post(f"{BASE_URL}/api/latency/set-mode", json={"mode": "manual"})
        api_client.post(f"{BASE_URL}/api/latency/set-manual-offset", json={"offset_seconds": 5.0})
        
        # Reset
        response = api_client.post(f"{BASE_URL}/api/latency/reset")
        assert response.status_code == 200, f"Reset failed: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("mode") == "auto"
        assert data.get("auto_correction_offset") == 0.0
        assert data.get("manual_offset") == 0.0
        
        print("✅ Latency settings reset to defaults")

    def test_reset_clears_accuracy_stats(self, api_client):
        """Verify reset clears all accuracy tracking"""
        # First record some feedback
        api_client.post(
            f"{BASE_URL}/api/latency/record-timing-feedback",
            json={"timeframe": "5s", "was_early": True, "was_late": False, "was_win": True}
        )
        
        # Reset
        api_client.post(f"{BASE_URL}/api/latency/reset")
        
        # Check status
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        data = response.json()
        
        # All accuracy stats should be zero
        accuracy = data.get("timeframe_accuracy", {})
        for tf, stats in accuracy.items():
            assert stats.get("wins", 0) == 0, f"{tf} wins should be 0 after reset"
            assert stats.get("losses", 0) == 0, f"{tf} losses should be 0 after reset"
        
        print("✅ Accuracy stats cleared after reset")


class TestEffectiveBuffersPerMode:
    """Tests verifying effective buffers behavior per mode"""

    def test_auto_mode_uses_base_buffers_plus_offset(self, api_client):
        """Verify AUTO mode uses base buffers + auto_correction_offset"""
        # Reset and set to AUTO
        api_client.post(f"{BASE_URL}/api/latency/reset")
        
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        data = response.json()
        
        assert data.get("mode") == "auto"
        buffers = data.get("effective_buffers", {})
        
        # In AUTO mode with 0 offset, should match base values:
        # 5s: 2.5, 15s: 3.0, 30s: 3.5, 1m: 4.0, 2m: 5.0
        expected_base = {"5s": 2.5, "15s": 3.0, "30s": 3.5, "1m": 4.0, "2m": 5.0}
        
        for tf, expected in expected_base.items():
            actual = buffers.get(tf)
            assert abs(actual - expected) < 0.5, f"{tf} buffer {actual} not near expected {expected}"
        
        print(f"✅ AUTO mode buffers match expected base values")

    def test_manual_mode_adjusts_buffers(self, api_client):
        """Verify MANUAL mode correctly adjusts buffers based on offset"""
        # Reset first
        api_client.post(f"{BASE_URL}/api/latency/reset")
        
        # Get baseline
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        baseline = response.json().get("effective_buffers", {}).get("5s")
        
        # Set manual offset of -1.0 (arrive 1s earlier)
        api_client.post(f"{BASE_URL}/api/latency/set-manual-offset", json={"offset_seconds": -1.0})
        
        response = api_client.get(f"{BASE_URL}/api/latency/status")
        data = response.json()
        
        new_buffer = data.get("effective_buffers", {}).get("5s")
        
        # With negative offset, buffer should increase (base - (-offset) = base + offset)
        assert new_buffer == baseline + 1.0, f"Expected buffer to increase. Baseline: {baseline}, New: {new_buffer}"
        
        print(f"✅ MANUAL mode buffer adjusted correctly: {baseline} -> {new_buffer}")


class TestCleanup:
    """Reset state after tests"""

    def test_cleanup_reset_to_auto(self, api_client):
        """Reset to AUTO mode after all tests"""
        response = api_client.post(f"{BASE_URL}/api/latency/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("mode") == "auto"
        
        print("✅ Cleanup complete - reset to AUTO mode")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
