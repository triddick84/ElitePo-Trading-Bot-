"""Iter 131 — RiskGuard: Capital-Guard-Pro–style trade sizing + session discipline.

Provides:
  1. Trade-size calculator — how big should the next trade be given capital,
     payout %, target profit, stop-loss and how many trades remain in the
     session.
  2. Session tracker — every session has hard stop-loss / target / max-trades
     limits. Records each trade outcome (win/loss/draw) and blocks further
     trades once a limit is breached.
  3. Performance analytics — win-rate, avg P&L, account gain across sessions.

Persistence: `risk_guard_sessions` collection (Mongo). One active session at a
time per user, plus historical rows.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum stake the calculator will ever suggest (PO's floor is $1 for demo,
# $1 for real). Anything below feels reckless.
MIN_STAKE = 1.0
# Maximum stake the calculator will ever suggest as a fraction of capital.
# Even if the raw math says "$400 on a $1000 account" we cap it to 25 % so
# the user cannot blow the account on one over-sized bet.
MAX_STAKE_FRACTION = 0.25


def calculate_next_trade(
    *,
    capital: float,
    payout_pct: float,
    target_profit: float,
    stop_loss: float,
    max_trades: int,
    trades_taken: int,
    current_pnl: float,
) -> Dict[str, Any]:
    """Compute the minimum next-trade amount for a binary-options session.

    Formula:
        remaining_target = max(target_profit - current_pnl, 0)
        remaining_trades = max(max_trades - trades_taken, 1)
        raw = remaining_target / (remaining_trades * payout_pct)

    Then clamped by:
      • MIN_STAKE
      • capital * MAX_STAKE_FRACTION
      • remaining_stop_loss_budget (never risk more than what's left before
        the session hits its stop-loss cap)
    """
    if capital <= 0 or payout_pct <= 0:
        return {
            "allowed": False,
            "reason": "capital and payout must be positive",
            "amount": 0.0,
        }

    remaining_target = max(target_profit - current_pnl, 0.0)
    remaining_trades = max(int(max_trades) - int(trades_taken), 1)

    # If session is already past its target → tell the user to stop.
    if current_pnl >= target_profit and target_profit > 0:
        return {
            "allowed": False,
            "reason": "target_reached",
            "amount": 0.0,
            "session_status": "target_reached",
            "current_pnl": current_pnl,
            "target_profit": target_profit,
        }

    # If session is already past its stop-loss → force stop.
    if current_pnl <= -abs(stop_loss) and stop_loss > 0:
        return {
            "allowed": False,
            "reason": "stop_loss_hit",
            "amount": 0.0,
            "session_status": "stop_loss_hit",
            "current_pnl": current_pnl,
            "stop_loss": -abs(stop_loss),
        }

    # If no trades left → stop.
    if trades_taken >= max_trades:
        return {
            "allowed": False,
            "reason": "max_trades_reached",
            "amount": 0.0,
            "session_status": "max_trades_reached",
        }

    raw = remaining_target / (remaining_trades * payout_pct) if remaining_target > 0 else MIN_STAKE

    # Never risk more than remaining stop-loss budget on a single trade.
    remaining_loss_budget = abs(stop_loss) - abs(current_pnl) if current_pnl < 0 else abs(stop_loss)
    if remaining_loss_budget > 0:
        raw = min(raw, remaining_loss_budget)

    # Cap at MAX_STAKE_FRACTION * capital.
    raw = min(raw, capital * MAX_STAKE_FRACTION)
    # Floor at MIN_STAKE.
    amount = max(round(raw, 2), MIN_STAKE)

    return {
        "allowed": True,
        "amount": amount,
        "remaining_target": round(remaining_target, 2),
        "remaining_trades": remaining_trades,
        "remaining_loss_budget": round(max(remaining_loss_budget, 0.0), 2),
        "session_status": "active",
    }


def compute_session_status(session: Dict[str, Any]) -> str:
    """Derive a session's status from its rules + trade history."""
    trades = session.get("trades") or []
    pnl = sum(t.get("pnl", 0.0) for t in trades)
    if pnl >= float(session.get("target_profit") or 0) and session.get("target_profit"):
        return "target_reached"
    if abs(pnl) >= float(session.get("stop_loss") or 0) and session.get("stop_loss") and pnl < 0:
        return "stop_loss_hit"
    if len(trades) >= int(session.get("max_trades") or 0) and session.get("max_trades"):
        return "max_trades_reached"
    if session.get("closed_at"):
        return "closed"
    return "active"


def summarize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate a session doc into the shape the UI wants."""
    trades: List[Dict[str, Any]] = session.get("trades") or []
    wins = sum(1 for t in trades if t.get("outcome") == "win")
    losses = sum(1 for t in trades if t.get("outcome") == "loss")
    draws = sum(1 for t in trades if t.get("outcome") == "draw")
    pnl = round(sum(t.get("pnl", 0.0) for t in trades), 2)
    win_rate = round((wins / (wins + losses)) * 100, 1) if (wins + losses) else 0.0
    capital = float(session.get("capital") or 0.0)
    account_gain_pct = round((pnl / capital) * 100, 2) if capital else 0.0
    return {
        "id": session.get("id"),
        "user_id": session.get("user_id"),
        "capital": capital,
        "payout_pct": float(session.get("payout_pct") or 0.0),
        "target_profit": float(session.get("target_profit") or 0.0),
        "stop_loss": float(session.get("stop_loss") or 0.0),
        "max_trades": int(session.get("max_trades") or 0),
        "trades_taken": len(trades),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "current_pnl": pnl,
        "win_rate": win_rate,
        "account_gain_pct": account_gain_pct,
        "status": compute_session_status(session),
        "started_at": session.get("started_at"),
        "closed_at": session.get("closed_at"),
        "trades": trades,
    }


class RiskGuardService:
    """Persistence + business logic for the RiskGuard module.

    One active session per user. Historical sessions kept for analytics.
    """

    def __init__(self):
        self._db = None

    def bind_db(self, db) -> None:
        self._db = db

    # ---------------- Session lifecycle ----------------
    async def start_session(
        self,
        user_id: str,
        capital: float,
        payout_pct: float,
        target_profit: float,
        stop_loss: float,
        max_trades: int,
    ) -> Dict[str, Any]:
        assert self._db is not None
        # Close any existing active session first (only one at a time).
        await self._db.risk_guard_sessions.update_many(
            {"user_id": user_id, "closed_at": None},
            {"$set": {"closed_at": datetime.now(timezone.utc).isoformat(),
                      "closed_reason": "superseded"}},
        )
        session = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "capital": float(capital),
            "payout_pct": float(payout_pct),
            "target_profit": float(target_profit),
            "stop_loss": float(stop_loss),
            "max_trades": int(max_trades),
            "trades": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "closed_at": None,
        }
        await self._db.risk_guard_sessions.insert_one(session)
        session.pop("_id", None)
        return summarize_session(session)

    async def get_active_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        assert self._db is not None
        doc = await self._db.risk_guard_sessions.find_one(
            {"user_id": user_id, "closed_at": None},
            {"_id": 0},
            sort=[("started_at", -1)],
        )
        if not doc:
            return None
        return summarize_session(doc)

    async def record_trade(
        self,
        user_id: str,
        outcome: str,   # "win" | "loss" | "draw"
        amount: float,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        assert self._db is not None
        session = await self._db.risk_guard_sessions.find_one(
            {"user_id": user_id, "closed_at": None},
            sort=[("started_at", -1)],
        )
        if not session:
            return {"success": False, "error": "no_active_session"}
        outcome = (outcome or "").lower()
        payout_pct = float(session.get("payout_pct") or 0.0)
        amt = float(amount)
        if outcome == "win":
            pnl = round(amt * payout_pct, 2)
        elif outcome == "loss":
            pnl = round(-amt, 2)
        elif outcome == "draw":
            pnl = 0.0
        else:
            return {"success": False, "error": "invalid_outcome"}
        trade = {
            "id": str(uuid.uuid4()),
            "outcome": outcome,
            "amount": amt,
            "pnl": pnl,
            "note": note,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        await self._db.risk_guard_sessions.update_one(
            {"id": session["id"]},
            {"$push": {"trades": trade}},
        )
        # Refresh the session doc after push.
        session = await self._db.risk_guard_sessions.find_one(
            {"id": session["id"]}, {"_id": 0},
        )
        status = compute_session_status(session)
        # Auto-close if a hard limit is hit.
        if status in ("target_reached", "stop_loss_hit", "max_trades_reached"):
            await self._db.risk_guard_sessions.update_one(
                {"id": session["id"]},
                {"$set": {"closed_at": datetime.now(timezone.utc).isoformat(),
                          "closed_reason": status}},
            )
            session = await self._db.risk_guard_sessions.find_one(
                {"id": session["id"]}, {"_id": 0},
            )
        return {"success": True, "session": summarize_session(session), "trade": trade}

    async def close_session(self, user_id: str) -> Dict[str, Any]:
        assert self._db is not None
        result = await self._db.risk_guard_sessions.update_many(
            {"user_id": user_id, "closed_at": None},
            {"$set": {"closed_at": datetime.now(timezone.utc).isoformat(),
                      "closed_reason": "manual"}},
        )
        return {"success": True, "closed": result.modified_count}

    async def get_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        assert self._db is not None
        limit = max(1, min(200, int(limit)))
        cur = self._db.risk_guard_sessions.find(
            {"user_id": user_id},
            {"_id": 0},
        ).sort("started_at", -1).limit(limit)
        rows = await cur.to_list(length=limit)
        return [summarize_session(r) for r in rows]

    async def summary(self, user_id: str) -> Dict[str, Any]:
        history = await self.get_history(user_id, limit=200)
        total_trades = sum(h["trades_taken"] for h in history)
        wins = sum(h["wins"] for h in history)
        losses = sum(h["losses"] for h in history)
        pnl = round(sum(h["current_pnl"] for h in history), 2)
        wr = round((wins / (wins + losses)) * 100, 1) if (wins + losses) else 0.0
        sessions_hit_target = sum(1 for h in history if h["status"] == "target_reached")
        sessions_hit_stop   = sum(1 for h in history if h["status"] == "stop_loss_hit")
        return {
            "total_sessions": len(history),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": wr,
            "total_pnl": pnl,
            "sessions_hit_target": sessions_hit_target,
            "sessions_hit_stop_loss": sessions_hit_stop,
        }


risk_guard_service = RiskGuardService()
