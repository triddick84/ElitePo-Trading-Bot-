"""
Auto-Retrain Scheduler
======================
Schedules ML model retraining at market open times.
Uses asyncio background tasks — no external dependencies.

Schedule:
- London Open: 08:00 UTC (Mon-Fri)
- New York Open: 13:00 UTC (Mon-Fri)
- Custom intervals (configurable)
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class AutoRetrainScheduler:
    """Schedules automatic ML model retraining at market open times."""

    def __init__(self, db):
        self.db = db
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._manual_task: Optional[asyncio.Task] = None
        self._manual_started_at: Optional[datetime] = None
        self._config = {
            "enabled": True,
            "retrain_hours_utc": [8, 13],  # London open, NY open
            "retrain_days": [0, 1, 2, 3, 4],  # Mon-Fri
            "min_hours_between_retrain": 4,
            "use_otc_data": True,
            "use_oanda_data": True,
            "timeframes": ["S5", "M1"],
            "symbols_oanda": ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "EUR_JPY"],
            # Iter 58: full mappable OTC pool — matches the OANDA backfill set
            "symbols_otc": [
                "AUDCAD_OTC", "EURUSD_OTC", "CADJPY_OTC", "NZDJPY_OTC",
                "USDCNH_OTC", "EURGBP_OTC", "GBPJPY_OTC", "CADCHF_OTC",
                "EURNZD_OTC", "USDCHF_OTC", "EURJPY_OTC", "AUDUSD_OTC",
                "NZDUSD_OTC", "AUDCHF_OTC", "USDCAD_OTC", "USDJPY_OTC",
                "EURCHF_OTC", "CHFJPY_OTC", "EURAUD_OTC", "AUDJPY_OTC",
                "GBPAUD_OTC", "GBPNZD_OTC", "EURCAD_OTC", "GBPCAD_OTC",
                "GBPUSD_OTC", "AUDNZD_OTC", "NZDCAD_OTC", "NZDCHF_OTC",
                "GBPCHF_OTC",
            ],
            "min_otc_candles": 200,
            # London-Open overlay-aware backfill (Iter 58, Apr 25, 2026):
            # at the 08:00 UTC slot, top up under-target OTC pairs from
            # OANDA before retraining. Live PO ticks always overlay.
            "london_overlay_backfill": True,
        }
        self._last_retrain: Optional[datetime] = None
        self._retrain_history: list = []
        self._next_scheduled: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    def start(self):
        """Start the scheduler background task."""
        if self.is_running:
            logger.info("Auto-retrain scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Auto-retrain scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Auto-retrain scheduler stopped")

    def update_config(self, updates: Dict):
        """Update scheduler configuration."""
        for key, val in updates.items():
            if key in self._config:
                self._config[key] = val
        logger.info(f"Scheduler config updated: {updates}")

    def get_status(self) -> Dict:
        """Get scheduler status."""
        manual_in_progress = (
            self._manual_task is not None and not self._manual_task.done()
        )
        return {
            "running": self.is_running,
            "config": self._config,
            "last_retrain": self._last_retrain.isoformat() if self._last_retrain else None,
            "next_scheduled": self._next_scheduled,
            "retrain_count": len(self._retrain_history),
            "recent_history": self._retrain_history[-5:],
            "manual_in_progress": manual_in_progress,
            "manual_started_at": self._manual_started_at.isoformat() if (manual_in_progress and self._manual_started_at) else None,
        }

    def _get_next_retrain_time(self) -> Optional[datetime]:
        """Calculate the next scheduled retrain time."""
        now = datetime.now(timezone.utc)

        for hour in sorted(self._config["retrain_hours_utc"]):
            candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if candidate > now and now.weekday() in self._config["retrain_days"]:
                return candidate

        # Next valid day
        for days_ahead in range(1, 8):
            next_day = now + timedelta(days=days_ahead)
            if next_day.weekday() in self._config["retrain_days"]:
                first_hour = min(self._config["retrain_hours_utc"])
                return next_day.replace(hour=first_hour, minute=0, second=0, microsecond=0)

        return None

    async def _scheduler_loop(self):
        """Main scheduler loop — checks every 60 seconds if retrain is due."""
        logger.info("Scheduler loop started — checking every 60s")

        while self._running:
            try:
                if not self._config["enabled"]:
                    await asyncio.sleep(60)
                    continue

                now = datetime.now(timezone.utc)

                # Update next scheduled display
                next_time = self._get_next_retrain_time()
                self._next_scheduled = next_time.isoformat() if next_time else None

                # Check if we should retrain now
                should_retrain = self._should_retrain_now(now)

                if should_retrain:
                    logger.info("Auto-retrain triggered at scheduled time")
                    await self._execute_retrain()

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)

        logger.info("Scheduler loop exited")

    def _should_retrain_now(self, now: datetime) -> bool:
        """Check if current time matches a retrain schedule."""
        # Must be a valid day
        if now.weekday() not in self._config["retrain_days"]:
            return False

        # Must match a retrain hour (within first 2 minutes of the hour)
        if now.hour not in self._config["retrain_hours_utc"]:
            return False
        if now.minute > 1:  # Only trigger in first 2 minutes
            return False

        # Respect min interval between retrains
        if self._last_retrain:
            hours_since = (now - self._last_retrain).total_seconds() / 3600
            if hours_since < self._config["min_hours_between_retrain"]:
                return False

        return True

    async def _execute_retrain(self):
        """Execute the actual retraining process."""
        start = datetime.now(timezone.utc)
        result = {"started_at": start.isoformat(), "status": "running", "models_trained": []}

        try:
            from enhanced_oanda_service import enhanced_oanda
            from ml_accuracy_tuner import get_ml_tuner

            # Step 0 (Iter 58): Overlay-aware backfill — only at London Open.
            # Top up under-target OTC pairs from OANDA so the pool is fresh
            # for retrain. Live PO ticks (source='po_live') always overlay
            # OANDA backfill at the same (symbol, timestamp) slot.
            if self._config.get("london_overlay_backfill") and start.hour == 8:
                try:
                    inserted = await self._overlay_backfill(target_count=500)
                    result["overlay_backfill"] = inserted
                    logger.info(f"Overlay backfill inserted {inserted.get('total_inserted', 0)} rows across {inserted.get('newly_trainable', 0)} newly-trainable pairs")
                except Exception as e:
                    logger.warning(f"Overlay backfill error: {e}")
                    result["overlay_backfill_error"] = str(e)

            # Step 1: Train from OTC data if available and configured
            if self._config["use_otc_data"]:
                try:
                    tuner = get_ml_tuner(self.db)
                    sample_sym = self._config["symbols_otc"][0] if self._config["symbols_otc"] else None
                    otc_df = await tuner.get_otc_training_data(sample_sym) if sample_sym else None

                    if otc_df is not None and len(otc_df) >= self._config["min_otc_candles"]:
                        # Import ML systems
                        try:
                            from server import maximized_ai_ml, improved_ai_ml
                        except ImportError:
                            maximized_ai_ml = None
                            improved_ai_ml = None

                        if maximized_ai_ml:
                            otc_result = await tuner.train_from_otc(
                                ml_system=maximized_ai_ml,
                                symbols=self._config["symbols_otc"],
                                min_samples=500
                            )
                            if otc_result.get("success"):
                                result["models_trained"].append({
                                    "model": "maximized_v3_otc",
                                    "accuracy": otc_result.get("cv_accuracy"),
                                    "samples": otc_result.get("total_samples"),
                                    # Iter 58 — surface OOS metrics for the Ensemble tab
                                    "oos_accuracy": otc_result.get("test_accuracy"),
                                    "overfit_gap": otc_result.get("overfit_gap"),
                                    "overfit_warning": otc_result.get("overfit_warning"),
                                })
                                logger.info(
                                    f"OTC retrain (maximized): CV={otc_result.get('cv_accuracy')}% "
                                    f"OOS={otc_result.get('test_accuracy')}% "
                                    f"gap={otc_result.get('overfit_gap')}%"
                                )

                        if improved_ai_ml:
                            otc_result_imp = await tuner.train_from_otc(
                                ml_system=improved_ai_ml,
                                symbols=self._config["symbols_otc"],
                                min_samples=500
                            )
                            if otc_result_imp.get("success"):
                                result["models_trained"].append({
                                    "model": "improved_v2_otc",
                                    "accuracy": otc_result_imp.get("cv_accuracy"),
                                    "samples": otc_result_imp.get("total_samples"),
                                    "oos_accuracy": otc_result_imp.get("test_accuracy"),
                                    "overfit_gap": otc_result_imp.get("overfit_gap"),
                                    "overfit_warning": otc_result_imp.get("overfit_warning"),
                                })
                                logger.info(
                                    f"OTC retrain (improved): CV={otc_result_imp.get('cv_accuracy')}% "
                                    f"OOS={otc_result_imp.get('test_accuracy')}% "
                                    f"gap={otc_result_imp.get('overfit_gap')}%"
                                )

                except Exception as e:
                    logger.warning(f"OTC retrain error: {e}")
                    result["otc_error"] = str(e)

            # Step 2: Train from OANDA data if configured
            if self._config["use_oanda_data"]:
                try:
                    try:
                        from server import maximized_ai_ml, improved_ai_ml
                    except ImportError:
                        maximized_ai_ml = None
                        improved_ai_ml = None

                    if maximized_ai_ml:
                        oanda_result = await asyncio.to_thread(
                            lambda: asyncio.run(maximized_ai_ml.train_from_oanda(
                                enhanced_oanda,
                                symbols=self._config["symbols_oanda"],
                                candle_count=2000,
                                timeframes=self._config["timeframes"]
                            ))
                        )
                        if oanda_result and oanda_result.get("success"):
                            result["models_trained"].append({
                                "model": "maximized_v3_oanda",
                                "success": True
                            })
                            logger.info("OANDA retrain completed")

                except Exception as e:
                    logger.warning(f"OANDA retrain error: {e}")
                    result["oanda_error"] = str(e)

            # Done
            end = datetime.now(timezone.utc)
            duration = (end - start).total_seconds()
            result["status"] = "complete"
            result["completed_at"] = end.isoformat()
            result["duration_seconds"] = round(duration, 1)
            result["models_count"] = len(result["models_trained"])

            # Iter 58 — compute Ensemble-tab aggregate OOS so the UI can show
            # a single "ensemble was healthy / overfit" read after retrain.
            oos_values = [m.get("oos_accuracy") for m in result["models_trained"]
                          if isinstance(m.get("oos_accuracy"), (int, float))]
            gap_values = [m.get("overfit_gap") for m in result["models_trained"]
                          if isinstance(m.get("overfit_gap"), (int, float))]
            any_overfit = any(m.get("overfit_warning") for m in result["models_trained"])
            if oos_values:
                result["aggregate_oos"] = {
                    "mean_oos_accuracy": round(sum(oos_values) / len(oos_values), 2),
                    "min_oos_accuracy": round(min(oos_values), 2),
                    "max_oos_accuracy": round(max(oos_values), 2),
                    "mean_overfit_gap": round(sum(gap_values) / len(gap_values), 2) if gap_values else None,
                    "any_overfit": bool(any_overfit),
                    "models_included": len(oos_values),
                }

            self._last_retrain = end
            self._retrain_history.append(result)
            if len(self._retrain_history) > 50:
                self._retrain_history = self._retrain_history[-50:]

            logger.info(f"Auto-retrain complete: {len(result['models_trained'])} models in {duration:.1f}s")

            # Iter 58 — Run a Daily Model Tournament after each retrain.
            # The freshly-trained models are evaluated on the latest holdout
            # day and their dynamic vote multipliers are persisted. Fire and
            # forget — failure does not break the retrain summary.
            try:
                from model_tournament import run_tournament
                tour = await asyncio.wait_for(run_tournament(), timeout=300)
                if tour.get("success") and tour.get("tournament"):
                    t = tour["tournament"]
                    result["tournament"] = {
                        "weights": t.get("weights"),
                        "model_winrates": t.get("model_winrates"),
                        "symbols_evaluated": len(t.get("symbols_evaluated", [])),
                    }
                    logger.info(f"[tournament] post-retrain weights: {t.get('weights')}")
            except asyncio.TimeoutError:
                logger.warning("[tournament] post-retrain run hit 5-min timeout — skipped")
            except Exception as _te:
                logger.warning(f"[tournament] post-retrain run failed: {_te}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._retrain_history.append(result)
            logger.error(f"Auto-retrain failed: {e}")

    async def trigger_manual_retrain(self) -> Dict:
        """Trigger an immediate retrain (manual override)."""
        if self._last_retrain:
            hours_since = (datetime.now(timezone.utc) - self._last_retrain).total_seconds() / 3600
            if hours_since < 0.5:  # 30 min cooldown for manual
                return {"success": False, "message": f"Cooldown: last retrain was {hours_since:.1f}h ago (min 0.5h)"}

        await self._execute_retrain()
        return {
            "success": True,
            "result": self._retrain_history[-1] if self._retrain_history else {}
        }

    def trigger_manual_retrain_async(self) -> Dict:
        """
        Fire-and-forget manual retrain. Returns immediately so frontend / ingress
        proxies don't time out (the actual retrain takes 2-5 min). Status visible
        via GET /api/ml/scheduler/status (manual_in_progress flag).

        Hard timeout: 10 min. If the training subprocess hangs (e.g. PPO rebuild,
        joblib worker stuck), the task is cancelled to keep the server responsive.
        """
        if self._manual_task is not None and not self._manual_task.done():
            return {
                "success": False,
                "accepted": False,
                "message": "Manual retrain already in progress",
                "started_at": self._manual_started_at.isoformat() if self._manual_started_at else None,
            }

        if self._last_retrain:
            hours_since = (datetime.now(timezone.utc) - self._last_retrain).total_seconds() / 3600
            if hours_since < 0.5:
                return {
                    "success": False,
                    "accepted": False,
                    "message": f"Cooldown: last retrain was {hours_since:.1f}h ago (min 0.5h)",
                }

        async def _bg():
            try:
                # Hard ceiling so a stuck sklearn/joblib subprocess can't pin
                # CPU forever. 10 min is well over the historical average
                # (~2-3 min for full ensemble retrain) but well below the
                # length where a user assumes the server is down.
                await asyncio.wait_for(self._execute_retrain(), timeout=600)
            except asyncio.TimeoutError:
                logger.error(
                    "Manual retrain background task exceeded 10-min timeout — cancelled"
                )
                self._retrain_history.append({
                    "started_at": self._manual_started_at.isoformat() if self._manual_started_at else None,
                    "status": "timeout",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "exceeded 10-min hard timeout",
                })
            except Exception as e:
                logger.exception(f"Manual retrain background task failed: {e}")
            finally:
                self._manual_started_at = None

        self._manual_started_at = datetime.now(timezone.utc)
        self._manual_task = asyncio.create_task(_bg())
        return {
            "success": True,
            "accepted": True,
            "message": "Manual retrain started in background — poll /api/ml/scheduler/status for progress",
            "started_at": self._manual_started_at.isoformat(),
        }

    async def _overlay_backfill(self, target_count: int = 500) -> Dict:
        """
        London-Open overlay-aware backfill (Apr 25, 2026, Iter 58).
        Calls the same backfill logic as POST /api/ml/backfill-otc-from-oanda
        but inline (no HTTP round-trip). Auto-discovers OTC symbols below
        target_count, tags inserted rows with source='oanda_backfill'.
        Idempotent: po_live overlay rows are never overwritten.
        """
        from enhanced_oanda_service import enhanced_oanda
        from routes.ml import OTC_TO_OANDA
        import pandas as pd

        if not enhanced_oanda or not getattr(enhanced_oanda, "is_configured", False):
            return {"status": "skipped", "reason": "OANDA not configured"}

        coll = self.db["otc_candles_5s"]

        # Find OTC pairs under target
        existing_counts: Dict[str, int] = {}
        async for d in coll.aggregate([{"$group": {"_id": "$symbol", "count": {"$sum": 1}}}]):
            existing_counts[d["_id"]] = d["count"]

        symbols = [
            s for s in OTC_TO_OANDA
            if existing_counts.get(s, 0) < target_count
        ]

        total_inserted = 0
        newly_trainable = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for otc_sym in symbols:
            oanda_pair = OTC_TO_OANDA.get(otc_sym)
            if not oanda_pair:
                continue
            try:
                df = await asyncio.to_thread(
                    enhanced_oanda.get_candles,
                    instrument=oanda_pair,
                    granularity="S5",
                    count=target_count,
                )
                if df is None or df.empty:
                    continue
                df = df.reset_index()
                inserted_for_sym = 0
                for _, row in df.iterrows():
                    ts = row.get("timestamp")
                    if pd.isna(ts):
                        continue
                    ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                    doc = {
                        "symbol": otc_sym,
                        "timestamp": ts_iso,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row.get("volume", 0)),
                        "timeframe": "5s",
                        "source": "oanda_backfill",
                        "oanda_pair": oanda_pair,
                        "collected_at": now_iso,
                    }
                    # $setOnInsert: never overwrite po_live overlay rows
                    r = await coll.update_one(
                        {"symbol": otc_sym, "timestamp": ts_iso},
                        {"$setOnInsert": doc},
                        upsert=True,
                    )
                    if r.upserted_id is not None:
                        inserted_for_sym += 1
                total_inserted += inserted_for_sym
                total_after = await coll.count_documents({"symbol": otc_sym})
                if total_after >= 200 and inserted_for_sym > 0:
                    newly_trainable += 1
            except Exception as e:
                logger.debug(f"backfill {otc_sym}: {e}")

        return {
            "status": "ok",
            "total_inserted": total_inserted,
            "newly_trainable": newly_trainable,
            "scanned_symbols": len(symbols),
        }


# Singleton
_scheduler = None

def get_retrain_scheduler(db) -> AutoRetrainScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutoRetrainScheduler(db)
    return _scheduler
