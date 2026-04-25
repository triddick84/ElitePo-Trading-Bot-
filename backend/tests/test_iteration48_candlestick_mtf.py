"""
Iteration 48 backend regression tests.

Scope: validates the Apr 24, 2026 expansion of MLAccuracyTuner.extract_5s_features()
with three new feature groups (candlestick patterns, multi-timeframe fusion,
volume validation) plus the SelectKBest k bump from 50 -> 70.

Also re-runs core regression on signal generation, trade reporting, win-rate
stats and trade outcome endpoints to ensure no behavioural drift was introduced
by the feature pipeline expansion.
"""

import os
import sys
import math
import uuid
import time
import asyncio
import importlib

import numpy as np
import pandas as pd
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fallback: read from /app/frontend/.env
    try:
        with open('/app/frontend/.env', 'r') as fp:
            for line in fp:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                    break
    except Exception:
        pass

assert BASE_URL, "REACT_APP_BACKEND_URL not configured"

# Make backend importable for direct unit calls on the tuner
sys.path.insert(0, '/app/backend')


# =========================================================================
# /api/ml/tuning-report endpoint tests
# =========================================================================

@pytest.fixture(scope='module')
def tuning_report():
    r = requests.get(f"{BASE_URL}/api/ml/tuning-report", timeout=30)
    assert r.status_code == 200, f"tuning-report status={r.status_code} body={r.text[:300]}"
    return r.json()


class TestTuningReportEndpoint:
    """Verify the /api/ml/tuning-report exposes the new candlestick+MTF group."""

    def test_success_flag_true(self, tuning_report):
        assert tuning_report.get('success') is True

    def test_feature_selection_k70(self, tuning_report):
        cfg = tuning_report.get('tuning_config', {})
        fs = cfg.get('feature_selection', '')
        assert 'k=70' in fs, f"Expected 'k=70' in feature_selection, got: {fs!r}"

    def test_candlestick_mtf_apr24_block_present(self, tuning_report):
        cfg = tuning_report.get('tuning_config', {})
        block = cfg.get('candlestick_mtf_apr24')
        assert isinstance(block, dict), "candlestick_mtf_apr24 missing or not a dict"

        # Sub-groups
        assert 'candlestick_patterns' in block
        assert 'multi_timeframe_fusion' in block
        assert 'volume_validation' in block

        # Counts per spec
        assert len(block['candlestick_patterns']) == 19, \
            f"candlestick_patterns expected 19 items, got {len(block['candlestick_patterns'])}"
        assert len(block['multi_timeframe_fusion']) == 14, \
            f"multi_timeframe_fusion expected 14 items, got {len(block['multi_timeframe_fusion'])}"
        assert len(block['volume_validation']) == 4, \
            f"volume_validation expected 4 items, got {len(block['volume_validation'])}"

        # Metadata
        assert block.get('k_bumped_to') == 70
        assert block.get('added_on') == '2026-04-24'

    def test_apr23_features_preserved(self, tuning_report):
        cfg = tuning_report.get('tuning_config', {})
        old = cfg.get('new_features_apr23')
        assert isinstance(old, list)
        assert len(old) == 13, f"new_features_apr23 should still have 13 items, got {len(old)}"
        # Spot-check a couple of expected names
        for key in ('fib_impulse_up', 'fib_dist_618', 'volume_osc', 'volume_spike'):
            assert key in old, f"{key} missing from new_features_apr23 (regression!)"

    def test_otc_data_block_intact(self, tuning_report):
        otc = tuning_report.get('otc_data')
        assert isinstance(otc, dict)
        assert 'total_candles' in otc and isinstance(otc['total_candles'], int)
        assert 'by_symbol' in otc and isinstance(otc['by_symbol'], list)
        assert otc.get('min_required') == 200
        assert isinstance(otc.get('ready_for_training'), bool)


# =========================================================================
# Direct unit test on MLAccuracyTuner.extract_5s_features()
# =========================================================================

class FakeDB:
    """Minimal stand-in: extract_5s_features doesn't use db, only the constructor."""
    def __getitem__(self, key):
        return None


def _synthetic_ohlcv(rows: int = 80, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = 1.1000
    closes = base + np.cumsum(rng.normal(0, 0.0004, rows))
    opens = np.concatenate([[base], closes[:-1]])
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0, 0.0002, rows))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0, 0.0002, rows))
    volumes = rng.integers(800, 1500, rows).astype(float)
    timestamps = pd.date_range('2026-04-24 10:00:00', periods=rows, freq='5s')
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    })


@pytest.fixture(scope='module')
def tuner():
    from ml_accuracy_tuner import MLAccuracyTuner
    return MLAccuracyTuner(FakeDB())


class TestExtract5sFeaturesUnit:
    """Direct unit-level tests on the feature extraction pipeline."""

    def test_returns_dict_at_idx75(self, tuner):
        df = _synthetic_ohlcv(80)
        feats = tuner.extract_5s_features(df, 75)
        assert isinstance(feats, dict)
        assert len(feats) >= 85, f"expected >=85 features, got {len(feats)}"

    def test_contains_cdl_mtf_vol_fib_keys(self, tuner):
        df = _synthetic_ohlcv(80)
        feats = tuner.extract_5s_features(df, 75)
        keys = list(feats.keys())
        assert any(k.startswith('cdl_') for k in keys), "no cdl_* keys"
        assert any(k.startswith('mtf_') for k in keys), "no mtf_* keys"
        assert any(k.startswith('vol_') for k in keys), "no vol_* keys"
        assert any(k.startswith('fib_') for k in keys), "no fib_* keys"

    def test_no_nan_or_inf(self, tuner):
        df = _synthetic_ohlcv(80)
        feats = tuner.extract_5s_features(df, 75)
        bad = []
        for k, v in feats.items():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                bad.append((k, v, 'not-numeric'))
                continue
            if math.isnan(fv) or math.isinf(fv):
                bad.append((k, v, 'nan-or-inf'))
        assert not bad, f"NaN/Inf/non-numeric features: {bad[:5]}"

    def test_pattern_score_present(self, tuner):
        df = _synthetic_ohlcv(80)
        feats = tuner.extract_5s_features(df, 75)
        assert 'cdl_pattern_score' in feats
        assert 'mtf_trend_strength' in feats
        assert 'vol_ratio_20' in feats


# =========================================================================
# Backend regression: signals + trades endpoints
# =========================================================================

class TestSignalsRegression:
    """Re-validate iteration 47 surface stays intact after the feature wiring."""

    def test_force_generate_v2_envelope(self):
        payload = {"symbol": "EURUSD_OTC", "timeframe": "5s"}
        r = requests.post(
            f"{BASE_URL}/api/signals/force-generate-v2",
            json=payload,
            timeout=60,
        )
        assert r.status_code == 200, f"force-generate-v2 status={r.status_code} body={r.text[:300]}"
        data = r.json()
        # Some envs return {"success": true, "signal": {...}}; some flatten — handle both
        sig = data.get('signal', data)
        assert sig is not None
        # Required keys per review
        for key in ('direction', 'confidence', 'quality', 'agreeing_strategies', 'components', 'votes'):
            assert key in sig, f"signal missing key: {key}"
        # beta key — mandated by iteration 47 regression
        assert 'beta' in sig, "signal.beta missing (iteration 47 regression)"
        assert isinstance(sig['beta'], bool), f"signal.beta should be bool, got {type(sig['beta'])}"

    def test_win_rate_stats(self):
        r = requests.get(f"{BASE_URL}/api/signals/win-rate-stats", timeout=30)
        assert r.status_code == 200, f"win-rate-stats status={r.status_code} body={r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)
        # Should have at least success or stats payload
        assert data.get('success') is True or 'overall' in data or 'stats' in data or 'rolling' in data, \
            f"unexpected win-rate-stats shape: {list(data.keys())[:8]}"


class TestTradesRegression:
    """Trade reporting + outcome update endpoints — must remain 200 OK."""

    @pytest.fixture(scope='class')
    def reported_trade(self):
        tag = f"TEST_ITER48_{uuid.uuid4().hex[:8]}"
        payload = {
            "asset": "EURUSD_OTC",
            "direction": "CALL",
            "amount": 1.0,
            "strategy": tag,
            "confidence": 72.5,
            "source": "iteration48_test",
            "timestamp": str(int(time.time() * 1000)),
        }
        r = requests.post(f"{BASE_URL}/api/trades/report", json=payload, timeout=30)
        assert r.status_code == 200, f"trades/report status={r.status_code} body={r.text[:300]}"
        body = r.json()
        assert body.get('success') is True, f"trades/report success false: {body}"
        return tag

    def test_trades_report_ok(self, reported_trade):
        assert reported_trade.startswith('TEST_ITER48_')

    def test_trades_outcome_ok(self, reported_trade):
        payload = {
            "outcome": "WIN",
            "asset": "EURUSD_OTC",
            "strategy": reported_trade,
            "profit": 0.85,
        }
        r = requests.post(f"{BASE_URL}/api/trades/outcome", json=payload, timeout=30)
        assert r.status_code == 200, f"trades/outcome status={r.status_code} body={r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)
        assert data.get('success') is True, f"trades/outcome non-success: {data}"
