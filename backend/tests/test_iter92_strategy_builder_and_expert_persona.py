"""
Iter 92 — Strategy Builder condition-persistence bug fixes + LLM expert persona.

Reported bug: "The strategy Builder seems to only be saving one condition
out of multiple ones added into the strategy."

Root causes fixed:
  1. Frontend save silently dropped any condition whose picked indicator
     had a mismatching (or empty) conditionType. Now pre-flight validates
     every condition and blocks Save with a clear toast.
  2. Frontend edit-load only read `call_conditions` and only the first
     inner condition per group — PUT rules AND multi-condition groups
     (Ichimoku preset!) were lost on Edit -> Save round-trip.
  3. `addCondition` used `Date.now()` as id, letting rapid double-clicks
     produce duplicate keys that React collapsed.
  4. LLM system prompt for `GPTSignalEnhancer` now runs a 4kB "30-year
     expert" playbook (session filter, microstructure hard-stops,
     6-of-6 confluence, behavioural biases).

Backend guard tests here — the frontend fixes are validated by lint +
manual trace + the E2E create-then-fetch round-trip below (which was
already passing but locks the contract).
"""

from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")


# ---------------------------------------------------------------------------
# 1) Backend correctly persists multi-group call+put strategies
# ---------------------------------------------------------------------------
def test_backend_persists_all_call_and_put_groups():
    """3 CALL groups + 2 PUT groups must round-trip untouched."""
    uid = f"multi_cond_user_{int(time.time())}"
    payload = {
        "name": f"MULTI_COND_{int(time.time())}",
        "user_id": uid,
        "call_conditions": [
            {"id": f"c{i}", "logical_operator": "AND", "conditions": [
                {"id": f"c{i}i", "indicator": ind, "parameters": {},
                 "conditionType": ct, "reversal": False}
            ]}
            for i, (ind, ct) in enumerate([
                ("RSI", "crosses_above_oversold"),
                ("EMA", "price_crosses_above"),
                ("MACD", "bullish_cross"),
            ])
        ],
        "put_conditions": [
            {"id": f"p{i}", "logical_operator": "AND", "conditions": [
                {"id": f"p{i}i", "indicator": ind, "parameters": {},
                 "conditionType": ct, "reversal": False}
            ]}
            for i, (ind, ct) in enumerate([
                ("RSI", "crosses_below_overbought"),
                ("EMA", "price_crosses_below"),
            ])
        ],
        "timeframes": ["1m"],
        "assets": ["EURUSD"],
        "markets": ["regular"],
        "min_confidence": 70,
    }
    r = requests.post(f"{BASE_URL}/api/custom-strategies", json=payload, timeout=15).json()
    assert r.get("success") is True

    listing = requests.get(
        f"{BASE_URL}/api/custom-strategies", params={"user_id": uid}, timeout=10,
    ).json()
    found = next((s for s in listing["strategies"] if s["name"] == payload["name"]), None)
    assert found is not None
    assert len(found.get("call_conditions", [])) == 3, \
        f"CALL groups collapsed: {len(found.get('call_conditions', []))}"
    assert len(found.get("put_conditions", [])) == 2, \
        f"PUT groups collapsed: {len(found.get('put_conditions', []))}"
    # Indicators preserved in order
    call_inds = [g["conditions"][0]["indicator"] for g in found["call_conditions"]]
    put_inds = [g["conditions"][0]["indicator"] for g in found["put_conditions"]]
    assert call_inds == ["RSI", "EMA", "MACD"]
    assert put_inds == ["RSI", "EMA"]


# ---------------------------------------------------------------------------
# 2) Multi-INNER groups (like the Ichimoku preset) survive round-trip
# ---------------------------------------------------------------------------
def test_backend_persists_multi_inner_condition_groups():
    """A single group with 3 inner conditions must persist all 3."""
    uid = f"multi_inner_user_{int(time.time())}"
    payload = {
        "name": f"MULTI_INNER_{int(time.time())}",
        "user_id": uid,
        "call_conditions": [
            {
                "id": "g1", "logical_operator": "AND",
                "conditions": [
                    {"id": "g1i1", "indicator": "RSI", "parameters": {"period": 14},
                     "conditionType": "crosses_above_oversold", "reversal": False},
                    {"id": "g1i2", "indicator": "EMA", "parameters": {"period": 9},
                     "conditionType": "price_crosses_above", "reversal": False},
                    {"id": "g1i3", "indicator": "MACD", "parameters": {},
                     "conditionType": "bullish_cross", "reversal": False},
                ],
            },
        ],
        "put_conditions": [],
        "timeframes": ["1m"], "assets": ["EURUSD"], "markets": ["regular"],
    }
    r = requests.post(f"{BASE_URL}/api/custom-strategies", json=payload, timeout=15).json()
    assert r.get("success") is True

    listing = requests.get(
        f"{BASE_URL}/api/custom-strategies", params={"user_id": uid}, timeout=10,
    ).json()
    found = next((s for s in listing["strategies"] if s["name"] == payload["name"]), None)
    assert found is not None
    assert len(found["call_conditions"]) == 1
    inner = found["call_conditions"][0].get("conditions", [])
    assert len(inner) == 3, f"Multi-inner group collapsed to {len(inner)}"
    assert [c["indicator"] for c in inner] == ["RSI", "EMA", "MACD"]


# ---------------------------------------------------------------------------
# 3) Applying the Ichimoku preset gives 3 inner CALL + 3 inner PUT conditions
# ---------------------------------------------------------------------------
def test_ichimoku_preset_persists_full_condition_tree():
    uid = f"ichi_user_{int(time.time())}"
    apply = requests.post(
        f"{BASE_URL}/api/custom-strategies/presets/ichimoku-cloud-break/apply",
        params={"user_id": uid}, timeout=10,
    ).json()
    assert apply.get("success") is True

    listing = requests.get(
        f"{BASE_URL}/api/custom-strategies", params={"user_id": uid}, timeout=10,
    ).json()
    found = next((s for s in listing["strategies"]
                  if "Ichimoku Cloud Break" in (s.get("name") or "")), None)
    assert found is not None
    # 1 CALL group with 3 inner rules, 1 PUT group with 3 inner rules
    assert len(found["call_conditions"]) == 1
    assert len(found["call_conditions"][0]["conditions"]) == 3
    assert len(found["put_conditions"]) == 1
    assert len(found["put_conditions"][0]["conditions"]) == 3


# ---------------------------------------------------------------------------
# 4) LLM expert persona is loaded correctly (imports without syntax error,
#    prompt has meaningful expert content)
# ---------------------------------------------------------------------------
def test_gpt_expert_persona_prompt_contains_key_terms():
    from gpt_signal_enhancer import GPTSignalEnhancer
    prompt = GPTSignalEnhancer._get_expert_system_prompt()
    # Must be a substantial document, not the old thin prompt
    assert len(prompt) > 2500, f"Expert prompt shrank: {len(prompt)}"
    # Key concepts from qtpylib + our own domain knowledge
    for term in (
        "SENIOR institutional",
        "Break-even win-rate",       # payout math
        "VPIN",                      # our microstructure module
        "Kyle",                       # Kyle's lambda
        "crossover",                  # qtpylib mental model
        "session",                    # session filter
        "confluence",                 # 6-of-6 rule
        "REJECT",                     # ruthless bias
        "OTC",                        # PO-specific quirk
    ):
        assert term.lower() in prompt.lower(), f"Missing key term: {term}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
