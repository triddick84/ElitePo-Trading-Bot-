"""Iter 144 — Wide-net deal-row discovery + balance-delta fallback."""

import re
from pathlib import Path

import pytest

SRC = Path("/app/tampermonkey-src/src/trading/tradeResultWatcher.js")
BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")


def _r(p):
    if not p.exists(): pytest.skip(f"missing: {p}")
    return p.read_text(encoding="utf-8")


def test_source_expanded_selector_list():
    s = _r(SRC)
    for tok in ('trades-list', 'operation', 'data-test', 'portfolio'):
        assert tok in s, f"expanded selector token missing: {tok}"


def test_source_has_widenet_fallback():
    s = _r(SRC)
    assert "_wideNetDealRows" in s
    assert "wide-net fallback" in s
    assert "hasDir && hasMoney" in s


def test_source_has_balance_delta_fallback():
    s = _r(SRC)
    assert "_readBalance" in s
    assert "balance-delta-fallback" in s
    assert "isSoloTimeout" in s


def test_source_has_diag_helper():
    s = _r(SRC)
    assert "__aiEliteDealDiag" in s
    assert "sample_css" in s
    assert "sample_widenet" in s


def test_source_scan_records_last_scan():
    s = _r(SRC)
    assert "_lastScan" in s
    assert "resolved_this_tick" in s


def _semver_ge(a: str, b: str) -> bool:
    aa = tuple(int(x) for x in a.split("."))
    bb = tuple(int(x) for x in b.split("."))
    return aa >= bb


def test_bundle_version_bumped():
    s = _r(BUNDLE)
    m = re.search(r"//\s*@version\s+(\d+\.\d+\.\d+)", s)
    assert m and _semver_ge(m.group(1), "8.151.0")


def test_bundle_has_diag_and_delta_markers():
    """Post-webpack: diag helper name + balance-delta reason string survive."""
    s = _r(BUNDLE)
    assert "__aiEliteDealDiag" in s
    assert "balance-delta-fallback" in s


def test_bundle_has_widenet_indicator_strings():
    s = _r(BUNDLE)
    # After minification, source strings ("wide-net fallback") are preserved
    # because they're literal message strings inside `log(...)` calls.
    assert "wide-net fallback" in s
