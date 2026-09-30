"""Iter 153 — Clean Retrain hang fix.

Root cause: `maximized_ai_ml.train_from_oanda(...)` and friends are declared
`async` but their bodies do 100% synchronous CPU-bound work (sklearn training,
walk-forward CV, feature loops). Because they never yield to the event loop:
  1. `asyncio.wait_for` cannot cancel them (no yield = no cancellation).
  2. The main event loop is fully blocked, so `/api/ml/retrain-status`
     polls stall — UI hangs on "retraining" until the whole pipeline
     finishes or the browser times out.

Fix: `run_phase_with_timeout` now drives each phase coroutine inside a worker
thread with its own event loop via `asyncio.to_thread`. Main loop stays free.
"""

from __future__ import annotations

import asyncio
import time
import pytest


# ---------------------------------------------------------------------------
# The main-event-loop-blocking hazard is what actually bit the user.
# Prove it's gone.
# ---------------------------------------------------------------------------

def test_run_phase_does_not_block_main_event_loop():
    """A phase that runs a synchronous busy-loop must NOT prevent other
    tasks on the main event loop from making progress.

    Under the old implementation (`await asyncio.wait_for(coro, ...)` with a
    coroutine that never yields) this test would deadlock the heartbeat.
    """
    from routes.iter150_fixpack import run_phase_with_timeout

    async def go():
        # Simulates train_from_oanda: `async def` body that does 100 %
        # synchronous CPU-bound work with zero yields.
        async def cpu_hog():
            deadline = time.monotonic() + 0.6
            total = 0
            while time.monotonic() < deadline:
                total += 1  # busy-loop, never yields to the loop
            return total

        heartbeats = {"n": 0}

        async def heartbeat():
            # If the main loop is blocked, this task can't tick.
            for _ in range(20):
                heartbeats["n"] += 1
                await asyncio.sleep(0.05)

        phase_task = asyncio.create_task(
            run_phase_with_timeout(cpu_hog(), phase_name="cpu_hog", timeout_s=5)
        )
        hb_task = asyncio.create_task(heartbeat())
        phase_result = await phase_task
        await hb_task
        return phase_result, heartbeats["n"]

    result, ticks = asyncio.run(go())
    assert result["success"] is True
    # If the main loop stayed responsive during the ~0.6 s busy phase, we
    # should have logged >= 8 heartbeats (20 × 50 ms = 1 s total). The old
    # implementation would log 0-1 heartbeats since the loop was frozen.
    assert ticks >= 8, (
        f"main event loop was blocked during phase — only {ticks} heartbeats"
    )


def test_run_phase_times_out_hung_sync_coroutine():
    """The old impl's `asyncio.wait_for` was defeated by CPU-bound bodies
    (no yield = no cancellation). Under the new impl the phase reports
    timeout cleanly even when the underlying work never yields."""
    from routes.iter150_fixpack import run_phase_with_timeout

    async def go():
        async def sync_hog():
            # 3-second synchronous work — timeout is 1 s so wait_for should
            # fire on the worker-thread future.
            time.sleep(3)
            return "should not reach"

        return await run_phase_with_timeout(
            sync_hog(), phase_name="sync_hog", timeout_s=1
        )

    r = asyncio.run(go())
    assert r["success"] is False
    assert "timeout" in r["error"].lower()
    assert r["elapsed_s"] == 1


def test_run_phase_returns_success_when_phase_completes_in_time():
    """Regression guard: normal async coroutines that yield still work."""
    from routes.iter150_fixpack import run_phase_with_timeout

    async def go():
        async def normal():
            await asyncio.sleep(0.05)
            return {"cv_accuracy": 87.3}

        return await run_phase_with_timeout(
            normal(), phase_name="normal", timeout_s=5
        )

    r = asyncio.run(go())
    assert r["success"] is True
    assert "cv_accuracy" in r["result"]


def test_run_phase_propagates_exception_type_from_worker_thread():
    from routes.iter150_fixpack import run_phase_with_timeout

    async def go():
        async def boom():
            raise ValueError("insufficient candle data")

        return await run_phase_with_timeout(
            boom(), phase_name="boom", timeout_s=5
        )

    r = asyncio.run(go())
    assert r["success"] is False
    assert "ValueError" in r["error"]
    assert "insufficient candle data" in r["error"]


def test_helper_drives_coroutine_in_isolated_event_loop():
    """The worker-thread driver must create its OWN event loop so the
    main loop's currently-running task isn't reentered."""
    from routes.iter150_fixpack import _drive_coroutine_in_thread

    async def c():
        return 42

    result = _drive_coroutine_in_thread(c())
    assert result == 42
