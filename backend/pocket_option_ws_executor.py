"""
Pocket Option WebSocket Trade Executor
--------------------------------------

Thin service wrapper around `pocketoptionapi_async.AsyncPocketOptionClient`.

Responsibilities:
- Maintains a singleton connected client using the currently bridged SSID
  (populated by the Tampermonkey interceptor at /api/po/ssid/update).
- Auto-reconnects on SSID rotation or connection drop.
- Exposes `place_order()` that returns in <500ms typical latency — critical
  for the 21-Second Reversal strategy which must fire at a precise time.

This service is intentionally minimal — no trade bookkeeping, no strategy
logic, no martingale. Just: "given SSID, place a trade as fast as possible".
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_client = None
_client_lock = asyncio.Lock()
_current_session: Optional[str] = None


def _normalize_asset(asset: str) -> str:
    """
    Normalize an asset symbol to the format pocketoptionapi_async expects.
    Handles inputs like 'EURUSD', 'EUR/USD', 'EURUSD_OTC', 'EUR/USD OTC', etc.
    """
    if not asset:
        return asset
    a = asset.strip().replace(" ", "").replace("/", "")
    # Normalize OTC suffix
    if a.upper().endswith("OTC") and not a.upper().endswith("_OTC"):
        a = a[:-3] + "_otc"
    a = a.replace("_OTC", "_otc")
    # If no OTC marker, leave uppercase (e.g., EURUSD)
    return a


async def _get_or_create_client(db) -> Any:
    """
    Return a connected AsyncPocketOptionClient using the latest bridged SSID.
    Reconnects if the SSID has rotated.
    """
    global _client, _current_session

    async with _client_lock:
        doc = await db["po_ssid_state"].find_one({"_id": "current"}, {"_id": 0})
        if not doc or not doc.get("session"):
            raise RuntimeError(
                "No bridged SSID available. Open Pocket Option with the "
                "Tampermonkey script installed so the WS auth frame is captured."
            )

        session = doc["session"]
        uid = int(doc.get("uid") or 0)
        is_demo = bool(doc.get("is_demo", True))

        # Client is valid and session hasn't rotated — reuse
        if _client is not None and _current_session == session:
            try:
                # cheap liveness check; if it raises, fall through to reconnect
                _ = await _client.get_balance()
                return _client
            except Exception as e:
                logger.warning(f"Existing PO client failed liveness check: {e}; reconnecting")
                try:
                    await _client.disconnect()
                except Exception:
                    pass
                _client = None

        # Session rotated or no client yet — (re)create
        from pocketoptionapi_async import AsyncPocketOptionClient

        client = AsyncPocketOptionClient(
            ssid=session,
            is_demo=is_demo,
            uid=uid,
            enable_logging=False,
        )
        ok = await client.connect()
        if not ok:
            raise RuntimeError("Pocket Option WS handshake failed (SSID may be expired)")

        _client = client
        _current_session = session
        logger.info(
            f"🔌 PO WS client connected: uid={uid} demo={is_demo} "
            f"session={session[:10]}..."
        )
        return _client


async def place_trade(
    db,
    asset: str,
    direction: str,
    amount: float,
    duration_seconds: int,
    wait_for_result: bool = False,
    result_timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Place a binary-option order via direct WebSocket.

    Args:
        db: Motor db instance
        asset: Asset symbol (e.g., 'EURUSD_otc', 'EUR/USD OTC')
        direction: 'CALL' or 'PUT'
        amount: Dollar amount
        duration_seconds: Expiry duration (4-5 for scalp strategies)
        wait_for_result: If True, awaits WIN/LOSS result (blocks up to result_timeout)
        result_timeout: Max seconds to wait if wait_for_result is True

    Returns:
        {
            "success": bool,
            "order_id": str,
            "placed_at_ms": int,
            "latency_ms": int,          # request → placed round-trip
            "asset": str,
            "direction": str,
            "amount": float,
            "duration": int,
            "status": str,              # 'placed' or 'closed' (if waited)
            "result": Optional[dict],   # {win: bool, profit: float} if waited
            "error": Optional[str],
        }
    """
    t0 = time.monotonic()
    asset_norm = _normalize_asset(asset)
    d = direction.upper()
    if d not in ("CALL", "PUT"):
        return {"success": False, "error": f"Invalid direction: {direction}"}

    try:
        client = await _get_or_create_client(db)
        from pocketoptionapi_async.models import OrderDirection

        order_dir = OrderDirection.CALL if d == "CALL" else OrderDirection.PUT
        order = await client.place_order(
            asset=asset_norm,
            amount=float(amount),
            direction=order_dir,
            duration=int(duration_seconds),
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        out: Dict[str, Any] = {
            "success": True,
            "order_id": getattr(order, "order_id", None),
            "placed_at_ms": int(time.time() * 1000),
            "latency_ms": latency_ms,
            "asset": asset_norm,
            "direction": d,
            "amount": float(amount),
            "duration": int(duration_seconds),
            "status": "placed",
            "result": None,
            "error": getattr(order, "error_message", None),
        }

        if wait_for_result and out["order_id"]:
            try:
                res = await asyncio.wait_for(
                    client.check_win(out["order_id"], max_wait_time=result_timeout),
                    timeout=result_timeout + 5,
                )
                if res:
                    profit = res.get("profit") if isinstance(res, dict) else None
                    win = bool(profit and profit > 0)
                    out["status"] = "closed"
                    out["result"] = {
                        "win": win,
                        "profit": profit,
                        "raw": res if isinstance(res, dict) else str(res),
                    }
            except asyncio.TimeoutError:
                out["status"] = "placed"
                out["result"] = {"win": None, "profit": None, "error": "result_timeout"}

        return out

    except RuntimeError as e:
        return {"success": False, "error": str(e), "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        logger.error(f"place_trade failure: {e}")
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }


async def get_client_status(db) -> Dict[str, Any]:
    """Lightweight health probe for the cached client."""
    global _client, _current_session
    if _client is None:
        return {"connected": False, "session_cached": None}
    try:
        balance = await _client.get_balance()
        return {
            "connected": True,
            "session_cached": (_current_session or "")[:10] + "...",
            "balance": balance,
        }
    except Exception as e:
        return {"connected": False, "session_cached": (_current_session or "")[:10] + "...", "error": str(e)}
