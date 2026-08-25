"""
Iter 114 — AI-Analysis tab fixes for TM script.

Users reported the AI tab was empty (no votes, no indicators, no data).
Two root causes:
  1. `/api/signals/preview` endpoint didn't exist → poller got 404 → votes empty
  2. `/api/signals/latest` returned `supporting_indicators` (string array) but
     no `indicators` dict → poller had nothing to map into the indicator grid

Fixes:
  A. New `GET /signals/preview` returns strategy votes {name, direction, confidence}
  B. `/signals/latest` now attaches an `indicators` dict built from:
     - Parsed "NAME (value)" pairs in supporting_indicators
     - Microstructure vpin/kyle_lambda/flow_imbalance/flow_streak
     - Accuracy-engine win_rate/n_trades
     - Trend strength + direction
  C. Poller normalises confidence 0-1 → 0-100 so the panel's `Math.round(conf)%`
     doesn't display "1%" for a 78% signal
"""

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
TM_SRC = BACKEND_DIR.parent / "tampermonkey-src" / "src"
TM_BUNDLE = FRONTEND_DIR / "public" / "pocket-option-auto-trader.user.js"


class TestSignalsPreviewEndpoint:
    def test_endpoint_source_registered(self):
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        assert '@router.get("/signals/preview")' in body
        assert "get_signal_preview" in body
        # Returns structured votes
        assert '"votes"' in body

    def test_endpoint_normalises_confidence_and_dedupes(self):
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        # Confidence > 1 divided by 100 (percent → fraction)
        assert "if conf > 1.0:" in body and "conf = conf / 100.0" in body
        # Dedupe by strategy name
        assert "seen: set = set()" in body

    def test_endpoint_never_returns_404(self):
        """Preview endpoint should always return a JSON body with a `votes` key,
        never a 404. Callers should be able to consume it unconditionally."""
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        # Except block returns dict, not raise
        assert '"success": False' in body and '"votes": []' in body


class TestLatestSignalIndicators:
    def test_indicators_dict_attached(self):
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        assert 'latest_signal["indicators"] = indicators' in body
        # Folds microstructure + accuracy + trend into the dict
        assert '"vpin", "kyle_lambda", "flow_imbalance", "flow_streak"' in body
        assert '"win_rate"' in body
        assert '"trend_strength"' in body

    def test_macd_histogram_renamed_to_macd_hist(self):
        """Panel expects `macd_hist` key. Backend must translate to match."""
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        assert 'key = "macd_hist"' in body

    def test_regex_requires_parentheses(self):
        """Tightened regex avoids garbage like 'SMA20 > SMA50' being read
        as `sma2 = 0`. Only 'NAME (value)' pairs count."""
        p = BACKEND_DIR / "routes" / "signals.py"
        body = p.read_text()
        assert r"([A-Za-z][A-Za-z0-9_]*)[^()]*\(([-+]?\d*\.?\d+)\)" in body


class TestPollerConfidenceNormalisation:
    def test_signal_confidence_normalised(self):
        p = TM_SRC / "trading" / "aiAnalysisPoller.js"
        body = p.read_text()
        # Multiply by 100 when 0 < conf <= 1
        assert "if (sconf > 0 && sconf <= 1) sconf *= 100" in body

    def test_vote_confidence_normalised(self):
        p = TM_SRC / "trading" / "aiAnalysisPoller.js"
        body = p.read_text()
        assert "if (conf > 0 && conf <= 1) conf *= 100" in body


class TestBundleShip:
    def test_bundle_version_at_least_140(self):
        b = TM_BUNDLE.read_text()
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", b)
        assert m
        maj, minr, _ = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (maj, minr) >= (8, 140), f"version {maj}.{minr} < 8.140"

    def test_bundle_contains_normalisation_logic(self):
        b = TM_BUNDLE.read_text()
        # Class name is minified in prod build. Look for the endpoint + logic
        # marker that we know made it through (the `signals/preview` fetch).
        assert "signals/preview" in b
        # The confidence normalisation multiplication pattern
        assert "*=100" in b or "*= 100" in b


class TestEndpointIntegration:
    """Integration test — hits the actual live endpoint through the process."""
    def test_preview_endpoint_returns_shape(self):
        import asyncio
        from routes.signals import get_signal_preview
        r = asyncio.run(get_signal_preview(asset="EURUSD_OTC",
                                           timeframe="1m", limit=6))
        assert r["success"] is True
        assert "votes" in r and isinstance(r["votes"], list)
        assert "count" in r


class TestNoRegression:
    def test_iter113_diag_buttons_intact(self):
        b = TM_BUNDLE.read_text()
        assert "btn-invert-diag" in b
        assert "btn-invert-test" in b

    def test_iter112_auto_scan_intact(self):
        p = BACKEND_DIR / "auto_scan_service.py"
        assert p.exists()

    def test_iter111_microstructure_fix_intact(self):
        p = BACKEND_DIR / "microstructure_models.py"
        body = p.read_text()
        assert '"symbol": {"$in":' in body
