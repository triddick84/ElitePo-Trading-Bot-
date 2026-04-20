"""
Real-Time Signal Feed (WebSocket)
==================================
Broadcasts signals, decisions, and trade outcomes to connected WebSocket clients.
Also persists strategy tracker data to MongoDB for cross-session continuity.
"""

import asyncio
import logging
import json
from typing import Dict, List, Set
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class SignalFeedManager:
    """Manages WebSocket connections and broadcasts real-time signal events."""

    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._event_history: List[Dict] = []  # Last 100 events
        self._max_history = 100

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)
        logger.info(f"WebSocket client connected ({self.client_count} total)")
        # Send recent history on connect
        try:
            await ws.send_json({"type": "history", "events": self._event_history[-20:]})
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)
        logger.info(f"WebSocket client disconnected ({self.client_count} total)")

    async def broadcast(self, event: Dict):
        """Broadcast an event to all connected clients."""
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        dead = set()
        for ws in self._clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    async def broadcast_signal(self, signal: Dict, source: str = "scan"):
        """Broadcast a new signal event."""
        await self.broadcast({
            "type": "signal",
            "source": source,
            "direction": signal.get("direction"),
            "symbol": signal.get("symbol"),
            "confidence": signal.get("confidence"),
            "strategy": signal.get("strategy") or signal.get("analysis_type", ""),
        })

    async def broadcast_decision(self, decision: Dict):
        """Broadcast a decision engine result."""
        await self.broadcast({
            "type": "decision",
            "action": decision.get("action"),
            "confidence": decision.get("confidence"),
            "regime": decision.get("regime"),
            "strategy_mode": decision.get("strategy_mode"),
            "position_size_pct": decision.get("position_size_pct"),
            "risk_check_passed": decision.get("risk_check_passed"),
            "model_votes": {k: v.get("direction") for k, v in (decision.get("model_votes") or {}).items()},
        })

    async def broadcast_outcome(self, symbol: str, direction: str, outcome: str, strategy: str = ""):
        """Broadcast a trade outcome."""
        await self.broadcast({
            "type": "outcome",
            "symbol": symbol,
            "direction": direction,
            "outcome": outcome,
            "strategy": strategy,
        })

    async def broadcast_routing(self, routing: Dict):
        """Broadcast signal routing result."""
        await self.broadcast({
            "type": "routing",
            "destinations": routing.get("destinations", []),
            "matched_rules": len(routing.get("matched_rules", [])),
            "dispatch": routing.get("dispatch_results", {}),
        })

    def get_status(self) -> Dict:
        return {
            "connected_clients": self.client_count,
            "events_buffered": len(self._event_history),
            "recent_events": self._event_history[-5:],
        }


class StrategyTrackerPersistence:
    """Persists strategy tracker data to MongoDB for cross-session continuity."""

    def __init__(self, db):
        self.db = db
        self.collection = db["strategy_tracker"]

    async def save(self, engine):
        """Save current strategy performance to MongoDB."""
        try:
            for symbol, perf in engine.performance.strategy_performance.items():
                total = perf.get("_total", {})
                strategies = {}
                for sk, sv in perf.items():
                    if not sk.startswith("_"):
                        strategies[sk] = sv

                await self.collection.update_one(
                    {"symbol": symbol},
                    {"$set": {
                        "symbol": symbol,
                        "total_wins": total.get("wins", 0),
                        "total_losses": total.get("losses", 0),
                        "total_pnl": total.get("pnl", 0),
                        "best_strategy": total.get("best_strategy", ""),
                        "best_win_rate": total.get("best_win_rate", 0),
                        "strategies": strategies,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True
                )

            # Save overall performance
            p = engine.performance
            await self.collection.update_one(
                {"symbol": "__overall__"},
                {"$set": {
                    "symbol": "__overall__",
                    "total_trades": p.total_trades,
                    "wins": p.wins,
                    "losses": p.losses,
                    "peak_balance": p.peak_balance,
                    "current_balance": p.current_balance,
                    "max_drawdown": p.max_drawdown,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Strategy tracker save error: {e}")

    async def load(self, engine):
        """Load persisted strategy performance into engine on startup."""
        try:
            cursor = self.collection.find({}, {"_id": 0})
            docs = await cursor.to_list(200)

            for doc in docs:
                sym = doc.get("symbol")
                if not sym or sym == "__overall__":
                    continue

                # Rebuild strategy_performance dict
                engine.performance.strategy_performance[sym] = {
                    "_total": {
                        "wins": doc.get("total_wins", 0),
                        "losses": doc.get("total_losses", 0),
                        "pnl": doc.get("total_pnl", 0),
                        "best_strategy": doc.get("best_strategy", ""),
                        "best_win_rate": doc.get("best_win_rate", 0),
                    }
                }
                for sk, sv in doc.get("strategies", {}).items():
                    engine.performance.strategy_performance[sym][sk] = sv

            # Restore overall
            overall = await self.collection.find_one({"symbol": "__overall__"}, {"_id": 0})
            if overall:
                engine.performance.total_trades = overall.get("total_trades", 0)
                engine.performance.wins = overall.get("wins", 0)
                engine.performance.losses = overall.get("losses", 0)
                engine.performance.peak_balance = overall.get("peak_balance", 10000)
                engine.performance.current_balance = overall.get("current_balance", 10000)
                engine.performance.max_drawdown = overall.get("max_drawdown", 0)

            loaded = len([d for d in docs if d.get("symbol") != "__overall__"])
            logger.info(f"Strategy tracker loaded: {loaded} assets from MongoDB")
            return loaded

        except Exception as e:
            logger.warning(f"Strategy tracker load error: {e}")
            return 0


# Singletons
_signal_feed = None
_tracker_persistence = None


def get_signal_feed() -> SignalFeedManager:
    global _signal_feed
    if _signal_feed is None:
        _signal_feed = SignalFeedManager()
    return _signal_feed


def get_tracker_persistence(db) -> StrategyTrackerPersistence:
    global _tracker_persistence
    if _tracker_persistence is None:
        _tracker_persistence = StrategyTrackerPersistence(db)
    return _tracker_persistence
