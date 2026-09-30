"""Iter 154 — DISABLE_BG_LOOPS env gate for the FastAPI startup.

Prod-only symptom: heavy background loops (yfinance scraping, ml tuner,
flexible_crossover scans, OANDA polling that 401s, sentiment refresh)
saturated the pod's 500 m CPU ceiling and starved the request loop, so
/api/auth/login timed out from the browser. The RCA from the deployer
agent recommended moving heavy loops off the request process; the
minimum-risk fix is an env gate the deployer can flip on prod so heavy
loops don't auto-start, while preview keeps working unchanged.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest


SERVER_PY = Path("/app/backend/server.py")


def _r() -> str:
    return SERVER_PY.read_text()


# ---------------------------------------------------------------------------
# Contract of the new gate helper
# ---------------------------------------------------------------------------

def test_server_reads_disable_bg_loops_env_var():
    s = _r()
    assert 'os.environ.get("DISABLE_BG_LOOPS"' in s, (
        "startup_event must read DISABLE_BG_LOOPS to know which loops to skip"
    )


def test_server_defines_bg_enabled_helper():
    s = _r()
    assert "def _bg_enabled(name: str) -> bool:" in s
    assert "_disable_all" in s
    assert "_disabled_names" in s


def test_all_keyword_disables_everything():
    """`DISABLE_BG_LOOPS=all` (or 1/true/yes) must disable every heavy loop
    in one flip — the recovery path when prod is on fire."""
    s = _r()
    # The truthy-any check MUST accept the standard aliases.
    m = re.search(r"_disable_all\s*=\s*_bg_raw\s+in\s*\(([^\)]+)\)", s)
    assert m, "no truthy-alias tuple for DISABLE_BG_LOOPS"
    aliases = m.group(1)
    for token in ('"1"', '"true"', '"yes"', '"all"'):
        assert token in aliases, f"missing alias {token} in disable-all check"


def test_csv_list_disables_specific_loops():
    s = _r()
    # CSV splitter must trim whitespace.
    assert '_bg_raw.split(",")' in s
    assert 's.strip()' in s


# ---------------------------------------------------------------------------
# Gate applied to the heavy loops
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("loop_name", [
    "market_data_ingester",
    "ai_learning_scheduler",
    "retrain_scheduler",
    "sentiment_loop",
    "network_latency_probe",
    "signal_prewarm",
    "auto_scan",
    "telegram_bot",
])
def test_each_heavy_loop_is_guarded(loop_name):
    s = _r()
    assert f'_bg_enabled("{loop_name}")' in s, (
        f"loop '{loop_name}' is NOT wrapped in _bg_enabled(...) — will "
        f"still run on prod even when DISABLE_BG_LOOPS is set"
    )


def test_market_data_ingester_still_binds_db_when_gated():
    """When the ingester's refresh loop is disabled, DB binding must
    still happen — otherwise endpoints that read historical_candles
    break silently."""
    s = _r()
    # Bind happens before the gate check.
    seg = s[s.index("Iter 149 — bind + boot"):s.index("Iter 126 — Start Telegram bot")]
    bind_idx = seg.index("ingester.bind_db(db)")
    gate_idx = seg.index('_bg_enabled("market_data_ingester")')
    assert bind_idx < gate_idx, "bind_db must run BEFORE the gate check"


def test_auto_scan_bind_db_survives_gate_but_forces_disabled():
    """auto_scan_service.bind_db(db) must still run so the REST endpoints
    keep working, but the persisted `enabled=True` must be flipped to
    False so the scan loop doesn't auto-resume."""
    s = _r()
    seg = s[s.index("Iter 112 — Auto-Scan"):s.index("Iter 131 — RiskGuard")]
    assert "auto_scan_service.bind_db(db)" in seg
    assert 'if _bg_enabled("auto_scan"):' in seg
    # Else branch forces enabled=False and persists it.
    assert 'cur["enabled"] = False' in seg
    assert "auto_scan_service.set_config(cur)" in seg


def test_gate_helper_logs_a_skip_message():
    """Prod diagnosis is easier when the pod logs which loops were
    skipped and why — otherwise the operator can't tell whether the
    env var took effect."""
    s = _r()
    assert 'DISABLE_BG_LOOPS=all' in s and '[bg-gate] SKIPPING' in s


# ---------------------------------------------------------------------------
# Documentation guardrail
# ---------------------------------------------------------------------------

def test_docstring_names_every_gated_loop():
    """The startup_event docstring is the operator's contract for which
    names DISABLE_BG_LOOPS accepts. Missing entries lead to prod
    incidents that look 'unfixable' with the env flag."""
    s = _r()
    docstring_start = s.index("Iter 154")
    docstring_end = s.index("Defaults preserve behavior for preview", docstring_start)
    docstring = s[docstring_start:docstring_end]
    for name in (
        "market_data_ingester",
        "ai_learning_scheduler",
        "retrain_scheduler",
        "sentiment_loop",
        "network_latency_probe",
        "signal_prewarm",
        "auto_scan",
        "telegram_bot",
    ):
        assert name in docstring, f"docstring missing loop name {name!r}"
