"""
Iter 64 — Auto-Invert simplification + SNS rename + on/off

Sanity checks (TM-side behavioural changes are tested at runtime, but we can
verify the userscript bundle changes here so a future build doesn't regress).
"""
import os
import pathlib
import re

USERSCRIPT = pathlib.Path("/app/frontend/public/pocket-option-auto-trader.user.js")
TM_VERSION_FILE = pathlib.Path("/app/tampermonkey-src/version.txt")


def test_userscript_bundle_exists():
    assert USERSCRIPT.is_file(), "production userscript not deployed to /app/frontend/public"


def test_userscript_version_bumped_to_8_66_or_higher():
    text = USERSCRIPT.read_text()
    m = re.search(r"@version\s+([\d.]+)", text)
    assert m, "no @version header in bundle"
    major, minor, patch = (int(p) for p in m.group(1).split("."))
    assert (major, minor) >= (8, 66), f"bundle version too low: {m.group(1)}"


def test_sns_rename_landed_in_bundle():
    text = USERSCRIPT.read_text()
    # The user-facing labels must use "SNS" (Seconds Number Strategy) wording
    assert 'data-testid="seconds-number-strategy-toggle"' in text
    assert 'data-testid="sns-timing-slider"' in text
    assert "Seconds Number Strategy" in text


def test_sns_no_longer_hard_locked_on_at_startup():
    """state.js was changed so _twentyOneSEnabled defaults to false on first run."""
    text = USERSCRIPT.read_text()
    # The previous bundle had `_twentyOneSEnabled:!0` (true) in the initial state.
    # The new bundle must initialise it to false.
    assert "_twentyOneSEnabled:!1" in text, (
        "SNS still hard-locked ON at startup — expected `_twentyOneSEnabled:!1` "
        "in the minified state object"
    )


def test_latency_slider_present_in_bundle():
    text = USERSCRIPT.read_text()
    assert 'data-testid="latency-offset-slider"' in text
    assert "latencyOffsetSec" in text


def test_auto_invert_uses_global_loss_streak():
    """
    The new auto-invert reads from stats.currentStreak (global) and no longer
    calls getConsecutiveSameDirectionLosses. The cooldown gate is removed too.
    """
    src = pathlib.Path("/app/tampermonkey-src/src/trading/smartInvert.js").read_text()
    assert "state.stats.currentStreak" in src
    assert "getConsecutiveSameDirectionLosses" not in src, (
        "Per Iter 64, auto-invert must use the global loss streak rather than "
        "per-asset same-direction grouping."
    )
    assert "INVERT_COOLDOWN_MS" not in src, (
        "Per Iter 64, the cooldown gate must be removed so 2 consecutive losses "
        "always trigger an immediate flip."
    )
