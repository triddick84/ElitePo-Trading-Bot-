"""
Iter 113 — Auto-Invert engine hardening.

Users reported auto-invert never firing after consecutive losses. Root cause
was silent early-returns from guards (no observability). This iter adds:
  • Loud WARN logs on every guard so users see WHY it doesn't fire
  • `smartInvert.diagnose()` — snapshot of every gate condition
  • `smartInvert.runSelfTest()` — simulates losses, confirms flip works
  • Panel Config-tab "Diag" + "Test Flip" buttons + inline status line
  • window.__aiEliteInvertDiag() / __aiEliteInvertTest() console helpers
"""

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
TM_SRC = BACKEND_DIR.parent / "tampermonkey-src" / "src"
TM_BUNDLE = FRONTEND_DIR / "public" / "pocket-option-auto-trader.user.js"


class TestSmartInvertHardening:
    def test_source_has_diagnose_and_selftest(self):
        p = TM_SRC / "trading" / "smartInvert.js"
        body = p.read_text()
        assert "diagnose()" in body
        assert "runSelfTest" in body
        assert "blockers" in body
        assert "wouldFire" in body

    def test_source_warns_on_every_guard(self):
        """Every early-return in evaluateInversion must surface a WARN so
        users can debug from the console."""
        p = TM_SRC / "trading" / "smartInvert.js"
        body = p.read_text()
        assert "BLOCKED — CONFIG.AUTO_INVERT_ENABLED is false" in body
        assert "BLOCKED — state.autoInvertEnabled is false" in body
        assert "BLOCKED — manualOverride is true" in body

    def test_index_exposes_window_helpers(self):
        p = TM_SRC / "index.js"
        body = p.read_text()
        assert "__aiEliteInvertDiag" in body
        assert "__aiEliteInvertTest" in body
        # And the callbacks wired for panel buttons
        assert "onAutoInvertDiagnose" in body
        assert "onAutoInvertSelfTest" in body

    def test_panel_has_diag_and_test_buttons(self):
        p = TM_SRC / "ui" / "panel.js"
        body = p.read_text()
        assert 'data-testid="btn-invert-diag"' in body
        assert 'data-testid="btn-invert-test"' in body
        assert "invDiag" in body
        assert "invSelfTest" in body
        assert "invDiagOut" in body


class TestBundleShip:
    def test_bundle_version_at_least_139(self):
        b = TM_BUNDLE.read_text()
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", b)
        assert m
        maj, minr, _ = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (maj, minr) >= (8, 139), f"version {maj}.{minr} < 8.139"

    def test_bundle_contains_new_markers(self):
        b = TM_BUNDLE.read_text()
        for marker in ("btn-invert-diag", "btn-invert-test",
                       "__aiEliteInvertDiag", "__aiEliteInvertTest",
                       "AutoInvert",  # log tag
                       "BLOCKED — CONFIG"):
            assert marker in b, f"missing {marker}"


class TestNoRegression:
    def test_iter112_auto_scan_intact(self):
        p = BACKEND_DIR / "auto_scan_service.py"
        body = p.read_text()
        assert "class AutoScanService" in body

    def test_iter111_microstructure_fix_intact(self):
        p = BACKEND_DIR / "microstructure_models.py"
        body = p.read_text()
        assert '"symbol": {"$in":' in body

    def test_iter110_master_toggle_intact(self):
        b = TM_BUNDLE.read_text()
        assert "tm-master-toggle" in b
