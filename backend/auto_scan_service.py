"""
Auto-Scan & Route Service — Iter 112 (Feb 2026)

Continuously scans a user-defined list of assets using the flexible-crossover
strategy, ranks matches by confidence, filters via the Elite Score Gate, and
sets `tampermonkey_settings.active_target` so the TM script auto-switches the
chart and executes the winning trade.

Public API
    scan_once(assets, cfg) → {results, winner}
    start(cfg)  – enable background loop (no-op if already running)
    stop()      – cancel background loop
    status()    – current running state + last scan
    set_config(cfg) – merge partial config, persist to Mongo
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "interval_seconds": 15,
    "chart_timeframe": "1m",
    "trade_duration_seconds": 82,
    "min_confidence": 0.65,
    "min_elite_score": 0,           # 0 = elite-gate disabled for scanner
    "prefer_elite_on_tie": True,
    "assets": [],                    # populated from config.selected_assets
    "strategy": {
        "sma_fast": 6, "sma_slow": 12,
        "supertrend_atr_period": 2, "supertrend_multiplier": 2.2,
        "ao_short_period": 6, "ao_long_period": 12,
    },
    "force_signal": False,
    "target_ttl_seconds": 60,       # how long the routed target stays valid
}


@dataclass
class _State:
    task: Optional[asyncio.Task] = None
    running: bool = False
    last_scan_ts: Optional[float] = None
    last_scan_results: List[Dict[str, Any]] = field(default_factory=list)
    last_winner: Optional[Dict[str, Any]] = None
    total_scans: int = 0
    total_routed: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


class AutoScanService:
    """Singleton coordinator for the auto-scan background loop."""

    def __init__(self):
        self._state = _State()
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._db = None  # set by server bootstrap
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Bootstrap / persistence
    # ------------------------------------------------------------------
    def bind_db(self, db) -> None:
        """Attach a Motor DB handle. Called once from server bootstrap."""
        self._db = db

    async def load_persisted_config(self) -> None:
        """Restore the last-saved config on startup."""
        if self._db is None:
            return
        try:
            doc = await self._db.auto_scan_config.find_one({"_id": "singleton"})
            if doc:
                self._merge_config({k: v for k, v in doc.items() if k != "_id"})
                logger.info(f"[auto_scan] restored config: enabled={self._config.get('enabled')} · "
                            f"interval={self._config.get('interval_seconds')}s · "
                            f"assets={len(self._config.get('assets') or [])}")
                if self._config.get("enabled"):
                    await self.start(self._config)
        except Exception as e:
            logger.warning(f"[auto_scan] load config failed: {e}")

    async def _persist_config(self) -> None:
        if self._db is None:
            return
        try:
            await self._db.auto_scan_config.update_one(
                {"_id": "singleton"},
                {"$set": {**self._config,
                          "_last_saved": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[auto_scan] persist failed: {e}")

    def _merge_config(self, cfg: Dict[str, Any]) -> None:
        for k, v in (cfg or {}).items():
            if k in DEFAULT_CONFIG:
                # Deep-merge the nested strategy dict
                if k == "strategy" and isinstance(v, dict):
                    strat = dict(self._config.get("strategy") or {})
                    strat.update(v)
                    self._config["strategy"] = strat
                else:
                    self._config[k] = v

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    async def set_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            self._merge_config(cfg or {})
            await self._persist_config()
        return self.get_config()

    def status(self) -> Dict[str, Any]:
        s = self._state
        return {
            "running": s.running,
            "config": self.get_config(),
            "stats": {
                "last_scan_ts": s.last_scan_ts,
                "total_scans": s.total_scans,
                "total_routed": s.total_routed,
                "error_count": s.error_count,
                "last_error": s.last_error,
            },
            "last_scan_results": s.last_scan_results,
            "last_winner": s.last_winner,
        }

    # ------------------------------------------------------------------
    # Core scan pipeline
    # ------------------------------------------------------------------
    async def _score_asset(self, asset: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Run flexible strategy on one asset and return a compact row."""
        from flexible_crossover_strategy import get_flexible_strategy

        row: Dict[str, Any] = {
            "asset": asset, "signal": None, "direction": None,
            "confidence": 0.0, "elite_score": None, "matched": False,
            "reason": "", "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            strategy_cfg = cfg.get("strategy") or {}
            strategy = get_flexible_strategy(
                chart_timeframe=cfg.get("chart_timeframe", "1m"),
                sma_fast=strategy_cfg.get("sma_fast", 6),
                sma_slow=strategy_cfg.get("sma_slow", 12),
                supertrend_atr_period=strategy_cfg.get("supertrend_atr_period", 2),
                supertrend_multiplier=strategy_cfg.get("supertrend_multiplier", 2.2),
                ao_short_period=strategy_cfg.get("ao_short_period", 6),
                ao_long_period=strategy_cfg.get("ao_long_period", 12),
            )
            # yfinance symbol mapping (mirrors /signals/flexible-generate)
            base = asset.replace("_OTC", "").replace("_otc", "")
            yf_symbol = base
            forex = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
                     "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "EURCHF",
                     "GBPJPY", "GBPCHF", "CHFJPY", "CADJPY", "AUDJPY",
                     "AUDCHF", "NZDJPY"}
            if base in forex:
                yf_symbol = f"{base}=X"
            elif base in ("BTCUSD", "ETHUSD", "LTCUSD", "ADAUSD", "DOGEUSD",
                          "SOLUSD"):
                yf_symbol = base[:-3] + "-USD"

            # Run in a thread so we don't block the event loop
            result = await asyncio.to_thread(
                strategy.generate_signal,
                yf_symbol,
                trade_duration_seconds=cfg.get("trade_duration_seconds", 82),
                force_signal=cfg.get("force_signal", False),
            )
            if not result:
                row["reason"] = "no_signal"
                return row

            direction = str(result.get("direction") or result.get("signal") or "").upper()
            confidence = float(result.get("confidence", 0.0) or 0.0)
            if confidence > 1.0:
                confidence /= 100.0

            row["signal"] = {k: v for k, v in result.items() if k not in ("candles",)}
            row["direction"] = direction if direction in ("CALL", "PUT") else None
            row["confidence"] = confidence
            row["matched"] = bool(row["direction"]) and confidence >= float(cfg.get("min_confidence", 0.65))
            if not row["matched"]:
                row["reason"] = f"low_conf {confidence:.2f} < {cfg.get('min_confidence',0.65)}"
        except Exception as e:
            row["reason"] = f"scan_error: {e}"
            logger.debug(f"[auto_scan] {asset} scan_error: {e}")

        # Iter 109 — attach Elite Score for tie-breaking + optional gating.
        try:
            from elite_screener_service import score_asset as elite_score_asset
            es = await elite_score_asset(asset, timeframe=cfg.get("chart_timeframe", "1m"))
            row["elite_score"] = float(es.get("elite_score", 0.0) or 0.0)
            row["elite_direction"] = es.get("direction", "NEUTRAL")
        except Exception:
            row["elite_score"] = None

        return row

    async def scan_once(self, assets: Optional[List[str]] = None,
                        cfg_override: Optional[Dict[str, Any]] = None
                        ) -> Dict[str, Any]:
        """Run one full scan. Returns {results, winner}."""
        cfg = dict(self._config)
        if cfg_override:
            for k, v in cfg_override.items():
                if k == "strategy" and isinstance(v, dict):
                    s = dict(cfg.get("strategy") or {})
                    s.update(v)
                    cfg["strategy"] = s
                elif k in cfg:
                    cfg[k] = v

        universe = [a.strip().upper() for a in (assets or cfg.get("assets") or [])
                    if a and a.strip()]
        if not universe:
            self._state.last_error = "empty_universe"
            return {"success": False, "error": "no assets in universe",
                    "results": [], "winner": None}

        # Concurrent scan across universe
        rows = await asyncio.gather(
            *[self._score_asset(a, cfg) for a in universe],
            return_exceptions=False,
        )

        # Filter: matched + optional elite-gate
        min_elite = float(cfg.get("min_elite_score", 0) or 0)
        matched = [r for r in rows if r.get("matched") and r.get("direction")
                   and (min_elite == 0 or (r.get("elite_score") or 0) >= min_elite)]

        # Sort by confidence desc, prefer higher elite score on tie
        def _key(r):
            elite = r.get("elite_score") or 0
            return (-round(r["confidence"], 6),
                    -(elite if cfg.get("prefer_elite_on_tie", True) else 0))
        matched.sort(key=_key)
        winner = matched[0] if matched else None

        # Update state
        self._state.last_scan_ts = datetime.now(timezone.utc).timestamp()
        self._state.last_scan_results = rows
        self._state.total_scans += 1

        # Route to TM if we have a winner
        if winner:
            await self._route_to_tm(winner, cfg)
            self._state.last_winner = winner
            self._state.total_routed += 1

        return {"success": True, "results": rows, "winner": winner,
                "universe_size": len(universe),
                "matched_count": len(matched)}

    async def _route_to_tm(self, winner: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        """Set `tampermonkey_settings.active_target` so the TM script switches
        the chart and executes the winning trade."""
        if self._db is None:
            return
        expires_at = (datetime.now(timezone.utc) +
                      timedelta(seconds=int(cfg.get("target_ttl_seconds", 60)))
                      ).isoformat()
        target = {
            "asset": winner["asset"],
            "timeframe": cfg.get("chart_timeframe", "1m"),
            "direction": winner["direction"],
            "confidence": winner["confidence"],
            "elite_score": winner.get("elite_score"),
            "source": "auto_scan",
            "expires_at": expires_at,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._db.tampermonkey_settings.update_one(
                {"_id": "singleton"},
                {"$set": {"active_target": target,
                          "last_updated": target["set_at"]}},
                upsert=True,
            )
            logger.info(f"[auto_scan] 🎯 ROUTED to TM · {winner['asset']} · "
                        f"{winner['direction']} · conf={winner['confidence']:.2f} · "
                        f"elite={winner.get('elite_score') or '—'}")
        except Exception as e:
            logger.warning(f"[auto_scan] route failed: {e}")

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------
    async def _loop(self) -> None:
        self._state.running = True
        logger.info(f"[auto_scan] background loop started · "
                    f"interval={self._config.get('interval_seconds')}s")
        try:
            while self._state.running:
                try:
                    await self.scan_once()
                except Exception as e:
                    self._state.error_count += 1
                    self._state.last_error = str(e)
                    logger.warning(f"[auto_scan] loop iter error: {e}")
                await asyncio.sleep(max(3, int(self._config.get("interval_seconds", 15))))
        except asyncio.CancelledError:
            logger.info("[auto_scan] loop cancelled")
        finally:
            self._state.running = False
            logger.info("[auto_scan] loop stopped")

    async def start(self, cfg_override: Optional[Dict[str, Any]] = None
                    ) -> Dict[str, Any]:
        """Enable + kick off the background loop."""
        async with self._lock:
            if cfg_override:
                self._merge_config(cfg_override)
            self._config["enabled"] = True
            await self._persist_config()
            if self._state.task and not self._state.task.done():
                return {"success": True, "message": "already running",
                        "status": self.status()}
            self._state.task = asyncio.create_task(self._loop())
            return {"success": True, "message": "started",
                    "status": self.status()}

    async def stop(self) -> Dict[str, Any]:
        async with self._lock:
            self._config["enabled"] = False
            await self._persist_config()
            self._state.running = False
            if self._state.task and not self._state.task.done():
                self._state.task.cancel()
                try:
                    await asyncio.wait_for(self._state.task, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            self._state.task = None
            return {"success": True, "message": "stopped",
                    "status": self.status()}


# Module-level singleton
auto_scan_service = AutoScanService()
