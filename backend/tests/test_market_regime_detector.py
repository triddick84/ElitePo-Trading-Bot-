"""
Test Suite for Market Regime Detector - Losing Streak Bug Fix

This tests the critical fix for the 'losing streak' bug where:
- Fallback signals were hardcoded to always return 'CALL'
- Fix implements streak tracking with auto-inversion after 3 consecutive losses

Key Tests:
1. POST /api/trading/record-result - Record win/loss and track streaks
2. GET /api/trading/regime-status - Get current regime status
3. POST /api/trading/reset-streak - Reset streak counter
4. Streak inversion activates after 3 consecutive losses
"""

import pytest
import requests
import os
import time

# Get BASE_URL from environment - production URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-broker-dev.preview.emergentagent.com').rstrip('/')


class TestHealthAndSetup:
    """Basic health checks before testing regime detector"""
    
    def test_api_health(self):
        """Test that the API is healthy and running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"API not healthy: {data}"
        print(f"✅ API health check passed: {data}")


class TestRegimeStatus:
    """Test GET /api/trading/regime-status endpoint"""
    
    def test_get_regime_status(self):
        """Test that regime status endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/trading/regime-status")
        assert response.status_code == 200, f"Regime status failed: {response.text}"
        
        data = response.json()
        print(f"📊 Regime Status Response: {data}")
        
        # Check for success
        assert data.get("success") == True, f"Regime status not successful: {data}"
        
        # Check status structure
        status = data.get("status")
        assert status is not None, "Status object is missing"
        
        # Validate required fields in status
        required_fields = [
            "current_regime",
            "current_streak", 
            "streak_inversion_active",
            "recent_win_rate",
            "total_trades_tracked"
        ]
        
        for field in required_fields:
            assert field in status, f"Missing field '{field}' in status: {status}"
        
        # Validate field types
        assert isinstance(status["current_streak"], int), "current_streak should be int"
        assert isinstance(status["streak_inversion_active"], bool), "streak_inversion_active should be bool"
        assert isinstance(status["recent_win_rate"], (int, float)), "recent_win_rate should be numeric"
        
        print(f"✅ Regime status structure validated")
        print(f"   - Current Regime: {status['current_regime']}")
        print(f"   - Current Streak: {status['current_streak']}")
        print(f"   - Inversion Active: {status['streak_inversion_active']}")
        print(f"   - Win Rate: {status['recent_win_rate']:.1f}%")


class TestResetStreak:
    """Test POST /api/trading/reset-streak endpoint"""
    
    def test_reset_streak(self):
        """Test that streak reset works correctly"""
        response = requests.post(f"{BASE_URL}/api/trading/reset-streak")
        assert response.status_code == 200, f"Reset streak failed: {response.text}"
        
        data = response.json()
        print(f"🔄 Reset Streak Response: {data}")
        
        # Check success
        assert data.get("success") == True, f"Reset not successful: {data}"
        assert "message" in data, "Missing success message"
        
        # Verify new status after reset
        new_status = data.get("new_status")
        assert new_status is not None, "new_status missing from response"
        
        # After reset, streak should be 0 and inversion should be false
        assert new_status["current_streak"] == 0, f"Streak not reset to 0: {new_status['current_streak']}"
        assert new_status["streak_inversion_active"] == False, "Inversion should be False after reset"
        
        print(f"✅ Streak reset successful")
        print(f"   - New Streak: {new_status['current_streak']}")
        print(f"   - Inversion Active: {new_status['streak_inversion_active']}")


class TestRecordTradeResult:
    """Test POST /api/trading/record-result endpoint"""
    
    def test_record_win(self):
        """Test recording a winning trade"""
        # First reset to start fresh
        requests.post(f"{BASE_URL}/api/trading/reset-streak")
        
        payload = {
            "direction": "CALL",
            "symbol": "TEST_EURUSD",
            "win": True,
            "signal_id": "test_win_001"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/record-result", json=payload)
        assert response.status_code == 200, f"Record result failed: {response.text}"
        
        data = response.json()
        print(f"✅ Record WIN Response: {data}")
        
        assert data.get("success") == True, f"Recording not successful: {data}"
        
        # After one win, streak should be 1
        assert data.get("current_streak") == 1, f"Expected streak 1 after win, got {data.get('current_streak')}"
        assert data.get("streak_inversion_active") == False, "Inversion should not be active after a win"
        
        print(f"   - Current Streak: {data['current_streak']}")
        print(f"   - Inversion Active: {data['streak_inversion_active']}")
    
    def test_record_loss(self):
        """Test recording a losing trade"""
        # First reset to start fresh
        requests.post(f"{BASE_URL}/api/trading/reset-streak")
        
        payload = {
            "direction": "CALL",
            "symbol": "TEST_EURUSD",
            "win": False,
            "signal_id": "test_loss_001"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/record-result", json=payload)
        assert response.status_code == 200, f"Record result failed: {response.text}"
        
        data = response.json()
        print(f"❌ Record LOSS Response: {data}")
        
        assert data.get("success") == True, f"Recording not successful: {data}"
        
        # After one loss, streak should be -1
        assert data.get("current_streak") == -1, f"Expected streak -1 after loss, got {data.get('current_streak')}"
        
        print(f"   - Current Streak: {data['current_streak']}")


class TestLosingStreakInversion:
    """
    CRITICAL TEST: Verify streak inversion activates after 3 consecutive losses
    This is the core fix for the 'losing streak' bug
    """
    
    def test_three_consecutive_losses_activates_inversion(self):
        """
        Test that after 3 consecutive losses, streak_inversion_active becomes True
        
        This is the main bug fix verification:
        - Before fix: Fallback always returned CALL (stuck in losing streaks)
        - After fix: After 3 losses, signals are automatically inverted
        """
        # Step 1: Reset streak to start fresh
        print("\n📝 Starting streak inversion test...")
        reset_response = requests.post(f"{BASE_URL}/api/trading/reset-streak")
        assert reset_response.status_code == 200, "Failed to reset streak"
        print("✅ Step 1: Streak reset")
        
        # Verify initial state
        status_response = requests.get(f"{BASE_URL}/api/trading/regime-status")
        initial_status = status_response.json().get("status", {})
        print(f"   Initial state: streak={initial_status.get('current_streak')}, inversion={initial_status.get('streak_inversion_active')}")
        
        # Step 2: Record 3 consecutive losses
        for i in range(1, 4):
            payload = {
                "direction": "CALL",
                "symbol": "TEST_STREAK_SYMBOL",
                "win": False,
                "signal_id": f"test_loss_streak_{i}"
            }
            
            response = requests.post(f"{BASE_URL}/api/trading/record-result", json=payload)
            assert response.status_code == 200, f"Failed to record loss {i}"
            
            data = response.json()
            streak = data.get("current_streak")
            inversion_active = data.get("streak_inversion_active")
            
            print(f"❌ Loss {i}: streak={streak}, inversion_active={inversion_active}")
            
            # Verify streak is updating correctly (negative values)
            assert streak == -i, f"Expected streak -{i}, got {streak}"
            
            # After exactly 3 losses, inversion should activate
            if i >= 3:
                assert inversion_active == True, f"CRITICAL: Inversion should be ACTIVE after {i} losses! Got: {inversion_active}"
                print(f"🎉 SUCCESS: Streak inversion activated after {i} consecutive losses!")
        
        # Step 3: Verify final regime status
        final_status = requests.get(f"{BASE_URL}/api/trading/regime-status")
        final_data = final_status.json().get("status", {})
        
        assert final_data.get("streak_inversion_active") == True, "Final status should show inversion active"
        assert final_data.get("current_streak") <= -3, f"Final streak should be -3 or less, got {final_data.get('current_streak')}"
        
        print(f"\n✅ CRITICAL TEST PASSED: Streak inversion correctly activates after 3 consecutive losses")
        print(f"   Final Status: streak={final_data.get('current_streak')}, inversion={final_data.get('streak_inversion_active')}")
    
    def test_win_after_losses_updates_streak(self):
        """Test that a win after losses correctly updates the streak"""
        # Reset first
        requests.post(f"{BASE_URL}/api/trading/reset-streak")
        
        # Record 2 losses
        for i in range(2):
            requests.post(f"{BASE_URL}/api/trading/record-result", json={
                "direction": "CALL",
                "symbol": "TEST_SYMBOL",
                "win": False
            })
        
        # Now record a win
        response = requests.post(f"{BASE_URL}/api/trading/record-result", json={
            "direction": "CALL",
            "symbol": "TEST_SYMBOL",
            "win": True
        })
        
        data = response.json()
        streak = data.get("current_streak")
        
        # After 2 losses and 1 win, streak should be 1 (win starts new streak)
        print(f"📊 After 2 losses + 1 win: streak={streak}")
        assert streak == 1, f"Expected streak 1 after win (new streak), got {streak}"
        
        print("✅ Win correctly resets losing streak")
    
    def test_inversion_deactivates_after_wins(self):
        """Test that 2 consecutive wins deactivate inversion"""
        # First, create an inversion state (3 losses)
        requests.post(f"{BASE_URL}/api/trading/reset-streak")
        
        for i in range(3):
            requests.post(f"{BASE_URL}/api/trading/record-result", json={
                "direction": "PUT",
                "symbol": "TEST_SYMBOL",
                "win": False
            })
        
        # Verify inversion is active
        status = requests.get(f"{BASE_URL}/api/trading/regime-status").json()
        assert status.get("status", {}).get("streak_inversion_active") == True, "Inversion should be active after 3 losses"
        print("✅ Inversion activated after 3 losses")
        
        # Now record 2 wins
        for i in range(2):
            response = requests.post(f"{BASE_URL}/api/trading/record-result", json={
                "direction": "CALL",
                "symbol": "TEST_SYMBOL", 
                "win": True
            })
            data = response.json()
            print(f"✅ Win {i+1}: streak={data.get('current_streak')}, inversion={data.get('streak_inversion_active')}")
        
        # After 2 wins, inversion should be deactivated
        final_data = response.json()
        assert final_data.get("streak_inversion_active") == False, "Inversion should deactivate after 2 wins"
        assert final_data.get("current_streak") == 2, f"Expected streak 2, got {final_data.get('current_streak')}"
        
        print("✅ Inversion correctly deactivates after 2 consecutive wins")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_record_result_with_missing_fields(self):
        """Test that API handles missing fields gracefully"""
        # Send minimal payload (only win field)
        response = requests.post(f"{BASE_URL}/api/trading/record-result", json={
            "win": True
        })
        
        # Should still succeed with defaults
        assert response.status_code == 200, f"API should handle missing fields: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Should succeed with defaults: {data}"
        print("✅ API handles missing fields with defaults")
    
    def test_record_result_with_invalid_direction(self):
        """Test recording with non-standard direction values"""
        # Test BUY instead of CALL
        response = requests.post(f"{BASE_URL}/api/trading/record-result", json={
            "direction": "BUY",
            "symbol": "EURUSD",
            "win": True
        })
        
        assert response.status_code == 200, f"Should accept BUY direction: {response.text}"
        print("✅ API accepts BUY/SELL directions")


class TestCleanup:
    """Cleanup test data after tests"""
    
    def test_final_reset(self):
        """Reset streak after all tests"""
        response = requests.post(f"{BASE_URL}/api/trading/reset-streak")
        assert response.status_code == 200
        print("✅ Final cleanup: streak reset")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
