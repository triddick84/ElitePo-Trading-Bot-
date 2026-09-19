"""Iter 151b — Win/Loss detection health & early balance-delta resolver."""

from __future__ import annotations

from pathlib import Path

import pytest


WATCHER = Path("/app/tampermonkey-src/src/trading/tradeResultWatcher.js")
PANEL = Path("/app/tampermonkey-src/src/ui/panel.js")
BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
VERSION = Path("/app/tampermonkey-src/version.txt")


def _r(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"missing: {p}")
    return p.read_text()


def test_version_bumped_to_iter151b():
    assert VERSION.read_text().strip() == "8.157.0"
    assert "@version      8.157.0" in _r(BUNDLE)


def test_watcher_defines_early_balance_delta_resolver():
    """Prior impl only used balance-delta AT the deadline (expiry + 4 s
    safety buffer). Iter 151b resolves the moment expiry passes AND
    balance moved — dramatically shrinking the window where a trade sits
    in the queue with no outcome."""
    s = _r(WATCHER)
    assert "balance-delta-early" in s
    assert "expiryPassed" in s
    # Guard: only when queue has EXACTLY one unresolved arm (else delta
    # can conflate different trades).
    assert "unresolved.length === 1" in s


def test_watcher_bounds_seen_rows():
    """Previously seenRows grew unbounded — long sessions leaked memory
    AND stale ids blocked re-detection when PO recycled row nodes."""
    s = _r(WATCHER)
    assert "this.seenRows.size > 500" in s
    assert "new Set(arr.slice(-250))" in s


def test_watcher_exposes_get_stats_for_health_indicator():
    s = _r(WATCHER)
    assert "getStats()" in s
    # Fields the panel reads to build the health banner.
    for field in ("enabled", "queueLength", "timeoutCount", "healthy"):
        assert field in s, f"getStats() missing field {field}"


def test_watcher_logs_actionable_timeout_message():
    """Timeout log must point users at the fix path — the teach flow —
    otherwise silent failures repeat forever."""
    s = _r(WATCHER)
    assert "__aiEliteDealDiag()" in s
    assert 'TIMEOUT' in s
    assert 'Win/Loss Detection Teach' in s


def test_panel_renders_health_banner_on_live_tab():
    s = _r(PANEL)
    assert 'data-testid="detect-health"' in s
    assert "detectHealthMsg" in s
    # Banner is hidden by default (display:none) — only surfaces on
    # timeout.
    assert 'id="${P}detectHealth"' in s
    assert 'display:none' in s
    # Clicking the banner jumps to the forex tab (teach flow lives there).
    assert 'data-tab="forex"' in s


def test_panel_updates_health_from_watcher_stats():
    s = _r(PANEL)
    assert "tradeResultWatcher.getStats()" in s
    assert "st.timeoutCount" in s
    assert "detectHealth" in s


def test_bundle_carries_iter151b_markers():
    s = _r(BUNDLE)
    # Minifier keeps strings; check the literal strings we added.
    assert "balance-delta-early" in s
    assert "detect-health" in s
