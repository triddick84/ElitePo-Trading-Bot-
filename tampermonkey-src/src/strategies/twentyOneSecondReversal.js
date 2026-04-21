/**
 * 21-Second Reversal Strategy (1-minute candles)
 *
 * Timing-based contrarian strategy for Pocket Option short-expiry trades.
 *
 * Mechanism:
 *  - Tracks the current LIVE 1m candle (open = first price seen at second 0,
 *    close = current price at fire moment, wick-ignored body direction).
 *  - Fires a trade in the OPPOSITE direction of the candle's body when the
 *    candle has ~21 seconds remaining (configurable tolerance window).
 *  - Trade expiry: auto-selects closest PO expiry (≈5s); user should preset
 *    PO expiry to 5s for best accuracy.
 *  - Cooldown: skips exactly 1 full candle after every fire.
 *  - Optional: rotates to next asset on win.
 *
 * Runs its own high-frequency loop (100ms) independent of the shared
 * priceScraper / strategyManager chain, because timing precision is critical.
 */

import { CONFIG } from '../core/config.js';
import { state } from '../core/state.js';
import { log, success, warn, error, info } from '../core/logger.js';
import {
  getCurrentPrice,
  getCurrentAsset,
  executeTrade,
  switchAsset,
  getPayout,
} from '../utils/dom.js';
import { reportTrade } from '../utils/api.js';

const LOOP_INTERVAL_MS = 100;
const FIRE_AT_MS_LEFT = 21_000;
const DEFAULT_TOLERANCE_MS = 1_000; // ±1s around the 21s-left mark
const MIN_BODY_BPS = 0.8;           // ignore indecision candles

class TwentyOneSecondReversal {
  constructor() {
    this.enabled = false;
    this.loopId = null;

    // Per-minute candle tracker
    this.candleStartTs = 0; // wall-clock ms, aligned to minute
    this.candleOpen = null; // first observed price in the current minute
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;

    // Fire tracking
    this.firedThisCandle = false;     // already fired on current candle?
    this.lastFireCandleTs = 0;        // ts of the candle we last fired on
    this.pendingResult = null;        // { asset, direction, fireTs, candleTs }

    // Per-asset performance
    this.assetStats = {}; // { [asset]: { fires, wins, losses, lastWinAt } }

    // Config (user-tunable via panel)
    this.config = {
      toleranceMs: DEFAULT_TOLERANCE_MS,
      expirySeconds: 5,
      autoRotateOnWin: false,
      rotationAssets: [
        'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC',
        'EURJPY_OTC', 'GBPJPY_OTC', 'NZDUSD_OTC', 'USDCAD_OTC',
      ],
    };
  }

  // -- Public API -----------------------------------------------------------

  enable() {
    if (this.enabled) return;
    this.enabled = true;
    this._resetCandle(this._minuteOfNow());
    this.loopId = setInterval(() => this._tick(), LOOP_INTERVAL_MS);
    success('[21s-Reversal] Enabled — firing on 1m candles @ 21s left (opposite direction, 5s expiry)');
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.loopId) {
      clearInterval(this.loopId);
      this.loopId = null;
    }
    log('[21s-Reversal] Disabled');
  }

  isEnabled() {
    return this.enabled;
  }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    log(`[21s-Reversal] Config updated: ${JSON.stringify(this.config)}`);
  }

  getStats() {
    const totals = Object.values(this.assetStats).reduce(
      (acc, s) => {
        acc.fires += s.fires;
        acc.wins += s.wins;
        acc.losses += s.losses;
        return acc;
      },
      { fires: 0, wins: 0, losses: 0 }
    );
    const wr = (totals.wins + totals.losses) > 0
      ? (totals.wins / (totals.wins + totals.losses)) * 100
      : 0;
    return { ...totals, winRate: +wr.toFixed(1), perAsset: { ...this.assetStats } };
  }

  /**
   * External hook: call when the trade executor records a result.
   * Matches by asset + direction + recent fire window.
   */
  onResultRecorded(isWin) {
    if (!this.pendingResult) return;
    const { asset, fireTs } = this.pendingResult;
    const age = Date.now() - fireTs;
    // Only claim the result if it happened within a realistic window
    // (fire + 5s expiry + some slack)
    if (age > 30_000) {
      this.pendingResult = null;
      return;
    }
    const s = (this.assetStats[asset] = this.assetStats[asset] || { fires: 0, wins: 0, losses: 0, lastWinAt: 0 });
    if (isWin) {
      s.wins++;
      s.lastWinAt = Date.now();
      if (this.config.autoRotateOnWin) {
        this._rotateAsset(asset);
      }
    } else {
      s.losses++;
    }
    this.pendingResult = null;
  }

  // -- Core loop ------------------------------------------------------------

  _tick() {
    try {
      const now = Date.now();
      const minute = this._minuteOfNow(now);

      // Candle rollover
      if (minute !== this.candleStartTs) {
        // Candle closed — reset tracker
        this._resetCandle(minute);
      }

      // Update running OHLC
      const price = getCurrentPrice();
      if (price && price > 0) {
        if (this.candleOpen === null) {
          this.candleOpen = price;
          this.candleHigh = price;
          this.candleLow = price;
        }
        this.candleClose = price;
        this.candleHigh = Math.max(this.candleHigh, price);
        this.candleLow = Math.min(this.candleLow, price);
      }

      // Already fired on this candle? skip
      if (this.firedThisCandle) return;

      // Cooldown: must skip exactly 1 candle after a fire
      if (this.lastFireCandleTs > 0 && (minute - this.lastFireCandleTs) < 120_000) {
        return;
      }

      // Must be within the ±tolerance window around 21s-left
      const msLeft = 60_000 - (now - minute);
      const tol = this.config.toleranceMs || DEFAULT_TOLERANCE_MS;
      if (Math.abs(msLeft - FIRE_AT_MS_LEFT) > tol) return;

      // Must have enough data
      if (this.candleOpen === null || this.candleClose === null) return;

      this._attemptFire();
    } catch (e) {
      warn(`[21s-Reversal] tick error: ${e.message}`);
    }
  }

  _attemptFire() {
    const o = this.candleOpen;
    const c = this.candleClose;
    const mid = (o + c) / 2;
    const body = c - o;
    const bodyBps = mid > 0 ? (Math.abs(body) / mid) * 10_000 : 0;

    if (bodyBps < MIN_BODY_BPS) {
      return; // flat/indecision — skip quietly
    }

    const originalDirection = body > 0 ? 'UP' : 'DOWN';
    const tradeDirection = body > 0 ? 'PUT' : 'CALL';
    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    // Pre-fire guards
    if (!state.autoTradeEnabled) {
      log(`[21s-Reversal] Would fire ${tradeDirection} on ${asset} (body=${body.toFixed(6)}, ${bodyBps.toFixed(2)}bps) — AUTO off`);
      this.firedThisCandle = true; // still mark so we don't spam logs
      return;
    }
    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      warn(`[21s-Reversal] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% — skip`);
      this.firedThisCandle = true;
      return;
    }

    // Try to auto-select 5s expiry if UI exposes it
    this._trySetExpiry(this.config.expirySeconds);

    info(`[21s-Reversal] Candle ${originalDirection} (body=${bodyBps.toFixed(2)}bps) → FIRE ${tradeDirection} on ${asset} @ $${amount} [5s]`);

    this.firedThisCandle = true;
    this.lastFireCandleTs = this.candleStartTs;

    executeTrade(tradeDirection, amount).then((ok) => {
      if (!ok) {
        error('[21s-Reversal] Trade click failed');
        return;
      }

      const fireTs = Date.now();
      this.pendingResult = { asset, direction: tradeDirection, fireTs, candleTs: this.candleStartTs };

      // Tag lastSignal so WIN/LOSS recording flows through strategy tracker with correct label
      state.lastSignal = {
        direction: tradeDirection,
        symbol: asset,
        confidence: 65,
        strategy: '1m_21s_reversal',
      };

      const s = (this.assetStats[asset] = this.assetStats[asset] || { fires: 0, wins: 0, losses: 0, lastWinAt: 0 });
      s.fires++;

      // Report fire to backend (fire-and-forget, tagged for strategy tracker)
      reportTrade({
        timestamp: new Date().toISOString(),
        asset,
        direction: tradeDirection,
        amount,
        confidence: 65,
        strategy: '1m_21s_reversal',
        source: '21s-reversal',
        payout,
        wasInverted: false,
        meta: {
          candleStart: new Date(this.candleStartTs).toISOString(),
          bodyBps: +bodyBps.toFixed(2),
          fireAtMsLeft: 60_000 - (fireTs - this.candleStartTs),
          expirySeconds: this.config.expirySeconds,
        },
      }).catch(() => { /* ignore */ });
    }).catch((e) => {
      error(`[21s-Reversal] executeTrade error: ${e.message}`);
    });
  }

  // -- Helpers --------------------------------------------------------------

  _minuteOfNow(ts = Date.now()) {
    return Math.floor(ts / 60_000) * 60_000;
  }

  _resetCandle(minuteTs) {
    this.candleStartTs = minuteTs;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
    this.firedThisCandle = false;
  }

  _trySetExpiry(seconds) {
    // Best-effort — PO exposes expiry selectors in several layouts.
    // Try common patterns; silently skip if none match (user should preset).
    try {
      // Pattern 1: dropdown items with "S" labels (e.g., "5 s", "5S", "5 S")
      const items = document.querySelectorAll(
        '.drop-down-modal .drop-down-modal-item, .expiry-switcher__item, .trading-panel-modal__item, [data-hd-test="expiration-item"]'
      );
      for (const el of items) {
        const txt = (el.textContent || '').trim().toLowerCase().replace(/\s+/g, '');
        if (txt === `${seconds}s` || txt === `0:0${seconds}` || txt === `0:00:0${seconds}`) {
          el.click();
          return true;
        }
      }
    } catch (_e) { /* ignore */ }
    return false;
  }

  _rotateAsset(currentAsset) {
    try {
      const pool = this.config.rotationAssets.filter((a) => a !== currentAsset);
      if (pool.length === 0) return;
      // Pick the one we haven't used recently (least recent lastWinAt)
      const ranked = pool.map((a) => {
        const s = this.assetStats[a] || {};
        return { asset: a, lastWinAt: s.lastWinAt || 0 };
      }).sort((x, y) => x.lastWinAt - y.lastWinAt);
      const next = ranked[0].asset;
      log(`[21s-Reversal] Win on ${currentAsset} — rotating to ${next}`);
      switchAsset(next);
    } catch (e) {
      warn(`[21s-Reversal] rotation error: ${e.message}`);
    }
  }
}

export const twentyOneSecondReversal = new TwentyOneSecondReversal();
export default twentyOneSecondReversal;
