"""
Iteration 43 — 21-Second Reversal Strategy Tests
 - Backend: Strategy1m21sReversal direction/neutral behavior
 - Backend: strategy_registry.execute_strategy('1m_21s_reversal')
 - API: GET /api/strategies/available/1m includes '1m_21s_reversal'
 - Assets: Tampermonkey modular and legacy user scripts served 200
 - Assets: Modular bundle contains 21s-Reversal logic markers + v8.9.0
"""

import os
import sys
import pytest
import requests
import pandas as pd

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auto-invert-engine.preview.emergentagent.com').rstrip('/')

# Ensure backend package import works
sys.path.insert(0, '/app/backend')


# -- Direct strategy module tests ----------------------------------------------
class TestStrategyModuleDirect:
    """Unit-level tests for Strategy1m21sReversal (in-process)"""

    def test_up_candle_returns_put(self):
        from strategies.strategy_1m_21s_reversal import strategy_1m_21s_reversal
        df = pd.DataFrame([{
            'open': 1.0800, 'high': 1.0825, 'low': 1.0795, 'close': 1.0815, 'volume': 50
        }])
        sig = strategy_1m_21s_reversal.generate_signal(df)
        assert sig['direction'] == 'PUT', f"Expected PUT, got {sig}"
        assert sig['strategy'] == '1m 21s Reversal'
        assert sig['expiry_seconds'] == 5
        assert sig['fire_at_seconds_remaining'] == 21
        assert sig['cooldown_candles'] == 1
        assert 'body_ratio' in sig and 'body_bps' in sig
        assert 55 <= sig['confidence'] <= 78

    def test_down_candle_returns_call(self):
        from strategies.strategy_1m_21s_reversal import strategy_1m_21s_reversal
        df = pd.DataFrame([{
            'open': 1.0820, 'high': 1.0822, 'low': 1.0800, 'close': 1.0805, 'volume': 50
        }])
        sig = strategy_1m_21s_reversal.generate_signal(df)
        assert sig['direction'] == 'CALL', f"Expected CALL, got {sig}"
        assert sig['expiry_seconds'] == 5

    def test_flat_candle_returns_neutral(self):
        from strategies.strategy_1m_21s_reversal import strategy_1m_21s_reversal
        df = pd.DataFrame([{
            'open': 1.0800, 'high': 1.0801, 'low': 1.0799, 'close': 1.0800, 'volume': 50
        }])
        sig = strategy_1m_21s_reversal.generate_signal(df)
        assert sig['direction'] == 'NEUTRAL'
        assert sig['confidence'] == 0
        assert 'Body too small' in sig['reason']


# -- Registry integration ------------------------------------------------------
class TestStrategyRegistryIntegration:
    def test_registry_has_21s_reversal(self):
        from strategy_registry import strategy_registry
        assert '1m_21s_reversal' in strategy_registry.strategies
        strat = strategy_registry.get_strategy('1m_21s_reversal')
        assert strat is not None
        assert strat.timeframe == '1m'

    def test_registry_execute_up_to_put(self):
        from strategy_registry import strategy_registry
        df = pd.DataFrame([{
            'open': 1.0800, 'high': 1.0825, 'low': 1.0795, 'close': 1.0815, 'volume': 50
        }])
        result = strategy_registry.execute_strategy('1m_21s_reversal', df)
        assert isinstance(result, dict)
        assert result['direction'] == 'PUT'
        assert result.get('confidence', 0) > 0


# -- Public HTTP API -----------------------------------------------------------
class TestAvailableStrategiesAPI:
    def test_available_1m_contains_21s_reversal(self):
        r = requests.get(f"{BASE_URL}/api/strategies/available/1m", timeout=15)
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        data = r.json()
        # Response may be {strategies:[...]} or a bare list
        strategies = data.get('strategies') if isinstance(data, dict) else data
        assert isinstance(strategies, list) and len(strategies) > 0
        ids = [s.get('id') for s in strategies]
        assert '1m_21s_reversal' in ids, f"missing 1m_21s_reversal in {ids}"

        match = next(s for s in strategies if s.get('id') == '1m_21s_reversal')
        assert '21-Second Reversal' in match.get('name', ''), \
            f"name should contain '21-Second Reversal', got {match.get('name')}"


# -- Tampermonkey assets -------------------------------------------------------
class TestTampermonkeyAssets:
    def test_modular_script_served_200(self):
        r = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=20)
        assert r.status_code == 200
        assert '==UserScript==' in r.text

    def test_legacy_script_served_200(self):
        r = requests.get(f"{BASE_URL}/pocket-option-auto-trader.user.js", timeout=20)
        assert r.status_code == 200
        assert '==UserScript==' in r.text

    def test_modular_version_is_8_9_0(self):
        r = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=20)
        assert r.status_code == 200
        assert '@version      8.9.0' in r.text or '@version 8.9.0' in r.text or '8.9.0' in r.text[:2000]

    def test_modular_contains_21s_logic_markers(self):
        r = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=20)
        assert r.status_code == 200
        body = r.text
        # String literals preserved in bundle
        required_substrings = [
            '21s-Reversal',           # log prefix
            '_attemptFire',           # core fire method referenced
            '_minuteOfNow',           # minute alignment helper
            'r21s',                   # panel button ID/class
            '1m_21s_reversal',        # strategy tag for backend reporting
            'on21sReversalToggle',    # exposed panel hook
            'eliteBot21sReversal',    # window global exposure
        ]
        missing = [s for s in required_substrings if s not in body]
        assert not missing, f"missing markers in modular bundle: {missing}"

    def test_modular_contains_timing_constants(self):
        """Webpack may minify 21_000 → 21e3 and 60_000 → 6e4; check either form."""
        r = requests.get(f"{BASE_URL}/pocket-option-auto-trader-modular.user.js", timeout=20)
        body = r.text
        # 21-second-left target
        assert ('21000' in body) or ('21e3' in body), "missing FIRE_AT_MS_LEFT 21000/21e3"
        # 120s cooldown (1 candle skip) or its minified form
        assert ('120000' in body) or ('12e4' in body), \
            "missing 120000/12e4 cooldown marker"
        # Min body bps filter (0.8 or minified .8 form)
        assert ('0.8' in body) or ('<.8' in body) or ('<0.8' in body), \
            "missing MIN_BODY_BPS 0.8 filter"
        # Asset rotation helper
        assert 'rotationAssets' in body, "missing rotationAssets pool"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
