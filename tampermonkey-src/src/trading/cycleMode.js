/**
 * CYCLE Mode — Forex Payout Scanner (v8.60.0 rewrite)
 *
 * Rotates through ALL forex currency pairs whose CURRENT payout is ≥ the
 * configured threshold (default 85%). Uses a SINGLE asset-picker workflow:
 *   1. Open the picker, click the "Currencies" tab
 *   2. Scrape every visible row → [{symbol, payout, el}]
 *   3. Filter rows where payout >= minPayoutPercent
 *   4. For each eligible row: open picker → click "Currencies" → click row → dwell 30s
 *
 * v8.60.0 fixes the user complaint that earlier cycles "kept clicking the
 * search window open" — we never type into the search input anymore. We
 * also stopped trying slot-tile clicks (which fall through to the search
 * box). The picker is opened EXACTLY ONCE per asset switch, then closed
 * by clicking the row (PO auto-closes after a row click).
 *
 * Re-discovery cadence: every `discoveryStaleMs` (5 min) we re-open the
 * picker and re-scrape so payout changes are reflected.
 */

import { log, info, warn, success, error } from '../core/logger.js';
import {
  getCurrentAsset,
  getPayout,
  openCurrenciesPicker,
  readCurrencyPairsWithPayouts,
  clickPickerRowEl,
  dismissPicker,
} from '../utils/dom.js';

const DEFAULTS = {
  rotateEveryMs: 30_000,         // 30s per asset (user request)
  minPayoutPercent: 85,          // skip < 85% (user request)
  chartLoadMs: 1_200,            // wait after row click before reading payout
  discoveryStaleMs: 5 * 60_000,  // re-scrape full pair list every 5 min
};

// Filter rule: ONLY currency pairs (skip stocks, indices, crypto, commodities)
// — the picker's Currencies tab already filters but as a safety net we
// require the symbol to look like a 6-char FX pair, optionally with _OTC.
const FX_PAIR_RE = /^[A-Z]{3}[A-Z]{3}(_OTC)?$/;

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
      `[CYCLE] started — Currencies-tab scanner @ ${this.config.rotateEveryMs/1000}s/asset, ` +
      `min payout ${this.config.minPayoutPercent}%`
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
   * Open the picker, switch to Currencies tab, scrape ALL rows with
   * payouts, filter to FX pairs ≥ minPayoutPercent. Closes the picker
   * after scraping. Caches the symbol+payout list (refs not retained
   * because they're invalidated when the picker closes).
   */
  async _discoverEligiblePairs() {
    log('[CYCLE] discovering eligible currency pairs (≥' + this.config.minPayoutPercent + '%)…');
    const opened = await openCurrenciesPicker();
    if (!opened) {
      warn('[CYCLE] could not open Currencies picker — keeping previous list');
      return;
    }
    await this._sleep(500);

    const all = readCurrencyPairsWithPayouts();
    this.stats.scanned = all.length;

    // Filter: must be FX pair AND payout ≥ threshold
    const eligible = all.filter((p) => {
      if (!p.symbol || !FX_PAIR_RE.test(p.symbol)) return false;
      if (typeof p.payout !== 'number') return false;
      return p.payout >= this.config.minPayoutPercent;
    });

    // Sort by payout desc — best-first
    eligible.sort((a, b) => (b.payout || 0) - (a.payout || 0));

    this._lastPairs = eligible.map(({ symbol, payout }) => ({ symbol, payout }));
    this._lastDiscoveryAt = Date.now();

    await dismissPicker();
    success(
      `[CYCLE] discovered ${eligible.length}/${all.length} eligible FX pairs ` +
      `(≥${this.config.minPayoutPercent}%): ${eligible.slice(0, 8).map(p => `${p.symbol}@${p.payout}%`).join(', ')}` +
      (eligible.length > 8 ? '…' : '')
    );
  }

  /**
   * Open the picker → Currencies tab → click the row matching `symbol` → done.
   * Picker auto-closes when the row is clicked. NEVER uses the search box.
   */
  async _switchAssetViaPickerOnly(symbol) {
    // Already on this asset?
    try {
      if (getCurrentAsset() === symbol) return true;
    } catch (_e) { /* ignore */ }

    const opened = await openCurrenciesPicker();
    if (!opened) return false;
    await this._sleep(400);

    const rows = readCurrencyPairsWithPayouts();
    const match = rows.find((r) => r.symbol === symbol);
    if (match && match.el) {
      await clickPickerRowEl(match.el);
      return true;
    }

    // Symbol not visible on the current Currencies tab page — close picker
    // (we'll just skip this asset; no search-typing fallback)
    await dismissPicker();
    return false;
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
