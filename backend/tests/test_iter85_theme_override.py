"""
Iter 85 (Jul 2026) — AI Trading Synthwave theme override integrity.

Locks in that our compiled userscript continues to ship with the theme
override block. If the block ever gets stripped (e.g., a future rebuild
overwrites the deployed file), this test flags it immediately.

Also verifies the theme override is IDEMPOTENT — we don't want the block
duplicated on repeat installs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
USERSCRIPT_ONDISK = Path("/app/frontend/public/pocket-option-auto-trader.user.js")


def test_theme_override_block_present_on_disk():
    assert USERSCRIPT_ONDISK.exists()
    body = USERSCRIPT_ONDISK.read_text()
    assert "AI Elite Bot — Iter 85 Theme Override" in body


def test_theme_override_block_is_idempotent():
    body = USERSCRIPT_ONDISK.read_text()
    wrapper_hits = body.count("AI Elite Bot — Iter 85 Theme Override")
    assert wrapper_hits <= 3, (
        f"Theme override appears to be duplicated ({wrapper_hits} sentinels)"
    )


def test_theme_override_uses_gm_addstyle():
    body = USERSCRIPT_ONDISK.read_text()
    # The override must use GM_addStyle (already granted in the metadata block)
    override_block = re.search(
        r"AI Elite Bot — Iter 85 Theme Override.*?themeOverride",
        body, re.DOTALL,
    )
    assert override_block, "Override block not found in expected shape"
    # And within the block, GM_addStyle must be called
    idx = body.index("AI Elite Bot — Iter 85 Theme Override")
    slice_ = body[idx:idx + 12000]
    assert "GM_addStyle" in slice_, "Override doesn't invoke GM_addStyle"


def test_theme_override_targets_expected_panel_ids():
    body = USERSCRIPT_ONDISK.read_text()
    # We must be styling the trader IDs that matter — sanity check a handful
    required_selectors = [
        "#panel-sidebar", "#panel-content",
        "#call", "#buy", "#put", "#sell",
        "#backend-health-row", "#status-strip",
        "#asset-name", "#current-price", "#trade-amount",
    ]
    idx = body.index("AI Elite Bot — Iter 85 Theme Override")
    slice_ = body[idx:idx + 12000]
    for sel in required_selectors:
        assert sel in slice_, f"Missing selector in theme override: {sel}"


def test_served_script_still_valid_userscript():
    r = requests.get(f"{BASE_URL}/api/tampermonkey/script", timeout=60)
    assert r.status_code == 200
    body = r.text
    assert body.startswith("// ==UserScript==")
    assert "// ==/UserScript==" in body
    assert "@version" in body
    assert "AI Elite Bot — Iter 85 Theme Override" in body


def test_metadata_block_preserved_intact():
    """The override must be injected AFTER the metadata block so Tampermonkey
    parses the @grant directives correctly."""
    body = USERSCRIPT_ONDISK.read_text()
    meta_end = body.index("// ==/UserScript==")
    theme_start = body.index("AI Elite Bot — Iter 85 Theme Override")
    assert theme_start > meta_end, (
        "Theme override injected inside/before UserScript metadata block!"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
