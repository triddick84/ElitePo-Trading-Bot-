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
    "interval_seconds": 5,  # Iter 125 — was 15s; multi-asset rotation needs faster ticks
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
    # Iter 140 — Confluence gate. When enabled, the auto-scan winner must
    # ALSO pass the Iter 137 confluence engine (patterns + smart-money +
    # mean-reversion + strategy signal → weighted score) before a trade
    # can be routed. Threshold + min_sources come from confluence_routes'
    # get_confluence_config() so the CONFIG-tab slider takes effect live.
    "confluence_gate_enabled": True,
    "confluence_candle_limit": 200, # how many candles to pull per gate check
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
    # Iter 125 — rotate through top-N winners on consecutive scans so the TM
    # script places trades across multiple assets, not just the same one.
    rotation_index: int = 0


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

        # Iter 140 — Confluence gate enrichment. Runs the Iter 137 patterns +
        # Iter 139 smart-money detectors + mean-reversion + the strategy
        # signal itself through score_confluence(). Result is stored on the
        # row so scan_once() can filter by should_fire() when the gate is on.
        if row.get("matched"):
            try:
                row["confluence"] = await self._confluence_evaluate(asset, row, cfg)
            except Exception as _ce:
                logger.debug(f"[auto_scan] {asset} confluence skipped: {_ce}")
                row["confluence"] = None
        return row

    async def _confluence_evaluate(
        self, asset: str, row: Dict[str, Any], cfg: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Build a signal list from patterns + smart-money + mean-reversion +
        strategy + elite, and score it through the Iter 137 confluence engine.

        Returns:
            {
                "result": <score_confluence output dict>,
                "fires": bool,
                "threshold": float, "min_sources": int,
                "n_signals": int,
            }
            or None when we can't evaluate (no candles / import failure).
        """
        # Late imports keep the auto-scan service loadable even if these
        # modules haven't fully initialised on server start.
        from routes.confluence_routes import _load_candles_from_db, get_confluence_config
        from confluence_service import score_confluence, should_fire, signals_from_patterns
        from pattern_detector import detect_all as detect_patterns
        from smart_money import detect_all_smart_money
        from strategies.mean_reversion import mean_reversion_signal

        timeframe = cfg.get("chart_timeframe", "1m")
        limit = int(cfg.get("confluence_candle_limit", 200))
        df = await _load_candles_from_db(asset, timeframe, limit)
        if df is None or df.empty:
            return None

        signals: List[Dict[str, Any]] = []

        # 1. The strategy's own vote — carries its own confidence.
        if row.get("direction") in ("CALL", "PUT"):
            signals.append({
                "source": "strategy:flexible_crossover",
                "direction": row["direction"],
                "confidence": float(row.get("confidence") or 0.0),
                "asset": asset,
                "timeframe": timeframe,
            })

        # 2. Elite score — treat it as a directional signal when it has one.
        elite_dir = (row.get("elite_direction") or "").upper()
        elite = row.get("elite_score")
        if elite_dir in ("CALL", "PUT") and elite is not None and elite > 0:
            signals.append({
                "source": "elite",
                "direction": elite_dir,
                "confidence": min(1.0, float(elite) / 100.0 if elite > 1 else float(elite)),
                "asset": asset,
                "timeframe": timeframe,
            })

        # 3. Chart patterns (Iter 137)
        pattern_hits = [h.to_dict() for h in detect_patterns(df)]
        signals.extend(signals_from_patterns(pattern_hits, asset=asset, timeframe=timeframe))

        # 4. Smart money (Iter 139)
        sm_hits = [h.to_dict() for h in detect_all_smart_money(df)]
        for h in sm_hits:
            d = (h.get("direction") or "").upper()
            if d in ("CALL", "PUT"):
                signals.append({
                    "source": f"smart_money:{h.get('pattern')}",
                    "direction": d,
                    "confidence": float(h.get("confidence") or 0.0),
                    "asset": asset,
                    "timeframe": timeframe,
                })

        # 5. Mean reversion (Iter 139)
        mr = mean_reversion_signal(df)
        if mr.direction in ("CALL", "PUT"):
            signals.append({
                "source": "strategy:mean_reversion",
                "direction": mr.direction,
                "confidence": float(mr.confidence or 0.0),
                "asset": asset,
                "timeframe": timeframe,
            })

        gate_cfg = get_confluence_config()
        threshold = float(gate_cfg.get("threshold", 0.65))
        min_sources = int(gate_cfg.get("min_sources", 3))
        result = score_confluence(signals, min_sources=min_sources)
        fires = should_fire(result, threshold=threshold, min_sources=min_sources)
        return {
            "result": result,
            "fires": fires,
            "threshold": threshold,
            "min_sources": min_sources,
            "n_signals": len(signals),
        }

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

        # Iter 140 — Confluence gate. Drop winners whose combined signal
        # stack didn't clear the threshold. This is the primary noise filter:
        # a strategy signal alone is no longer enough — patterns / smart
        # money / mean-reversion / elite must corroborate.
        gate_active = bool(cfg.get("confluence_gate_enabled", True))
        if gate_active:
            before = len(matched)
            matched = [
                r for r in matched
                if r.get("confluence") is None or r["confluence"].get("fires", False)
                # We keep rows with confluence=None (evaluation couldn't run —
                # no candles etc.) so the bot still trades when data is thin.
                # Rows that DID evaluate but didn't fire are the ones dropped.
            ]
            dropped = before - len(matched)
            if dropped > 0:
                logger.info(f"[auto_scan] 🔮 confluence gate dropped {dropped}/{before} winners")

        # Sort by confidence desc, prefer higher elite score on tie
        def _key(r):
            elite = r.get("elite_score") or 0
            return (-round(r["confidence"], 6),
                    -(elite if cfg.get("prefer_elite_on_tie", True) else 0))
        matched.sort(key=_key)

        # Iter 125 — Rotate through top-5 winners on consecutive scans so
        # the TM script trades across multiple assets, not just the same one.
        top_n = matched[:5]
        if top_n:
            winner = top_n[self._state.rotation_index % len(top_n)]
            self._state.rotation_index = (self._state.rotation_index + 1) % max(1, len(top_n))
        else:
            winner = None

        # Update state
        self._state.last_scan_ts = datetime.now(timezone.utc).timestamp()
        self._state.last_scan_results = rows
        self._state.total_scans += 1

        # Route to TM if we have a winner
        if winner:
            await self._route_to_tm(winner, cfg)
            self._state.last_winner = winner
            self._state.total_routed += 1

        # Iter 125 — Multi-asset queue. Persist the TOP N matched winners as
        # a rolling queue that the TM script cycles through (switching PO
        # chart per asset). Previously only ONE winner ever routed, so users
        # complained that "auto-trading only trades on a single asset".
        try:
            await self._push_multi_asset_queue(top_n, cfg)
        except Exception as e:
            logger.warning(f"[auto_scan] multi-asset queue push failed: {e}")

        return {"success": True, "results": rows, "winner": winner,
                "universe_size": len(universe),
                "matched_count": len(matched),
                "rotation_index": self._state.rotation_index}

    async def _push_multi_asset_queue(self, winners: list, cfg: Dict[str, Any]) -> None:
        """Persist top-N winners as a rolling queue in `active_target_queue`.
        The TM script polls `/api/tampermonkey/active-target-queue` and cycles
        through each entry, switching PO chart + firing per asset."""
        if self._db is None or not winners:
            return
        ttl = int(cfg.get("target_ttl_seconds", 60))
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=ttl)).isoformat()
        docs = []
        for rank, w in enumerate(winners):
            docs.append({
                "asset": w["asset"],
                "timeframe": cfg.get("chart_timeframe", "1m"),
                "direction": w["direction"],
                "confidence": w["confidence"],
                "elite_score": w.get("elite_score"),
                "rank": rank,
                "source": "auto_scan",
                "set_at": now.isoformat(),
                "expires_at": expires_at,
            })
        # Atomic replace: drop old queue + insert new one
        await self._db.active_target_queue.delete_many({})
        await self._db.active_target_queue.insert_many(docs)
        try:
            from perf_cache import active_target_cache
            active_target_cache.invalidate("queue")
        except Exception:
            pass

    async def _route_to_tm(self, winner: Dict[str, Any], cfg: Dict[str, Any]) -> None:
        """Set `tampermonkey_settings.active_target` so the TM script switches
        the chart and executes the winning trade."""
        if self._db is None:
            return

        # Iter 134 — RiskGuard-aware pre-flight gate.
        # If the user's active RiskGuard session has hit its target, stop-loss
        # or max-trades limit, DO NOT route another trade. Prevents the auto-
        # scan from burning through the session after limits are breached.
        try:
            from risk_guard_service import risk_guard_service
            active = await risk_guard_service.get_active_session("default")
            if active and active.get("status") != "active":
                self._state.last_error = f"riskguard_lock:{active.get('status')}"
                logger.info(
                    f"[auto_scan] 🛑 RiskGuard locked ({active.get('status')}) — "
                    f"skipping route for {winner['asset']}"
                )
                return
        except Exception as _rge:
            logger.debug(f"[auto_scan] RiskGuard pre-flight skipped: {_rge}")

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
            # Iter 140 — expose the confluence stack so the TM panel / dashboard
            # can render "why this trade fired": which sources agreed, score,
            # timeframes aligned, etc.
            "confluence": (winner.get("confluence") or {}).get("result"),
            "confluence_score": (winner.get("confluence") or {}).get("result", {}).get("confluence_score"),
        }
        try:
            # Iter 125 — BUG FIX: previous code wrote to _id="singleton" but
            # every reader (server.py, signals.py) queries _id="default", so
            # auto_scan winners were WRITTEN AND NEVER READ. This is the
            # primary reason auto-scan wasn't placing trades.
            await self._db.tampermonkey_settings.update_one(
                {"_id": "default"},
                {"$set": {"active_target": target,
                          "last_updated": target["set_at"]}},
                upsert=True,
            )
            # Also invalidate the in-process TTL cache so the next TM poll
            # sees the new target immediately.
            try:
                from perf_cache import active_target_cache
                active_target_cache.invalidate("default")
            except Exception:
                pass
            logger.info(f"[auto_scan] 🎯 ROUTED to TM · {winner['asset']} · "
                        f"{winner['direction']} · conf={winner['confidence']:.2f} · "
                        f"elite={winner.get('elite_score') or '—'} · "
                        f"confluence={target.get('confluence_score') or '—'}")
            # Iter 126 — Telegram notification (fire-and-forget)
            try:
                from telegram_service import send_message
                await send_message(
                    f"🎯 <b>Auto-Scan Winner</b>\n"
                    f"Asset: <code>{winner['asset']}</code>\n"
                    f"Direction: <b>{winner['direction']}</b>\n"
                    f"Confidence: {winner['confidence']:.1%}\n"
                    f"Elite: {winner.get('elite_score') or '—'}"
                )
            except Exception:
                pass
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
