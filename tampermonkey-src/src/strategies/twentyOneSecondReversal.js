/**
 * 51-Second Reversal Strategy (1-minute candles)
 *
 * Timing-based contrarian strategy for Pocket Option short-expiry trades.
 *
 * Mechanism:
 *  - Tracks the current LIVE 1m candle (open = first price seen at second 0,
 *    close = current price at fire moment, wick-ignored body direction).
 *  - Fires a trade in the OPPOSITE direction of the candle's body when the
 *    candle has ~51 seconds remaining (configurable tolerance window).
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
const FIRE_AT_MS_LEFT = 49_000;
const DEFAULT_TOLERANCE_MS = 1_000;   // ±1s around the 49s-left mark (fires ~2s after the :51 mark)
const DEFAULT_MIN_BODY_BPS = 0.1;     // near-zero; strategy is timing-based, not body-filter
const TICK_HISTORY_MAX = 120;         // 12s @ 100ms

class TwentyOneSecondReversal {
  constructor() {
    this.enabled = false;
    this.loopId = null;

    // Per-minute candle tracker
    this.candleStartTs = 0;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;

    // Intra-candle tick history for slope-based fallback when body is flat
    this.tickHistory = []; // [{ ts, price }]

    // Fire tracking
    this.firedThisCandle = false;
    this.lastFireCandleTs = 0;
    this.pendingResult = null;

    // Per-asset performance
    this.assetStats = {};

    // Config (user-tunable via panel / setConfig)
    this.config = {
      toleranceMs: DEFAULT_TOLERANCE_MS,
      expirySeconds: 5,
      // minBodyBps: minimum body size (in bps of mid price) to consider candle directional.
      // Set to 0 for "always fire" behaviour where even 1-pip bodies count.
      minBodyBps: DEFAULT_MIN_BODY_BPS,
      // If body filter rejects, use recent-tick slope to determine direction
      useSlopeFallback: true,
      slopeWindowMs: 5_000,
      // alwaysFire: if true, at the 51s mark fire regardless of body/slope.
      // Direction is picked from the most recent non-zero delta in tick history,
      // or defaults to CALL if everything is perfectly flat.
      // This is the recommended mode when you want to trust the timing edge
      // and ignore the price-movement filter entirely.
      alwaysFire: true,
      autoRotateOnWin: false,
      executionMode: 'auto',
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
    this._resetCandle(this._minuteOfNow());

    // Ensure the shared price scraper is running — our primary price source
    try {
      if (!priceScraper.scrapeInterval) {
        priceScraper.start(250); // faster poll for accurate 51s-left timing
      }
    } catch (_e) { /* ignore */ }

    // Start the change-detecting live price tracker
    try { livePriceTracker.start(); } catch (_e) { /* ignore */ }

    // Initial bridge health probe + periodic refresh (15s) so we know whether
    // to use WS execution (<200ms) or fall back to DOM clicks.
    this._checkBridgeHealth();
    this.bridgeHealthIntervalId = setInterval(() => this._checkBridgeHealth(), 15_000);

    this.loopId = setInterval(() => this._tick(), LOOP_INTERVAL_MS);
    success(`[51s-Reversal] Enabled — mode=${this.config.executionMode} (WS when bridge healthy)`);
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.loopId) {
      clearInterval(this.loopId);
      this.loopId = null;
    }
    if (this.bridgeHealthIntervalId) {
      clearInterval(this.bridgeHealthIntervalId);
      this.bridgeHealthIntervalId = null;
    }
    log('[51s-Reversal] Disabled');
  }

  isEnabled() {
    return this.enabled;
  }

  setConfig(partial = {}) {
    Object.assign(this.config, partial);
    log(`[51s-Reversal] Config updated: ${JSON.stringify(this.config)}`);
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

      // Update running OHLC - multi-source price chain (ordered by reliability):
      // 1) WS-captured live price (from PO's own socket frames - most accurate)
      // 2) livePriceTracker (DOM element that has been observed to CHANGE - skips static axis labels)
      // 3) priceScraper cached last price (500ms interval, DOM-based)
      // 4) getCurrentPrice (standard selectors)
      // 5) getCurrentPriceRobust (TreeWalker/SVG - may pick static axis labels, last resort)
      let price = null;
      try {
        const wsPrice = poLivePrice.getLatest();
        const wsAge = poLivePrice.getLatestAge();
        if (wsPrice && wsAge !== null && wsAge < 5000) {
          price = wsPrice;
        }
      } catch (_e) { /* ignore */ }
      if (!price || price <= 0) {
        try { price = livePriceTracker.getLivePrice(); } catch (_e) { /* ignore */ }
      }
      if (!price || price <= 0) {
        try { price = priceScraper.getCurrentPrice(); } catch (_e) { /* ignore */ }
      }
      if (!price || price <= 0) {
        try { price = getCurrentPrice(); } catch (_e) { /* ignore */ }
      }
      if (!price || price <= 0) {
        try { price = getCurrentPriceRobust(); } catch (_e) { /* ignore */ }
      }
      if (price && price > 0) {
        if (this.candleOpen === null) {
          this.candleOpen = price;
          this.candleHigh = price;
          this.candleLow = price;
        }
        this.candleClose = price;
        this.candleHigh = Math.max(this.candleHigh, price);
        this.candleLow = Math.min(this.candleLow, price);

        // Record tick for slope fallback
        this.tickHistory.push({ ts: now, price });
        if (this.tickHistory.length > TICK_HISTORY_MAX) {
          this.tickHistory.shift();
        }
      }

      // Already fired on this candle? skip
      if (this.firedThisCandle) return;

      // Cooldown: must skip exactly 1 candle after a fire
      if (this.lastFireCandleTs > 0 && (minute - this.lastFireCandleTs) < 120_000) {
        this._logSkipOnce('cooldown', `Cooldown active (${Math.round((120_000 - (minute - this.lastFireCandleTs)) / 1000)}s remaining)`);
        return;
      }

      // Must be within the ±tolerance window around 51s-left
      const msLeft = 60_000 - (now - minute);
      const tol = this.config.toleranceMs || DEFAULT_TOLERANCE_MS;
      if (Math.abs(msLeft - FIRE_AT_MS_LEFT) > tol) return;

      // Inside the fire window - verify we have data
      if (this.candleOpen === null || this.candleClose === null) {
        // Try one last-ditch price fetch from WS bridge before giving up
        const wsLatest = poLivePrice.getLatest();
        const wsAge = poLivePrice.getLatestAge();
        if (this.config.alwaysFire && wsLatest && wsLatest > 0 && wsAge !== null && wsAge < 30_000) {
          // alwaysFire: synthesize a candle from the latest WS tick so the fire can proceed
          this.candleOpen = wsLatest;
          this.candleClose = wsLatest;
          this.candleHigh = wsLatest;
          this.candleLow = wsLatest;
          info(`[51s-Reversal] alwaysFire: synthesizing candle from last WS tick (${wsLatest}, age=${wsAge}ms)`);
        } else {
          this._logSkipOnce(
            'nodata',
            `In fire window but no price yet. WS ticks: ${wsLatest ? `last=${wsLatest} age=${wsAge}ms` : 'none yet'}. ` +
            `Enable alwaysFire or ensure price flow.`
          );
          return;
        }
      }

      this._attemptFire();
    } catch (e) {
      warn(`[51s-Reversal] tick error: ${e.message}`);
    }
  }

  _logSkipOnce(reasonKey, msg) {
    // One log per candle per reason, to avoid spam but keep visibility
    const key = `${this.candleStartTs}:${reasonKey}`;
    if (this._loggedSkipKey === key) return;
    this._loggedSkipKey = key;
    log(`[51s-Reversal] ${msg}`);
  }

  _attemptFire() {
    const o = this.candleOpen;
    const c = this.candleClose;
    const mid = (o + c) / 2;
    const body = c - o;
    const bodyBps = mid > 0 ? (Math.abs(body) / mid) * 10_000 : 0;

    let originalDirection;
    let tradeDirection;
    let reasonTag;

    const threshold = this.config.minBodyBps;

    if (bodyBps >= threshold && Math.abs(body) > 1e-9) {
      // Path 1: Candle body is directional — use it
      originalDirection = body > 0 ? 'UP' : 'DOWN';
      tradeDirection = body > 0 ? 'PUT' : 'CALL';
      reasonTag = `body=${bodyBps.toFixed(3)}bps`;
    } else if (this.config.useSlopeFallback) {
      // Path 2: Try recent-tick slope
      const slope = this._computeRecentSlope(this.config.slopeWindowMs);
      if (slope && Math.abs(slope.delta) > 1e-9) {
        originalDirection = slope.delta > 0 ? 'UP-slope' : 'DOWN-slope';
        tradeDirection = slope.delta > 0 ? 'PUT' : 'CALL';
        reasonTag = `slope=${slope.bps.toFixed(3)}bps/${(this.config.slopeWindowMs / 1000)}s`;
      } else if (this.config.alwaysFire) {
        // Path 3: alwaysFire — scan ENTIRE tick history for any movement
        const anyDelta = this._computeAnyDelta();
        if (anyDelta && Math.abs(anyDelta.delta) > 1e-9) {
          originalDirection = anyDelta.delta > 0 ? 'UP-hist' : 'DOWN-hist';
          tradeDirection = anyDelta.delta > 0 ? 'PUT' : 'CALL';
          reasonTag = `hist=${anyDelta.bps.toFixed(3)}bps(${anyDelta.samples}samples)`;
        } else {
          // Path 4: Absolutely no data — default to CALL (user can flip via INVERT)
          originalDirection = 'FLAT';
          tradeDirection = 'CALL';
          reasonTag = 'flat-default-CALL';
          warn('[51s-Reversal] ZERO price movement detected all candle - defaulting to CALL');
        }
      } else {
        // alwaysFire disabled + no slope + flat body → skip
        this._logSkipOnce(
          'truly-flat',
          `Flat body + no slope - skip (set alwaysFire:true to fire anyway)`
        );
        this.firedThisCandle = true;
        return;
      }
    } else {
      // Old strict behavior — skip if body below threshold
      this._logSkipOnce('flat', `Body ${bodyBps.toFixed(3)}bps < ${threshold}bps threshold - skip`);
      this.firedThisCandle = true;
      return;
    }

    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      warn(`[51s-Reversal] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% - skip`);
      this.firedThisCandle = true;
      return;
    }

    // Try to auto-select 5s expiry if UI exposes it (needed for DOM fallback)
    this._trySetExpiry(this.config.expirySeconds);

    this.firedThisCandle = true;
    this.lastFireCandleTs = this.candleStartTs;

    const fireTs = Date.now();
    const msLeftAtFire = 60_000 - (fireTs - this.candleStartTs);

    // Tag lastSignal so WIN/LOSS recording flows through strategy tracker with correct label
    state.lastSignal = {
      direction: tradeDirection,
      symbol: asset,
      confidence: 65,
      strategy: '1m_21s_reversal',
    };
    this.pendingResult = { asset, direction: tradeDirection, fireTs, candleTs: this.candleStartTs };

    const statsRow = (this.assetStats[asset] = this.assetStats[asset] || { fires: 0, wins: 0, losses: 0, lastWinAt: 0 });
    statsRow.fires++;

    // Choose execution path
    const useWs = this._shouldUseWs();
    info(`[51s-Reversal] ${originalDirection} (${reasonTag}) → FIRE ${tradeDirection} on ${asset} @ $${amount} [${this.config.expirySeconds}s] via ${useWs ? 'WS' : 'DOM'}`);

    const executionPromise = useWs
      ? this._executeViaWs(asset, tradeDirection, amount)
      : this._executeViaDom(tradeDirection, amount);

    executionPromise
      .then((ok) => {
        if (!ok && useWs) {
          warn('[51s-Reversal] WS fire failed — falling back to DOM click');
          return this._executeViaDom(tradeDirection, amount);
        }
        return ok;
      })
      .then((ok) => {
        if (!ok) {
          error('[51s-Reversal] All execution paths failed');
          statsRow.fires = Math.max(0, statsRow.fires - 1);
          return;
        }

        // Audit report (fire-and-forget) — tagged for strategy tracker
        reportTrade({
          timestamp: new Date().toISOString(),
          asset,
          direction: tradeDirection,
          amount,
          confidence: 65,
          strategy: '1m_21s_reversal',
          source: `51s-reversal-${useWs ? 'ws' : 'dom'}`,
          payout,
          wasInverted: false,
          meta: {
            candleStart: new Date(this.candleStartTs).toISOString(),
            bodyBps: +bodyBps.toFixed(2),
            reasonTag,
            fireAtMsLeft: msLeftAtFire,
            expirySeconds: this.config.expirySeconds,
            executionMode: useWs ? 'ws' : 'dom',
          },
        }).catch(() => { /* ignore */ });
      })
      .catch((e) => {
        error(`[51s-Reversal] execution error: ${e.message}`);
      });
  }

  _computeAnyDelta() {
    if (!this.tickHistory || this.tickHistory.length < 2) return null;
    // Scan from most recent backwards for the first distinct price
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
    const now = Date.now();
    const cutoff = now - windowMs;
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
    // auto: fast path — rely on last known bridge health (refreshed every 15s)
    return !!this.config.bridgeHealthy;
  }

  async _executeViaWs(asset, direction, amount) {
    try {
      const resp = await post('/po/trade/ws-execute', {
        asset,
        direction,
        amount,
        duration_seconds: this.config.expirySeconds,
        wait_for_result: false,
        strategy: '1m_21s_reversal',
      });
      if (resp && resp.success) {
        success(`[51s-Reversal] WS trade placed: order_id=${resp.order_id || '?'} latency=${resp.latency_ms || '?'}ms`);
        return true;
      }
      warn(`[51s-Reversal] WS trade rejected: ${(resp && resp.error) || 'unknown'}`);
      return false;
    } catch (e) {
      warn(`[51s-Reversal] WS trade network error: ${e.message}`);
      return false;
    }
  }

  async _executeViaDom(direction, amount) {
    try {
      const ok = await executeTrade(direction, amount);
      return !!ok;
    } catch (e) {
      error(`[51s-Reversal] DOM click error: ${e.message}`);
      return false;
    }
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

  _minuteOfNow(ts = Date.now()) {
    return Math.floor(ts / 60_000) * 60_000;
  }

  _resetCandle(minuteTs) {
    this.candleStartTs = minuteTs;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
    this.tickHistory = [];
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
      log(`[51s-Reversal] Win on ${currentAsset} — rotating to ${next}`);
      switchAsset(next);
    } catch (e) {
      warn(`[51s-Reversal] rotation error: ${e.message}`);
    }
  }
}

export const twentyOneSecondReversal = new TwentyOneSecondReversal();
export default twentyOneSecondReversal;
