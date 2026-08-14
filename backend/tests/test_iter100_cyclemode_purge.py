"""
Iter 100 — Regression guard for the P0 CYCLE bug fix.

Bug: The TM script's CYCLE feature was still opening the asset-picker
dropdown instead of rotating the user-taught favorites bar because the
legacy `cycleMode.js` module was still imported and auto-started inside
`src/index.js` alongside the new `favoritesCycle.js`.

Fix: Removed all `cycleMode` imports/references from `src/index.js`,
deleted `src/trading/cycleMode.js`, and rebuilt the bundle.

These tests fail LOUDLY if either:
  1. `cycleMode` sneaks back into the compiled bundle
  2. `favoritesCycle` is missing from the compiled bundle
  3. The public `/api/tampermonkey/script` endpoint serves a bundle
     that mentions the legacy cycle logic
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
MODULAR_BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader-modular.user.js")
LEGACY_MODULE_PATH = Path("/app/tampermonkey-src/src/trading/cycleMode.js")

# Prefer the internal service URL for local pytest runs.
BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")


class TestIter100CycleModePurge:
    """Guarantee legacy cycleMode.js is fully removed from the TM pipeline."""

    def test_legacy_cyclemode_source_file_is_deleted(self):
        assert not LEGACY_MODULE_PATH.exists(), (
            f"Legacy {LEGACY_MODULE_PATH} MUST stay deleted — "
            "it fights favoritesCycle.js for the CYCLE toggle."
        )

    def test_index_js_has_no_cyclemode_references(self):
        index_js = Path("/app/tampermonkey-src/src/index.js").read_text()
        assert "cycleMode" not in index_js and "CycleMode" not in index_js, (
            "src/index.js still references cycleMode — remove all imports, "
            "start()/stop() calls, and the window.eliteBotCycleMode alias."
        )

    def test_compiled_bundle_has_no_cyclemode(self):
        assert BUNDLE_PATH.exists(), f"Bundle missing at {BUNDLE_PATH}"
        text = BUNDLE_PATH.read_text()
        # allow the string "CYCLE" (the UX label) but not the module name
        assert "cycleMode" not in text, (
            "compiled bundle still contains 'cycleMode' — rebuild required "
            "(cd /app/tampermonkey-src && yarn build:deploy)."
        )

    def test_compiled_bundle_contains_favorites_cycle(self):
        text = BUNDLE_PATH.read_text()
        # favoritesCycle module logs a distinctive [favCycle] prefix
        assert "favCycle" in text, (
            "compiled bundle is missing favoritesCycle wiring — check that "
            "src/trading/favoritesCycle.js is imported by src/index.js."
        )

    def test_modular_bundle_matches(self):
        assert MODULAR_BUNDLE_PATH.exists(), "modular bundle missing"
        # both files should be identical (yarn build:deploy copies the same
        # output to both filenames)
        assert BUNDLE_PATH.read_bytes() == MODULAR_BUNDLE_PATH.read_bytes(), (
            "modular and canonical bundles diverged — re-run yarn build:deploy"
        )


class TestIter100BundleEndpoint:
    """The /api/tampermonkey/script endpoint must serve the cleaned bundle."""

    def test_endpoint_serves_cleaned_bundle(self):
        try:
            r = requests.get(f"{BASE_URL}/api/tampermonkey/script", timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200, r.status_code
        body = r.text
        # Any 8.130+ version proves the cleanup shipped and hasn't been rolled back.
        import re
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", body)
        assert m, "no @version header in served bundle"
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (major, minor, patch) >= (8, 130, 0), (
            f"endpoint served an older bundle ({major}.{minor}.{patch})"
        )
        assert "cycleMode" not in body, "endpoint served a bundle still containing cycleMode"
        assert "favCycle" in body, "endpoint served a bundle missing favoritesCycle"


class TestIter100TeachVisuals:
    """The new teach-mode visual helpers must be bundled and wired up."""

    def test_teach_visuals_module_bundled(self):
        text = BUNDLE_PATH.read_text()
        # unique symbols from teachVisuals.js
        assert "pobot_capture_pulse" in text, (
            "teachVisuals.js CSS keyframes not in bundle — did webpack rebuild?"
        )
        assert "pobot_teach_toast" in text, (
            "teachVisuals.js toast class not in bundle"
        )

    def test_chart_switch_toast_wired(self):
        text = BUNDLE_PATH.read_text()
        # showTeachToast call from chartTypeSwitcher.ensure() success branch
        assert "Chart →" in text or "Chart \\u2192" in text, (
            "chartTypeSwitcher no longer emits a success toast — check "
            "the ensure() 'switched' branch."
        )
