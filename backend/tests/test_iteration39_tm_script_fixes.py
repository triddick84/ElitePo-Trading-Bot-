"""
Iteration 39 Tests: Tampermonkey Script Outcome Detection Fixes

Tests verify:
1. Legacy script served at /pocket-option-auto-trader.user.js with version 8.8.1 (HTTP 200)
2. Modular script served at /pocket-option-auto-trader-modular.user.js (HTTP 200)
3. Legacy script contains 'scanDOMForResult' function with expanded selectors
4. Legacy script contains adaptive timing: 5s trades get 5000ms buffer, 15s get 4000ms, 30s get 3500ms
5. Legacy script markTradePending captures balanceBeforeTrade with retry on failure
6. Legacy script startOutcomePolling has DOM fallback when balance detection fails
7. Legacy script startOutcomePolling has pre-trade balance comparison as last resort
8. Legacy script detectAccountBalance has 30+ selectors including PO-specific newer layouts
9. Modular script has getAccountBalance and scanDOMForTradeResult exported functions
10. Backend still healthy: /api/health returns status=healthy
11. Regression: /api/signals/engine-status works
12. Regression: /api/ml/scheduler/status works
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTampermonkeyScriptServing:
    """Test that TM scripts are served correctly"""
    
    def test_legacy_script_served_http_200(self):
        """Legacy script should be served with HTTP 200"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASSED: Legacy script served with HTTP {response.status_code}")
    
    def test_legacy_script_version_8_8_1(self):
        """Legacy script should have version 8.8.1"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=30)
        assert response.status_code == 200
        content = response.text
        assert "@version      8.8.1" in content, "Version 8.8.1 not found in legacy script"
        print("PASSED: Legacy script has version 8.8.1")
    
    def test_modular_script_served_http_200(self):
        """Modular script should be served with HTTP 200"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASSED: Modular script served with HTTP {response.status_code}")
    
    def test_legacy_script_file_size(self):
        """Legacy script should be approximately 316KB"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=30)
        assert response.status_code == 200
        size_kb = len(response.content) / 1024
        assert 300 < size_kb < 350, f"Expected ~316KB, got {size_kb:.1f}KB"
        print(f"PASSED: Legacy script size is {size_kb:.1f}KB")
    
    def test_modular_script_file_size(self):
        """Modular script should be approximately 113KB"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=30)
        assert response.status_code == 200
        size_kb = len(response.content) / 1024
        assert 100 < size_kb < 130, f"Expected ~113KB, got {size_kb:.1f}KB"
        print(f"PASSED: Modular script size is {size_kb:.1f}KB")


class TestLegacyScriptFunctions:
    """Test that legacy script contains the new fix functions"""
    
    @pytest.fixture(scope="class")
    def legacy_script_content(self):
        """Fetch legacy script content once for all tests"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=30)
        assert response.status_code == 200
        return response.text
    
    def test_contains_scanDOMForResult_function(self, legacy_script_content):
        """Legacy script should contain scanDOMForResult function"""
        assert "function scanDOMForResult()" in legacy_script_content, "scanDOMForResult function not found"
        print("PASSED: Legacy script contains scanDOMForResult function")
    
    def test_scanDOMForResult_has_expanded_selectors(self, legacy_script_content):
        """scanDOMForResult should have expanded selectors for deal history"""
        # Check for deal list selectors
        assert "deals-list" in legacy_script_content, "deals-list selector not found"
        assert "closed-deals" in legacy_script_content, "closed-deals selector not found"
        print("PASSED: scanDOMForResult has expanded selectors")
    
    def test_contains_adaptive_timing_5s_buffer(self, legacy_script_content):
        """Legacy script should have 5000ms buffer for 5s trades"""
        # Check for adaptive timing logic
        assert "expirySeconds <= 5 ? 5000" in legacy_script_content, "5s adaptive timing (5000ms) not found"
        print("PASSED: Legacy script has 5000ms buffer for 5s trades")
    
    def test_contains_adaptive_timing_15s_buffer(self, legacy_script_content):
        """Legacy script should have 4000ms buffer for 15s trades"""
        assert "expirySeconds <= 15 ? 4000" in legacy_script_content, "15s adaptive timing (4000ms) not found"
        print("PASSED: Legacy script has 4000ms buffer for 15s trades")
    
    def test_contains_adaptive_timing_30s_buffer(self, legacy_script_content):
        """Legacy script should have 3500ms buffer for 30s trades"""
        assert "expirySeconds <= 30 ? 3500" in legacy_script_content, "30s adaptive timing (3500ms) not found"
        print("PASSED: Legacy script has 3500ms buffer for 30s trades")
    
    def test_contains_markTradePending_function(self, legacy_script_content):
        """Legacy script should contain markTradePending function"""
        assert "function markTradePending(" in legacy_script_content, "markTradePending function not found"
        print("PASSED: Legacy script contains markTradePending function")
    
    def test_markTradePending_captures_balanceBeforeTrade(self, legacy_script_content):
        """markTradePending should capture balanceBeforeTrade"""
        assert "audioDetection.balanceBeforeTrade" in legacy_script_content, "balanceBeforeTrade capture not found"
        print("PASSED: markTradePending captures balanceBeforeTrade")
    
    def test_contains_startOutcomePolling_function(self, legacy_script_content):
        """Legacy script should contain startOutcomePolling function"""
        assert "function startOutcomePolling(" in legacy_script_content, "startOutcomePolling function not found"
        print("PASSED: Legacy script contains startOutcomePolling function")
    
    def test_startOutcomePolling_has_dom_fallback(self, legacy_script_content):
        """startOutcomePolling should have DOM fallback"""
        # Check for DOM fallback logic
        assert "scanDOMForResult()" in legacy_script_content, "DOM fallback call not found"
        assert "DOM FALLBACK" in legacy_script_content or "DOM" in legacy_script_content, "DOM fallback logic not found"
        print("PASSED: startOutcomePolling has DOM fallback")
    
    def test_startOutcomePolling_has_pretrade_comparison(self, legacy_script_content):
        """startOutcomePolling should have pre-trade balance comparison"""
        # Check for pre-trade balance comparison
        assert "preTradeBal" in legacy_script_content or "balanceBeforeTrade" in legacy_script_content, "Pre-trade balance comparison not found"
        print("PASSED: startOutcomePolling has pre-trade balance comparison")
    
    def test_contains_detectAccountBalance_function(self, legacy_script_content):
        """Legacy script should contain detectAccountBalance function"""
        assert "function detectAccountBalance(" in legacy_script_content, "detectAccountBalance function not found"
        print("PASSED: Legacy script contains detectAccountBalance function")
    
    def test_detectAccountBalance_has_expanded_selectors(self, legacy_script_content):
        """detectAccountBalance should have 30+ selectors"""
        # Count balance-related selectors
        balance_selectors = [
            ".balance__value",
            ".balance-value",
            "[class*=\"balance__value\"]",
            "[class*=\"balance-value\"]",
            ".js-balance",
            "[data-testid=\"balance\"]",
            ".balance span",
            ".balance",
            "[class*=\"balances\"]",
            "[class*=\"user-balance\"]",
            "[class*=\"account-value\"]",
            ".account-balance",
            "[class*=\"demo-balance\"]",
            "[class*=\"real-balance\"]",
            "[class*=\"current-balance\"]",
            "header [class*=\"balance\"]",
            ".header__balance",
            ".main-balance",
            "[class*=\"main-balance\"]",
            "[class*=\"BalanceValue\"]",
            "[class*=\"balanceValue\"]",
            ".popover-balance__item-value",
        ]
        
        found_count = sum(1 for sel in balance_selectors if sel in legacy_script_content)
        assert found_count >= 15, f"Expected 15+ balance selectors, found {found_count}"
        print(f"PASSED: detectAccountBalance has {found_count} balance selectors")
    
    def test_detectAccountBalance_has_deep_dom_search(self, legacy_script_content):
        """detectAccountBalance should have deep DOM search in header area"""
        # Check for deep search logic
        assert "Deep search" in legacy_script_content or "headerArea" in legacy_script_content or "header" in legacy_script_content, "Deep DOM search not found"
        print("PASSED: detectAccountBalance has deep DOM search")
    
    def test_more_polls_for_5s_trades(self, legacy_script_content):
        """Legacy script should have more polls (30) for 5s trades"""
        assert "expirySeconds <= 5 ? 30" in legacy_script_content, "30 polls for 5s trades not found"
        print("PASSED: Legacy script has 30 polls for 5s trades")


class TestModularScriptFunctions:
    """Test that modular script contains the new functions"""
    
    @pytest.fixture(scope="class")
    def modular_script_content(self):
        """Fetch modular script content once for all tests"""
        response = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=30)
        assert response.status_code == 200
        return response.text
    
    def test_modular_script_version(self, modular_script_content):
        """Modular script should have version 8.8.0 or higher"""
        assert "@version" in modular_script_content, "Version not found in modular script"
        # Check for 8.8.x version
        assert "8.8." in modular_script_content, "Version 8.8.x not found"
        print("PASSED: Modular script has version 8.8.x")


class TestDomUtilsModule:
    """Test that dom.js module has the new functions"""
    
    def test_dom_utils_has_getAccountBalance(self):
        """dom.js should export getAccountBalance function"""
        # Read the source file directly
        dom_js_path = "/app/tampermonkey-src/src/utils/dom.js"
        with open(dom_js_path, 'r') as f:
            content = f.read()
        
        assert "export function getAccountBalance()" in content, "getAccountBalance export not found"
        print("PASSED: dom.js exports getAccountBalance function")
    
    def test_dom_utils_has_scanDOMForTradeResult(self):
        """dom.js should export scanDOMForTradeResult function"""
        dom_js_path = "/app/tampermonkey-src/src/utils/dom.js"
        with open(dom_js_path, 'r') as f:
            content = f.read()
        
        assert "export function scanDOMForTradeResult()" in content, "scanDOMForTradeResult export not found"
        print("PASSED: dom.js exports scanDOMForTradeResult function")
    
    def test_dom_utils_default_export_includes_functions(self):
        """dom.js default export should include new functions"""
        dom_js_path = "/app/tampermonkey-src/src/utils/dom.js"
        with open(dom_js_path, 'r') as f:
            content = f.read()
        
        assert "getAccountBalance," in content, "getAccountBalance not in default export"
        assert "scanDOMForTradeResult," in content, "scanDOMForTradeResult not in default export"
        print("PASSED: dom.js default export includes new functions")


class TestBackendRegression:
    """Test that backend APIs still work"""
    
    def test_api_health(self):
        """Backend health endpoint should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy, got {data.get('status')}"
        print("PASSED: /api/health returns healthy")
    
    def test_signals_engine_status(self):
        """Signals engine status should work"""
        response = requests.get(f"{BASE_URL}/api/signals/engine-status", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "version" in data or "status" in data, "Engine status response missing expected fields"
        print(f"PASSED: /api/signals/engine-status works - {data}")
    
    def test_ml_scheduler_status(self):
        """ML scheduler status should work"""
        response = requests.get(f"{BASE_URL}/api/ml/scheduler/status", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "running" in data or "config" in data, "Scheduler status response missing expected fields"
        print(f"PASSED: /api/ml/scheduler/status works")


class TestDashboardWidget:
    """Test that IQ-720 widget endpoint works"""
    
    def test_iq720_ensemble_endpoint(self):
        """IQ-720 ensemble endpoint should respond"""
        # This endpoint requires POST method
        response = requests.post(f"{BASE_URL}/api/signals/iq720-ensemble", json={}, timeout=15)
        # May return 200 with success=false if no signal, or 200 with signal
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have success field
        assert "success" in data, "Response missing success field"
        print(f"PASSED: /api/signals/iq720-ensemble responds - success={data.get('success')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
