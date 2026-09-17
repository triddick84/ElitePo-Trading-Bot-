"""Iter 141 — Win/loss detection fix + compact UI + dual-edge resize."""

import re
from pathlib import Path

import pytest

BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
SRC_WATCHER = Path("/app/tampermonkey-src/src/trading/tradeResultWatcher.js")
SRC_PANEL = Path("/app/tampermonkey-src/src/ui/panel.js")


def _read(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"file missing: {p}")
    return p.read_text()


def _semver_ge(a: str, b: str) -> bool:
    """Compare dotted-int versions — no pre-release handling needed here."""
    aa = tuple(int(x) for x in a.split("."))
    bb = tuple(int(x) for x in b.split("."))
    return aa >= bb


# ---------------------------------------------------------------------------
# Win/loss detection — the actual bug
# ---------------------------------------------------------------------------

def test_watcher_source_uses_color_class_strategies():
    src = _read(SRC_WATCHER)
    # New strategies must appear in the parser
    assert "value_up" in src, "value_up color-class fallback missing"
    assert "value_down" in src, "value_down color-class fallback missing"
    assert "getComputedStyle" in src, "RGB-color fallback missing"


def test_watcher_defers_when_outcome_null():
    src = _read(SRC_WATCHER)
    assert "deferring row (no outcome yet)" in src, (
        "row-deferral message missing — we lost the 'don't mark seen until "
        "outcome is known' safety net"
    )


def test_watcher_match_lenient_on_amount():
    src = _read(SRC_WATCHER)
    # Second-pass matcher should exist (asset+direction only)
    assert "Second pass" in src or "same asset+direction" in src, (
        "lenient (amount-less) matcher fallback missing"
    )


# ---------------------------------------------------------------------------
# UI redesign
# ---------------------------------------------------------------------------

def test_panel_default_width_is_compact():
    src = _read(SRC_PANEL)
    # New default: 320 desktop / 290 mobile
    assert re.search(r"const W\s*=\s*mobile\s*\?\s*290\s*:\s*320", src), (
        "compact 320 px default width not applied"
    )


def test_panel_has_dual_side_resize_handles():
    src = _read(SRC_PANEL)
    assert "resize-handle-left" in src
    assert "resize-handle-right" in src
    assert "sideresize" in src
    # Bind logic must exist for both sides
    assert "_bindSideResize('resizeL', 'left')" in src
    assert "_bindSideResize('resizeR', 'right')" in src


def test_panel_drag_from_anywhere():
    src = _read(SRC_PANEL)
    # Should attach drag to the panel, not just header
    assert "dragSurface" in src, "drag-from-anywhere plumbing missing"
    # Should skip interactive elements
    assert "shouldSkipDrag" in src
    assert "NO_DRAG" in src


# ---------------------------------------------------------------------------
# Bundle carries all changes
# ---------------------------------------------------------------------------

def test_bundle_version_bumped():
    src = _read(BUNDLE)
    m = re.search(r"//\s*@version\s+(\d+\.\d+\.\d+)", src)
    assert m and _semver_ge(m.group(1), "8.151.0"), f"expected >= 8.151.0, got {m and m.group(1)}"


def test_bundle_has_side_resize_testids():
    src = _read(BUNDLE)
    assert "resize-handle-left" in src
    assert "resize-handle-right" in src


def test_bundle_has_value_up_class_hook():
    """Regression guard so future rebuilds don't drop the win/loss fix."""
    src = _read(BUNDLE)
    assert "value_up" in src, "compiled bundle lost the color-class strategy"
    assert "getComputedStyle" in src
