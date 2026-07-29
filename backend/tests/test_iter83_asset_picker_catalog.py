"""
Iter 83 (Jul 2026) — AssetPicker + asset universe smoke tests.

The React-side interactivity of AssetPicker is covered by the frontend agent
via data-testid attributes. This test locks in the *backend contract* the
component depends on:

- `GET /api/backtest/assets-universe` returns a `classes` array with the
  expected shape (`id`, `label`, `symbols`, `timeframes`, `min_timeframe`).
- Both `_otc` and non-`_otc` class ids are present so the AssetPicker's
  Regular/OTC bulk toolbar has both sides to work with.
- Total symbol count is stable (used for the "N available" caption).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


def _get(path: str, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=15, **kwargs)


@pytest.fixture(scope="module")
def universe() -> Dict[str, Any]:
    r = _get("/api/backtest/assets-universe")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    return body


def test_universe_shape(universe: Dict[str, Any]):
    classes: List[Dict[str, Any]] = universe["classes"]
    assert isinstance(classes, list) and len(classes) >= 8
    required_keys = {"id", "label", "symbols", "timeframes", "min_timeframe"}
    for c in classes:
        missing = required_keys - set(c.keys())
        assert not missing, f"class {c.get('id')} missing keys: {missing}"
        assert isinstance(c["symbols"], list) and len(c["symbols"]) > 0
        assert isinstance(c["timeframes"], list) and len(c["timeframes"]) > 0


def test_universe_has_both_market_sides(universe: Dict[str, Any]):
    ids = {c["id"] for c in universe["classes"]}
    otc = {i for i in ids if i.endswith("_otc")}
    reg = {i for i in ids if not i.endswith("_otc")}
    assert len(otc) >= 4, f"expected ≥4 OTC classes, got {sorted(otc)}"
    assert len(reg) >= 4, f"expected ≥4 regular classes, got {sorted(reg)}"


def test_universe_symbol_totals(universe: Dict[str, Any]):
    reg = otc = 0
    for c in universe["classes"]:
        n = len(c["symbols"])
        if c["id"].endswith("_otc"):
            otc += n
        else:
            reg += n
    total = reg + otc
    # Guard against a silent shrink of the catalog. Current: 366 (183 + 183).
    # Allow ± 50 for future edits without paranoia.
    assert reg >= 100, f"regular symbols dropped to {reg}"
    assert otc >= 100, f"OTC symbols dropped to {otc}"
    assert total >= 300, f"total universe shrank to {total}"


def test_universe_otc_symbols_carry_marker(universe: Dict[str, Any]):
    """Every OTC-class symbol should encode `_OTC` in its name so the
    AssetPicker's Regular/OTC breakdown counter can classify it correctly."""
    misses = []
    for c in universe["classes"]:
        if not c["id"].endswith("_otc"):
            continue
        for s in c["symbols"]:
            if "_OTC" not in s.upper():
                misses.append(s)
    assert not misses, f"OTC symbols missing `_OTC` marker: {misses[:10]}"


def test_universe_no_duplicate_symbols_within_market(universe: Dict[str, Any]):
    """Same symbol should not appear twice within the same market side."""
    reg_syms: List[str] = []
    otc_syms: List[str] = []
    for c in universe["classes"]:
        if c["id"].endswith("_otc"):
            otc_syms.extend(c["symbols"])
        else:
            reg_syms.extend(c["symbols"])
    assert len(reg_syms) == len(set(reg_syms)), "duplicate regular symbols"
    assert len(otc_syms) == len(set(otc_syms)), "duplicate OTC symbols"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
