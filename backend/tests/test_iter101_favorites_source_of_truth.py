"""
Iter 101 — Favorites-bar becomes the single source of truth.

User complaint: "cycle feature is clicking on the drop down menu instead
of the favorites bar."

Root cause: The APP signal poller's Iter 95 fallback chain was
    switchAsset() → switchAssetViaPicker() → switchAssetViaSearch()
which opens the currency-picker dropdown as fallback #1. Once the user
taught a favorites container, they never wanted the dropdown opened
again — the favorites bar is meant to be the exclusive routing surface.

Fix: When teach data is present, appSignalPoller now:
    1. Calls favoritesCycle.clickAsset(target) — tile-by-symbol lookup
       inside the taught container.
    2. Aborts the trade if the target isn't in favorites (no dropdown fallback).
When no teach data is present, the legacy 3-step fallback (with dropdown)
still applies so nothing breaks for un-taught users.

Also: CYCLE toggle button now visually flips OFF if start() fails, so
users don't get a "green button but nothing rotating" surprise.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
MODULAR_BUNDLE_PATH = Path("/app/frontend/public/pocket-option-auto-trader-modular.user.js")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


class TestIter101FavoritesBarIsSourceOfTruth:
    def test_version_advanced(self):
        v = Path("/app/tampermonkey-src/version.txt").read_text().strip()
        # Loose check — any 8.131+ version proves the Iter 101 fix shipped.
        # (Later iters keep bumping the number; we only care it didn't regress.)
        parts = v.split(".")
        assert len(parts) >= 3, f"unexpected version format: {v}"
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        assert (major, minor, patch) >= (8, 131, 0), f"expected ≥ 8.131.0, got {v}"

    def test_favorites_cycle_exposes_click_asset(self):
        src = Path("/app/tampermonkey-src/src/trading/favoritesCycle.js").read_text()
        assert "clickAsset(symbol)" in src, (
            "favoritesCycle must expose a clickAsset(symbol) method that "
            "clicks the matching tile in the taught container."
        )
        assert "not in taught favorites" in src, (
            "clickAsset should log a distinctive 'not in taught favorites' "
            "message so debugging failed switches is obvious."
        )

    def test_app_signal_poller_uses_favorites_when_taught(self):
        src = Path("/app/tampermonkey-src/src/trading/appSignalPoller.js").read_text()
        assert "favoritesCycle" in src, "appSignalPoller must import favoritesCycle"
        assert "favoritesCycle.clickAsset" in src, (
            "appSignalPoller must call favoritesCycle.clickAsset instead of "
            "always falling back to the currency picker."
        )
        assert "asset_not_in_favorites" in src, (
            "abort reason for not-in-favorites case must be surfaced in "
            "state.lastSignal so downstream UIs can display it."
        )
        # Sanity: the legacy 3-step fallback must still exist for users who
        # haven't taught a favorites bar yet.
        assert "switchAssetViaPicker" in src and "switchAssetViaSearch" in src, (
            "legacy dropdown/search fallback must remain for un-taught users."
        )

    def test_bundle_contains_favorites_click_asset(self):
        text = BUNDLE_PATH.read_text()
        assert "clickAsset" in text, (
            "compiled bundle missing clickAsset — rebuild required."
        )
        assert "asset_not_in_favorites" in text, (
            "abort reason literal not in compiled bundle."
        )

    def test_cycle_toggle_visually_reverts_on_failure(self):
        src = Path("/app/tampermonkey-src/src/index.js").read_text()
        # The onCycleToggle handler must call setToggleActive('cycle', false)
        # inside the !ok branch.
        assert "setToggleActive('cycle', false)" in src, (
            "onCycleToggle must visually flip CYCLE off if favoritesCycle.start() returns false"
        )

    def test_bundles_are_synchronised(self):
        assert BUNDLE_PATH.read_bytes() == MODULAR_BUNDLE_PATH.read_bytes(), (
            "modular and canonical userscript bundles diverged"
        )

    def test_no_cyclemode_regression(self):
        # Guardrail from Iter 100 — the legacy module must stay gone.
        text = BUNDLE_PATH.read_text()
        assert "cycleMode" not in text, "cycleMode leaked back into the bundle"


class TestIter101Endpoint:
    def test_endpoint_serves_v131(self):
        try:
            r = requests.get(f"{BASE_URL}/api/tampermonkey/script", timeout=15)
        except requests.RequestException as e:
            pytest.skip(f"backend unreachable: {e}")
        assert r.status_code == 200, r.status_code
        # Loose check — any 8.131+ header proves the Iter 101 fix shipped.
        import re
        m = re.search(r"@version\s+(\d+)\.(\d+)\.(\d+)", r.text)
        assert m, "no @version header in served bundle"
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        assert (major, minor, patch) >= (8, 131, 0), (
            f"endpoint served an older bundle ({major}.{minor}.{patch})"
        )
        assert "clickAsset" in r.text, "endpoint served a bundle without clickAsset"
