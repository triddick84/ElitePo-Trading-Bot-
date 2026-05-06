/**
 * CYCLE Mode — Forex Payout Scanner (v8.59.0 rewrite)
 *
 * Rotates through a curated list of forex OTC pairs, switching the chart
 * every 30 seconds. After each switch we check the current payout via the
 * DOM scraper and SKIP any asset where the payout is below the configured
 * threshold (default 85%). The mode is purely a scheduler — it does NOT
 * fire trades itself. Combine with Time Strategy or AUTO mode to place
 * actual orders on the currently-cycled asset.
 *
 * Previously this mode rotated through user favorites and waited for trade
 * results (replaced because the user wants every forex pair scanned at
 * ≥85% payout, not just favorites).
 */

import { log, info, warn, success, error } from '../core/logger.js';
import { switchAsset, switchAssetViaPicker, getCurrentAsset, getPayout } from '../utils/dom.js';

/**
 * Curated list of major + minor + exotic forex OTC pairs. Order matters
 * only for first-pass scan; after a full cycle the order repeats.
 * We include both `_OTC` and non-OTC variants so weekend/weekday works.
 */
const FOREX_POOL = [
  // Majors
  'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'USDCHF_OTC', 'USDCAD_OTC',
  'AUDUSD_OTC', 'NZDUSD_OTC',
  // Crosses
  'EURJPY_OTC', 'EURGBP_OTC', 'EURCHF_OTC', 'EURCAD_OTC', 'EURAUD_OTC',
  'GBPJPY_OTC', 'GBPCHF_OTC', 'GBPCAD_OTC', 'GBPAUD_OTC', 'GBPNZD_OTC',
  'AUDJPY_OTC', 'AUDCAD_OTC', 'AUDCHF_OTC', 'AUDNZD_OTC',
  'NZDJPY_OTC', 'NZDCAD_OTC', 'NZDCHF_OTC',
  'CADJPY_OTC', 'CADCHF_OTC', 'CHFJPY_OTC',
  // Exotics
  'USDZAR_OTC', 'USDTRY_OTC', 'USDMXN_OTC', 'USDSGD_OTC', 'USDNOK_OTC',
  'USDSEK_OTC', 'USDBRL_OTC',
  'EURNOK_OTC', 'EURSEK_OTC',
];

const DEFAULTS = {
  rotateEveryMs: 30_000,          // 30 seconds per asset (user request)
  minPayoutPercent: 85,           // skip anything below this (user request)
  chartLoadMs: 1_500,             // wait after switching before reading payout
  payoutCheckTimeoutMs: 3_000,    // max time to wait for a readable payout
};

class CycleMode {
  constructor() {
    this.running = false;
    this.abortRequested = false;
    this.currentAsset = null;
    this.startedAt = 0;
    this.cycleCount = 0;
    this.skipThisPass = new Set();   // payout-below-threshold within this pass
    this.config = { ...DEFAULTS };
    this.stats = { scanned: 0, eligible: 0, skipped_low_payout: 0, switch_failures: 0 };
  }

  isRunning() { return this.running; }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    log(`[CYCLE] config updated: ${JSON.stringify(this.config)}`);
  }

  async start() {
    if (this.running) { warn('[CYCLE] already running'); return; }
    this.running = true;
    this.abortRequested = false;
    this.startedAt = Date.now();
    this.cycleCount = 0;
    this.stats = { scanned: 0, eligible: 0, skipped_low_payout: 0, switch_failures: 0 };
    success(
      `[CYCLE] started — forex scanner @ ${this.config.rotateEveryMs/1000}s/asset, ` +
      `min payout ${this.config.minPayoutPercent}%, pool=${FOREX_POOL.length}`
    );
    this._loop().catch((e) => {
      error(`[CYCLE] loop crashed: ${e.message}`);
      this.running = false;
    });
  }

  stop() {
    if (!this.running) return;
    this.abortRequested = true;
    log('[CYCLE] stop requested — finishing current rotation');
  }

  async _loop() {
    while (this.running && !this.abortRequested) {
      // Clear the "skipped this pass" set on each full cycle — payouts
      // can change mid-session.
      this.skipThisPass.clear();

      for (const asset of FOREX_POOL) {
        if (this.abortRequested) break;
        this.stats.scanned++;
        this.currentAsset = asset;
        this.cycleCount++;

        info(`[CYCLE #${this.cycleCount}] → ${asset}`);

        // 1. Switch asset. Prefer slot-tile click; fall back to picker.
        let switched = false;
        try {
          const already = getCurrentAsset();
          if (already === asset) {
            switched = true;
          } else {
            switchAsset(asset);
            await this._sleep(this.config.chartLoadMs);
            const after = getCurrentAsset();
            if (after === asset) {
              switched = true;
            } else {
              // Escalate to picker
              const picked = await switchAssetViaPicker(asset);
              if (picked) {
                await this._sleep(this.config.chartLoadMs);
                switched = getCurrentAsset() === asset;
              }
            }
          }
        } catch (e) {
          warn(`[CYCLE] switch error for ${asset}: ${e.message}`);
        }

        if (!switched) {
          this.stats.switch_failures++;
          log(`[CYCLE] ${asset} switch failed — skipping`);
          continue;
        }

        if (this.abortRequested) break;

        // 2. Read payout & gate on ≥ minPayoutPercent
        const payout = await this._readPayoutWithRetry();
        if (payout === null) {
          warn(`[CYCLE] ${asset} no payout reading — skipping`);
          continue;
        }
        if (payout < this.config.minPayoutPercent) {
          log(`[CYCLE] ${asset} payout ${payout}% < ${this.config.minPayoutPercent}% — SKIP`);
          this.skipThisPass.add(asset);
          this.stats.skipped_low_payout++;
          // Spend a minimal dwell on skipped assets so the user can see
          // the rotation moving, but advance faster than the full dwell.
          await this._sleep(2_000);
          continue;
        }

        // 3. Eligible — dwell for the full rotation period so other
        // strategies (Time Strategy, AUTO scanner) can fire trades on
        // this asset while it's current.
        this.stats.eligible++;
        success(`[CYCLE] ${asset} payout ${payout}% ✓ eligible — dwelling ${this.config.rotateEveryMs/1000}s`);
        await this._sleep(this.config.rotateEveryMs);
      }
    }
    this.running = false;
    this.currentAsset = null;
    log(`[CYCLE] stopped — scanned=${this.stats.scanned} eligible=${this.stats.eligible} skipped=${this.stats.skipped_low_payout}`);
  }

  /** Poll getPayout() until we get a real reading, or timeout. */
  async _readPayoutWithRetry() {
    const start = Date.now();
    while (Date.now() - start < this.config.payoutCheckTimeoutMs) {
      const p = getPayout();
      if (typeof p === 'number' && p > 0 && p < 200) return p;
      await this._sleep(250);
    }
    return null;
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
      skipThisPass: Array.from(this.skipThisPass),
      pool: FOREX_POOL,
      config: this.config,
      stats: { ...this.stats },
    };
  }
}

export const cycleMode = new CycleMode();
export default cycleMode;
