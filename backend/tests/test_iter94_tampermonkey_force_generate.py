"""
Iter 94 — /api/tampermonkey/force-generate now delegates to force_generate_signal_v2.
Verify the response is NO LONGER a random dice-roll and contains full analytics.
"""
from __future__ import annotations
import os
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def test_tm_force_generate_returns_candle_analysis_and_v2_analytics():
    r = requests.post(
        f"{BASE_URL}/api/tampermonkey/force-generate",
        params={"timeframe": "1m", "asset": "EURUSD_OTC"},
        timeout=45,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, f"expected success:true, got {body}"
    sig = body.get("signal") or {}
    # candle_analysis embedded from v2
    ca = sig.get("candle_analysis")
    assert ca is not None, f"missing candle_analysis in signal: {list(sig.keys())}"
    for k in ("patterns", "pattern_count", "pattern_bias",
              "pattern_bias_strength", "behavioural_summary"):
        assert k in ca, f"candle_analysis missing key: {k}"
    # v2 rich analytics fields — some may be optional but at least a few must exist
    v2_expected = ["strategy", "confluence_score", "quality", "mtf_confluence",
                   "ml_agree_count", "vol_regime", "atr_percent",
                   "components", "votes", "fire_offset_sec"]
    present = [k for k in v2_expected if k in sig]
    assert len(present) >= 6, (
        f"v2 analytics fields largely missing (only {present}); "
        f"signal keys: {list(sig.keys())}"
    )
    # Direction should be UP or DOWN, not random labels
    assert sig.get("direction") in ("UP", "DOWN", "CALL", "PUT"), \
        f"unexpected direction: {sig.get('direction')}"


def test_tm_force_generate_not_dice_roll_structure():
    """Old dice-roll response was very shallow. Verify richness now."""
    r = requests.post(
        f"{BASE_URL}/api/tampermonkey/force-generate",
        params={"timeframe": "1m", "asset": "EURUSD_OTC"},
        timeout=45,
    ).json()
    sig = r.get("signal") or {}
    # Rich payload => at least 10 top-level signal keys
    assert len(sig.keys()) >= 10, f"payload too shallow: {list(sig.keys())}"
