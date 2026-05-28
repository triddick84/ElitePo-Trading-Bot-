"""
Background Job Manager (Iter 65)
================================

Generic pattern for long-running async tasks (ML training, comprehensive
backtests, OANDA bulk backfills) that would otherwise blow past the 60s
ingress/proxy timeout.

Usage from a route handler:

    from background_jobs import job_manager

    @router.post("/ml/train-from-otc-async")
    async def train_async(req: TrainRequest):
        async def runner(update):
            update(progress=10, message="loading candles…")
            # …do work…
            update(progress=50, message="fitting model…")
            return {"val_accuracy": 0.83}
        job = job_manager.submit("ml_train", runner, payload=req.dict())
        return {"success": True, "job_id": job["job_id"]}

    @router.get("/jobs/{job_id}")  # already exposed below as /api/jobs/{id}
    async def get_status(...): ...

Jobs are persisted to MongoDB (`background_jobs` collection) so:
  - Status survives backend restarts
  - The UI can poll without holding a single HTTP connection
  - You get an audit trail of every long-running job
"""
from __future__ import annotations
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "gpt_signal_bot")
_client = MongoClient(_MONGO_URL)
_db = _client[_DB_NAME]
jobs_col = _db["background_jobs"]
jobs_col.create_index([("job_id", 1)], unique=True)
jobs_col.create_index([("created_at", DESCENDING)])
# TTL — jobs auto-purge after 7 days
jobs_col.create_index("created_at_dt", expireAfterSeconds=7 * 24 * 3600)


# A runner takes a `update(progress=..., message=..., partial=...)` callable
# and returns the final result dict.
Runner = Callable[[Callable[..., None]], Awaitable[Dict[str, Any]]]


class JobManager:
    def __init__(self):
        self._running: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def submit(
        self,
        kind: str,
        runner: Runner,
        payload: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """
        Queue a runner for execution. Returns immediately with a job descriptor.

        :param kind: short job-type identifier (e.g. "ml_train", "backtest")
        :param runner: async callable; receives an `update(...)` setter
        :param payload: serializable inputs (stored for audit / debugging)
        :param ttl_seconds: max wall-clock runtime; runner is cancelled after this
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0,
            "message": "queued",
            "payload": payload or {},
            "result": None,
            "error": None,
            "created_at": now.isoformat(),
            "created_at_dt": now,  # for TTL
            "started_at": None,
            "finished_at": None,
        }
        jobs_col.insert_one(dict(doc))  # copy so caller doesn't see _id

        task = asyncio.create_task(self._wrap(job_id, runner, ttl_seconds))
        self._running[job_id] = task

        # Drop the helper-collection mongo `_id` before returning to the caller
        return {"job_id": job_id, "kind": kind, "status": "queued"}

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = jobs_col.find_one({"job_id": job_id}, {"_id": 0, "created_at_dt": 0})
        return doc

    def cancel(self, job_id: str) -> bool:
        task = self._running.get(job_id)
        if task and not task.done():
            task.cancel()
            jobs_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "cancelled",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            return True
        return False

    def list_recent(self, limit: int = 50, kind: Optional[str] = None):
        q = {"kind": kind} if kind else {}
        return list(jobs_col.find(q, {"_id": 0, "created_at_dt": 0})
                            .sort("created_at", -1).limit(limit))

    # ------------------------------------------------------------------ #
    # internal
    # ------------------------------------------------------------------ #
    async def _wrap(self, job_id: str, runner: Runner, ttl_seconds: int):
        def update(progress: Optional[int] = None,
                   message: Optional[str] = None,
                   partial: Optional[Any] = None):
            patch = {}
            if progress is not None:
                patch["progress"] = max(0, min(100, int(progress)))
            if message is not None:
                patch["message"] = str(message)[:200]
            if partial is not None:
                patch["partial"] = partial
            if patch:
                jobs_col.update_one({"job_id": job_id}, {"$set": patch})

        jobs_col.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "message": "running",
            }},
        )

        try:
            result = await asyncio.wait_for(runner(update), timeout=ttl_seconds)
            jobs_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "completed",
                    "progress": 100,
                    "result": result,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "message": "done",
                }},
            )
        except asyncio.CancelledError:
            jobs_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "cancelled",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "message": "cancelled",
                }},
            )
        except asyncio.TimeoutError:
            jobs_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": f"timeout after {ttl_seconds}s",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "message": "timed out",
                }},
            )
        except Exception as e:
            logger.exception(f"[job:{job_id}] runner failed")
            jobs_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "message": "failed",
                }},
            )
        finally:
            self._running.pop(job_id, None)


job_manager = JobManager()
