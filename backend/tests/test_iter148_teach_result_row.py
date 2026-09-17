"""Iter 148 — TradeResultWatcher point-to-teach fallback (bundle sanity)."""

import re
import subprocess
from pathlib import Path

import pytest

BUNDLE = Path("/app/frontend/public/pocket-option-auto-trader.user.js")
BUNDLE_MODULAR = Path("/app/frontend/public/pocket-option-auto-trader-modular.user.js")
SRC = Path("/app/tampermonkey-src/src/trading/tradeResultWatcher.js")
PANEL_SRC = Path("/app/tampermonkey-src/src/ui/panel.js")


def _r(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"missing: {p}")
    return p.read_text()


# ---------------------------------------------------------------------------
# Source-level contracts
# ---------------------------------------------------------------------------

def test_source_defines_teach_gm_keys():
    s = _r(SRC)
    assert "ai_elite_teach_win_row" in s
    assert "ai_elite_teach_loss_row" in s
    assert "ai_elite_teach_deal_container" in s


def test_source_defines_start_teach_and_clear():
    s = _r(SRC)
    assert re.search(r"startTeach\s*\(kind", s)
    assert "clearTaught" in s
    assert "getTaught" in s


def test_source_taught_signatures_short_circuit_parse():
    """Strategy 0 (taught) must run BEFORE Strategy A (numeric signed
    detection) — otherwise the heuristics can outvote the user's taught
    class signature. Verify by ordering the anchor comments in-file."""
    s = _r(SRC)
    strat0 = s.find("Strategy 0")
    strat_a = s.find("Strategy A:")
    assert strat0 != -1 and strat_a != -1
    assert strat0 < strat_a, "taught-parse must come before numeric strategy"


def test_source_taught_container_short_circuit_scan():
    s = _r(SRC)
    scan = s.find("_scanNewRows()")
    css_default = s.find("DEAL_ROW_SELECTOR", scan)
    taught = s.find("taughtContainer", scan)
    assert scan != -1 and css_default != -1 and taught != -1
    assert taught < css_default, "taught container check must run before default CSS scan"


def test_source_window_helpers_exposed():
    s = _r(SRC)
    for name in [
        "__aiEliteTeachWin",
        "__aiEliteTeachLoss",
        "__aiEliteTeachDealContainer",
        "__aiEliteClearTeach",
        "__aiEliteGetTaught",
    ]:
        assert name in s, f"missing window helper: {name}"


def test_panel_forex_tab_has_result_teach_section():
    s = _r(PANEL_SRC)
    assert "Win/Loss Detection Teach" in s
    assert "result-teach-btn" in s
    assert "result-diag-btn" in s
    assert "_initResultTeachSection" in s


# ---------------------------------------------------------------------------
# Bundle contracts (post-webpack) — mangling can rename functions but the
# GM-key STRINGS and testid attributes are inlined, so they survive.
# ---------------------------------------------------------------------------

def test_bundle_contains_teach_strings():
    b = _r(BUNDLE)
    assert "ai_elite_teach_win_row" in b
    assert "ai_elite_teach_loss_row" in b
    assert "ai_elite_teach_deal_container" in b
    assert "__aiEliteTeachWin" in b
    assert "result-teach-btn" in b


def test_bundle_and_modular_are_the_same_build():
    """v8.153+ we ship the same bundle to both paths so users don't have
    to know which URL their TM installer is following."""
    a = _r(BUNDLE)
    b = _r(BUNDLE_MODULAR)
    assert len(a) == len(b), f"byte counts differ: {len(a)} vs {len(b)}"


def test_bundle_version_at_least_iter148():
    b = _r(BUNDLE)
    m = re.search(r"//\s*@version\s+(\d+\.\d+\.\d+)", b)
    assert m, "no @version header in bundle"
    parts = tuple(int(x) for x in m.group(1).split("."))
    assert parts >= (8, 154, 0), f"expected >= 8.154.0, got {m.group(1)}"


# ---------------------------------------------------------------------------
# Node-side smoke — runs the JS sanity test if node is available
# ---------------------------------------------------------------------------

def test_node_bundle_smoke_runs():
    script = Path("/app/tampermonkey-src/tests/iter148_teach_parse.test.js")
    if not script.exists():
        pytest.skip("smoke script not present")
    try:
        r = subprocess.run(
            ["node", str(script)],
            cwd="/app/tampermonkey-src",
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        pytest.skip("node not installed")
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "bundle checks passed" in r.stdout
