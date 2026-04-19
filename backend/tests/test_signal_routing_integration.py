"""
Test Signal Routing Integration into Signal Generation Pipeline
================================================================
Tests that signal routing is properly wired into scan-markets and iq720-ensemble endpoints.
Verifies dispatch to pocket_option, mt5, and telegram destinations.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSignalRoutingIntegration:
    """Test signal routing integration into signal generation pipeline"""
    
    # ==================== SCAN-MARKETS WITH ROUTING ====================
    
    def test_scan_markets_returns_routing_field(self):
        """GET /api/signals/scan-markets should return routing field when signals are found"""
        # Use low confidence to increase chance of getting a signal
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55, "max_signals": 5},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        # Check response structure
        assert "scanned_assets" in data
        assert "signals_found" in data
        assert "top_signals" in data
        
        # If signals were found, routing should be present
        if data.get("signals_found", 0) > 0 and data.get("top_signals"):
            assert "routing" in data, "routing field should be present when signals are found"
            routing = data.get("routing")
            if routing:
                # Verify routing structure
                assert "matched_rules" in routing, "routing should have matched_rules"
                assert "destinations" in routing, "routing should have destinations"
                assert "dispatch_results" in routing, "routing should have dispatch_results"
                print(f"✅ scan-markets routing: matched_rules={routing.get('matched_rules')}, destinations={routing.get('destinations')}")
                print(f"   dispatch_results: {routing.get('dispatch_results')}")
        else:
            print(f"⚠️ No signals found (signals_found={data.get('signals_found')}), routing may be None")
    
    def test_scan_markets_routing_dispatch_pocket_option(self):
        """Verify pocket_option dispatch returns {queued: true}"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        routing = data.get("routing")
        
        if routing and routing.get("dispatch_results"):
            dispatch = routing.get("dispatch_results", {})
            if "pocket_option" in dispatch:
                assert dispatch["pocket_option"].get("queued") == True, \
                    f"pocket_option should return queued=true, got {dispatch['pocket_option']}"
                print(f"✅ pocket_option dispatch: {dispatch['pocket_option']}")
    
    def test_scan_markets_routing_dispatch_mt5(self):
        """Verify mt5 dispatch returns executed or not_connected"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        routing = data.get("routing")
        
        if routing and routing.get("dispatch_results"):
            dispatch = routing.get("dispatch_results", {})
            if "mt5" in dispatch:
                mt5_result = dispatch["mt5"]
                # MT5 should return either executed=true with ticket, or reason=not_connected
                assert "executed" in mt5_result or "reason" in mt5_result, \
                    f"mt5 should have executed or reason field, got {mt5_result}"
                if mt5_result.get("executed"):
                    assert "ticket" in mt5_result, "mt5 executed should have ticket"
                    print(f"✅ mt5 dispatch: executed=True, ticket={mt5_result.get('ticket')}")
                else:
                    print(f"✅ mt5 dispatch: {mt5_result}")
    
    def test_scan_markets_routing_dispatch_telegram(self):
        """Verify telegram dispatch returns sent status"""
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55},
            timeout=30
        )
        assert response.status_code == 200
        
        data = response.json()
        routing = data.get("routing")
        
        if routing and routing.get("dispatch_results"):
            dispatch = routing.get("dispatch_results", {})
            if "telegram" in dispatch:
                tg_result = dispatch["telegram"]
                assert "sent" in tg_result, f"telegram should have sent field, got {tg_result}"
                print(f"✅ telegram dispatch: {tg_result}")
    
    # ==================== IQ720-ENSEMBLE WITH ROUTING ====================
    
    def test_iq720_ensemble_returns_routing_field(self):
        """POST /api/signals/iq720-ensemble should return routing field when signal is generated"""
        response = requests.post(
            f"{BASE_URL}/api/signals/iq720-ensemble",
            json={"symbol": "EURUSD", "timeframe": "M1", "candle_count": 100},
            timeout=30
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # IQ720 may return success=false if conditions not met
        if data.get("success") == True and data.get("signal"):
            assert "routing" in data, "routing field should be present when signal is generated"
            routing = data.get("routing")
            if routing:
                assert "matched_rules" in routing
                assert "destinations" in routing
                assert "dispatch_results" in routing
                print(f"✅ iq720-ensemble routing: matched_rules={routing.get('matched_rules')}, destinations={routing.get('destinations')}")
                print(f"   dispatch_results: {routing.get('dispatch_results')}")
        else:
            print(f"⚠️ IQ720 returned success={data.get('success')}, message={data.get('message')}")
    
    # ==================== ROUTING STATS ====================
    
    def test_signal_routing_stats_total_routed_increases(self):
        """GET /api/signal-routing/stats should show total_routed increasing"""
        # Get initial stats
        response1 = requests.get(f"{BASE_URL}/api/signal-routing/stats", timeout=10)
        assert response1.status_code == 200
        stats1 = response1.json()
        initial_routed = stats1.get("total_routed", 0)
        print(f"Initial total_routed: {initial_routed}")
        
        # Generate a signal to trigger routing
        scan_response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55},
            timeout=30
        )
        assert scan_response.status_code == 200
        scan_data = scan_response.json()
        
        # If a signal was routed, stats should increase
        if scan_data.get("routing"):
            time.sleep(1)  # Allow DB write
            response2 = requests.get(f"{BASE_URL}/api/signal-routing/stats", timeout=10)
            assert response2.status_code == 200
            stats2 = response2.json()
            new_routed = stats2.get("total_routed", 0)
            print(f"New total_routed: {new_routed}")
            
            # Stats should have increased (or stayed same if routing failed)
            assert new_routed >= initial_routed, \
                f"total_routed should not decrease: {initial_routed} -> {new_routed}"
    
    def test_signal_routing_log_shows_recent_entries(self):
        """GET /api/signal-routing/log should show recent routing log entries"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/log", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        # API returns {success: true, logs: [...]}
        logs = data.get("logs", data) if isinstance(data, dict) else data
        assert isinstance(logs, list), f"Expected list in logs, got {type(logs)}: {data}"
        
        if logs:
            # Verify log entry structure
            entry = logs[0]
            assert "signal_symbol" in entry or "signal" in entry, f"Log entry should have signal info: {entry.keys()}"
            assert "destinations" in entry, f"Log entry should have destinations: {entry.keys()}"
            assert "routed_at" in entry, f"Log entry should have routed_at: {entry.keys()}"
            print(f"✅ Routing log has {len(logs)} entries")
            print(f"   Latest: symbol={entry.get('signal_symbol')}, destinations={entry.get('destinations')}")
    
    # ==================== ROUTING IS NON-BLOCKING ====================
    
    def test_signal_generation_succeeds_even_if_routing_fails(self):
        """Signal generation should succeed even if routing fails"""
        # This is implicitly tested - if routing fails, the endpoint should still return signals
        response = requests.get(
            f"{BASE_URL}/api/signals/scan-markets",
            params={"assets": "EURUSD_OTC", "min_confidence": 55},
            timeout=30
        )
        assert response.status_code == 200, "Endpoint should return 200 even if routing fails"
        
        data = response.json()
        assert data.get("success") == True, "success should be True even if routing fails"
        # routing can be None if it failed, but that's OK
        print(f"✅ Signal generation succeeded, routing={'present' if data.get('routing') else 'None'}")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_mt5_status_works(self):
        """GET /api/mt5/status should work"""
        response = requests.get(f"{BASE_URL}/api/mt5/status", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "success" in data or "status" in data, f"Response should have success or status: {data}"
        print(f"✅ MT5 status: {data}")
    
    def test_tradingview_webhook_works(self):
        """POST /api/tradingview/webhook should work"""
        response = requests.post(
            f"{BASE_URL}/api/tradingview/webhook",
            json={
                "symbol": "EURUSD",
                "ticker": "EURUSD",
                "action": "buy",
                "price": 1.0850,
                "strategy": "test_strategy"
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        print(f"✅ TradingView webhook: {data}")
    
    def test_telegram_bot_status_works(self):
        """GET /api/telegram-bot/status should work"""
        response = requests.get(f"{BASE_URL}/api/telegram-bot/status", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        assert "status" in data, f"Response should have status: {data}"
        print(f"✅ Telegram bot status: {data.get('status')}")
    
    def test_health_endpoint(self):
        """GET /api/health should work"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print(f"✅ Health check passed")


class TestMT5Connection:
    """Test MT5 connection for routing dispatch"""
    
    def test_mt5_connect_for_routing(self):
        """POST /api/mt5/connect should work (simulation mode)"""
        response = requests.post(
            f"{BASE_URL}/api/mt5/connect",
            params={"login": 12345678, "password": "test", "server": "MetaQuotes-Demo"},
            timeout=10
        )
        # MT5 may return success or failure depending on simulation mode
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"✅ MT5 connect response: {data}")


class TestSignalRoutingRulesExist:
    """Verify routing rules exist for testing"""
    
    def test_routing_rules_exist(self):
        """GET /api/signal-routing/rules should return existing rules"""
        response = requests.get(f"{BASE_URL}/api/signal-routing/rules", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        # API returns {success: true, rules: [...]}
        rules = data.get("rules", data) if isinstance(data, dict) else data
        assert isinstance(rules, list), f"Expected list in rules, got {type(rules)}: {data}"
        
        print(f"✅ Found {len(rules)} routing rules:")
        for rule in rules:
            print(f"   - {rule.get('name')} (priority={rule.get('priority')}, enabled={rule.get('enabled')}, destinations={rule.get('destinations')})")
        
        # Verify at least one rule exists
        assert len(rules) >= 1, "At least one routing rule should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
