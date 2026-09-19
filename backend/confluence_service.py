"""Iter 137 — Confluence Scoring Engine.

Combines raw signals from multiple sources (technical indicators, chart
patterns, ML models, S/R levels, multi-timeframe votes) into one
`confluence_score ∈ [0, 1]`. Auto-scan uses this as a hard gate so trades
only fire when several independent signals align.

Contract
--------
Each `Signal` is:
    {
        "source": "rsi" | "macd" | "pattern:head_and_shoulders" | "ml:rf" | "sr" | "tf:5m" | ...,
        "direction": "CALL" | "PUT" | "NEUTRAL",
        "confidence": float in [0, 1],   # raw confidence of that indicator
        "weight": float | None,           # optional override weight (defaults from `_DEFAULT_WEIGHTS`)
        "asset": str | None,              # used to look up per-asset AUC from RF Audit
        "timeframe": str | None,
    }

The engine:
1. Filters out NEUTRAL signals.
2. Computes each signal's effective weight:
       effective_weight = base_weight * rf_audit_weight * signal_confidence
3. Groups by direction and returns the winning direction's normalised score.
4. Adds a bonus for **multi-timeframe agreement** (same-direction signals
   from ≥ 2 timeframes).
5. Adds a bonus when ≥ N distinct sources agree ("stack bonus").
6. Result clipped to [0, 1].

The gate `should_fire(...)` returns True iff score ≥ threshold AND
minimum-agreement rule holds.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


# Hard-coded base weights per signal FAMILY. Callers may override per-signal
# via the `weight` field. Patterns weigh more than momentum oscillators
# because they encode structural context; ML models weigh more still because
# they are already meta-learners.
_DEFAULT_WEIGHTS: Dict[str, float] = {
    "rsi": 0.6,
    "macd": 0.7,
    "bollinger": 0.6,
    "vwap": 0.6,
    "ma": 0.5,
    "adx": 0.5,
    "sr": 0.8,                          # support / resistance level touches
    "pattern": 1.0,                     # any chart pattern hit
    "ml": 1.2,                          # any ML prediction (LightGBM, RF, etc.)
    "ml:tqnet": 1.25,                   # Iter 146 — RevIN + Temporal Query attention
    "smart_money": 1.1,                 # order block / liquidity sweep signals
    "tf": 0.9,                          # multi-timeframe alignment tag
    "sentiment": 0.4,                   # news / macro sentiment
    "default": 0.5,
}

# Minimum number of DISTINCT sources needed to fire.
DEFAULT_MIN_SOURCES = 3

# Score threshold to fire.
DEFAULT_THRESHOLD = 0.65


def _base_weight_for(source: str) -> float:
    """Look up the base weight by source family — the prefix before ':'.
    Exact keys (e.g. ``ml:tqnet``) take precedence over family fallbacks."""
    if not source:
        return _DEFAULT_WEIGHTS["default"]
    key = source.lower()
    if key in _DEFAULT_WEIGHTS:
        return _DEFAULT_WEIGHTS[key]
    family = key.split(":", 1)[0]
    return _DEFAULT_WEIGHTS.get(family, _DEFAULT_WEIGHTS["default"])


def _rf_audit_multiplier(source: str, asset: Optional[str], timeframe: Optional[str]) -> float:
    """For ml/rf signals, multiply the base weight by the RF Audit weight
    (Iter 135). Defaults to 1.0 when the audit is unavailable or the source
    family isn't ML.

    Iter 149 — SILENT BUG FIX. The RF audit was designed for the specific
    RandomForest model shipped in Iter 135 (source = "ml:rf"). It was
    accidentally applied to EVERY ml:* source via `startswith("ml")`,
    including `ml:tqnet` (Iter 146). When a legacy yfinance probe failed
    to fetch training data, rf_audit persisted `weight=0.0` for those
    (asset, timeframe) pairs — silently zeroing every ML contribution to
    confluence for months.

    We now scope the RF audit to `ml:rf` only. `ml:tqnet` (and any future
    ML source we add) uses its base weight without the audit multiplier.
    """
    if not source:
        return 1.0
    s = source.lower()
    # Only the original RF ensemble gets the RF-audit multiplier
    if not (s == "ml:rf" or s == "ml" or s.startswith("ml:rf:")):
        return 1.0
    if not asset or not timeframe:
        return 1.0
    try:
        from rf_audit_service import rf_audit_service  # local import to avoid startup loops
        return float(rf_audit_service.get_effective_weight(asset, timeframe))
    except Exception:
        return 1.0


def score_confluence(
    signals: Iterable[Dict[str, Any]],
    *,
    min_sources: int = DEFAULT_MIN_SOURCES,
    tf_bonus: float = 0.12,
    stack_bonus: float = 0.10,
) -> Dict[str, Any]:
    """Produce the aggregated confluence result.

    Returns dict:
        {
            "direction": "CALL" | "PUT" | "NEUTRAL",
            "confluence_score": float in [0, 1],
            "call_score": float,
            "put_score": float,
            "sources_call": [source strings],
            "sources_put": [source strings],
            "timeframes_call": [timeframe strings],
            "timeframes_put": [timeframe strings],
            "reason": human-readable summary,
        }
    """
    call_total = 0.0
    put_total = 0.0
    sources_call: List[str] = []
    sources_put: List[str] = []
    tf_call: set = set()
    tf_put: set = set()
    total_weight = 0.0

    for s in signals or []:
        direction = (s.get("direction") or "").upper()
        if direction not in ("CALL", "PUT"):
            continue  # ignore NEUTRAL
        conf = float(s.get("confidence") or 0.0)
        conf = max(0.0, min(1.0, conf))
        source = str(s.get("source") or "default")
        base_w = float(s.get("weight") or _base_weight_for(source))
        rf_w = _rf_audit_multiplier(source, s.get("asset"), s.get("timeframe"))
        eff = base_w * rf_w * conf
        total_weight += base_w * rf_w
        tf = s.get("timeframe")
        if direction == "CALL":
            call_total += eff
            sources_call.append(source)
            if tf:
                tf_call.add(str(tf))
        else:
            put_total += eff
            sources_put.append(source)
            if tf:
                tf_put.add(str(tf))

    # Score = winner_effective / total_possible_weight  →  bounded [0, 1]
    if total_weight <= 0:
        return {
            "direction": "NEUTRAL",
            "confluence_score": 0.0,
            "call_score": 0.0,
            "put_score": 0.0,
            "sources_call": [],
            "sources_put": [],
            "timeframes_call": [],
            "timeframes_put": [],
            "reason": "no non-neutral signals",
        }

    call_score = call_total / total_weight
    put_score = put_total / total_weight

    if call_score > put_score:
        direction = "CALL"
        base_score = call_score
        winning_sources = sources_call
        winning_tfs = tf_call
    elif put_score > call_score:
        direction = "PUT"
        base_score = put_score
        winning_sources = sources_put
        winning_tfs = tf_put
    else:
        return {
            "direction": "NEUTRAL",
            "confluence_score": max(call_score, put_score),
            "call_score": call_score,
            "put_score": put_score,
            "sources_call": sources_call,
            "sources_put": sources_put,
            "timeframes_call": sorted(tf_call),
            "timeframes_put": sorted(tf_put),
            "reason": "tie between CALL and PUT",
        }

    # ---- Bonuses ----
    bonus = 0.0
    reasons: List[str] = []
    distinct_sources = len(set(winning_sources))
    if distinct_sources >= min_sources:
        bonus += stack_bonus
        reasons.append(f"{distinct_sources} independent sources agree")
    if len(winning_tfs) >= 2:
        bonus += tf_bonus
        reasons.append(f"aligned across {len(winning_tfs)} timeframes")

    final_score = max(0.0, min(1.0, base_score + bonus))

    return {
        "direction": direction,
        "confluence_score": final_score,
        "call_score": call_score,
        "put_score": put_score,
        "sources_call": sources_call,
        "sources_put": sources_put,
        "timeframes_call": sorted(tf_call),
        "timeframes_put": sorted(tf_put),
        "reason": (
            f"{direction} wins with {distinct_sources} distinct sources"
            + (" · " + " · ".join(reasons) if reasons else "")
        ),
    }


def should_fire(
    result: Dict[str, Any],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> bool:
    """Hard gate for the auto-scan router."""
    if not result or result.get("direction") == "NEUTRAL":
        return False
    if float(result.get("confluence_score") or 0.0) < threshold:
        return False
    if result["direction"] == "CALL":
        if len(set(result.get("sources_call") or [])) < min_sources:
            return False
    else:
        if len(set(result.get("sources_put") or [])) < min_sources:
            return False
    return True


# ---------------------------------------------------------------------------
# Helper: turn a pattern-detector result into confluence signals
# ---------------------------------------------------------------------------

def signals_from_patterns(
    pattern_hits: List[Dict[str, Any]],
    asset: Optional[str] = None,
    timeframe: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert `PatternHit.to_dict()` outputs into confluence-engine signals."""
    out: List[Dict[str, Any]] = []
    for h in pattern_hits or []:
        d = (h.get("direction") or "").upper()
        if d not in ("CALL", "PUT"):
            continue
        out.append({
            "source": f"pattern:{h.get('pattern', 'unknown')}",
            "direction": d,
            "confidence": float(h.get("confidence") or 0.0),
            "asset": asset,
            "timeframe": timeframe,
        })
    return out
