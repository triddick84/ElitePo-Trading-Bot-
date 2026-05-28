/**
 * CYCLE Mode — Universal asset rotator (Iter 68 rewrite)
 *
 * Per user request (May 29, 2026): scan ALL asset categories ≥85% payout
 * (forex + crypto + commodities + stocks + indices), rotate every 15 seconds,
 * and pair with the SCAN feature so signals are generated on whatever asset
 * CYCLE has currently selected. Does NOT pair with the APP poller (which is
 * locked to a single asset).
 *
 * v8.68.0 changes vs v8.60.0:
 *   1. rotateEveryMs default 30s → 15s
 *   2. Discovery walks EVERY category tab (Currencies, Crypto, Commodities,
 *      Stocks, Indices) instead of only Currencies
 *   3. Symbol filter relaxed from 6-char FX-only to any [A-Z0-9]{2,12}(_OTC)?
 *   4. Switch path retries on the Currencies-only tab first (fast path) then
 *      falls back to the universal discovery (slow path).
 */

import { log, info, warn, success, error } from '../core/logger.js';
import {
  getCurrentAsset,
  getPayout,
  openCurrenciesPicker,
  readCurrencyPairsWithPayouts,
  discoverAllAssetsWithPayouts,
  clickPickerRowEl,
  dismissPicker,
} from '../utils/dom.js';

const DEFAULTS = {
  rotateEveryMs: 15_000,         // Iter 68 — user request: 15s per asset
  minPayoutPercent: 85,          // skip < 85% (user request)
  chartLoadMs: 1_200,            // wait after row click before reading payout
  discoveryStaleMs: 5 * 60_000,  // re-scrape full asset universe every 5 min
};

// Iter 68 — relaxed to accept any asset class. Symbols like EURUSD, BTCUSD,
// XAUUSD, US30, NDX100, AAPL, AAPL_OTC, etc. all pass. The picker-row text
// already provides PO-canonical symbols so we just sanity-check the shape.
const SYMBOL_RE = /^[A-Z0-9]{2,12}(_OTC)?$/;

class CycleMode {
  constructor() {
    this.running = false;
    this.abortRequested = false;
    this.currentAsset = null;
    this.startedAt = 0;
    this.cycleCount = 0;
    this.config = { ...DEFAULTS };
    this.stats = { scanned: 0, eligible: 0, skipped_low_payout: 0, switch_failures: 0 };
    this._lastDiscoveryAt = 0;
    this._lastPairs = [];   // [{symbol, payout}] — clickable refs lost after picker close
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
      `[CYCLE] started — universal asset scanner @ ${this.config.rotateEveryMs/1000}s/asset, ` +
      `min payout ${this.config.minPayoutPercent}% (pairs with SCAN; ignores APP poller)`
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
    // Make sure picker isn't left open
    dismissPicker().catch(() => {});
  }

  async _loop() {
    while (this.running && !this.abortRequested) {
      // 1. Discover/refresh the eligible pair list (every 5 min)
      const stale = (Date.now() - this._lastDiscoveryAt) > this.config.discoveryStaleMs;
      if (stale || this._lastPairs.length === 0) {
        await this._discoverEligiblePairs();
        if (this._lastPairs.length === 0) {
          warn('[CYCLE] discovery returned 0 eligible pairs — retrying in 30s');
          await this._sleep(30_000);
          continue;
        }
      }

      // 2. Iterate eligible pairs
      for (const pair of this._lastPairs) {
        if (this.abortRequested) break;
        this.cycleCount++;
        this.currentAsset = pair.symbol;
        info(`[CYCLE #${this.cycleCount}] → ${pair.symbol} (last seen payout=${pair.payout}%)`);

        const switched = await this._switchAssetViaPickerOnly(pair.symbol);
        if (!switched) {
          this.stats.switch_failures++;
          log(`[CYCLE] ${pair.symbol} switch failed — skipping`);
          continue;
        }

        // 3. Confirm payout post-switch (live-update value can differ
        // from what we scraped during discovery)
        await this._sleep(this.config.chartLoadMs);
        const livePayout = getPayout();
        if (typeof livePayout === 'number' && livePayout > 0 && livePayout < this.config.minPayoutPercent) {
          log(`[CYCLE] ${pair.symbol} live payout ${livePayout}% dropped below ${this.config.minPayoutPercent}% — moving on`);
          this.stats.skipped_low_payout++;
          continue;
        }

        // 4. Eligible — DWELL the full rotation period. Other strategies
        // (Time Strategy, AUTO scanner) fire trades on this asset while
        // it's current. We do NOT touch the picker during the dwell.
        this.stats.eligible++;
        success(`[CYCLE] ${pair.symbol} ✓ payout ${livePayout || pair.payout}% — dwelling ${this.config.rotateEveryMs/1000}s`);
        await this._sleep(this.config.rotateEveryMs);
      }
    }
    this.running = false;
    this.currentAsset = null;
    log(`[CYCLE] stopped — scanned=${this.stats.scanned} eligible=${this.stats.eligible} skipped=${this.stats.skipped_low_payout}`);
  }

  /**
   * Iter 68 — Open the picker, iterate ALL category tabs (Currencies,
   * Crypto, Commodities, Stocks, Indices), scrape every row with its
   * payout, filter to ≥minPayoutPercent. Picker is left CLOSED.
   */
  async _discoverEligiblePairs() {
    log(`[CYCLE] discovering eligible assets across ALL categories (≥${this.config.minPayoutPercent}%)…`);
    const all = await discoverAllAssetsWithPayouts();
    this.stats.scanned = all.length;

    const eligible = all.filter((p) => {
      if (!p.symbol || !SYMBOL_RE.test(p.symbol)) return false;
      if (typeof p.payout !== 'number') return false;
      return p.payout >= this.config.minPayoutPercent;
    });

    // Sort by payout desc — best edge first
    eligible.sort((a, b) => (b.payout || 0) - (a.payout || 0));

    this._lastPairs = eligible.map(({ symbol, payout }) => ({ symbol, payout }));
    this._lastDiscoveryAt = Date.now();

    if (eligible.length === 0) {
      warn(`[CYCLE] scanned ${all.length} assets, 0 met the ${this.config.minPayoutPercent}% payout floor`);
      return;
    }

    success(
      `[CYCLE] discovered ${eligible.length}/${all.length} eligible assets ` +
      `(≥${this.config.minPayoutPercent}%): ${eligible.slice(0, 10).map(p => `${p.symbol}@${p.payout}%`).join(', ')}` +
      (eligible.length > 10 ? '…' : '')
    );
  }

  /**
   * Open the picker → walk tabs → click the row matching `symbol`.
   * Fast-path tries Currencies tab first (covers 80%+ of cases). Falls
   * back to a full multi-tab discovery if not found.
   */
  async _switchAssetViaPickerOnly(symbol) {
    // Already on this asset?
    try {
      if (getCurrentAsset() === symbol) return true;
    } catch (_e) { /* ignore */ }

    // Fast path: most active OTC trading is FX, so try Currencies tab first
    const opened = await openCurrenciesPicker();
    if (opened) {
      await this._sleep(300);
      const rows = readCurrencyPairsWithPayouts();
      const match = rows.find((r) => r.symbol === symbol);
      if (match && match.el) {
        await clickPickerRowEl(match.el);
        return true;
      }
      await dismissPicker();
    }

    // Slow path: walk every category tab
    const all = await discoverAllAssetsWithPayouts();
    // discoverAllAssetsWithPayouts closes the picker before returning.
    // Re-open and click the target row.
    const target = all.find((r) => r.symbol === symbol);
    if (!target || !target.el) return false;

    // The `el` from `discoverAllAssetsWithPayouts` was captured while the
    // picker was open and is no longer in the DOM. Re-open + re-scrape and
    // click the fresh element.
    const opened2 = await openCurrenciesPicker();
    if (!opened2) return false;
    await this._sleep(300);
    // The target may be on a non-Currencies tab — find which tab via class hint.
    const fresh = await discoverAllAssetsWithPayouts();
    const live = fresh.find((r) => r.symbol === symbol);
    if (!live || !live.el) return false;
    await clickPickerRowEl(live.el);
    return true;
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
      eligiblePairs: this._lastPairs.length,
      lastDiscoveryAt: this._lastDiscoveryAt,
      config: this.config,
      stats: { ...this.stats },
    };
  }
}

export const cycleMode = new CycleMode();
export default cycleMode;
