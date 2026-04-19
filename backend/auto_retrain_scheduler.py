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
        self._config = {
            "enabled": True,
            "retrain_hours_utc": [8, 13],  # London open, NY open
            "retrain_days": [0, 1, 2, 3, 4],  # Mon-Fri
            "min_hours_between_retrain": 4,
            "use_otc_data": True,
            "use_oanda_data": True,
            "timeframes": ["S5", "M1"],
            "symbols_oanda": ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "EUR_JPY"],
            "symbols_otc": ["EURUSD_OTC"],
            "min_otc_candles": 200,
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
        return {
            "running": self.is_running,
            "config": self._config,
            "last_retrain": self._last_retrain.isoformat() if self._last_retrain else None,
            "next_scheduled": self._next_scheduled,
            "retrain_count": len(self._retrain_history),
            "recent_history": self._retrain_history[-5:]
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

            # Step 1: Train from OTC data if available and configured
            if self._config["use_otc_data"]:
                try:
                    tuner = get_ml_tuner(self.db)
                    otc_stats = await tuner.get_otc_training_data(self._config["symbols_otc"][0] if self._config["symbols_otc"] else None)

                    if len(otc_stats) >= self._config["min_otc_candles"]:
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
                                min_samples=50
                            )
                            if otc_result.get("success"):
                                result["models_trained"].append({
                                    "model": "maximized_v3_otc",
                                    "accuracy": otc_result.get("cv_accuracy"),
                                    "samples": otc_result.get("total_samples")
                                })
                                logger.info(f"OTC retrain: {otc_result.get('cv_accuracy')}% accuracy")

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

            self._last_retrain = end
            self._retrain_history.append(result)
            if len(self._retrain_history) > 50:
                self._retrain_history = self._retrain_history[-50:]

            logger.info(f"Auto-retrain complete: {len(result['models_trained'])} models in {duration:.1f}s")

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


# Singleton
_scheduler = None

def get_retrain_scheduler(db) -> AutoRetrainScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutoRetrainScheduler(db)
    return _scheduler
