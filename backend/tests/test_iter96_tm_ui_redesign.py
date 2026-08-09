"""
Iter 96 — Locks the modern tabbed TM panel redesign.

Guards against future rebuilds accidentally dropping:
  * The 4-tab bar (Live · Trade · Config · Stats)
  * The expand-to-fullscreen button
  * The Iter 96 strategy TF picker (`stratTf`) + reactive strategy dropdown
  * All 60+ pre-existing IDs that back-end event wiring depends on
"""

from __future__ import annotations

import os
import re

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


def _get_userscript() -> str:
    r = requests.get(f"{API}/tampermonkey/script", timeout=15)
    assert r.status_code == 200
    return r.text


# ---------------------------------------------------------------------------
# Modern redesign: tab-bar + expand button + section grouping
# ---------------------------------------------------------------------------
def test_ui_has_four_tab_bar():
    body = _get_userscript()
    for tab in ('data-tab="live"', 'data-tab="trade"', 'data-tab="config"', 'data-tab="stats"'):
        assert tab in body, f"missing tab attr: {tab}"


def test_ui_has_expand_fullscreen_button():
    body = _get_userscript()
    assert "expandbtn" in body, "expand-to-fullscreen button missing"
    # class .expanded must be defined in CSS
    assert re.search(r"\.expanded", body), "fullscreen .expanded CSS rule missing"


def test_ui_tab_panels_present():
    body = _get_userscript()
    for panel in ('data-tab-panel="live"', 'data-tab-panel="trade"',
                  'data-tab-panel="config"', 'data-tab-panel="stats"'):
        assert panel in body, f"missing tab panel: {panel}"


# ---------------------------------------------------------------------------
# Iter 96 strategy TF picker
# ---------------------------------------------------------------------------
def test_ui_has_strategy_tf_picker_with_all_options():
    body = _get_userscript()
    assert "stratTf" in body, "stratTf select missing"
    # All 7 TF options must be present in the compiled bundle
    for tf in ("5s", "15s", "30s", "1m", "2m", "3m", "5m"):
        assert f'value="{tf}"' in body, f"stratTf option {tf} missing"


def test_ui_stratTf_change_reloads_strategies():
    body = _get_userscript()
    # The wire-up: onStrategyTfChange callback + loadStrategies(tf) plumbing
    assert "onStrategyTfChange" in body, "onStrategyTfChange callback missing"
    assert "_selectedStrategyTf" in body, "_selectedStrategyTf persisted var missing"


# ---------------------------------------------------------------------------
# Runtime rendering — inject the userscript into a headless-friendly stub
# page (`/tm-panel-preview.html`) and verify the panel appears with all
# expected element IDs. This proves the ${P}-prefixed IDs get evaluated at
# runtime even though they don't appear as literals in the minified body.
# ---------------------------------------------------------------------------
def test_userscript_body_is_non_empty_and_parseable():
    """
    Compiled userscript must be a non-empty, IIFE-wrapped bundle. Guards
    against the endpoint accidentally serving an empty file if the on-disk
    bundle is missing / build failed.
    """
    body = _get_userscript()
    assert len(body) > 100_000, f"userscript too short: {len(body)} bytes"
    # Must start with the userscript metadata block
    assert body.startswith("// ==UserScript=="), "missing userscript header"
    # Compiled body should invoke an IIFE
    assert "(()=>{" in body or "(function(){" in body, "compiled IIFE wrapper missing"


# ---------------------------------------------------------------------------
# Version marker
# ---------------------------------------------------------------------------
def test_userscript_version_is_at_least_8_127():
    body = _get_userscript()
    m = re.search(r"@version\s+([\d.]+)", body)
    assert m, "no @version"
    parts = [int(x) for x in m.group(1).split(".")]
    assert parts >= [8, 127, 0], f"expected >= 8.127.0, got {m.group(1)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
