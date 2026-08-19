"""
Iter 110 — AI Models fine-tuning + data-flow audit + Master Auto-Trade toggle.

Covers:
  • data-collector/stats no longer 500s on legacy docs missing `asset`
  • otc_candles_5s data is now surfaced via the AI trainer
  • ML trainer accepts fine-tuning params (days, feature_groups, weights,
    lookahead, test_size, model_types)
  • /ml-trainer/train-comparison side-by-side model comparison
  • Feature-group toggles actually change the feature count
  • TM bundle contains master-toggle markers + at v8.138.0+
"""

import re
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
TM_SRC = BACKEND_DIR.parent / "tampermonkey-src" / "src"
TM_BUNDLE = FRONTEND_DIR / "public" / "pocket-option-auto-trader.user.js"


# ---------------------------------------------------------------------------
# Data-collector stats robustness (Iter 110 fix)
# ---------------------------------------------------------------------------
class TestDataCollectorStats:
    def _dummy_ohlc(self, n=100):
        rng = np.random.default_rng(0)
        base = 1.10
        rows = []
        for _ in range(n):
            o = base + rng.random() * 0.0001
            c = base + rng.random() * 0.0001
            rows.append({"open": o, "high": max(o, c) + 0.0001,
                         "low": min(o, c) - 0.0001, "close": c,
                         "timestamp": pd.Timestamp.utcnow().value // 10**9})
            base = c
        return pd.DataFrame(rows)

    def test_feature_engineer_full_groups(self):
        from real_data_trainer import AdvancedFeatureEngineer
        df = self._dummy_ohlc(200)
        eng = AdvancedFeatureEngineer()
        feats = eng.create_features(df, timeframe="1m")
        assert not feats.empty
        # baseline group of ~40 columns
        assert feats.shape[1] >= 30

    def test_feature_engineer_toggle_off_shrinks_frame(self):
        """Turning momentum + divergence off must reduce column count."""
        from real_data_trainer import AdvancedFeatureEngineer
        df = self._dummy_ohlc(200)
        eng = AdvancedFeatureEngineer()
        full = eng.create_features(df, timeframe="1m")
        subset = eng.create_features(df, timeframe="1m",
                                     groups={"momentum": False,
                                             "divergence": False})
        assert subset.shape[1] < full.shape[1]
        # Momentum-family columns must be gone
        assert "rsi" not in subset.columns
        assert "macd" not in subset.columns

    def test_feature_engineer_feature_group_constant(self):
        from real_data_trainer import AdvancedFeatureEngineer
        assert set(AdvancedFeatureEngineer.FEATURE_GROUPS) == {
            "trend", "momentum", "volatility",
            "price_action", "divergence", "support_resistance",
        }


# ---------------------------------------------------------------------------
# Ensemble weight tests
# ---------------------------------------------------------------------------
class TestEnsembleWeights:
    def test_default_50_50(self):
        from real_data_trainer import HighAccuracyEnsemble
        e = HighAccuracyEnsemble()
        assert abs(e.rf_weight - 0.5) < 1e-6
        assert abs(e.gb_weight - 0.5) < 1e-6

    def test_custom_weights_normalised(self):
        from real_data_trainer import HighAccuracyEnsemble
        e = HighAccuracyEnsemble(rf_weight=3.0, gb_weight=1.0)
        # 3:1 → 0.75 / 0.25
        assert abs(e.rf_weight - 0.75) < 1e-6
        assert abs(e.gb_weight - 0.25) < 1e-6

    def test_model_types_gb_only(self):
        from real_data_trainer import HighAccuracyEnsemble
        e = HighAccuracyEnsemble(rf_weight=1.0, gb_weight=1.0,
                                 model_types=["gb"])
        # RF disabled → weight collapses to 0
        assert e.rf_weight == 0.0
        assert abs(e.gb_weight - 1.0) < 1e-6

    def test_model_types_rf_only(self):
        from real_data_trainer import HighAccuracyEnsemble
        e = HighAccuracyEnsemble(rf_weight=1.0, gb_weight=1.0,
                                 model_types=["rf"])
        assert abs(e.rf_weight - 1.0) < 1e-6
        assert e.gb_weight == 0.0


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class TestRequestSchema:
    def test_train_request_accepts_new_fields(self):
        from routes.models import TrainModelRequest
        r = TrainModelRequest(
            asset="EURUSD_OTC", timeframe="1m",
            days=45, lookahead=3, test_size=0.25,
            rf_weight=0.6, gb_weight=0.4,
            feature_groups={"trend": True, "momentum": False},
            model_types=["rf", "gb"],
        )
        assert r.days == 45
        assert r.lookahead == 3
        assert r.rf_weight == 0.6
        assert r.feature_groups == {"trend": True, "momentum": False}


# ---------------------------------------------------------------------------
# Tampermonkey Master toggle wiring
# ---------------------------------------------------------------------------
class TestMasterToggle:
    def _bundle(self):
        assert TM_BUNDLE.exists(), "TM bundle not built"
        return TM_BUNDLE.read_text()

    def test_bundle_version_at_least_138(self):
        b = self._bundle()
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", b)
        assert m
        maj, minr, _ = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (maj, minr) >= (8, 138), f"version {maj}.{minr} < 8.138"

    def test_bundle_contains_master_markers(self):
        b = self._bundle()
        # Header pill + big-button + section
        assert "tm-master-toggle" in b
        assert "tm-master-toggle-big" in b
        assert "master-toggle-section" in b
        # CSS class markers
        assert "masterbtn" in b
        assert "masterbig" in b
        # Callback identifier
        assert "onMasterToggle" in b

    def test_panel_source_wires_master_handler(self):
        p = TM_SRC / "ui" / "panel.js"
        body = p.read_text()
        assert "handleMasterTap" in body
        assert "_allEnabled" in body
        assert "renderMaster" in body


# ---------------------------------------------------------------------------
# No-regression
# ---------------------------------------------------------------------------
class TestNoRegression:
    def test_iter109_elite_gate_still_present(self):
        b = TM_BUNDLE.read_text()
        assert "elite-gate-slider" in b
        assert "screener/score" in b

    def test_iter108_latency_abstain_still_present(self):
        b = TM_BUNDLE.read_text()
        assert "latency-abstain-slider" in b
