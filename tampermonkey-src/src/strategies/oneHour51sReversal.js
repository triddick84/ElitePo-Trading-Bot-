/**
 * Candle-Timer 51s Reversal Strategy
 *
 * Timeframe-agnostic timing-based contrarian. Works on ANY chart timeframe
 * (1m / 5m / 15m / 1H / etc.) — the bot just monitors PO's candle countdown
 * timer and fires whenever the seconds digits read 51.
 *
 * Mechanism:
 *   1. Read PO's chart countdown via DOM (`getCandleCountdown()`).
 *   2. Detect a new candle: the countdown's `totalSeconds` JUMPS UP
 *      (e.g. 0:01 → 4:59 means a new 5m candle just started).
 *      At that moment, capture the current price as the candle's OPEN.
 *   3. While the candle is open, track current price as `candleClose`.
 *   4. When countdown.seconds === 51, fire a 5s trade in the OPPOSITE
 *      direction of the candle's body (close vs open).
 *   5. After firing, rotate to the next asset in the configured pool.
 *
 * One fire per countdown :51 slot — debounced on `(candleEpoch, minutes)`
 * so we never double-fire while the seconds digit lingers at 51.
 */

import { CONFIG } from '../core/config.js';
import { state } from '../core/state.js';
import { log, success, warn, error, info } from '../core/logger.js';
import {
  getCurrentPrice,
  getCurrentPriceRobust,
  getCurrentAsset,
  executeTrade,
  switchAsset,
  getPayout,
  getCandleCountdown,
} from '../utils/dom.js';
import { priceScraper } from '../trading/priceScraper.js';
import { poLivePrice } from '../trading/ssidBridge.js';
import { livePriceTracker } from '../trading/livePriceTracker.js';
import { reportTrade, post, get as apiGet } from '../utils/api.js';

const LOOP_INTERVAL_MS = 100;
// Fire when the candle countdown's seconds digits === FIRE_AT_COUNTDOWN_SECONDS
const FIRE_AT_COUNTDOWN_SECONDS = 51;
// Detect new candle when countdown jumps UP by at least this many seconds
const CANDLE_RESET_DELTA_SEC = 3;
const TICK_HISTORY_MAX = 600;          // 60s @ 100ms

class OneHour51sReversal {
  constructor() {
    this.enabled = false;
    this.loopId = null;

    // Active candle tracker (timeframe-agnostic — populated when the
    // countdown indicates a new candle has started)
    this.candleEpoch = 0;          // monotonic id, increments on each new candle
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
    this.lastCountdownTotal = -1;  // for new-candle detection (jump-up)

    // Cooldown key: `${candleEpoch}-${cd.minutes}` so we never double-fire
    // within the same MM:51 slot of the same candle
    this.lastFireKey = null;

    // Asset rotation index
    this.assetRotationIdx = 0;

    // Pending result for stat aggregation
    this.pendingResult = null;
    this.assetStats = {};

    // Tick history for slope fallback when body is flat
    this.tickHistory = [];

    this.config = {
      expirySeconds: 5,
      // Always fire when countdown hits :51 even if body is flat
      // (uses last-tick slope as fallback)
      alwaysFire: true,
      // After every fire, rotate to next asset (per user spec)
      rotateAfterFire: true,
      executionMode: 'auto',   // auto | ws | dom
      bridgeHealthy: false,
      bridgeHealthCheckedAt: 0,
      // Allow ± this many seconds around 51 in case the countdown is read
      // mid-tick (e.g. transitioning from :52 → :51 → :50). Defaults to 0
      // since DOM countdown is sampled at 100ms.
      countdownToleranceSec: 0,
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
    this._resetCandle();

    try {
      if (!priceScraper.scrapeInterval) priceScraper.start(250);
    } catch (_e) { /* ignore */ }
    try { livePriceTracker.start(); } catch (_e) { /* ignore */ }

    this._checkBridgeHealth();
    this.bridgeHealthIntervalId = setInterval(() => this._checkBridgeHealth(), 15_000);

    this.loopId = setInterval(() => this._tick(), LOOP_INTERVAL_MS);
    success(`[51s] Enabled — fires every time candle countdown hits :${FIRE_AT_COUNTDOWN_SECONDS}, opposite of candle direction, then rotates asset`);

    // Self-diagnostic: probe for PO's countdown timer for 4 seconds.
    this._runCountdownDiagnostic();
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.loopId) { clearInterval(this.loopId); this.loopId = null; }
    if (this.bridgeHealthIntervalId) { clearInterval(this.bridgeHealthIntervalId); this.bridgeHealthIntervalId = null; }
    log('[51s] Disabled');
  }

  isEnabled() { return this.enabled; }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    log(`[51s] Config updated: ${JSON.stringify(this.config)}`);
  }

  getStats() {
    const totals = Object.values(this.assetStats).reduce(
      (acc, s) => { acc.fires += s.fires; acc.wins += s.wins; acc.losses += s.losses; return acc; },
      { fires: 0, wins: 0, losses: 0 }
    );
    const wr = (totals.wins + totals.losses) > 0
      ? (totals.wins / (totals.wins + totals.losses)) * 100
      : 0;
    return { ...totals, winRate: +wr.toFixed(1), perAsset: { ...this.assetStats } };
  }

  /**
   * External hook from the trade executor.
   */
  onResultRecorded(isWin) {
    if (!this.pendingResult) return;
    const { asset, fireTs } = this.pendingResult;
    if (Date.now() - fireTs > 30_000) { this.pendingResult = null; return; }
    const s = (this.assetStats[asset] = this.assetStats[asset] || { fires: 0, wins: 0, losses: 0 });
    if (isWin) s.wins++; else s.losses++;
    this.pendingResult = null;
  }

  // -- Core loop ------------------------------------------------------------

  _tick() {
    try {
      // Read PO's candle countdown timer directly from the chart UI
      const cd = getCandleCountdown();
      if (!cd) {
        this._logSkipOnce('nocd', 'Candle countdown not visible on chart yet — waiting for it to render');
        return;
      }

      // Pull current price from best available source
      let price = null;
      try {
        const wsPrice = poLivePrice.getLatest();
        const wsAge = poLivePrice.getLatestAge();
        if (wsPrice && wsAge !== null && wsAge < 5000) price = wsPrice;
      } catch (_e) { /* ignore */ }
      if (!price || price <= 0) { try { price = livePriceTracker.getLivePrice(); } catch (_e) { /* ignore */ } }
      if (!price || price <= 0) { try { price = priceScraper.getCurrentPrice(); } catch (_e) { /* ignore */ } }
      if (!price || price <= 0) { try { price = getCurrentPrice(); } catch (_e) { /* ignore */ } }
      if (!price || price <= 0) { try { price = getCurrentPriceRobust(); } catch (_e) { /* ignore */ } }

      // New-candle detection — countdown jumped UP (e.g. 0:01 → 4:59 means a
      // new 5m candle just started). Capture current price as the open.
      const candleStarted = (
        this.lastCountdownTotal >= 0 &&
        cd.totalSeconds > this.lastCountdownTotal + CANDLE_RESET_DELTA_SEC
      );
      const firstObservation = this.lastCountdownTotal < 0;

      if (candleStarted || firstObservation) {
        this.candleEpoch++;
        this.candleOpen = price && price > 0 ? price : null;
        this.candleHigh = this.candleOpen;
        this.candleLow = this.candleOpen;
        this.candleClose = this.candleOpen;
        this.tickHistory = [];
        if (candleStarted) {
          info(`[51s] New candle detected (countdown jumped to ${cd.minutes}:${String(cd.seconds).padStart(2, '0')}) — open=${this.candleOpen}`);
        }
      }
      this.lastCountdownTotal = cd.totalSeconds;

      // Update running candle OHLC
      if (price && price > 0) {
        if (this.candleOpen === null) {
          this.candleOpen = price;
          this.candleHigh = price;
          this.candleLow = price;
        }
        this.candleClose = price;
        this.candleHigh = Math.max(this.candleHigh, price);
        this.candleLow = Math.min(this.candleLow, price);
        this.tickHistory.push({ ts: Date.now(), price });
        if (this.tickHistory.length > TICK_HISTORY_MAX) this.tickHistory.shift();
      }

      // Per spec: fire when seconds digits === 51
      const tol = this.config.countdownToleranceSec || 0;
      const inWindow = Math.abs(cd.seconds - FIRE_AT_COUNTDOWN_SECONDS) <= tol;
      if (!inWindow) return;

      // Debounce: never double-fire within the same `(candle, minute)` slot
      const key = `${this.candleEpoch}-${cd.minutes}`;
      if (this.lastFireKey === key) return;

      // Verify we have data
      if (this.candleOpen === null || this.candleClose === null) {
        if (this.config.alwaysFire && price && price > 0) {
          this.candleOpen = price;
          this.candleClose = price;
          this.candleHigh = price;
          this.candleLow = price;
          info(`[51s] alwaysFire: synthesizing candle from current tick (${price})`);
        } else {
          this._logSkipOnce(`nodata-${key}`, `Countdown ${cd.minutes}:${FIRE_AT_COUNTDOWN_SECONDS} but no price yet — skip`);
          this.lastFireKey = key;
          return;
        }
      }

      this._attemptFire({ countdownMinutes: cd.minutes, countdownTotal: cd.totalSeconds, fireKey: key });
    } catch (e) {
      warn(`[51s] tick error: ${e.message}`);
    }
  }

  _logSkipOnce(reasonKey, msg) {
    if (this._loggedSkipKey === reasonKey) return;
    this._loggedSkipKey = reasonKey;
    log(`[51s] ${msg}`);
  }

  _attemptFire({ countdownMinutes, countdownTotal, fireKey }) {
    const o = this.candleOpen;
    const c = this.candleClose;
    const mid = (o + c) / 2;
    const body = c - o;
    const bodyBps = mid > 0 ? (Math.abs(body) / mid) * 10_000 : 0;

    let originalDirection;
    let tradeDirection;
    let reasonTag;

    if (Math.abs(body) > 1e-9 && bodyBps >= 0.5) {
      originalDirection = body > 0 ? 'UP' : 'DOWN';
      tradeDirection = body > 0 ? 'PUT' : 'CALL';
      reasonTag = `body=${bodyBps.toFixed(2)}bps`;
    } else {
      // Flat body — use recent tick slope
      const slope = this._computeRecentSlope(10_000);
      if (slope && Math.abs(slope.delta) > 1e-9) {
        originalDirection = slope.delta > 0 ? 'UP-slope' : 'DOWN-slope';
        tradeDirection = slope.delta > 0 ? 'PUT' : 'CALL';
        reasonTag = `slope=${slope.bps.toFixed(2)}bps/10s`;
      } else if (this.config.alwaysFire) {
        const anyDelta = this._computeAnyDelta();
        if (anyDelta && Math.abs(anyDelta.delta) > 1e-9) {
          originalDirection = anyDelta.delta > 0 ? 'UP-hist' : 'DOWN-hist';
          tradeDirection = anyDelta.delta > 0 ? 'PUT' : 'CALL';
          reasonTag = `hist=${anyDelta.bps.toFixed(2)}bps`;
        } else {
          originalDirection = 'FLAT';
          tradeDirection = 'CALL';
          reasonTag = 'flat-default-CALL';
        }
      } else {
        this._logSkipOnce(`flat-${fireKey}`, `Flat candle - skip (set alwaysFire:true)`);
        this.lastFireKey = fireKey;
        return;
      }
    }

    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      warn(`[51s] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% — skip`);
      this.lastFireKey = fireKey;
      return;
    }

    this._trySetExpiry(this.config.expirySeconds);

    this.lastFireKey = fireKey;
    const fireTs = Date.now();

    state.lastSignal = {
      direction: tradeDirection,
      symbol: asset,
      confidence: 65,
      strategy: '1h_51s_reversal',
    };
    this.pendingResult = { asset, direction: tradeDirection, fireTs };

    const statsRow = (this.assetStats[asset] = this.assetStats[asset] || { fires: 0, wins: 0, losses: 0 });
    statsRow.fires++;

    const useWs = this._shouldUseWs();
    info(`[51s] countdown=${countdownMinutes}:${FIRE_AT_COUNTDOWN_SECONDS} ${originalDirection} (${reasonTag}) → FIRE ${tradeDirection} on ${asset} @ $${amount} [${this.config.expirySeconds}s] via ${useWs ? 'WS' : 'DOM'}`);

    const executionPromise = useWs
      ? this._executeViaWs(asset, tradeDirection, amount)
      : this._executeViaDom(tradeDirection, amount);

    executionPromise
      .then((ok) => {
        if (!ok && useWs) {
          warn('[51s] WS fire failed — falling back to DOM click');
          return this._executeViaDom(tradeDirection, amount);
        }
        return ok;
      })
      .then((ok) => {
        if (!ok) {
          error('[51s] All execution paths failed');
          statsRow.fires = Math.max(0, statsRow.fires - 1);
          return;
        }

        // Audit
        reportTrade({
          timestamp: new Date().toISOString(),
          asset,
          direction: tradeDirection,
          amount,
          confidence: 65,
          strategy: '1h_51s_reversal',
          source: `51s-${useWs ? 'ws' : 'dom'}`,
          payout,
          wasInverted: false,
          meta: {
            candleEpoch: this.candleEpoch,
            bodyBps: +bodyBps.toFixed(2),
            reasonTag,
            countdownAt: `${countdownMinutes}:${FIRE_AT_COUNTDOWN_SECONDS}`,
            countdownTotalSeconds: countdownTotal,
            triggerSource: 'po-candle-countdown',
            expirySeconds: this.config.expirySeconds,
            executionMode: useWs ? 'ws' : 'dom',
          },
        }).catch(() => { /* ignore */ });

        // Rotate to next asset for the next :51 mark
        if (this.config.rotateAfterFire) {
          // Delay rotation by ~1.5s so click animation/order placement settles
          setTimeout(() => this._rotateToNext(asset), 1_500);
        }
      })
      .catch((e) => { error(`[51s] execution error: ${e.message}`); });
  }

  _computeAnyDelta() {
    if (!this.tickHistory || this.tickHistory.length < 2) return null;
    const last = this.tickHistory[this.tickHistory.length - 1];
    for (let i = this.tickHistory.length - 2; i >= 0; i--) {
      const t = this.tickHistory[i];
      if (Math.abs(t.price - last.price) > 1e-9) {
        const delta = last.price - t.price;
        const mid = (last.price + t.price) / 2;
        const bps = mid > 0 ? Math.abs(delta) / mid * 10_000 : 0;
        return { delta, bps, samples: this.tickHistory.length - i };
      }
    }
    return null;
  }

  _computeRecentSlope(windowMs) {
    if (!this.tickHistory || this.tickHistory.length < 2) return null;
    const cutoff = Date.now() - windowMs;
    const window = this.tickHistory.filter((t) => t.ts >= cutoff);
    if (window.length < 2) return null;
    const first = window[0];
    const last = window[window.length - 1];
    const delta = last.price - first.price;
    const mid = (first.price + last.price) / 2;
    const bps = mid > 0 ? Math.abs(delta) / mid * 10_000 : 0;
    return { delta, bps, samples: window.length };
  }

  _shouldUseWs() {
    if (this.config.executionMode === 'dom') return false;
    if (this.config.executionMode === 'ws') return true;
    return !!this.config.bridgeHealthy;
  }

  async _executeViaWs(asset, direction, amount) {
    try {
      const resp = await post('/po/trade/ws-execute', {
        asset, direction, amount,
        duration_seconds: this.config.expirySeconds,
        wait_for_result: false,
        strategy: '1h_51s_reversal',
      });
      if (resp && resp.success) {
        success(`[51s] WS trade placed: latency=${resp.latency_ms || '?'}ms`);
        return true;
      }
      warn(`[51s] WS trade rejected: ${(resp && resp.error) || 'unknown'}`);
      return false;
    } catch (e) {
      warn(`[51s] WS trade network error: ${e.message}`);
      return false;
    }
  }

  async _executeViaDom(direction, amount) {
    try { return !!(await executeTrade(direction, amount)); }
    catch (e) { error(`[51s] DOM click error: ${e.message}`); return false; }
  }

  async _checkBridgeHealth() {
    try {
      const st = await apiGet('/po/ssid/status');
      this.config.bridgeHealthy = !!(st && st.has_ssid && (st.health === 'healthy' || st.health === 'expiring'));
      this.config.bridgeHealthCheckedAt = Date.now();
    } catch (_e) {
      this.config.bridgeHealthy = false;
    }
  }

  // -- Helpers --------------------------------------------------------------

  /**
   * Probe PO's chart for the candle countdown timer. Logs the result
   * loudly so the user knows immediately whether scraping works on
   * their PO build.
   */
  _runCountdownDiagnostic() {
    let attempts = 0;
    const maxAttempts = 40;       // 4 seconds at 100ms
    const probe = setInterval(() => {
      attempts++;
      const cd = getCandleCountdown();
      if (cd) {
        success(
          `[51s] ✓ Candle countdown LOCKED: ${cd.minutes}:${String(cd.seconds).padStart(2, '0')} ` +
          `(found after ${attempts * 100}ms) — strategy is ready to fire when seconds === ${FIRE_AT_COUNTDOWN_SECONDS}`
        );
        clearInterval(probe);
        return;
      }
      if (attempts >= maxAttempts) {
        clearInterval(probe);
        warn(
          `[51s] ⚠ Could NOT detect candle countdown on the chart after ${maxAttempts * 100}ms. ` +
          `The strategy will keep retrying every tick, but you may need to share the inspector ` +
          `output of PO's countdown element so we can lock in a selector.`
        );
      }
    }, 100);
  }

  _resetCandle() {
    this.candleEpoch = 0;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
    this.lastCountdownTotal = -1;
    this.lastFireKey = null;
    this.tickHistory = [];
  }

  _trySetExpiry(seconds) {
    try {
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

  _rotateToNext(currentAsset) {
    try {
      const pool = this.config.rotationAssets;
      if (!pool || pool.length === 0) return;
      // Find current asset in pool
      const idx = pool.indexOf(currentAsset);
      // Advance index — wrap around
      this.assetRotationIdx = (idx >= 0 ? idx : this.assetRotationIdx) + 1;
      if (this.assetRotationIdx >= pool.length) this.assetRotationIdx = 0;
      const next = pool[this.assetRotationIdx];
      if (next === currentAsset) return;  // pool of size 1
      log(`[51s] Rotating ${currentAsset} → ${next}`);
      switchAsset(next);
    } catch (e) {
      warn(`[51s] rotation error: ${e.message}`);
    }
  }
}

export const oneHour51sReversal = new OneHour51sReversal();
export default oneHour51sReversal;
