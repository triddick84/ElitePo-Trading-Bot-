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
  getCandleCountdown,
  getChartTimeframe,
} from '../utils/dom.js';
import { priceScraper } from '../trading/priceScraper.js';
import { poLivePrice } from '../trading/ssidBridge.js';
import { livePriceTracker } from '../trading/livePriceTracker.js';
import { reportTrade, post, get as apiGet } from '../utils/api.js';
import { tradeExecutor } from '../trading/executor.js';
import { tradeResultWatcher } from '../trading/tradeResultWatcher.js';

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
      // Trigger second — fires when 1m candle has THIS many ms remaining.
      // 49_000 = fires at "49s left" (11s into the candle, ≈2s after :51 mark)
      // Adjustable from the panel's timing slider (range 10s–55s).
      fireAtMsLeft: FIRE_AT_MS_LEFT,
      toleranceMs: DEFAULT_TOLERANCE_MS,
      expirySeconds: 5,
      // minBodyBps: minimum body size (in bps of mid price) to consider candle directional.
      // Set to 0 for "always fire" behaviour where even 1-pip bodies count.
      minBodyBps: DEFAULT_MIN_BODY_BPS,
      // If body filter rejects, use recent-tick slope to determine direction
      useSlopeFallback: true,
      slopeWindowMs: 5_000,
      // alwaysFire: if true, at the trigger mark fire regardless of body/slope.
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

  /**
   * Get the last-read PO countdown value (seconds left in current candle)
   * and the wall-clock-derived value, plus the configured trigger second.
   * Used by the panel to render the live Time Strategy readout.
   */
  getLiveCountdown() {
    const now = Date.now();
    const periodSec = this._getCandlePeriodSeconds(now);
    const tfLabel = this._getCandlePeriodLabel();
    const minute = this._minuteOfNow(now);
    const wallSecLeft = Math.round(((periodSec * 1000) - (now - minute)) / 1000);
    const triggerSecRaw = Math.round((this.config.fireAtMsLeft || FIRE_AT_MS_LEFT) / 1000);
    const triggerSec = Math.max(1, Math.min(periodSec - 1, triggerSecRaw));
    return {
      poSecondsLeft: this._livePoSecondsLeft,
      wallSecondsLeft: wallSecLeft,
      triggerSec,
      periodSec,
      timeframeLabel: tfLabel,
      enabled: this.enabled,
      firedThisCandle: this.firedThisCandle,
    };
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
   * Reset the per-asset and pending-result counters (v8.45.0).
   * Used by the "Reset Stats" button in the panel — wipes Time-strategy
   * fire/win/loss history without disabling the strategy itself.
   */
  resetStats() {
    this.assetStats = {};
    this.pendingResult = null;
    log('[Time-Reversal] stats reset');
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

      // v8.50.0: Candle rollover — prefer PO's own countdown (reads the
      // chart ⏱ timer). A "new candle" is any moment the countdown jumps
      // UP (e.g. 3s → 59s). Falls back to wall-clock minute rollover when
      // the countdown DOM read fails.
      let poSecondsLeft = null;
      try {
        const cd = getCandleCountdown();
        if (cd && typeof cd.totalSeconds === 'number' && cd.totalSeconds >= 0 && cd.totalSeconds <= 60) {
          poSecondsLeft = cd.totalSeconds;
        }
      } catch (_e) { /* ignore */ }
      // v8.51.0: cache for UI readout (status strip shows live PO countdown)
      this._livePoSecondsLeft = poSecondsLeft;

      // Candle rollover detection: prefer PO-countdown jump, fall back to
      // wall-clock minute change. Either resets the fired-flag so the
      // strategy can fire the very next trigger.
      let rolledOver = false;
      if (poSecondsLeft !== null) {
        const last = this._lastCountdown;
        if (last != null && poSecondsLeft > last + 3) {
          // PO countdown jumped up → new candle
          rolledOver = true;
        }
        this._lastCountdown = poSecondsLeft;
      }
      if (minute !== this.candleStartTs) {
        rolledOver = true;
      }
      if (rolledOver) {
        this._resetCandle(minute);
      }

      // Update running OHLC - multi-source price chain (ordered by reliability):
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

      // v8.51.0: Trigger match — use BOTH timing sources OR'd together so
      // a single unreliable read never blocks a fire. Either (a) PO's DOM
      // countdown matches within ±2s, OR (b) wall-clock math matches within
      // ±2s — we fire. Previously v8.50.0 required an exact PO-countdown
      // match (±1s) which silently failed when PO's countdown DOM selector
      // didn't match the user's theme.
      //
      // v8.52.0: Timing now uses the CURRENT chart timeframe (not hardcoded
      // 60s). Works on S5 / S15 / S30 / M1 / M5 / M15 / M30 / H1 / H4 / D1.
      const periodSec = this._getCandlePeriodSeconds(now);
      const tfLabel = this._getCandlePeriodLabel();
      const triggerSecRaw = Math.round((this.config.fireAtMsLeft || FIRE_AT_MS_LEFT) / 1000);
      // Clamp trigger to a valid second within the current candle period
      const triggerSec = Math.max(1, Math.min(periodSec - 1, triggerSecRaw));
      const periodMs = periodSec * 1000;
      const msLeft = periodMs - (now - minute);
      const wallSecLeft = Math.round(msLeft / 1000);

      let inWindow = false;
      let matchSource = '';
      if (poSecondsLeft !== null && Math.abs(poSecondsLeft - triggerSec) <= 2) {
        inWindow = true;
        matchSource = `po=${poSecondsLeft}s`;
      }
      if (Math.abs(wallSecLeft - triggerSec) <= 2) {
        inWindow = true;
        matchSource = matchSource ? `${matchSource}+wall=${wallSecLeft}s` : `wall=${wallSecLeft}s`;
      }

      // One-shot per-candle fire log — only while INSIDE trigger window,
      // no spam outside. Lets the user confirm the trigger is being met.
      if (inWindow && this._windowLoggedGen !== this._candleGen) {
        this._windowLoggedGen = this._candleGen;
        info(`[Time-Reversal] TRIGGER HIT — tf=${tfLabel} ${matchSource} target=${triggerSec}s fired=${this.firedThisCandle}`);
      }
      if (!inWindow) return;

      // Per-candle debounce so we don't fire 10x inside the ~2s window on
      // a single candle. Reset on rollover (see _resetCandle).
      if (this.firedThisCandle) return;

      // Inside the fire window - verify we have data
      if (this.candleOpen === null || this.candleClose === null) {
        // Try one last-ditch price fetch from WS bridge before giving up
        const wsLatest = poLivePrice.getLatest();
        const wsAge = poLivePrice.getLatestAge();
        if (wsLatest && wsLatest > 0 && wsAge !== null && wsAge < 30_000) {
          // Synthesize a candle from the latest WS tick so the fire can proceed
          this.candleOpen = wsLatest;
          this.candleClose = wsLatest;
          this.candleHigh = wsLatest;
          this.candleLow = wsLatest;
          info(`[Time-Reversal] synthesizing candle from last WS tick (${wsLatest}, age=${wsAge}ms)`);
        } else {
          // v8.49.0: even with NO price data, still fire if alwaysFire is on.
          // Strategy is timing-based — never skip just because price signal
          // is offline. Direction defaults to CALL (flip via INVERT/A-INV).
          if (this.config.alwaysFire) {
            this.candleOpen = this.candleClose = this.candleHigh = this.candleLow = 1;
            warn(`[Time-Reversal] No price data — firing CALL fallback (alwaysFire)`);
          } else {
            this._logSkipOnce(
              'nodata',
              `In fire window but no price. Enable alwaysFire to fire anyway.`
            );
            return;
          }
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
          warn('[Time-Reversal] ZERO price movement detected all candle - defaulting to CALL');
        }
      } else {
        // v8.48.0: Never silently skip — user explicitly chose this trigger
        // second, fire at it regardless of body/slope. Default to CALL and
        // let INVERT/A-INV flip if needed.
        originalDirection = 'FLAT';
        tradeDirection = 'CALL';
        reasonTag = 'flat-fallback-CALL';
        warn('[Time-Reversal] Flat body + no slope - firing CALL as fallback (per always-fire policy)');
      }
    } else {
      // v8.48.0: Body below threshold used to skip the whole candle. Now
      // we honour the user's trigger second and fire CALL by default.
      warn(`[Time-Reversal] Body ${bodyBps.toFixed(3)}bps < ${threshold}bps threshold - firing CALL fallback`);
      originalDirection = 'FLAT-below-threshold';
      tradeDirection = 'CALL';
      reasonTag = `body-below-threshold=${bodyBps.toFixed(3)}bps`;
    }

    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      // v8.48.0: payout gate is now a soft warning — the user's timing
      // trigger is respected and we fire anyway. Previously this would
      // silently skip the entire candle.
      warn(`[Time-Reversal] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% - firing anyway (always-fire policy)`);
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

        // Build a trade record (matches tradeExecutor schema) and push it
        // onto the executor's pending queue. This is what auto-invert reads
        // when the user clicks WIN/LOSS so it can correctly attribute the
        // result to THIS 51S trade (not a stale scan/cycle one).
        const trade = {
          timestamp: new Date().toISOString(),
          asset,
          direction: tradeDirection,
          originalDirection,         // pre-invert original — for asset-history tracking
          amount,
          confidence: 65,
          strategy: '1m_21s_reversal',
          source: `51s-reversal-${useWs ? 'ws' : 'dom'}`,
          payout,
          wasInverted: false,        // 51S makes its own direction call; not invertible by SmartInvert pre-trade
        };
        try {
          tradeExecutor.tradeHistory.push(trade);
          tradeExecutor.pendingTrades.push(trade);
          state.lastTrade = trade;
        } catch (e) {
          warn(`[51s-Reversal] could not link trade to executor: ${e.message}`);
        }

        // Arm the trade-result watcher so WIN/LOSS auto-records (no manual clicks)
        try {
          tradeResultWatcher.armResolver({ ...trade, expirySeconds: this.config.expirySeconds });
        } catch (_e) { /* ignore */ }

        // Audit report (fire-and-forget) — tagged for strategy tracker
        reportTrade(trade).catch(() => { /* ignore */ });
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

  /**
   * v8.52.0: Dynamic candle period. Reads the chart's current timeframe
   * from PO's UI (M1 / M5 / S15 / etc.) and caches for 2s. Falls back to
   * 60s (M1) if PO's UI label can't be read.
   */
  _getCandlePeriodSeconds(ts = Date.now()) {
    const cache = this._tfCache;
    if (cache && (ts - cache.at) < 2000) return cache.seconds;
    let seconds = 60;
    let label = 'M1';
    try {
      const tf = getChartTimeframe();
      if (tf && tf.seconds >= 5 && tf.seconds <= 86400) {
        seconds = tf.seconds;
        label = tf.label;
      }
    } catch (_e) { /* ignore */ }
    this._tfCache = { at: ts, seconds, label };
    return seconds;
  }

  _getCandlePeriodLabel() {
    return (this._tfCache && this._tfCache.label) || 'M1';
  }

  // Aligned to local-clock period boundaries. Works for any period that
  // divides an hour cleanly (5s, 15s, 30s, 60s, 300s, 900s, 1800s, 3600s).
  _minuteOfNow(ts = Date.now()) {
    const periodMs = this._getCandlePeriodSeconds(ts) * 1000;
    return Math.floor(ts / periodMs) * periodMs;
  }

  _resetCandle(minuteTs) {
    this.candleStartTs = minuteTs;
    this.candleOpen = null;
    this.candleClose = null;
    this.candleHigh = null;
    this.candleLow = null;
    this.tickHistory = [];
    this.firedThisCandle = false;
    // v8.50.0: candle-generation counter so TRIGGER-HIT logs fire exactly
    // once per new candle (not on every 100ms tick inside the window)
    this._candleGen = (this._candleGen || 0) + 1;
    this._windowLoggedGen = null;
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
