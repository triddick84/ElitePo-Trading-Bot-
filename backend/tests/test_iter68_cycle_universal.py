"""
Iter 68 — CYCLE mode universal scanner + 15s rotation

Verifies the v8.68.0 userscript bundle ships the rewritten CYCLE behavior:
  - rotateEveryMs is 15s (was 30s)
  - discoverAllAssetsWithPayouts is exported (multi-tab discovery)
  - Symbol filter is relaxed from FX-only to universal SYMBOL_RE
  - User-visible log line announces "universal asset scanner"
  - Version bumped to 8.68.0+
"""
import pathlib
import re

USERSCRIPT = pathlib.Path("/app/frontend/public/pocket-option-auto-trader.user.js")
CYCLE_SRC = pathlib.Path("/app/tampermonkey-src/src/trading/cycleMode.js")
DOM_SRC = pathlib.Path("/app/tampermonkey-src/src/utils/dom.js")


def test_userscript_version_8_68_or_higher():
    text = USERSCRIPT.read_text()
    m = re.search(r"@version\s+([\d.]+)", text)
    assert m
    major, minor, patch = (int(p) for p in m.group(1).split("."))
    assert (major, minor) >= (8, 68), f"bundle too old: {m.group(1)}"


def test_rotate_every_15s_in_bundle():
    text = USERSCRIPT.read_text()
    # Webpack minified the integer literal 15_000 to `15e3`. Either form is OK.
    assert ("rotateEveryMs:15e3" in text) or ("rotateEveryMs:15000" in text), (
        "Iter 68 — CYCLE rotateEveryMs must be 15s (was 30s)"
    )
    # Make sure the OLD 30s default isn't lingering
    assert "rotateEveryMs:30e3" not in text, "old 30s default still in bundle"


def test_discover_all_assets_export_present():
    text = USERSCRIPT.read_text()
    assert "discoverAllAssetsWithPayouts" in text, (
        "Iter 68 — multi-tab discovery helper must be exported"
    )


def test_cycle_source_no_longer_FX_only():
    src = CYCLE_SRC.read_text()
    # The old FX_PAIR_RE = /^[A-Z]{3}[A-Z]{3}(_OTC)?$/ used to restrict to forex.
    assert "FX_PAIR_RE" not in src, (
        "Per Iter 68, the FX-only filter must be removed so CYCLE can rotate "
        "across crypto / commodities / stocks / indices OTC as well."
    )
    assert "SYMBOL_RE" in src, "new universal SYMBOL_RE filter must be present"


def test_cycle_source_uses_universal_discovery():
    src = CYCLE_SRC.read_text()
    assert "discoverAllAssetsWithPayouts" in src, (
        "cycleMode.js must call the multi-tab discovery instead of "
        "only the Currencies tab."
    )


def test_dom_exports_universal_discovery():
    src = DOM_SRC.read_text()
    assert "export async function discoverAllAssetsWithPayouts" in src
    assert "clickPickerTabByText" in src


def test_cycle_log_says_universal_scanner():
    src = CYCLE_SRC.read_text()
    assert "universal asset scanner" in src
    assert "pairs with SCAN" in src.lower() or "pairs with scan" in src.lower()
