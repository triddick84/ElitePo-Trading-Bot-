"""
Signal Routing API Tests
========================
Tests for the Signal Routing Dashboard feature:
- GET /api/signal-routing/rules - List routing rules
- POST /api/signal-routing/rules - Create routing rule
- PUT /api/signal-routing/rules/{rule_id} - Update rule
- DELETE /api/signal-routing/rules/{rule_id} - Delete rule
- POST /api/signal-routing/test - Test signal routing
- GET /api/signal-routing/log - Get routing log
- GET /api/signal-routing/stats - Get routing statistics
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSignalRoutingRules:
    """Test CRUD operations for signal routing rules"""
    
    created_rule_ids = []  # Track created rules for cleanup
    
    def test_get_rules_list(self):
        """GET /api/signal-routing/rules - Should return list of rules"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/rules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Expected success=True"
        assert "rules" in data, "Expected 'rules' key in response"
        assert isinstance(data["rules"], list), "Rules should be a list"
        
        # Check pre-existing rules from context (2 rules exist)
        print(f"Found {len(data['rules'])} existing rules")
        for rule in data["rules"]:
            print(f"  - {rule.get('name')} (ID: {rule.get('rule_id')}, enabled: {rule.get('enabled')})")
    
    def test_create_rule_success(self):
        """POST /api/signal-routing/rules - Should create a new rule"""
        rule_data = {
            "name": f"TEST_Rule_{uuid.uuid4().hex[:6]}",
            "destinations": ["telegram", "mt5"],
            "filters": {
                "min_confidence": 70,
                "assets": ["EURUSD", "GBPUSD"],
                "directions": ["CALL"]
            },
            "priority": 25,
            "enabled": True
        }
        
        response = requests.post(f"{BASE_URL}/api/signal-routing/rules", json=rule_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Expected success=True"
        assert "rule" in data, "Expected 'rule' key in response"
        
        rule = data["rule"]
        assert rule.get("name") == rule_data["name"], "Rule name mismatch"
        assert rule.get("destinations") == rule_data["destinations"], "Destinations mismatch"
        assert rule.get("priority") == rule_data["priority"], "Priority mismatch"
        assert rule.get("enabled") is True, "Rule should be enabled"
        assert "rule_id" in rule, "Rule should have rule_id"
        assert "created_at" in rule, "Rule should have created_at"
        
        # Store for cleanup
        self.created_rule_ids.append(rule["rule_id"])
        print(f"Created rule: {rule['name']} (ID: {rule['rule_id']})")
    
    def test_create_rule_validation(self):
        """POST /api/signal-routing/rules - Should require name and destinations"""
        # Missing name
        response = requests.post(f"{BASE_URL}/api/signal-routing/rules", json={
            "destinations": ["telegram"]
        })
        # FastAPI should return 422 for validation error
        assert response.status_code in [400, 422], f"Expected 400/422 for missing name, got {response.status_code}"
    
    def test_update_rule_toggle_enabled(self):
        """PUT /api/signal-routing/rules/{rule_id} - Should toggle enabled status"""
        # First create a rule to update
        rule_data = {
            "name": f"TEST_Toggle_{uuid.uuid4().hex[:6]}",
            "destinations": ["pocket_option"],
            "filters": {"min_confidence": 60},
            "priority": 40,
            "enabled": True
        }
        
        create_response = requests.post(f"{BASE_URL}/api/signal-routing/rules", json=rule_data)
        assert create_response.status_code == 200
        rule_id = create_response.json()["rule"]["rule_id"]
        self.created_rule_ids.append(rule_id)
        
        # Update to disable
        update_response = requests.put(
            f"{BASE_URL}/api/signal-routing/rules/{rule_id}",
            json={"enabled": False}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        data = update_response.json()
        assert data.get("success") is True
        assert data["rule"]["enabled"] is False, "Rule should be disabled"
        assert "updated_at" in data["rule"], "Should have updated_at timestamp"
        
        print(f"Toggled rule {rule_id} to enabled=False")
    
    def test_update_rule_not_found(self):
        """PUT /api/signal-routing/rules/{rule_id} - Should handle non-existent rule"""
        response = requests.put(
            f"{BASE_URL}/api/signal-routing/rules/nonexistent123",
            json={"enabled": False}
        )
        assert response.status_code == 200  # API returns 200 with success=False
        data = response.json()
        assert data.get("success") is False, "Should return success=False for non-existent rule"
    
    def test_delete_rule_success(self):
        """DELETE /api/signal-routing/rules/{rule_id} - Should delete a rule"""
        # Create a rule to delete
        rule_data = {
            "name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "destinations": ["telegram"],
            "filters": {},
            "priority": 99
        }
        
        create_response = requests.post(f"{BASE_URL}/api/signal-routing/rules", json=rule_data)
        assert create_response.status_code == 200
        rule_id = create_response.json()["rule"]["rule_id"]
        
        # Delete the rule
        delete_response = requests.delete(f"{BASE_URL}/api/signal-routing/rules/{rule_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("success") is True, "Delete should succeed"
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/signal-routing/rules")
        rules = get_response.json()["rules"]
        rule_ids = [r["rule_id"] for r in rules]
        assert rule_id not in rule_ids, "Deleted rule should not appear in list"
        
        print(f"Deleted rule {rule_id}")
    
    def test_delete_rule_not_found(self):
        """DELETE /api/signal-routing/rules/{rule_id} - Should handle non-existent rule"""
        response = requests.delete(f"{BASE_URL}/api/signal-routing/rules/nonexistent456")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False, "Should return success=False for non-existent rule"


class TestSignalRoutingEngine:
    """Test the signal routing engine"""
    
    def test_route_signal_matches_rule(self):
        """POST /api/signal-routing/test - Should match signal to rules"""
        test_signal = {
            "direction": "CALL",
            "symbol": "EURUSD_OTC",
            "confidence": 85,
            "strategy": "iq720_ensemble"
        }
        
        response = requests.post(f"{BASE_URL}/api/signal-routing/test", json=test_signal)
        assert response.status_code == 200, f"Test route failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "matched_rules" in data, "Should have matched_rules"
        assert "destinations" in data, "Should have destinations"
        assert "routed_at" in data, "Should have routed_at timestamp"
        assert "signal" in data, "Should echo back signal"
        
        print(f"Signal matched {len(data['matched_rules'])} rules -> destinations: {data['destinations']}")
    
    def test_route_signal_low_confidence(self):
        """POST /api/signal-routing/test - Low confidence signal routing"""
        test_signal = {
            "direction": "PUT",
            "symbol": "GBPJPY",
            "confidence": 50,  # Below most min_confidence thresholds
            "strategy": "test_strategy"
        }
        
        response = requests.post(f"{BASE_URL}/api/signal-routing/test", json=test_signal)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") is True
        # Low confidence may not match rules with min_confidence filters
        print(f"Low confidence signal matched {len(data['matched_rules'])} rules")
    
    def test_route_signal_creates_log_entry(self):
        """POST /api/signal-routing/test - Should create log entry"""
        unique_symbol = f"TEST_{uuid.uuid4().hex[:4]}"
        test_signal = {
            "direction": "CALL",
            "symbol": unique_symbol,
            "confidence": 90,
            "strategy": "test"
        }
        
        # Route the signal
        route_response = requests.post(f"{BASE_URL}/api/signal-routing/test", json=test_signal)
        assert route_response.status_code == 200
        
        # Check log for the entry
        log_response = requests.get(f"{BASE_URL}/api/signal-routing/log?limit=10")
        assert log_response.status_code == 200
        
        logs = log_response.json()["logs"]
        # Find our test signal in logs
        found = any(log.get("signal_symbol") == unique_symbol for log in logs)
        assert found, f"Test signal {unique_symbol} should appear in routing log"
        
        print(f"Verified log entry for {unique_symbol}")


class TestSignalRoutingLog:
    """Test routing log endpoint"""
    
    def test_get_routing_log(self):
        """GET /api/signal-routing/log - Should return recent logs"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/log")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "logs" in data
        assert isinstance(data["logs"], list)
        
        print(f"Found {len(data['logs'])} log entries")
        if data["logs"]:
            log = data["logs"][0]
            print(f"  Latest: {log.get('signal_symbol')} {log.get('signal_direction')} -> {log.get('destinations')}")
    
    def test_get_routing_log_with_limit(self):
        """GET /api/signal-routing/log?limit=5 - Should respect limit"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/log?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["logs"]) <= 5, "Should respect limit parameter"


class TestSignalRoutingStats:
    """Test routing statistics endpoint"""
    
    def test_get_routing_stats(self):
        """GET /api/signal-routing/stats - Should return statistics"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/stats")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data.get("success") is True
        assert "stats" in data
        
        stats = data["stats"]
        assert "total_routed" in stats, "Should have total_routed"
        assert "total_rules" in stats, "Should have total_rules"
        assert "enabled_rules" in stats, "Should have enabled_rules"
        assert "by_destination" in stats, "Should have by_destination breakdown"
        
        print(f"Stats: {stats['total_rules']} rules, {stats['enabled_rules']} enabled, {stats['total_routed']} signals routed")
        print(f"  By destination: {stats['by_destination']}")


class TestRegressionEndpoints:
    """Regression tests for existing functionality"""
    
    def test_health_endpoint(self):
        """GET /api/health - Should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("Health check passed")
    
    def test_telegram_bot_status(self):
        """GET /api/telegram-bot/status - Should return status"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"Telegram bot running: {data.get('status', {}).get('is_running')}")
    
    def test_mt5_status(self):
        """GET /api/mt5/status - Should return MT5 status"""
        response = requests.get(f"{BASE_URL}/api/mt5/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        print(f"MT5 status: {data.get('status', {})}")
    
    def test_tradingview_status(self):
        """GET /api/tradingview/status - Should return TradingView status"""
        response = requests.get(f"{BASE_URL}/api/tradingview/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("configured") is True
        print("TradingView webhook configured")
    
    def test_iq720_widget(self):
        """POST /api/signals/iq720-ensemble - IQ-720 widget should respond"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EURUSD_otc", "timeframe": "1m"}
        )
        assert response.status_code == 200
        data = response.json()
        # API may return success=False if insufficient data, which is valid behavior
        if data.get("success"):
            print(f"IQ-720 signal: {data.get('signal', {}).get('direction')}")
        else:
            print(f"IQ-720 response: {data.get('message', 'No signal')}")
        # Just verify the endpoint responds correctly
        assert "success" in data, "Response should have success field"


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_rules():
    """Cleanup TEST_ prefixed rules after all tests"""
    yield
    # Cleanup
    try:
        response = requests.get(f"{BASE_URL}/api/signal-routing/rules")
        if response.status_code == 200:
            rules = response.json().get("rules", [])
            for rule in rules:
                if rule.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/signal-routing/rules/{rule['rule_id']}")
                    print(f"Cleaned up test rule: {rule['name']}")
    except Exception as e:
        print(f"Cleanup error: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
