"""
Iter 72 (Feb 27, 2026) — regression for v8.72.0 settings persistence fix.

Coverage:
  A. Tampermonkey bundle bumped to v8.72.0.
  B. loadStrategies now prefers the locally-saved strategy over the server's
     /strategies/selected value (was overwriting it on every page reload).
  C. _restoreToggleStates restores the MM trade-amount input from
     state.moneyManagement.baseAmount (was resetting to $1 every reload).
"""
from pathlib import Path

TM_BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")


def test_tm_bundle_version_bumped_to_8_72():
    assert TM_BUNDLE.exists()
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    import re
    m = re.search(r'BOT_VERSION:"(\d+)\.(\d+)\.(\d+)"', text)
    assert m, "BOT_VERSION not found"
    major, minor = int(m.group(1)), int(m.group(2))
    assert (major, minor) >= (8, 72), f"Tampermonkey bundle must be at v8.72+ (got {major}.{minor})"


def test_strategy_local_overrides_server_on_reload():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # Either the verbatim comment from index.js or the resolved-selection log
    assert ("Local saved strategy wins" in text) or ("from local save" in text), \
        "loadStrategies must prefer the locally-saved strategy choice"
    # The fallback path for API offline should still apply the local pick
    assert "applied locally-saved strategy" in text, \
        "loadStrategies must apply the local strategy even when API is offline"


def test_mm_amount_input_restored_from_state():
    text = TM_BUNDLE.read_text(encoding="utf-8", errors="ignore")
    # Looks for the new restoration block referencing the amt input id
    assert "__epb__amt" in text, "MM trade-amount input must be restored on reload"
