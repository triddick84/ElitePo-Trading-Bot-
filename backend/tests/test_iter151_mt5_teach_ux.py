"""Iter 151 — MT5 Teach UI expansion.

Bundle-level contracts covering:
  1. mt5Adapter gains verify() / verifyAll() / dryRun() with the exact
     control names the Forex tab wires up.
  2. startTeach() paints a hover reticle overlay so the user visually
     sees which element they will teach.
  3. Panel adds a completeness counter, a cross-origin iframe banner,
     per-cell verify badges, and a DRY RUN button.
"""

from __future__ import annotations

from pathlib import Path

import pytest


ADAPTER = Path("/app/tampermonkey-src/src/trading/mt5Adapter.js")
PANEL = Path("/app/tampermonkey-src/src/ui/panel.js")
BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BUNDLE_MODULAR = Path(
    "/app/frontend/public/pocket-option-auto-trader-modular.user.js"
)
VERSION = Path("/app/tampermonkey-src/version.txt")


def _r(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"missing: {p}")
    return p.read_text()


# ---------------------------------------------------------------------------
# Version bump
# ---------------------------------------------------------------------------

def test_version_bumped_to_iter151():
    # Iter 151 shipped as 8.156.0; iter 151b bumped to 8.157.0.
    assert VERSION.read_text().strip() >= "8.156.0"


def test_bundles_carry_new_version():
    for b in (BUNDLE, BUNDLE_MODULAR):
        s = _r(b)
        assert "@version      8.15" in s, f"{b.name} missing v8.15x header"


# ---------------------------------------------------------------------------
# mt5Adapter — new public API
# ---------------------------------------------------------------------------

def test_adapter_defines_verify_single_control():
    s = _r(ADAPTER)
    assert "verify(control)" in s, "verify(control) helper missing"
    # Result shape used by the panel to colour badges.
    assert "found: true" in s and "taught:" in s and "source:" in s


def test_adapter_defines_verify_all():
    s = _r(ADAPTER)
    assert "verifyAll()" in s
    # Must iterate every SELECTORS key except iframe.
    assert "if (key === 'iframe') continue" in s


def test_adapter_defines_dry_run_that_never_clicks_buy_or_sell():
    s = _r(ADAPTER)
    assert "async dryRun(" in s, "dryRun method missing"
    # dryRun must resolve BUY/SELL buttons to *report* their state, but
    # must NOT call `.click()` inside its body — else it becomes a real
    # order placement.
    idx_start = s.index("async dryRun(")
    # Body ends at the closing brace of the next method or the class.
    idx_next = s.index("\n  }\n", idx_start)
    body = s[idx_start:idx_next]
    assert ".click(" not in body, "dryRun must never click BUY/SELL buttons"
    assert "buy_btn" in body and "sell_btn" in body


def test_adapter_start_teach_paints_hover_reticle():
    """Iter 151 UX: user must see what they're teaching before clicking."""
    s = _r(ADAPTER)
    assert "data-ai-elite-teach-reticle" in s, "hover reticle attribute missing"
    assert "reticle.style.top" in s
    assert "mouseover" in s and "onMove" in s


def test_adapter_exposes_new_devtools_helpers():
    s = _r(ADAPTER)
    assert "window.__aiEliteMt5Verify" in s
    assert "window.__aiEliteMt5DryRun" in s


# ---------------------------------------------------------------------------
# Panel — new UI wiring
# ---------------------------------------------------------------------------

def test_panel_renders_completeness_counter():
    s = _r(PANEL)
    assert 'data-testid="fx-teach-progress"' in s
    assert "0/6 taught" in s
    # And the render logic updates it after teach/clear.
    assert "taughtCount === _MT5_CONTROLS.length" in s


def test_panel_renders_cross_origin_banner():
    s = _r(PANEL)
    assert 'data-testid="fx-iframe-warn"' in s
    assert "cross-origin" in s.lower()
    # Only shown when diagnose reports doc_kind === 'cross-origin'.
    assert "doc_kind === 'cross-origin'" in s


def test_panel_renders_verify_badge_per_control():
    s = _r(PANEL)
    # Template literal in panel source: `fx-teach-badge-${c.key}`
    assert 'fx-teach-badge-${c.key}' in s
    # And the render helper reads/writes each badge id.
    assert 'fxTeachBadge_${c.key}' in s or 'fxTeachBadge_' in s
    # Same six controls the adapter/mt5 selectors define.
    for key in (
        "symbol_search",
        "lot_input",
        "sl_input",
        "tp_input",
        "buy_btn",
        "sell_btn",
    ):
        assert f"key: '{key}'" in s, f"MT5 control config missing {key}"


def test_panel_renders_dry_run_button_and_handler():
    s = _r(PANEL)
    assert 'data-testid="fx-dryrun-btn"' in s
    assert "🧪 DRY RUN" in s
    assert "mt5Adapter.dryRun(" in s
    # Never triggers a real order — placeOrder must not appear in the
    # dry-run wiring.
    dry_start = s.index('data-testid="fx-dryrun-btn"')
    dry_end = s.index('// ---- Clear all', dry_start)
    dry_block = s[dry_start:dry_end]
    assert "placeOrder" not in dry_block, (
        "DRY RUN handler must never call placeOrder"
    )


# ---------------------------------------------------------------------------
# Compiled bundle sanity — no minified name conflicts strip our new hooks
# ---------------------------------------------------------------------------

def test_bundle_contains_new_teach_ui_markers():
    s = _r(BUNDLE)
    assert 'fx-dryrun-btn' in s, "compiled bundle missing DRY RUN button testid"
    assert 'fx-iframe-warn' in s, "compiled bundle missing cross-origin banner"
    assert 'fx-teach-badge-' in s, "compiled bundle missing verify badges"
    assert 'ai-elite-teach-reticle' in s, "compiled bundle missing hover reticle"
    # Progress counter default text and control key labels must survive
    # minification because they're strings.
    assert "taught" in s


def test_all_six_mt5_controls_in_bundle():
    s = _r(BUNDLE)
    for key in (
        "symbol_search",
        "lot_input",
        "sl_input",
        "tp_input",
        "buy_btn",
        "sell_btn",
    ):
        assert key in s, f"MT5 control key {key!r} missing from bundle"
