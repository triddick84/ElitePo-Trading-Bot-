"""Iter 150 — Fix pack routes.

Ships 5 fixes requested by user:
    1. TM chart-type selector → backend accepts chart_type on signal requests (already existed, we just document + validate)
    2. Telegram invert toggle
    3. AI Models optimization determinism explainer
    4. ML Lab retrain per-phase timeout
    5. Risk Guard → TM stakes bridge

Prefix: /api/*  (mixed — see individual @router decorators)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["iter150-fixpack"])


# ---------------------------------------------------------------------------
# #2 Telegram invert toggle
# ---------------------------------------------------------------------------

class InvertSetIn(BaseModel):
    enabled: bool


def _get_tg_service():
    """Resolve the module-level Telegram service (initialised by server.py)."""
    try:
        import server
        svc = getattr(server, "telegram_bot", None) or getattr(server, "telegram_service", None)
        if svc is None:
            # Fallback — lazy-instantiate
            from telegram_bot_service import TelegramBotService
            svc = TelegramBotService()
        return svc
    except Exception as e:
        logger.warning(f"[iter150] telegram service unavailable: {e}")
        return None


@router.get("/telegram/invert")
async def telegram_invert_status() -> Dict[str, Any]:
    """Current state of the invert toggle."""
    svc = _get_tg_service()
    if svc is None:
        raise HTTPException(503, "telegram service unavailable")
    return {
        "enabled": bool(getattr(svc, "invert_enabled", False)),
        "note": "When enabled, every telegram signal has its direction flipped (CALL↔PUT) before send.",
    }


@router.post("/telegram/invert")
async def telegram_invert_set(payload: InvertSetIn) -> Dict[str, Any]:
    """Enable / disable signal inversion in the Telegram bot service."""
    svc = _get_tg_service()
    if svc is None:
        raise HTTPException(503, "telegram service unavailable")
    svc.invert_enabled = bool(payload.enabled)
    logger.info(f"[iter150] telegram invert_enabled = {svc.invert_enabled}")
    return {"enabled": svc.invert_enabled}


@router.post("/telegram/invert/toggle")
async def telegram_invert_toggle() -> Dict[str, Any]:
    """One-click flip — useful for a UI toggle button."""
    svc = _get_tg_service()
    if svc is None:
        raise HTTPException(503, "telegram service unavailable")
    svc.invert_enabled = not bool(getattr(svc, "invert_enabled", False))
    return {"enabled": svc.invert_enabled}


# ---------------------------------------------------------------------------
# #3 AI Models optimization determinism explainer
# ---------------------------------------------------------------------------
# The existing /api/ml-training/run-optimization endpoint aggregates data
# from `backtest_results`. If the underlying data doesn't change between
# calls, the output is identical — that's expected behaviour, not a bug.
# We surface a data-version stamp so the UI can show "you're seeing the
# same answer because the input hasn't changed".

@router.get("/ml-training/optimization-data-version")
async def optimization_data_version() -> Dict[str, Any]:
    """Return the current state of `backtest_results` so the UI can tell
    users when a fresh optimization run WOULD produce different output.
    Empty DB or unchanged DB → same output every time (by design).
    """
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            raise HTTPException(503, "db unavailable")
        n = await db.backtest_results.count_documents({})
        # Last-created marker
        last = await db.backtest_results.find({}).sort(
            "created_at", -1
        ).limit(1).to_list(1)
        last_ts = None
        if last:
            last_ts = last[0].get("created_at")
            if isinstance(last_ts, datetime):
                last_ts = last_ts.isoformat()
        return {
            "backtest_rows": n,
            "last_backtest_ts": last_ts,
            "min_required": 5,
            "eligible_to_optimize": n >= 5,
            "note": (
                "Optimization output is a deterministic aggregation of "
                "`backtest_results`. Identical inputs → identical outputs. "
                "Run new backtests to see recommendations change."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"failed: {e}")


# ---------------------------------------------------------------------------
# #4 ML Lab retrain — per-phase timeout wrapper
# ---------------------------------------------------------------------------
# See routes/ml.py::_do_clean_retrain — Phase 2 (`training_maximized_ml_v3`)
# can hang indefinitely because `train_from_oanda` isn't timeboxed. We add
# a helper that any caller can use to wrap a coroutine with a hard timeout
# so the entire retrain never stalls.
#
# Iter 153 (Feb 20, 2026) — Critical: `train_from_oanda` is declared `async`
# but its body is 100 % synchronous CPU-bound work (sklearn training,
# `cross_val_score`, feature-extraction loops). Because it never yields to
# the event loop:
#   1. `asyncio.wait_for` cannot cancel it — no yield = no cancellation.
#   2. The main event loop is fully blocked, so `/api/ml/retrain-status`
#      polls stall and the UI hangs on "retraining" until the whole
#      pipeline finishes (often minutes) or the browser gives up.
# We now offload each phase into a worker thread with its OWN event loop
# via `asyncio.to_thread`, so the main loop stays responsive AND `wait_for`
# on the thread future works correctly.

def _drive_coroutine_in_thread(coro):
    """Run a coroutine to completion in a fresh event loop. Called from
    inside `asyncio.to_thread`, so it executes in a worker thread — the
    main event loop stays free to serve status polls."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def run_phase_with_timeout(coro, phase_name: str,
                                 timeout_s: int = 90) -> Dict[str, Any]:
    """Run `coro` (a coroutine) with a hard time limit. Returns a status dict
    the retrain loop can persist directly to `_retrain_status["results"]`.

    The coroutine is driven in a worker thread — see the module docstring
    above for why this matters for CPU-bound "async" bodies.
    """
    started = datetime.now(timezone.utc)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_drive_coroutine_in_thread, coro),
            timeout=timeout_s,
        )
        return {
            "success": True,
            "phase": phase_name,
            "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
            "result": str(result)[:200] if result is not None else "ok",
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "phase": phase_name,
            "elapsed_s": timeout_s,
            "error": f"timeout after {timeout_s}s — phase did not complete",
        }
    except Exception as e:
        return {
            "success": False,
            "phase": phase_name,
            "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
            "error": f"{type(e).__name__}: {e}",
        }


# ---------------------------------------------------------------------------
# #5 Risk Guard → Tampermonkey bridge
# ---------------------------------------------------------------------------

@router.get("/riskguard/tampermonkey/config")
async def riskguard_tampermonkey_config(user_id: str = "default") -> Dict[str, Any]:
    """Everything the TM script needs to run a session with the current
    Risk Guard rules. Called when the user clicks "Start Session" in the
    TM panel.
    """
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            raise HTTPException(503, "db unavailable")

        # 1. Fetch the active Risk Guard session (if any)
        session = await db.riskguard_sessions.find_one(
            {"user_id": user_id, "status": "active"}
        )
        # 2. Fetch the latest closed session for defaults
        default_ref = await db.riskguard_sessions.find_one(
            {"user_id": user_id}, sort=[("started_at", -1)]
        )
        base = session or default_ref or {}

        start_amount = float(base.get("start_amount") or base.get("bankroll") or 100.0)
        per_trade = float(base.get("per_trade_amount")
                          or base.get("stake_amount")
                          or (start_amount * 0.02))          # default 2% of bankroll
        max_daily_loss = float(base.get("max_daily_loss") or (start_amount * 0.10))
        stop_after_losses = int(base.get("stop_after_losses")
                                or base.get("stop_trading_after_losses") or 3)

        # 3. Confidence-tiered stakes (multipliers by confidence bucket)
        tiered = base.get("confidence_tiers") or [
            {"min_confidence": 55, "multiplier": 0.75},
            {"min_confidence": 65, "multiplier": 1.00},
            {"min_confidence": 75, "multiplier": 1.50},
            {"min_confidence": 85, "multiplier": 2.00},
        ]

        return {
            "ok": True,
            "user_id": user_id,
            "session_active": session is not None,
            "session_id": (session or {}).get("session_id"),
            "start_amount": start_amount,
            "per_trade_amount": per_trade,
            "max_daily_loss": max_daily_loss,
            "stop_after_losses": stop_after_losses,
            "confidence_tiers": tiered,
            "server_ts": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[iter150] riskguard/tampermonkey/config error: {e}")
        # Never fail the TM start button — return safe defaults so trading
        # continues with conservative fixed stakes.
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "user_id": user_id,
            "session_active": False,
            "start_amount": 100.0,
            "per_trade_amount": 2.0,
            "max_daily_loss": 10.0,
            "stop_after_losses": 3,
            "confidence_tiers": [
                {"min_confidence": 55, "multiplier": 0.75},
                {"min_confidence": 65, "multiplier": 1.00},
                {"min_confidence": 75, "multiplier": 1.50},
                {"min_confidence": 85, "multiplier": 2.00},
            ],
        }
