/**
 * App Signal Poller
 *
 * Polls the backend `/api/signals/latest` endpoint at a fixed interval.
 * When a new signal arrives (dedup by `id` or timestamp), auto-executes
 * the trade via tradeExecutor (honoring AUTO + AUTO-INVERT toggles).
 *
 * Controlled from the TM panel APP button.
 */

import { log, info, warn, error } from '../core/logger.js';
import { state } from '../core/state.js';
import { fetchSignal } from '../utils/api.js';
import { tradeExecutor } from './executor.js';
import { getCurrentAsset, switchAsset } from '../utils/dom.js';

const DEFAULT_POLL_MS = 5_000;

class AppSignalPoller {
  constructor() {
    this.started = false;
    this.intervalId = null;
    this.pollMs = DEFAULT_POLL_MS;
    this.lastSignalId = null;
    this.lastSignalTs = null;
    this.inFlight = false;
    this.pollCount = 0;
    this.executedCount = 0;
    this.skippedCount = 0;
  }

  start(pollMs) {
    if (this.started) return;
    this.pollMs = pollMs || DEFAULT_POLL_MS;
    this.started = true;
    this.intervalId = setInterval(() => this._tick(), this.pollMs);
    info(`[APP] signal poller started (every ${this.pollMs}ms)`);
  }

  stop() {
    if (!this.started) return;
    if (this.intervalId) clearInterval(this.intervalId);
    this.intervalId = null;
    this.started = false;
    log('[APP] signal poller stopped');
  }

  isRunning() { return this.started; }

  async _tick() {
    if (this.inFlight) return;
    this.inFlight = true;
    this.pollCount++;
    try {
      // Poll the latest signal — optionally scoped to current asset
      const currentAsset = getCurrentAsset();
      const signal = await fetchSignal(currentAsset);
      if (!signal) return;

      // Dedup — skip if we've already processed this one
      const sigId = signal.id || signal.signal_id || signal.timestamp || null;
      if (sigId && sigId === this.lastSignalId) {
        return;
      }
      this.lastSignalId = sigId;
      this.lastSignalTs = Date.now();

      info(`[APP] signal received: ${signal.direction} ${signal.symbol || signal.asset || '?'} @ ${signal.confidence || '?'}% [${signal.strategy || 'app'}]`);

      // Decide how to route
      if (!state.autoTradeEnabled) {
        this.skippedCount++;
        log('[APP] AUTO is off — signal stored as lastSignal but not executed');
        state.lastSignal = {
          direction: (signal.direction || '').toUpperCase(),
          symbol: signal.symbol || signal.asset || currentAsset,
          confidence: signal.confidence,
          strategy: signal.strategy,
        };
        return;
      }

      // If the app signal targets a different asset, switch to it before trading
      const target = signal.symbol || signal.asset;
      if (target && currentAsset && target !== currentAsset) {
        try {
          switchAsset(target);
          // Short wait for chart to settle
          await new Promise((r) => setTimeout(r, 1200));
        } catch (e) {
          warn(`[APP] failed to switch to ${target}: ${e.message}`);
        }
      }

      const ok = await tradeExecutor.execute(signal, 'app');
      if (ok) {
        this.executedCount++;
        info(`[APP] trade executed from app signal`);
      } else {
        this.skippedCount++;
        log('[APP] trade NOT executed (validation/cooldown)');
      }
    } catch (e) {
      error(`[APP] poll error: ${e.message}`);
    } finally {
      this.inFlight = false;
    }
  }

  getStats() {
    return {
      running: this.started,
      pollMs: this.pollMs,
      pollCount: this.pollCount,
      executedCount: this.executedCount,
      skippedCount: this.skippedCount,
      lastSignalId: this.lastSignalId,
      lastSignalTs: this.lastSignalTs,
    };
  }
}

export const appSignalPoller = new AppSignalPoller();
export default appSignalPoller;
