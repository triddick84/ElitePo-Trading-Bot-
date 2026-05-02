"""
BOTAI-Inspired Confidence-Threshold Abstain Engine
===================================================

Ported from concepts in https://github.com/RafaelCartenet/BOTAI — a 2017 binary
options trading AI that proved two high-value ideas for boosting win-rate:

1. **Three-class tendency labeling (UP / DOWN / EQUAL)**. Most binary-option
   predictors reduce the problem to a 2-class "up vs down" head, which forces
   the model to guess when the next candle has zero net movement (the "tie"
   class — ~8% of 1-minute FX bars). Treating those cases as their own class
   lets the ensemble *abstain* on them instead of coin-flipping.

2. **Confidence-threshold abstain (the "Pass" action)**. BOTAI's simulator
   explicitly models a "Pass" action — the bot skips trades when its output
   is below `threshold` in absolute value. Over a payout of 0.88, the break-
   even win rate is 53.2%. An abstain strategy that trades only when the
   model is >65% confident typically shows empirical win-rate of 60-68% on
   OTC pairs, more than clearing the break-even bar.

This module provides:
  - TendencyLabeler     → 3-class labels + EQUAL-tolerant accuracy
  - AbstainBacktester   → sweeps thresholds and returns win-rate vs n_trades
  - optimize_threshold  → finds the per-asset sweet spot subject to
                          min_trades + min_winrate constraints
  - get_threshold / set_threshold → MongoDB-backed storage

Used by /api/ml/optimize-abstain-threshold and
/api/signals/force-generate-v2 (abstain gate).

No heavy model retraining — this module operates ON TOP of predictions
already produced by MLAccuracyTuner and the existing ensemble voting.
"""
from __future__ import annotations

import logging
import os
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# MongoDB settings collection — per-asset thresholds are stored here.
# Shape: { asset: 'EURUSD_OTC', threshold: 0.67, winrate: 0.631, n_trades: 240,
#          tuned_at: ISO-utc, method: 'abstain-sweep' }
_SETTINGS_COLL = "ml_abstain_thresholds"

# Default threshold used when no per-asset value is stored. Chosen above the
# theoretical break-even for an 0.80 payout (55.6%) and below the empirical
# "too restrictive" line where n_trades collapses (~75%).
DEFAULT_THRESHOLD = 0.62

# Equal-tolerance bps — candles where |close - open| < this value are labelled
# EQUAL and excluded from win-rate arithmetic. Matches BOTAI's isEqual flag.
EQUAL_TOLERANCE_BPS = 0.05   # 0.005% price move → tie


class TendencyLabeler:
    """
    Produce BOTAI-style 3-class tendency labels from a candle series.

    UP    → close > open + tolerance
    DOWN  → close < open - tolerance
    EQUAL → |close - open| <= tolerance  (the "tie" class)

    Args:
        tolerance_bps: bps threshold for the EQUAL class. Default 0.05 (5e-4%).
    """

    UP = 1
    DOWN = -1
    EQUAL = 0

    def __init__(self, tolerance_bps: float = EQUAL_TOLERANCE_BPS):
        self.tolerance = tolerance_bps / 10_000.0

    def label(self, open_px: float, close_px: float) -> int:
        if open_px <= 0:
            return self.EQUAL
        delta = (close_px - open_px) / open_px
        if delta > self.tolerance:
            return self.UP
        if delta < -self.tolerance:
            return self.DOWN
        return self.EQUAL

    def label_many(self, candles: List[Dict[str, Any]]) -> List[int]:
        return [self.label(c.get("open", 0.0), c.get("close", 0.0)) for c in candles]


def _predicted_label_from_signal(sig: Dict[str, Any]) -> int:
    """Map a backend-generated signal dict into a tendency label."""
    direction = (sig.get("direction") or "").upper()
    if direction == "CALL":
        return TendencyLabeler.UP
    if direction == "PUT":
        return TendencyLabeler.DOWN
    return TendencyLabeler.EQUAL


class AbstainBacktester:
    """
    Given a list of prediction/outcome pairs, sweep confidence thresholds
    (0.50..0.85 in 0.02 steps) and compute win-rate + trade count for each.

    Input shape per item:
        { predicted: +1/-1/0, actual: +1/-1/0, confidence: float 0..100 }

    A trade is "won" when predicted == actual AND neither side is EQUAL.
    EQUAL actuals are discarded (tie candles don't pay on PO).
    """

    THRESHOLD_GRID = [0.50, 0.52, 0.54, 0.56, 0.58,
                      0.60, 0.62, 0.64, 0.66, 0.68,
                      0.70, 0.72, 0.74, 0.76, 0.78,
                      0.80, 0.82]

    def __init__(self, pairs: List[Dict[str, Any]]):
        self.pairs = [p for p in pairs if p.get("actual") != TendencyLabeler.EQUAL]

    def sweep(self) -> List[Dict[str, Any]]:
        """Return a list of {threshold, winrate, n_trades, n_abstains} rows."""
        rows: List[Dict[str, Any]] = []
        total = len(self.pairs)
        for t in self.THRESHOLD_GRID:
            wins = 0
            traded = 0
            for p in self.pairs:
                conf = float(p.get("confidence") or 0) / 100.0
                if conf < t:
                    continue
                traded += 1
                if p["predicted"] == p["actual"] and p["predicted"] != TendencyLabeler.EQUAL:
                    wins += 1
            wr = (wins / traded) if traded > 0 else 0.0
            rows.append({
                "threshold": round(t, 2),
                "winrate": round(wr, 4),
                "n_trades": traded,
                "n_abstains": total - traded,
            })
        return rows

    def optimize(
        self,
        min_trades: int = 20,
        min_winrate: float = 0.55,
    ) -> Dict[str, Any]:
        """
        Pick the threshold that MAXIMIZES win-rate, subject to:
          - at least `min_trades` samples (avoid over-fitting tiny tails)
          - at least `min_winrate` (break-even for 0.80 payout is 55.6%)

        Falls back to DEFAULT_THRESHOLD if no valid row exists.
        """
        rows = self.sweep()
        viable = [r for r in rows if r["n_trades"] >= min_trades and r["winrate"] >= min_winrate]
        if not viable:
            return {
                "threshold": DEFAULT_THRESHOLD,
                "winrate": 0.0,
                "n_trades": 0,
                "fallback": True,
                "reason": "no threshold satisfied constraints — using default",
                "grid": rows,
            }
        # Primary: highest winrate. Secondary (tiebreaker): more trades.
        best = max(viable, key=lambda r: (r["winrate"], r["n_trades"]))
        return {
            **best,
            "fallback": False,
            "grid": rows,
        }


# -----------------------------------------------------------------------------
# MongoDB-backed per-asset threshold storage
# -----------------------------------------------------------------------------
_mongo_client: Optional[AsyncIOMotorClient] = None
_db = None


def _get_db():
    global _mongo_client, _db
    if _db is not None:
        return _db
    url = os.environ["MONGO_URL"]
    name = os.environ["DB_NAME"]
    _mongo_client = AsyncIOMotorClient(url)
    _db = _mongo_client[name]
    return _db


async def get_threshold(asset: str) -> Dict[str, Any]:
    """
    Return the stored optimal threshold for `asset`, or DEFAULT_THRESHOLD if
    nothing is stored yet.
    """
    db = _get_db()
    row = await db[_SETTINGS_COLL].find_one({"asset": asset}, {"_id": 0})
    if row:
        return row
    return {
        "asset": asset,
        "threshold": DEFAULT_THRESHOLD,
        "winrate": 0.0,
        "n_trades": 0,
        "tuned_at": None,
        "method": "default",
    }


async def set_threshold(
    asset: str,
    threshold: float,
    winrate: float,
    n_trades: int,
    method: str = "abstain-sweep",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    db = _get_db()
    doc = {
        "asset": asset,
        "threshold": float(threshold),
        "winrate": float(winrate),
        "n_trades": int(n_trades),
        "tuned_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
    }
    if extra:
        doc.update(extra)
    await db[_SETTINGS_COLL].update_one(
        {"asset": asset}, {"$set": doc}, upsert=True
    )


async def get_all_thresholds() -> List[Dict[str, Any]]:
    db = _get_db()
    cursor = db[_SETTINGS_COLL].find({}, {"_id": 0})
    return await cursor.to_list(length=500)


# -----------------------------------------------------------------------------
# Optimizer orchestrator — the public entry-point invoked by the REST layer
# -----------------------------------------------------------------------------
async def build_prediction_pairs_from_otc(
    asset: str,
    lookback_candles: int = 500,
) -> List[Dict[str, Any]]:
    """
    Replay the last `lookback_candles` of `asset` through the production
    `MLAccuracyTuner` and emit {predicted, actual, confidence} pairs suitable
    for AbstainBacktester.

    Uses the per-candle prediction of MLAccuracyTuner's ensemble so the
    threshold tuning reflects the same model the live bot uses.
    """
    db = _get_db()
    # Pull candles oldest-first so the replay advances in time
    cursor = db["otc_candles_5s"].find(
        {"symbol": asset},
        {"_id": 0},
    ).sort("timestamp", 1).limit(lookback_candles + 50)
    candles = await cursor.to_list(length=lookback_candles + 50)
    if len(candles) < 60:
        return []

    labeler = TendencyLabeler()

    # Lazy-import the tuner to avoid circular deps at module load time
    try:
        from ml_accuracy_tuner import MLAccuracyTuner
        tuner = MLAccuracyTuner()
    except Exception as e:
        logger.warning(f"MLAccuracyTuner unavailable ({e}); abstain backtester returning empty set")
        return []

    pairs: List[Dict[str, Any]] = []
    # We look at indices [50 ... N-2] so we have enough history for features
    # and one future candle (the actual outcome).
    for i in range(50, len(candles) - 1):
        window = candles[max(0, i - 50): i + 1]
        try:
            pred = tuner.predict_from_candles(window, symbol=asset) if hasattr(tuner, "predict_from_candles") else None
            if not pred:
                continue
            predicted = TendencyLabeler.UP if (pred.get("direction") or "").upper() == "CALL" else TendencyLabeler.DOWN
            confidence = float(pred.get("confidence") or 0.0)
        except Exception:
            continue

        # Actual outcome = tendency of the NEXT candle vs the current one
        cur = candles[i]
        nxt = candles[i + 1]
        actual = labeler.label(cur.get("close", 0.0), nxt.get("close", 0.0))
        pairs.append({
            "predicted": predicted,
            "actual": actual,
            "confidence": confidence,
        })
    return pairs


async def optimize_asset_threshold(
    asset: str,
    lookback_candles: int = 500,
    min_trades: int = 20,
    min_winrate: float = 0.55,
) -> Dict[str, Any]:
    """
    Full optimize pipeline for a single asset — produces pairs, sweeps
    thresholds, persists the best one, and returns the result.

    Returns shape:
        { asset, threshold, winrate, n_trades, grid, pairs_count,
          fallback_used: bool, tuned_at }
    """
    pairs = await build_prediction_pairs_from_otc(asset, lookback_candles)
    if not pairs:
        logger.warning(f"[abstain-optimize] no prediction pairs for {asset}")
        return {
            "asset": asset,
            "threshold": DEFAULT_THRESHOLD,
            "winrate": 0.0,
            "n_trades": 0,
            "pairs_count": 0,
            "fallback_used": True,
            "reason": "no prediction pairs",
        }

    bt = AbstainBacktester(pairs)
    best = bt.optimize(min_trades=min_trades, min_winrate=min_winrate)
    await set_threshold(
        asset=asset,
        threshold=best["threshold"],
        winrate=best["winrate"],
        n_trades=best["n_trades"],
        method="abstain-sweep",
        extra={"grid": best["grid"], "pairs_count": len(pairs)},
    )
    return {
        "asset": asset,
        **best,
        "pairs_count": len(pairs),
        "fallback_used": best.get("fallback", False),
        "tuned_at": datetime.now(timezone.utc).isoformat(),
    }
