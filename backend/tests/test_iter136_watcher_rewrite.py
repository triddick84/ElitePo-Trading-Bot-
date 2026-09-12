"""Iter 136 — tradeResultWatcher rewrite (multi-trade, no balance dependency).

These tests validate:
  1. The compiled TM bundle contains the new architecture.
  2. Old broken balance-based branches have been removed.
  3. Version was bumped so the browser's Tampermonkey picks up the update.
  4. Source-level guarantees about queue support and mutation-observer wiring.
"""
import os
import re
import subprocess


TM_SRC = "/app/tampermonkey-src/src/trading/tradeResultWatcher.js"
TM_BUNDLE = "/app/frontend/public/pocket-option-auto-trader.user.js"
TM_VERSION = "/app/tampermonkey-src/version.txt"


# ---------------------------------------------------------------------------
# Version bump
# ---------------------------------------------------------------------------
def test_tm_script_version_bumped_from_8_146():
    ver = open(TM_VERSION).read().strip()
    parts = ver.split(".")
    assert len(parts) == 3
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    # Must be > 8.146.0 so a browser hot-refresh actually picks up the fix
    assert (major, minor, patch) > (8, 146, 0), f"version {ver} did not bump past 8.146.0"


def test_tm_bundle_reflects_new_version():
    bundle = open(TM_BUNDLE).read()
    ver = open(TM_VERSION).read().strip()
    # The compiled bundle has `@version <ver>` in its userscript header
    assert f"@version      {ver}" in bundle or f"@version {ver}" in bundle, \
        f"bundle header does not contain new version {ver}"


# ---------------------------------------------------------------------------
# Balance-based detection is gone
# ---------------------------------------------------------------------------
def test_watcher_no_longer_polls_balance_delta():
    src = open(TM_SRC).read()
    # None of the old balance-delta symbols should remain
    for bad in ("preBalance", "getAccountBalance", "balance-up", "balance-flat"):
        assert bad not in src, f"leftover balance code found: {bad}"


def test_bundle_watcher_does_not_reference_prebalance():
    """The compiled bundle should also be free of the old preBalance branch."""
    bundle = open(TM_BUNDLE).read()
    # There will still be *some* balance references (executor, ui) but the
    # ResultWatcher block must not carry preBalance detection anymore
    assert "preBalance" not in bundle or bundle.count("preBalance") == 0, \
        "compiled bundle still contains preBalance from the old watcher"


# ---------------------------------------------------------------------------
# Multi-trade queue
# ---------------------------------------------------------------------------
def test_watcher_uses_queue_not_single_slot():
    src = open(TM_SRC).read()
    # Old: `this.armed = {...}`.  New: `this.armedQueue = [...]`.
    assert "armedQueue" in src
    assert "this.armed = " not in src or re.search(r"\bthis\.armed\s*=\s*null", src) is None
    # armResolver PUSHES to the queue (not overwrites)
    assert "this.armedQueue.push" in src


def test_watcher_matches_new_deal_rows_to_oldest_armed_trade():
    """The core fix: `_matchAndResolve` walks the queue by (asset, direction,
    amount) and resolves the FIRST match — the oldest un-resolved trade."""
    src = open(TM_SRC).read()
    assert "_matchAndResolve" in src
    # Match requires asset AND direction to line up
    assert "a.trade.direction !== parsed.direction" in src
    # Amount match uses a small tolerance so cents rounding doesn't break it
    assert "Math.abs(a.trade.amount - parsed.amount)" in src


def test_watcher_snapshots_existing_rows_on_arm():
    """When we arm a new trade, existing rows on the page must be marked
    seen so we don't fire a stale outcome for a trade that already resolved."""
    src = open(TM_SRC).read()
    # `seenRows` set + call to add existing deal rows in armResolver + enable
    assert "seenRows" in src
    assert "this.seenRows.add" in src


def test_watcher_supports_max_queue_length_to_prevent_leaks():
    """A stuck PO deal row should not leak the queue forever — old arms
    beyond MAX_QUEUE must be dropped."""
    src = open(TM_SRC).read()
    assert "MAX_QUEUE" in src
    # Drop when full
    assert "queue full" in src.lower() or "armedQueue.shift" in src


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------
def test_parse_deal_row_extracts_direction_asset_and_outcome():
    src = open(TM_SRC).read()
    assert "_parseDealRow" in src
    # Detects both up-family (CALL/UP/HIGHER/BUY) and down-family (PUT/DOWN/LOWER/SELL)
    assert "UP|CALL|HIGHER|BUY" in src
    assert "DOWN|PUT|LOWER|SELL" in src
    # Signed-number outcome parsing survives — this is the ONLY good signal
    # we have for win/loss now that balance is gone.
    assert "signed" in src.lower()


def test_asset_normalization_strips_separators_and_case():
    """`EUR/USD OTC`, `EURUSD-OTC`, `eurusdotc` must all normalize equally
    so the match logic doesn't miss on a formatting quirk."""
    src = open(TM_SRC).read()
    assert "_normAsset" in src
    # Strips spaces, slashes, underscores, dashes; uppercases
    assert "replace(/[\\s/_-]/g" in src or "replace(/[\\s\\/_-]/g" in src
    assert ".toUpperCase()" in src


# ---------------------------------------------------------------------------
# Debug surface
# ---------------------------------------------------------------------------
def test_queue_snapshot_helper_exposed_for_ui():
    """`getQueueSnapshot()` lets the AI panel render "3 trades pending"
    instead of the old lie that only one trade was being watched."""
    src = open(TM_SRC).read()
    assert "getQueueSnapshot" in src
