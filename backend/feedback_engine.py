"""
Post-trade Feedback Engine (Iter 115c).

Every time a trade closes (win / loss / tie), we update a per-strategy
Bayesian rolling win-rate and a confidence-scaling multiplier. The scaling
multiplier is applied to any live signal's confidence at emission time so
that:

- consistently-winning strategies boost their confidence upward
- consistently-losing strategies get dampened (or effectively muted)

The math is a lightweight Beta(α, β) posterior over the strategy's
win-probability p, plus a rolling context filter (regime × session).

Persistence layer: MongoDB collection `strategy_performance_stats`
Key document shape:
  {
    "_id":            "<strategy_id>",
    "strategy_id":    "<strategy_id>",
    "alpha":          10.0,          # Beta prior + wins
    "beta":           10.0,          # Beta prior + losses
    "wins":           17,
    "losses":         13,
    "ties":            0,
    "last_updated":   ISO8601,
    "by_regime": {
        "TREND":   {"wins": 10, "losses": 3, ...},
        "CHOPPY":  {"wins":  5, "losses": 7, ...},
        "NEUTRAL": {"wins":  2, "losses": 3, ...}
    },
    "recent_outcomes": ["WIN", "WIN", "LOSS", ...]  # capped at 50
  }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Beta prior — starts every strategy near 50/50 with modest confidence
_PRIOR_ALPHA = 10.0
_PRIOR_BETA = 10.0

# Multiplier bounds
_MIN_MULTIPLIER = 0.5    # never scale confidence below 50%
_MAX_MULTIPLIER = 1.30   # never boost above +30%


def _empty_stats(strategy_id: str) -> Dict[str, Any]:
    return {
        "_id": strategy_id,
        "strategy_id": strategy_id,
        "alpha": _PRIOR_ALPHA,
        "beta": _PRIOR_BETA,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "by_regime": {},
        "recent_outcomes": [],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _regime_bucket(stats: Dict[str, Any], regime: str) -> Dict[str, Any]:
    stats.setdefault("by_regime", {})
    return stats["by_regime"].setdefault(
        regime, {"wins": 0, "losses": 0, "ties": 0}
    )


async def record_outcome(
    db,
    strategy_id: str,
    outcome: str,
    regime: str = "NEUTRAL",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist a trade outcome and update the strategy's posterior.

    Args:
        db: motor.AsyncIOMotorDatabase instance (from routes.db).
        strategy_id: id of the strategy that produced the signal.
        outcome: "WIN" | "LOSS" | "TIE"
        regime: "TREND" | "CHOPPY" | "NEUTRAL"
        metadata: any extra info (asset, timeframe, confidence, etc.)
    """
    strategy_id = str(strategy_id or "unknown").strip()
    outcome = str(outcome or "").upper()
    if outcome not in ("WIN", "LOSS", "TIE"):
        return {"success": False, "error": f"invalid outcome {outcome!r}"}

    stats = await db.strategy_performance_stats.find_one(
        {"_id": strategy_id}
    ) or _empty_stats(strategy_id)

    if outcome == "WIN":
        stats["wins"] = int(stats.get("wins", 0)) + 1
        stats["alpha"] = float(stats.get("alpha", _PRIOR_ALPHA)) + 1.0
    elif outcome == "LOSS":
        stats["losses"] = int(stats.get("losses", 0)) + 1
        stats["beta"] = float(stats.get("beta", _PRIOR_BETA)) + 1.0
    else:
        stats["ties"] = int(stats.get("ties", 0)) + 1

    bucket = _regime_bucket(stats, regime)
    if outcome == "WIN":
        bucket["wins"] = int(bucket.get("wins", 0)) + 1
    elif outcome == "LOSS":
        bucket["losses"] = int(bucket.get("losses", 0)) + 1
    else:
        bucket["ties"] = int(bucket.get("ties", 0)) + 1

    recent = list(stats.get("recent_outcomes", []) or [])
    recent.append(outcome)
    if len(recent) > 50:
        recent = recent[-50:]
    stats["recent_outcomes"] = recent
    stats["last_updated"] = datetime.now(timezone.utc).isoformat()
    if metadata:
        stats["last_metadata"] = metadata

    await db.strategy_performance_stats.replace_one(
        {"_id": strategy_id}, stats, upsert=True
    )
    return {"success": True, "stats": _summarise(stats)}


def _summarise(stats: Dict[str, Any]) -> Dict[str, Any]:
    alpha = float(stats.get("alpha", _PRIOR_ALPHA))
    beta = float(stats.get("beta", _PRIOR_BETA))
    n = alpha + beta
    posterior_mean = alpha / n if n > 0 else 0.5
    return {
        "strategy_id": stats.get("strategy_id"),
        "posterior_win_rate": round(posterior_mean, 4),
        "alpha": alpha,
        "beta": beta,
        "wins": stats.get("wins", 0),
        "losses": stats.get("losses", 0),
        "ties": stats.get("ties", 0),
        "n_trades": int(stats.get("wins", 0)) + int(stats.get("losses", 0)) + int(stats.get("ties", 0)),
        "confidence_multiplier": _multiplier_from_posterior(posterior_mean, n),
        "by_regime": stats.get("by_regime", {}),
        "recent_outcomes": stats.get("recent_outcomes", []),
        "last_updated": stats.get("last_updated"),
    }


def _multiplier_from_posterior(p: float, n: float) -> float:
    """
    Map posterior win-rate to a confidence multiplier.

    - p = 0.50 → multiplier 1.00 (no change)
    - p = 0.60 → multiplier ≈ 1.15
    - p = 0.70 → multiplier ≈ 1.25 (clamped at MAX)
    - p = 0.40 → multiplier ≈ 0.85
    - p = 0.30 → multiplier ≈ 0.65

    Weight by sample size — until we have 30+ trades we barely tilt.
    """
    # Confidence in the posterior grows with n
    weight = min(1.0, max(0.0, (n - 20.0) / 60.0))  # 0 at n=20, 1 at n=80
    raw = 1.0 + (p - 0.5) * 1.5 * weight
    return round(max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, raw)), 4)


async def get_multiplier(
    db,
    strategy_id: str,
    regime: Optional[str] = None,
) -> float:
    """Return the current confidence multiplier for a strategy.
    If `regime` is given and the strategy has >= 15 trades in that regime,
    use the regime-specific posterior."""
    if not strategy_id:
        return 1.0
    stats = await db.strategy_performance_stats.find_one({"_id": str(strategy_id)})
    if not stats:
        return 1.0

    # regime-scoped multiplier
    if regime:
        bucket = (stats.get("by_regime") or {}).get(regime)
        if bucket:
            r_wins = int(bucket.get("wins", 0))
            r_losses = int(bucket.get("losses", 0))
            r_n = r_wins + r_losses
            if r_n >= 15:
                # Regime-scoped Beta with the same prior
                r_alpha = _PRIOR_ALPHA + r_wins
                r_beta = _PRIOR_BETA + r_losses
                r_p = r_alpha / (r_alpha + r_beta)
                return _multiplier_from_posterior(r_p, r_alpha + r_beta)

    # global posterior
    alpha = float(stats.get("alpha", _PRIOR_ALPHA))
    beta = float(stats.get("beta", _PRIOR_BETA))
    p = alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5
    return _multiplier_from_posterior(p, alpha + beta)


async def get_stats(db, strategy_id: str) -> Optional[Dict[str, Any]]:
    if not strategy_id:
        return None
    stats = await db.strategy_performance_stats.find_one({"_id": str(strategy_id)})
    return _summarise(stats) if stats else None


async def list_all(db, limit: int = 200) -> List[Dict[str, Any]]:
    cursor = db.strategy_performance_stats.find({}).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_summarise(d) for d in docs]
