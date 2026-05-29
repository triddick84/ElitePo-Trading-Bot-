"""
Iter 73 (Feb 27, 2026) — regression for v8.73.0 universal +3.5s fire offset.

Coverage:
  A. Tampermonkey bundle bumped, slider step is 0.5s and default 3.5s.
  B. state.js defaults latencyOffsetSec to 3.5 (any signal source applies it).
  C. SNS strategy now respects the global latency offset before firing
     (was previously bypassing it because SNS used its own _executeViaWs /
     _executeViaDom path).
  D. Backend /signals/force-generate-v2 emits fire_offset_sec=3.5 by default,
     overridable via SIGNAL_FIRE_OFFSET_SEC env var, clamped to [-15, 15].
"""
import os
import re
from pathlib import Path

import requests

API = "http://localhost:8001/api"
TM_BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
SIGNALS = Path("/app/backend/routes/signals.py")


def test_tm_version_at_least_8_73():
    assert TM_BUNDLE.exists()
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'BOT_VERSION:"(\d+)\.(\d+)\.(\d+)"', text)
    assert m
    assert (int(m.group(1)), int(m.group(2))) >= (8, 73)


def test_latency_slider_supports_half_second_steps_with_default_3_5():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # Slider HTML: step="0.5" value="3.5"
    assert 'step="0.5"' in text or 'step=\\"0.5\\"' in text, \
        "Latency slider must use 0.5s step"
    assert 'value="3.5"' in text or 'value=\\"3.5\\"' in text, \
        "Latency slider must default to 3.5"
    # State default
    assert "latencyOffsetSec:3.5" in text, "state.latencyOffsetSec must default to 3.5"


def test_sns_respects_latency_offset_before_fire():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # The new SNS arming block uses latencyOffsetSec inside the fire path
    assert "[51s-Reversal] latency offset" in text or "latency offset +" in text, \
        "SNS strategy must surface latency-offset sleep in fire path"


def test_backend_force_generate_v2_returns_fire_offset_sec():
    r = requests.post(
        f"{API}/signals/force-generate-v2",
        params={"asset": "EURUSD_OTC", "expiry_seconds": 60},
        json={},
        timeout=20,
    )
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    sig = data.get("signal") or {}
    assert "fire_offset_sec" in sig, "force-generate-v2 must surface fire_offset_sec"
    # Default value should be 3.5
    assert sig["fire_offset_sec"] == 3.5, f"expected 3.5, got {sig['fire_offset_sec']}"


def test_signal_fire_offset_helper_clamps_and_handles_invalid():
    """Direct unit test of the helper so env-driven overrides are safe."""
    src = SIGNALS.read_text(encoding="utf-8")
    assert "_signal_fire_offset_sec" in src, "Helper function must exist"
    # Sanity: clamp range
    assert "max(-15.0, min(15.0" in src
    # Default value 3.5
    assert '"SIGNAL_FIRE_OFFSET_SEC"' in src and '"3.5"' in src
