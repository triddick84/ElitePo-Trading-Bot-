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
import { fetchSignal, fetchActiveTarget } from '../utils/api.js';
import { tradeExecutor } from './executor.js';
import { getCurrentAsset, switchAsset } from '../utils/dom.js';

const DEFAULT_POLL_MS = 5_000;

// Iter 95 — asset-switch verification tuning
const ASSET_SWITCH_VERIFY_TRIES = 3;
const ASSET_SWITCH_VERIFY_INTERVAL_MS = 500;

/**
 * Normalise an asset name to the canonical EURUSD_OTC form so comparisons
 * work regardless of casing / whitespace / trailing "OTC" vs "_OTC".
 */
function normAsset(a) {
  if (!a) return '';
  let s = String(a).trim().replace(/[\s\-/]+/g, '').toUpperCase();
  if (s.endsWith('OTC') && !s.endsWith('_OTC')) s = s.slice(0, -3) + '_OTC';
  return s;
}


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
    this.assetSwitchFailedCount = 0;
    this.lastActiveTarget = null;
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

  /**
   * Iter 95 — Verify an asset switch actually completed by re-reading
   * PO's DOM. Retries up to ASSET_SWITCH_VERIFY_TRIES times with a
   * ASSET_SWITCH_VERIFY_INTERVAL_MS delay before returning false.
   */
  async _verifyAssetSwitched(target) {
    const want = normAsset(target);
    for (let i = 0; i < ASSET_SWITCH_VERIFY_TRIES; i++) {
      const now = normAsset(getCurrentAsset());
      if (now && now === want) return true;
      await new Promise((r) => setTimeout(r, ASSET_SWITCH_VERIFY_INTERVAL_MS));
    }
    return false;
  }

  async _tick() {
    if (this.inFlight) return;
    this.inFlight = true;
    this.pollCount++;
    try {
      // Iter 95 — poll signals scoped to the APP's active target, NOT PO's
      // current chart. This fixes: "TM fires on wrong asset when PO is on
      // the wrong asset when the signal comes through".
      let scopeAsset = null;
      let activeTarget = null;
      try {
        activeTarget = await fetchActiveTarget();
        if (activeTarget && activeTarget.asset) {
          scopeAsset = activeTarget.asset;
          this.lastActiveTarget = activeTarget;
        }
      } catch (_e) { /* silent — fallback below */ }
      // If active-target endpoint failed, fall back to PO's current asset
      if (!scopeAsset) {
        scopeAsset = getCurrentAsset();
      }

      const signal = await fetchSignal(scopeAsset);
      if (!signal) return;

      // Dedup — skip if we've already processed this one
      const sigId = signal.id || signal.signal_id || signal.timestamp || null;
      if (sigId && sigId === this.lastSignalId) {
        return;
      }
      this.lastSignalId = sigId;
      this.lastSignalTs = Date.now();

      info(`[APP] signal received: ${signal.direction} ${signal.symbol || signal.asset || '?'} @ ${signal.confidence || '?'}% [${signal.strategy || 'app'}] · target=${scopeAsset}`);

      // Decide how to route
      if (!state.autoTradeEnabled) {
        this.skippedCount++;
        log('[APP] AUTO is off — signal stored as lastSignal but not executed');
        state.lastSignal = {
          direction: (signal.direction || '').toUpperCase(),
          symbol: signal.symbol || signal.asset || scopeAsset,
          confidence: signal.confidence,
          strategy: signal.strategy,
        };
        return;
      }

      // Iter 95 — enforce asset alignment BEFORE firing. If PO is on the
      // wrong asset, switch and VERIFY. If verification fails, abort the
      // trade (do NOT fire on the wrong asset).
      const target = normAsset(signal.symbol || signal.asset || scopeAsset);
      const current = normAsset(getCurrentAsset());
      if (target && current !== target) {
        info(`[APP] asset mismatch — PO on ${current || '?'}, need ${target}. Switching...`);
        try {
          switchAsset(target);
        } catch (e) {
          warn(`[APP] switchAsset threw: ${e.message}`);
        }
        const ok = await this._verifyAssetSwitched(target);
        if (!ok) {
          this.assetSwitchFailedCount++;
          this.skippedCount++;
          error(`[APP] ✗ ABORT trade — could not switch PO to ${target} (still on ${normAsset(getCurrentAsset()) || '?'}) after ${ASSET_SWITCH_VERIFY_TRIES} retries. Signal ${signal.direction} dropped to protect from firing on wrong asset.`);
          state.lastSignal = {
            direction: (signal.direction || '').toUpperCase(),
            symbol: target,
            confidence: signal.confidence,
            strategy: signal.strategy,
            aborted_reason: 'asset_switch_failed',
          };
          return;
        }
        info(`[APP] ✓ asset switch verified — PO now on ${target}`);
      }

      const ok = await tradeExecutor.execute(signal, 'app');
      if (ok) {
        this.executedCount++;
        info(`[APP] trade executed from app signal on ${target}`);
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
      assetSwitchFailedCount: this.assetSwitchFailedCount,
      lastSignalId: this.lastSignalId,
      lastSignalTs: this.lastSignalTs,
      lastActiveTarget: this.lastActiveTarget,
    };
  }
}

export const appSignalPoller = new AppSignalPoller();
export default appSignalPoller;
