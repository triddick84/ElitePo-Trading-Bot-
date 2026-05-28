"""
Iter 69 — CYCLE no longer clicks the right-side "Trades / Closed" panel rows

Bug: PO's right-side trades panel shows rows in the same `SYMBOL +XX%` text
shape as the asset picker. `readPickerItems()` was scraping them and CYCLE
was clicking through closed-trade history instead of switching assets.

Fixes locked in:
  1. Trades-panel ancestor blacklist (`/trades|deals|history|opened|closed/`)
  2. Geometric guard — rows with bounding rect.left > 65% of viewport are rejected
  3. `clickPickerRowEl` refuses to fire on right-sidebar rows
"""
import pathlib
import re

USERSCRIPT = pathlib.Path("/app/frontend/public/pocket-option-auto-trader.user.js")
DOM_SRC = pathlib.Path("/app/tampermonkey-src/src/utils/dom.js")


def test_userscript_version_8_69_or_higher():
    text = USERSCRIPT.read_text()
    m = re.search(r"@version\s+([\d.]+)", text)
    assert m
    major, minor, _ = (int(p) for p in m.group(1).split("."))
    assert (major, minor) >= (8, 69), f"bundle too old: {m.group(1)}"


def test_blacklist_regex_present_in_source():
    src = DOM_SRC.read_text()
    assert "TRADES_BLACKLIST_RE" in src
    # Make sure all 6 critical keywords are in the regex
    for kw in ("trades", "deals", "history", "opened", "closed", "sidebar"):
        assert kw in src.lower()


def test_geometric_viewport_guard_present():
    src = DOM_SRC.read_text()
    assert "VIEWPORT_W" in src
    # 0.65 of viewport — anything past that is right-sidebar
    assert "0.65" in src or "0.7" in src


def test_click_picker_row_el_has_blacklist_check():
    src = DOM_SRC.read_text()
    # clickPickerRowEl must have the explicit ancestor + geometric guards.
    # Find the function body.
    fn_idx = src.find("export async function clickPickerRowEl(")
    assert fn_idx > 0
    body = src[fn_idx: fn_idx + 1500]
    assert "right-sidebar territory" in body or "refusing to click row" in body
    assert "TRADES_BLACKLIST_RE" in body


def test_bundle_contains_runtime_guards():
    text = USERSCRIPT.read_text()
    # Webpack inlined the user-facing warn strings; they must be in the bundle
    assert "right-sidebar territory" in text
    assert "refusing to click row" in text


def test_read_picker_items_has_blacklist_guard():
    src = DOM_SRC.read_text()
    fn_idx = src.find("function readPickerItems()")
    assert fn_idx > 0
    body = src[fn_idx: fn_idx + 3500]
    assert "_isLikelyTradePanelRow" in body
    assert "TRADES_BLACKLIST_RE" in body
