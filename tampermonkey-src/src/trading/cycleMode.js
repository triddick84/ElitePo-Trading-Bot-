/**
 * CYCLE Mode — Rotation scanner
 *
 * Iterates through the user's favorite assets on Pocket Option.
 * For each favorite:
 *   1. Click to switch the chart to that asset
 *   2. Wait for chart load (min 1.5s, max 6s)
 *   3. Run a signal scan
 *   4. If signal confidence ≥ MIN_CONFIDENCE and AUTO is on, place trade
 *   5. If waitForResult mode: wait for WIN/LOSS before rotating
 *      Otherwise: rotate after `perAssetMs` elapsed
 *   6. If any asset hits N consecutive losses, skip it for the rest of the session
 *
 * Controlled from the TM panel CYCLE button.
 */

import { log, info, warn, success, error } from '../core/logger.js';
import { state } from '../core/state.js';
import { getFavorites, switchAsset, getCurrentAsset } from '../utils/dom.js';
import { scanMarkets } from '../utils/api.js';
import { tradeExecutor } from './executor.js';
import { CONFIG } from '../core/config.js';

const DEFAULTS = {
  perAssetMs: 60_000,         // budget per asset when NOT waiting for result
  chartLoadMs: 1_800,         // wait after asset switch before scanning
  maxChartLoadMs: 6_000,      // cap
  waitForResult: true,        // pause rotation until WIN/LOSS recorded
  resultTimeoutMs: 70_000,    // max wait for a result before moving on
  maxConsecutiveLossesPerAsset: 3,
  minConfidence: 65,
};

class CycleMode {
  constructor() {
    this.running = false;
    this.abortRequested = false;
    this.currentAsset = null;
    this.startedAt = 0;
    this.cycleCount = 0;
    this.lossStreaks = {};   // { [asset]: consecutive losses }
    this.skipList = new Set();
    this.config = { ...DEFAULTS };
  }

  isRunning() { return this.running; }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    if (this.config.minConfidence === undefined || this.config.minConfidence === null) {
      this.config.minConfidence = CONFIG.MIN_CONFIDENCE || 65;
    }
    log(`[CYCLE] config updated: ${JSON.stringify(this.config)}`);
  }

  async start() {
    if (this.running) { warn('[CYCLE] already running'); return; }
    this.running = true;
    this.abortRequested = false;
    this.startedAt = Date.now();
    this.cycleCount = 0;
    success('[CYCLE] started — rotating through favorites');
    // Run loop without awaiting (fire-and-forget)
    this._loop().catch((e) => {
      error(`[CYCLE] loop crashed: ${e.message}`);
      this.running = false;
    });
  }

  stop() {
    if (!this.running) return;
    this.abortRequested = true;
    log('[CYCLE] stop requested — finishing current iteration');
  }

  async _loop() {
    while (this.running && !this.abortRequested) {
      const favorites = this._getActiveFavorites();
      if (!favorites || favorites.length === 0) {
        warn('[CYCLE] no favorites detected — add some in Pocket Option first. Retrying in 10s. ' +
          '(Diagnostic: open browser console and run `eliteBotDom.getFavorites()` to test the scraper.)');
        await this._sleep(10_000);
        continue;
      }

      for (const fav of favorites) {
        if (this.abortRequested) break;
        if (this.skipList.has(fav)) {
          log(`[CYCLE] skipping ${fav} (loss streak)`);
          continue;
        }

        this.currentAsset = fav;
        this.cycleCount++;
        info(`[CYCLE #${this.cycleCount}] → ${fav}`);

        // 1. Switch asset (no-op if already current)
        try {
          const already = getCurrentAsset();
          if (!already || already !== fav) {
            switchAsset(fav);
            await this._waitChartLoaded();
          }
        } catch (e) {
          warn(`[CYCLE] failed to switch to ${fav}: ${e.message} — skipping`);
          continue;
        }

        if (this.abortRequested) break;

        // 2. Scan for signal
        try {
          const resp = await scanMarkets([fav], this.config.minConfidence);
          const topSignal = resp && resp.success && resp.top_signals && resp.top_signals[0];
          if (!topSignal) {
            log(`[CYCLE] ${fav} no signal ≥${this.config.minConfidence}% — next`);
            continue;
          }

          // 3. Trade execution
          if (state.autoTradeEnabled) {
            const ok = await tradeExecutor.execute(topSignal, 'cycle');
            if (!ok) {
              log(`[CYCLE] ${fav} trade not executed (validation/cooldown/auto off) — next`);
              continue;
            }

            // 4. Wait for result if configured
            if (this.config.waitForResult) {
              const outcome = await this._waitForResult(topSignal.direction);
              if (outcome === 'LOSS') {
                this.lossStreaks[fav] = (this.lossStreaks[fav] || 0) + 1;
                if (this.lossStreaks[fav] >= this.config.maxConsecutiveLossesPerAsset) {
                  warn(`[CYCLE] ${fav} ${this.lossStreaks[fav]} losses in a row — skipping for rest of session`);
                  this.skipList.add(fav);
                }
              } else if (outcome === 'WIN') {
                this.lossStreaks[fav] = 0;
              }
            } else {
              await this._sleep(this.config.perAssetMs);
            }
          } else {
            log(`[CYCLE] ${fav} signal found but AUTO is off — not executing`);
            await this._sleep(3_000);
          }
        } catch (e) {
          warn(`[CYCLE] ${fav} scan/execute error: ${e.message}`);
        }

        if (this.abortRequested) break;
      }
    }
    this.running = false;
    this.currentAsset = null;
    log('[CYCLE] stopped');
  }

  _getActiveFavorites() {
    try {
      const raw = getFavorites() || [];
      // Filter out blacklisted
      return raw.filter((a) => !this.skipList.has(a));
    } catch (_e) {
      return [];
    }
  }

  async _waitChartLoaded() {
    const start = Date.now();
    // Basic wait — let PO render the new chart
    await this._sleep(this.config.chartLoadMs);
    // Optionally poll getCurrentPrice until it returns truthy, up to max
    while (Date.now() - start < this.config.maxChartLoadMs) {
      // Small additional wait if price isn't there yet
      await this._sleep(300);
      break;  // single poll is enough — price may be canvas-only
    }
  }

  async _waitForResult(tradeDirection) {
    // Uses state.stats to detect W/L changes. Records a snapshot then waits
    // for total to increment. Honors resultTimeoutMs.
    const startWins = state.stats.wins;
    const startLosses = state.stats.losses;
    const start = Date.now();
    const timeout = this.config.resultTimeoutMs;

    while (Date.now() - start < timeout) {
      if (this.abortRequested) return 'ABORT';
      if (state.stats.wins > startWins) return 'WIN';
      if (state.stats.losses > startLosses) return 'LOSS';
      await this._sleep(500);
    }
    warn(`[CYCLE] result timeout after ${Math.round(timeout / 1000)}s on ${tradeDirection}`);
    return 'TIMEOUT';
  }

  _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  getStats() {
    return {
      running: this.running,
      currentAsset: this.currentAsset,
      cycleCount: this.cycleCount,
      startedAt: this.startedAt,
      uptimeMs: this.startedAt ? Date.now() - this.startedAt : 0,
      skipList: Array.from(this.skipList),
      lossStreaks: { ...this.lossStreaks },
    };
  }
}

export const cycleMode = new CycleMode();
export default cycleMode;
