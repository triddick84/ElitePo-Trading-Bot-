/**
 * 1-Hour 51-Second Reversal Strategy
 *
 * Fires every minute at the :51-second wallclock mark, in the OPPOSITE
 * direction of the OPEN 1-hour candle's body. After each fire, rotates to
 * the next asset in the configured pool and waits for the next :51 mark.
 *
 * Mechanism:
 *   - Tracks the current LIVE 1-hour candle (open = first price seen this
 *     hour, close = current price at fire moment).
 *   - At wallclock seconds === 51 (within ±tolerance), evaluates the candle's
 *     body direction and fires the opposite side as a 5-second trade.
 *   - Once-per-minute cooldown: never double-fires within the same minute.
 *   - Rotates to the next asset on every fire.
 *
 * Independent 100ms loop (timing precision matters), separate from the
 * shared price scraper / strategy manager.
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
} from '../utils/dom.js';
import { priceScraper } from '../trading/priceScraper.js';
import { poLivePrice } from '../trading/ssidBridge.js';
import { livePriceTracker } from '../trading/livePriceTracker.js';
import { reportTrade, post, get as apiGet } from '../utils/api.js';

const LOOP_INTERVAL_MS = 100;
const FIRE_AT_SECOND = 51;
const DEFAULT_TOLERANCE_MS = 800;     // ±0.8s around the :51 mark
const HOUR_MS = 3_600_000;
const MINUTE_MS = 60_000;
const TICK_HISTORY_MAX = 600;          // 60s @ 100ms

class OneHour51sReversal {
  constructor() {
    this.enabled = false;
    this.loopId = null;

    // 1-hour candle tracker
    this.hourStartTs = 0;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;

    // Per-minute fire tracking — keyed by minute timestamp
    this.lastFireMinuteTs = 0;

    // Asset rotation index
    this.assetRotationIdx = 0;

    // Pending result for stat aggregation
    this.pendingResult = null;
    this.assetStats = {};

    // Tick history for slope fallback when body is flat
    this.tickHistory = [];

    this.config = {
      toleranceMs: DEFAULT_TOLERANCE_MS,
      expirySeconds: 5,
      // Always fire at :51 even if body is flat (uses last-tick slope as fallback)
      alwaysFire: true,
      // After every fire, rotate to next asset (per user spec)
      rotateAfterFire: true,
      executionMode: 'auto',   // auto | ws | dom
      bridgeHealthy: false,
      bridgeHealthCheckedAt: 0,
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
    this._resetCandle(this._hourOfNow());

    try {
      if (!priceScraper.scrapeInterval) priceScraper.start(250);
    } catch (_e) { /* ignore */ }
    try { livePriceTracker.start(); } catch (_e) { /* ignore */ }

    this._checkBridgeHealth();
    this.bridgeHealthIntervalId = setInterval(() => this._checkBridgeHealth(), 15_000);

    this.loopId = setInterval(() => this._tick(), LOOP_INTERVAL_MS);
    success(`[1h-51s] Enabled — fires every minute at :${FIRE_AT_SECOND}s, rotates after each fire`);
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.loopId) { clearInterval(this.loopId); this.loopId = null; }
    if (this.bridgeHealthIntervalId) { clearInterval(this.bridgeHealthIntervalId); this.bridgeHealthIntervalId = null; }
    log('[1h-51s] Disabled');
  }

  isEnabled() { return this.enabled; }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    log(`[1h-51s] Config updated: ${JSON.stringify(this.config)}`);
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
      const now = Date.now();
      const hour = this._hourOfNow(now);

      // 1H candle rollover
      if (hour !== this.hourStartTs) this._resetCandle(hour);

      // Update running 1H OHLC from best available price source
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

      if (price && price > 0) {
        if (this.candleOpen === null) {
          this.candleOpen = price;
          this.candleHigh = price;
          this.candleLow = price;
        }
        this.candleClose = price;
        this.candleHigh = Math.max(this.candleHigh, price);
        this.candleLow = Math.min(this.candleLow, price);
        this.tickHistory.push({ ts: now, price });
        if (this.tickHistory.length > TICK_HISTORY_MAX) this.tickHistory.shift();
      }

      // Cooldown: max once per minute
      const minuteTs = Math.floor(now / MINUTE_MS) * MINUTE_MS;
      if (minuteTs === this.lastFireMinuteTs) return;

      // Are we in the :51-second fire window?
      const msIntoMinute = now - minuteTs;
      const targetMs = FIRE_AT_SECOND * 1000;
      if (Math.abs(msIntoMinute - targetMs) > this.config.toleranceMs) return;

      // Verify we have data
      if (this.candleOpen === null || this.candleClose === null) {
        const wsLatest = poLivePrice.getLatest();
        const wsAge = poLivePrice.getLatestAge();
        if (this.config.alwaysFire && wsLatest && wsLatest > 0 && wsAge !== null && wsAge < 30_000) {
          this.candleOpen = wsLatest;
          this.candleClose = wsLatest;
          this.candleHigh = wsLatest;
          this.candleLow = wsLatest;
          info(`[1h-51s] alwaysFire: synthesizing from last WS tick (${wsLatest}, age=${wsAge}ms)`);
        } else {
          this._logSkipOnce(minuteTs, 'nodata', `In :${FIRE_AT_SECOND}s window but no price yet — skip this minute`);
          this.lastFireMinuteTs = minuteTs;  // burn the slot to prevent retry spam
          return;
        }
      }

      this._attemptFire(minuteTs);
    } catch (e) {
      warn(`[1h-51s] tick error: ${e.message}`);
    }
  }

  _logSkipOnce(minuteTs, reasonKey, msg) {
    const key = `${minuteTs}:${reasonKey}`;
    if (this._loggedSkipKey === key) return;
    this._loggedSkipKey = key;
    log(`[1h-51s] ${msg}`);
  }

  _attemptFire(minuteTs) {
    const o = this.candleOpen;
    const c = this.candleClose;
    const mid = (o + c) / 2;
    const body = c - o;
    const bodyBps = mid > 0 ? (Math.abs(body) / mid) * 10_000 : 0;

    let originalDirection;
    let tradeDirection;
    let reasonTag;

    if (Math.abs(body) > 1e-9 && bodyBps >= 0.5) {
      originalDirection = body > 0 ? '1H-UP' : '1H-DOWN';
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
        this._logSkipOnce(minuteTs, 'flat', `Flat candle - skip (set alwaysFire:true)`);
        this.lastFireMinuteTs = minuteTs;
        return;
      }
    }

    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      warn(`[1h-51s] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% — skip`);
      this.lastFireMinuteTs = minuteTs;
      return;
    }

    this._trySetExpiry(this.config.expirySeconds);

    this.lastFireMinuteTs = minuteTs;
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
    info(`[1h-51s] ${originalDirection} (${reasonTag}) → FIRE ${tradeDirection} on ${asset} @ $${amount} [${this.config.expirySeconds}s] via ${useWs ? 'WS' : 'DOM'}`);

    const executionPromise = useWs
      ? this._executeViaWs(asset, tradeDirection, amount)
      : this._executeViaDom(tradeDirection, amount);

    executionPromise
      .then((ok) => {
        if (!ok && useWs) {
          warn('[1h-51s] WS fire failed — falling back to DOM click');
          return this._executeViaDom(tradeDirection, amount);
        }
        return ok;
      })
      .then((ok) => {
        if (!ok) {
          error('[1h-51s] All execution paths failed');
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
          source: `1h-51s-${useWs ? 'ws' : 'dom'}`,
          payout,
          wasInverted: false,
          meta: {
            hourStart: new Date(this.hourStartTs).toISOString(),
            bodyBps: +bodyBps.toFixed(2),
            reasonTag,
            fireAtSecond: FIRE_AT_SECOND,
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
      .catch((e) => { error(`[1h-51s] execution error: ${e.message}`); });
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
        success(`[1h-51s] WS trade placed: latency=${resp.latency_ms || '?'}ms`);
        return true;
      }
      warn(`[1h-51s] WS trade rejected: ${(resp && resp.error) || 'unknown'}`);
      return false;
    } catch (e) {
      warn(`[1h-51s] WS trade network error: ${e.message}`);
      return false;
    }
  }

  async _executeViaDom(direction, amount) {
    try { return !!(await executeTrade(direction, amount)); }
    catch (e) { error(`[1h-51s] DOM click error: ${e.message}`); return false; }
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

  _hourOfNow(ts = Date.now()) {
    return Math.floor(ts / HOUR_MS) * HOUR_MS;
  }

  _resetCandle(hourTs) {
    this.hourStartTs = hourTs;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
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
      log(`[1h-51s] Rotating ${currentAsset} → ${next}`);
      switchAsset(next);
    } catch (e) {
      warn(`[1h-51s] rotation error: ${e.message}`);
    }
  }
}

export const oneHour51sReversal = new OneHour51sReversal();
export default oneHour51sReversal;
