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
import { chartTypeSwitcher } from './chartTypeSwitcher.js';
import { getCurrentAsset, switchAsset, switchAssetViaPicker, switchAssetViaSearch } from '../utils/dom.js';

const DEFAULT_POLL_MS = 5_000;

// Iter 95 → 98 — asset-switch verification tuning
// Iter 98 fix: PO's chart re-render can take 2-4s on slow networks. The
// old 3×500ms=1.5s window was too tight → most signals aborted with
// "asset_switch_failed" even though the switch DID work. New window is
// 8×500ms=4s which comfortably covers p95 switch latency.
const ASSET_SWITCH_VERIFY_TRIES = 8;
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

      // Iter 95 → 98 — Enforce asset alignment BEFORE firing. If PO is on
      // the wrong asset, switch and VERIFY. Iter 98 upgrade:
      //   1. Try the fast sync switch first (favorites-bar click).
      //   2. If that doesn't verify within 4s, fall back to the picker
      //      (openCurrenciesPicker + row-click), then to the search box.
      //   3. Only abort if BOTH paths fail. This drastically reduces the
      //      "trade dropped: asset_switch_failed" flapping the user reported.
      const target = normAsset(signal.symbol || signal.asset || scopeAsset);
      const current = normAsset(getCurrentAsset());
      if (target && current !== target) {
        info(`[APP] asset mismatch — PO on ${current || '?'}, need ${target}. Switching...`);
        let switched = false;

        // Fast path — favorites-bar / DOM click
        try { switchAsset(target); } catch (e) { warn(`[APP] switchAsset threw: ${e.message}`); }
        switched = await this._verifyAssetSwitched(target);

        // Slow path #1 — picker (openCurrenciesPicker → click row)
        if (!switched) {
          info(`[APP] fast switch missed — falling back to currencies picker for ${target}`);
          try {
            await switchAssetViaPicker(target);
          } catch (e) { warn(`[APP] picker fallback threw: ${e.message}`); }
          switched = await this._verifyAssetSwitched(target);
        }

        // Slow path #2 — search box
        if (!switched) {
          info(`[APP] picker missed — falling back to search box for ${target}`);
          try {
            await switchAssetViaSearch(target);
          } catch (e) { warn(`[APP] search fallback threw: ${e.message}`); }
          switched = await this._verifyAssetSwitched(target);
        }

        if (!switched) {
          this.assetSwitchFailedCount++;
          this.skippedCount++;
          error(`[APP] ✗ ABORT trade — could not switch PO to ${target} after fast/picker/search paths. Signal ${signal.direction} dropped to protect from firing on wrong asset.`);
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

      // Iter 99 — Enforce chart type BEFORE firing. The signal was
      // generated for a specific chart type (Japanese / Heikin / Line /
      // Bars). If PO's chart is showing a different type, silently switch
      // it so the human sees the same view the bot is trading on.
      const desiredChartType = activeTarget && activeTarget.chart_type;
      if (desiredChartType && desiredChartType !== 'japanese_candles') {
        try {
          const r = await chartTypeSwitcher.ensure(desiredChartType);
          if (r.changed) info(`[APP] chart type synced → ${desiredChartType}`);
          else if (!r.matched) warn(`[APP] chart-type sync missed for ${desiredChartType} (${r.reason})`);
        } catch (e) { warn(`[APP] chart-type sync threw: ${e.message}`); }
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
