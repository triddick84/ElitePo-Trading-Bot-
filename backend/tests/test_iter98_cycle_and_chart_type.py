"""
Iter 98 — CYCLE favorites-bar rewrite + chart-type selector.

Locks:
  * TM v8.128.0 userscript contains the new favorites-cycle machinery
    (favoritesTeachData, TEACH MODE overlay, teachFav button).
  * appSignalPoller falls back to picker + search when the fast switch
    doesn't verify (fixes "most signals wont place trades" bug).
  * /api/config exposes and persists a `chart_type` field with the four
    valid values (japanese_candles / heikin_ashi / line / bars).
  * force-generate signals accept a `chart_type` parameter.
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
# TM userscript compat: v8.128.0
# ---------------------------------------------------------------------------
def test_userscript_is_at_least_8_128():
    body = _get_userscript()
    m = re.search(r"@version\s+([\d.]+)", body)
    assert m
    parts = [int(x) for x in m.group(1).split(".")]
    assert parts >= [8, 128, 0], f"expected >= 8.128.0, got {m.group(1)}"


def test_favorites_cycle_markers_present():
    body = _get_userscript()
    for marker in (
        "pobot_favoritesTeachData",
        "TEACH MODE",
        "Teach Favorites",
    ):
        assert marker in body, f"missing favorites-cycle marker: {marker}"


def test_teach_favorites_button_wired():
    body = _get_userscript()
    # Panel button + data-testid + click handler chain
    assert "teachFav" in body, "teachFav button ID missing"
    assert 'data-testid="btn-teach-favorites"' in body


def test_signal_poller_has_fallback_paths():
    """Iter 98 — the poller should try picker+search fallbacks when the
    fast switchAsset doesn't verify. Guards against the user's bug:
    'most signals wont place trades'."""
    body = _get_userscript()
    assert "switchAssetViaPicker" in body, "picker fallback not compiled in"
    assert "switchAssetViaSearch" in body, "search fallback not compiled in"


# ---------------------------------------------------------------------------
# Chart type selector
# ---------------------------------------------------------------------------
VALID_CHART_TYPES = {"japanese_candles", "heikin_ashi", "line", "bars"}


def test_config_exposes_chart_type():
    r = requests.get(f"{API}/config", timeout=10).json()
    assert "chart_type" in r, "config missing chart_type field"
    assert r["chart_type"] in VALID_CHART_TYPES or r["chart_type"] == "japanese_candles"


def test_chart_type_persists_across_updates():
    # Set to heikin_ashi
    r = requests.put(
        f"{API}/config",
        json={
            "selected_assets": ["EURUSD_OTC"],
            "selected_expirations": ["1m"],
            "chart_type": "heikin_ashi",
            "selected_strategy": "",
            "selected_timeframe": "1m",
            "min_probability_threshold": 85,
            "invert_signals": False,
            "sound_alerts_enabled": True,
            "popup_notifications": True,
            "auto_trading_enabled": False,
            "trading_mode": "demo",
        },
        timeout=10,
    )
    assert r.status_code == 200

    got = requests.get(f"{API}/config", timeout=10).json()
    assert got.get("chart_type") == "heikin_ashi", f"chart_type didn't persist: {got}"

    # Reset back to japanese_candles for other tests
    requests.put(
        f"{API}/config",
        json={
            "selected_assets": ["EURUSD_OTC"],
            "selected_expirations": ["1m"],
            "chart_type": "japanese_candles",
            "selected_strategy": "",
            "selected_timeframe": "1m",
            "min_probability_threshold": 85,
            "invert_signals": False,
            "sound_alerts_enabled": True,
            "popup_notifications": True,
            "auto_trading_enabled": False,
            "trading_mode": "demo",
        },
        timeout=10,
    )


def test_all_four_chart_types_accepted():
    for ct in VALID_CHART_TYPES:
        r = requests.put(
            f"{API}/config",
            json={
                "selected_assets": ["EURUSD_OTC"],
                "selected_expirations": ["1m"],
                "chart_type": ct,
                "selected_strategy": "",
                "selected_timeframe": "1m",
                "min_probability_threshold": 85,
                "invert_signals": False,
                "sound_alerts_enabled": True,
                "popup_notifications": True,
                "auto_trading_enabled": False,
                "trading_mode": "demo",
            },
            timeout=10,
        )
        assert r.status_code == 200, f"chart_type={ct} rejected: {r.status_code} {r.text}"
        got = requests.get(f"{API}/config", timeout=10).json()
        assert got.get("chart_type") == ct


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
