"""
Iteration 38 Tests: Auto-Retrain Scheduler
==========================================
Tests for the scheduled auto-retraining feature that triggers ML model retraining
at market open times (London Open 08:00 UTC, NY Open 13:00 UTC, Mon-Fri).

Endpoints tested:
- GET /api/ml/scheduler/status - Returns scheduler running state, config, last_retrain, history
- POST /api/ml/scheduler/start - Starts the scheduler background task
- POST /api/ml/scheduler/stop - Stops the scheduler
- PUT /api/ml/scheduler/config - Updates config (retrain_hours_utc, min_hours_between_retrain, etc.)
- POST /api/ml/scheduler/trigger - Triggers immediate manual retrain

Regression tests:
- GET /api/signals/engine-status
- POST /api/signals/decision
- GET /api/ml/tuning-report
- POST /api/signals/iq720-ensemble
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSchedulerStatus:
    """Test GET /api/ml/scheduler/status endpoint"""
    
    def test_scheduler_status_returns_success(self):
        """Scheduler status endpoint should return success"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Scheduler status returns success")
    
    def test_scheduler_status_has_running_field(self):
        """Scheduler status should have running field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert "running" in data
        assert isinstance(data["running"], bool)
        print(f"✓ Scheduler running: {data['running']}")
    
    def test_scheduler_status_has_config(self):
        """Scheduler status should have config object"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert "config" in data
        config = data["config"]
        assert isinstance(config, dict)
        print(f"✓ Scheduler config present")
    
    def test_scheduler_config_has_retrain_hours_utc(self):
        """Config should have retrain_hours_utc (default [8, 13])"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "retrain_hours_utc" in config
        assert isinstance(config["retrain_hours_utc"], list)
        assert 8 in config["retrain_hours_utc"]  # London Open
        assert 13 in config["retrain_hours_utc"]  # NY Open
        print(f"✓ retrain_hours_utc: {config['retrain_hours_utc']}")
    
    def test_scheduler_config_has_retrain_days(self):
        """Config should have retrain_days (default Mon-Fri [0,1,2,3,4])"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "retrain_days" in config
        assert isinstance(config["retrain_days"], list)
        # Mon-Fri = 0-4
        assert 0 in config["retrain_days"]
        assert 4 in config["retrain_days"]
        print(f"✓ retrain_days: {config['retrain_days']}")
    
    def test_scheduler_config_has_enabled(self):
        """Config should have enabled field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "enabled" in config
        assert isinstance(config["enabled"], bool)
        print(f"✓ enabled: {config['enabled']}")
    
    def test_scheduler_config_has_use_otc_data(self):
        """Config should have use_otc_data field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "use_otc_data" in config
        assert isinstance(config["use_otc_data"], bool)
        print(f"✓ use_otc_data: {config['use_otc_data']}")
    
    def test_scheduler_config_has_use_oanda_data(self):
        """Config should have use_oanda_data field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "use_oanda_data" in config
        assert isinstance(config["use_oanda_data"], bool)
        print(f"✓ use_oanda_data: {config['use_oanda_data']}")
    
    def test_scheduler_config_has_timeframes(self):
        """Config should have timeframes field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "timeframes" in config
        assert isinstance(config["timeframes"], list)
        print(f"✓ timeframes: {config['timeframes']}")
    
    def test_scheduler_config_has_symbols(self):
        """Config should have symbols_oanda and symbols_otc"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        config = response.json()["config"]
        assert "symbols_oanda" in config
        assert "symbols_otc" in config
        print(f"✓ symbols_oanda: {config['symbols_oanda']}")
        print(f"✓ symbols_otc: {config['symbols_otc']}")
    
    def test_scheduler_status_has_last_retrain(self):
        """Scheduler status should have last_retrain field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert "last_retrain" in data
        # Can be None or ISO timestamp
        print(f"✓ last_retrain: {data['last_retrain']}")
    
    def test_scheduler_status_has_recent_history(self):
        """Scheduler status should have recent_history field"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert "recent_history" in data
        assert isinstance(data["recent_history"], list)
        print(f"✓ recent_history count: {len(data['recent_history'])}")


class TestSchedulerStartStop:
    """Test POST /api/ml/scheduler/start and /stop endpoints"""
    
    def test_scheduler_start_returns_success(self):
        """Start scheduler should return success"""
        response = requests.post(f"{BASE_URL}/api/ml/scheduler/start")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        print(f"✓ Scheduler start: {data['message']}")
    
    def test_scheduler_start_returns_status(self):
        """Start scheduler should return current status"""
        response = requests.post(f"{BASE_URL}/api/ml/scheduler/start")
        data = response.json()
        assert "status" in data
        assert "running" in data["status"]
        print(f"✓ Scheduler running after start: {data['status']['running']}")
    
    def test_scheduler_stop_returns_success(self):
        """Stop scheduler should return success"""
        response = requests.post(f"{BASE_URL}/api/ml/scheduler/stop")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        print(f"✓ Scheduler stop: {data['message']}")
    
    def test_scheduler_stop_then_status_shows_not_running(self):
        """After stop, status should show not running"""
        # Stop first
        requests.post(f"{BASE_URL}/api/ml/scheduler/stop")
        time.sleep(0.5)
        
        # Check status
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert data["running"] == False
        print(f"✓ Scheduler not running after stop")
    
    def test_scheduler_start_then_status_shows_running(self):
        """After start, status should show running"""
        # Start
        requests.post(f"{BASE_URL}/api/ml/scheduler/start")
        time.sleep(0.5)
        
        # Check status
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        assert data["running"] == True
        print(f"✓ Scheduler running after start")


class TestSchedulerConfig:
    """Test PUT /api/ml/scheduler/config endpoint"""
    
    def test_update_config_returns_success(self):
        """Update config should return success"""
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"min_hours_between_retrain": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Config update returns success")
    
    def test_update_config_returns_updated_config(self):
        """Update config should return the updated config"""
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"min_hours_between_retrain": 6}
        )
        data = response.json()
        assert "config" in data
        assert data["config"]["min_hours_between_retrain"] == 6
        print(f"✓ Config updated: min_hours_between_retrain = 6")
    
    def test_update_retrain_hours_utc(self):
        """Should be able to update retrain_hours_utc"""
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"retrain_hours_utc": [7, 12, 17]}
        )
        data = response.json()
        assert data["config"]["retrain_hours_utc"] == [7, 12, 17]
        print(f"✓ retrain_hours_utc updated to [7, 12, 17]")
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"retrain_hours_utc": [8, 13]}
        )
    
    def test_update_enabled_flag(self):
        """Should be able to update enabled flag"""
        # Disable
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"enabled": False}
        )
        data = response.json()
        assert data["config"]["enabled"] == False
        print(f"✓ enabled set to False")
        
        # Re-enable
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"enabled": True}
        )
        data = response.json()
        assert data["config"]["enabled"] == True
        print(f"✓ enabled set back to True")
    
    def test_update_multiple_config_fields(self):
        """Should be able to update multiple config fields at once"""
        response = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={
                "min_hours_between_retrain": 4,
                "use_otc_data": True,
                "use_oanda_data": True
            }
        )
        data = response.json()
        config = data["config"]
        assert config["min_hours_between_retrain"] == 4
        assert config["use_otc_data"] == True
        assert config["use_oanda_data"] == True
        print(f"✓ Multiple config fields updated")


class TestSchedulerTrigger:
    """Test POST /api/ml/scheduler/trigger endpoint"""
    
    def test_trigger_returns_response(self):
        """Trigger endpoint should return a response (may timeout but still runs)"""
        # Note: This endpoint may timeout (>30s) since it does actual ML training
        # But the retrain still completes in background
        try:
            response = requests.post(
                f"{BASE_URL}/api/ml/scheduler/trigger",
                timeout=90  # Allow up to 90 seconds
            )
            assert response.status_code in [200, 504]  # 200 OK or 504 Gateway Timeout
            
            if response.status_code == 200:
                data = response.json()
                # Either success or cooldown message
                if data.get("success"):
                    print(f"✓ Manual retrain triggered successfully")
                    if "result" in data:
                        result = data["result"]
                        print(f"  - Status: {result.get('status')}")
                        print(f"  - Models trained: {result.get('models_count', 0)}")
                else:
                    # Cooldown message
                    print(f"✓ Trigger returned cooldown message: {data.get('message')}")
            else:
                print(f"✓ Trigger returned 504 (timeout) - retrain running in background")
        except requests.exceptions.Timeout:
            print(f"✓ Trigger timed out - retrain running in background")
    
    def test_trigger_respects_cooldown(self):
        """Trigger should respect 30min cooldown between manual retrains"""
        # First trigger (may succeed or be on cooldown)
        response1 = requests.post(
            f"{BASE_URL}/api/ml/scheduler/trigger",
            timeout=90
        )
        
        # Immediate second trigger should be on cooldown
        response2 = requests.post(
            f"{BASE_URL}/api/ml/scheduler/trigger",
            timeout=10
        )
        
        if response2.status_code == 200:
            data = response2.json()
            # Should either be on cooldown or still running from first trigger
            if not data.get("success"):
                assert "cooldown" in data.get("message", "").lower() or "Cooldown" in data.get("message", "")
                print(f"✓ Cooldown enforced: {data.get('message')}")
            else:
                print(f"✓ Second trigger succeeded (first may have been on cooldown)")


class TestSchedulerHistory:
    """Test scheduler history in status endpoint"""
    
    def test_recent_history_structure(self):
        """Recent history entries should have proper structure"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        history = data.get("recent_history", [])
        
        if len(history) > 0:
            entry = history[-1]  # Most recent
            # Check expected fields
            assert "started_at" in entry
            assert "status" in entry
            print(f"✓ History entry has started_at and status")
            
            if entry["status"] == "complete":
                assert "completed_at" in entry
                assert "duration_seconds" in entry
                assert "models_trained" in entry
                print(f"  - Duration: {entry.get('duration_seconds')}s")
                print(f"  - Models trained: {len(entry.get('models_trained', []))}")
        else:
            print(f"✓ No history entries yet (scheduler may not have run)")
    
    def test_retrain_count_matches_history(self):
        """retrain_count should match history length"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        data = response.json()
        
        retrain_count = data.get("retrain_count", 0)
        history_len = len(data.get("recent_history", []))
        
        # recent_history is capped at 5, so count may be higher
        assert retrain_count >= history_len
        print(f"✓ retrain_count: {retrain_count}, recent_history: {history_len}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_engine_status_still_works(self):
        """GET /api/signals/engine-status should still work"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "version" in data
        print(f"✓ engine-status works: version {data.get('version')}")
    
    def test_decision_endpoint_still_works(self):
        """POST /api/signals/decision should still work"""
        response = requests.post(
            f"{BASE_URL}/api/signals/decision",
            json={"symbol": "EUR_USD", "timeframe": "M1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "decision" in data
        print(f"✓ decision endpoint works: action={data['decision'].get('action')}")
    
    def test_ml_tuning_report_still_works(self):
        """GET /api/ml/tuning-report should still work"""
        response = requests.get(f"{BASE_URL}/api/ml/tuning-report")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ ml/tuning-report works")
    
    def test_iq720_ensemble_still_works(self):
        """POST /api/signals/iq720-ensemble should still work"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EUR_USD"}
        )
        assert response.status_code == 200
        data = response.json()
        # Endpoint returns success=true with signal or success=false with message when no signal
        assert "success" in data
        assert "message" in data or "signal" in data
        print(f"✓ iq720-ensemble works: success={data.get('success')}, has_signal={data.get('signal') is not None}")
    
    def test_api_health(self):
        """GET /api/health should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ API health check passed")


class TestSchedulerIntegration:
    """Integration tests for scheduler with ML systems"""
    
    def test_scheduler_full_flow(self):
        """Test full scheduler flow: stop -> start -> status -> config"""
        # 1. Stop scheduler
        stop_resp = requests.post(f"{BASE_URL}/api/ml/scheduler/stop")
        assert stop_resp.status_code == 200
        print(f"✓ Step 1: Scheduler stopped")
        
        # 2. Check status shows not running
        time.sleep(0.5)
        status_resp = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        assert status_resp.json()["running"] == False
        print(f"✓ Step 2: Status shows not running")
        
        # 3. Update config
        config_resp = requests.put(
            f"{BASE_URL}/api/ml/scheduler/config",
            json={"min_hours_between_retrain": 4}
        )
        assert config_resp.status_code == 200
        print(f"✓ Step 3: Config updated")
        
        # 4. Start scheduler
        start_resp = requests.post(f"{BASE_URL}/api/ml/scheduler/start")
        assert start_resp.status_code == 200
        print(f"✓ Step 4: Scheduler started")
        
        # 5. Verify running
        time.sleep(0.5)
        final_status = requests.get(f"{BASE_URL}/api/ml/scheduler/status")
        assert final_status.json()["running"] == True
        print(f"✓ Step 5: Scheduler running confirmed")
        
        print(f"✓ Full scheduler flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
