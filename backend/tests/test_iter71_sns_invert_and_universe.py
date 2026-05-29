"""
Iter 71 (Feb 27, 2026) — regression for v8.71.0 changes.

Coverage:
  A. SNS-Invert decoupling — confirms the Tampermonkey bundle ships the new
     SNS-only invert engine (setSnsResultHook on executor, onSnsResultRecorded
     on the strategy, and the SNS-LOCAL invert swap in _attemptFire).
  B. canTrade log clarity — confirms the cooldown rejection log now embeds
     the remaining-seconds string.
  C. /api/backtest/assets-universe — sanity check still returns the full
     10-class / 366+-symbol universe that the new Real Data Training UI
     pulls from.
  D. DataCollectionDashboard — confirms it no longer hardcodes a 7-asset list
     and instead consumes the universe endpoint.
"""
from pathlib import Path

import requests

API = "http://localhost:8001/api"
TM_BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
DASHBOARD = Path("/app/frontend/src/components/DataCollectionDashboard.jsx")


def test_tm_bundle_version_bumped_to_8_71():
    assert TM_BUNDLE.exists(), "Tampermonkey bundle must be built and present in /app/frontend/public/"
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # Accept any 8.71.x+ patch / 8.72+ minor — once bumped further, this stays green.
    import re
    m = re.search(r'BOT_VERSION:"(\d+)\.(\d+)\.(\d+)"', text)
    assert m, "BOT_VERSION not found in bundle"
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    assert (major, minor) >= (8, 71), f"Tampermonkey bundle must be at v8.71+ (got {major}.{minor}.{patch})"


def test_sns_invert_hook_wired_in_executor():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # executor exposes the registration setter
    assert "setSnsResultHook" in text, "executor must expose setSnsResultHook for SNS routing"
    # And calls it when classifying an SNS-tagged result
    assert "SNS-scoped result" in text, "executor should log when it bypasses global A-INV for SNS"


def test_sns_local_invert_present_in_strategy():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    assert "onSnsResultRecorded" in text, "SNS-only result handler must be in bundle"
    assert "SNS-Invert" in text, "SNS-Invert log channel must be in bundle"
    assert "SNS-LOCAL invert" in text or "sns-inverted" in text, \
        "SNS-LOCAL direction swap must be wired in _attemptFire"


def test_cantrade_log_now_includes_remaining_time():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # The improved log uses the phrase "cooldown {N}s remaining" + bucket
    assert "cooldown" in text and "remaining" in text and "bucket" in text, \
        "canTrade rejection log should explain cooldown remaining + bucket"
    # The executor echoes the reason in the rejection log
    assert "canTrade returned false" in text


def test_assets_universe_endpoint_still_complete():
    r = requests.get(f"{API}/backtest/assets-universe", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    classes = data.get("classes") or []
    assert len(classes) >= 10, f"expected ≥10 classes, got {len(classes)}"
    total = sum(len(c.get("symbols") or []) for c in classes)
    assert total >= 350, f"expected ≥350 unique symbols across the universe, got {total}"
    # Confirm each class carries its own timeframe list (no silent regression)
    for c in classes:
        assert c.get("timeframes"), f"class {c.get('id')} missing timeframes array"


def test_data_collection_dashboard_uses_universe_endpoint():
    assert DASHBOARD.exists(), "DataCollectionDashboard.jsx missing"
    src = DASHBOARD.read_text(encoding="utf-8")
    # Old hardcoded list should be GONE (constant rename to FALLBACK_CLASSES is fine).
    # We assert the file fetches the universe and renders Select-ALL controls.
    assert "/backtest/assets-universe" in src, "Dashboard must fetch /backtest/assets-universe"
    assert "select-all-assets-btn" in src, "Dashboard must expose a global Select-All assets button"
    assert "select-all-tfs-btn" in src, "Dashboard must expose a global Select-All timeframes button"
    # And that asset selection state is a Set (multi-class aware)
    assert "selectedAssets" in src and "new Set" in src
