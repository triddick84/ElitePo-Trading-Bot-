"""
Iter 70 — CYCLE quick-pick strip fast path

The Pocket Option chart has a 5-7 tile horizontal strip along the top
(GBP/USD OTC +83%, JOD/CNY OTC +92%, ...). Clicking these is ~10x faster
than opening the picker dropdown (~100ms vs 1-2s). CYCLE now tries the
quick-pick tile FIRST and falls back to the picker only when the target
symbol isn't visible on the strip.
"""
import pathlib
import re

USERSCRIPT = pathlib.Path("/app/frontend/public/pocket-option-auto-trader.user.js")
DOM_SRC = pathlib.Path("/app/tampermonkey-src/src/utils/dom.js")
CYCLE_SRC = pathlib.Path("/app/tampermonkey-src/src/trading/cycleMode.js")


def test_userscript_version_8_70_or_higher():
    text = USERSCRIPT.read_text()
    m = re.search(r"@version\s+([\d.]+)", text)
    assert m
    major, minor, _ = (int(p) for p in m.group(1).split("."))
    assert (major, minor) >= (8, 70), f"bundle too old: {m.group(1)}"


def test_quick_pick_helpers_exported():
    src = DOM_SRC.read_text()
    assert "export function readQuickPickTiles" in src
    assert "export async function clickQuickPickTile" in src


def test_quick_pick_geometric_filter_present():
    """Tiles must live in the top ~250px of the viewport, not right-sidebar."""
    src = DOM_SRC.read_text()
    fn_idx = src.find("function _isQuickPickTile")
    assert fn_idx > 0
    body = src[fn_idx: fn_idx + 1500]
    # Top constraint
    assert "r.top" in body
    assert "260" in body or "250" in body or "200" in body
    # Right-sidebar guard
    assert "VIEWPORT_W" in body
    # Trades blacklist
    assert "trades" in body.lower()


def test_cycle_calls_quick_pick_before_picker():
    src = CYCLE_SRC.read_text()
    fn_idx = src.find("async _switchAssetViaPickerOnly(")
    assert fn_idx > 0, "function definition not found"
    body = src[fn_idx: fn_idx + 4000]
    # Quick-pick call must appear BEFORE the openCurrenciesPicker call
    quick_idx = body.find("clickQuickPickTile")
    picker_idx = body.find("openCurrenciesPicker")
    assert 0 < quick_idx < picker_idx, (
        "CYCLE must try the quick-pick fast path before opening the picker"
    )


def test_cycle_tracks_quick_pick_switches_stat():
    src = CYCLE_SRC.read_text()
    assert "quickPickSwitches" in src


def test_bundle_inlines_quick_pick_logic():
    text = USERSCRIPT.read_text()
    assert "readQuickPickTiles" in text
    assert "clickQuickPickTile" in text
    # log line that fires on a successful tile-click
    assert "quickpick" in text.lower()


def test_discovery_augments_with_quick_pick_tiles():
    src = CYCLE_SRC.read_text()
    # The discovery loop should pull `readQuickPickTiles` into the merged list
    assert "readQuickPickTiles" in src
    assert "quick-pick" in src.lower() or "quickpick" in src.lower()
