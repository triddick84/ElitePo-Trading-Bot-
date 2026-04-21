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
      // Execution mode: 'auto' (WS when bridge healthy, DOM fallback), 'ws' (force WS), 'dom' (force DOM)
      executionMode: 'auto',
      // Cache of last known SSID bridge health — refreshed by _checkBridgeHealth()
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
        priceScraper.start(250); // faster poll for accurate 21s-left timing
      }
    } catch (_e) { /* ignore */ }

    // Start the change-detecting live price tracker
    try { livePriceTracker.start(); } catch (_e) { /* ignore */ }

    // Initial bridge health probe + periodic refresh (15s) so we know whether
    // to use WS execution (<200ms) or fall back to DOM clicks.
    this._checkBridgeHealth();
    this.bridgeHealthIntervalId = setInterval(() => this._checkBridgeHealth(), 15_000);

    this.loopId = setInterval(() => this._tick(), LOOP_INTERVAL_MS);
    success(`[21s-Reversal] Enabled — mode=${this.config.executionMode} (WS when bridge healthy)`);
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
      }

      // Already fired on this candle? skip
      if (this.firedThisCandle) return;

      // Cooldown: must skip exactly 1 candle after a fire
      if (this.lastFireCandleTs > 0 && (minute - this.lastFireCandleTs) < 120_000) {
        this._logSkipOnce('cooldown', `Cooldown active (${Math.round((120_000 - (minute - this.lastFireCandleTs)) / 1000)}s remaining)`);
        return;
      }

      // Must be within the ±tolerance window around 21s-left
      const msLeft = 60_000 - (now - minute);
      const tol = this.config.toleranceMs || DEFAULT_TOLERANCE_MS;
      if (Math.abs(msLeft - FIRE_AT_MS_LEFT) > tol) return;

      // Inside the fire window — now verify we have data
      if (this.candleOpen === null || this.candleClose === null) {
        const wsAge = poLivePrice.getLatestAge();
        const wsLatest = poLivePrice.getLatest();
        this._logSkipOnce(
          'nodata',
          `In fire window but no price yet. WS ticks captured: ${wsLatest ? `last=${wsLatest} age=${wsAge}ms` : 'none yet'}. ` +
          `Ensure PO WS is connected and a currency pair is selected.`
        );
        return;
      }

      this._attemptFire();
    } catch (e) {
      warn(`[21s-Reversal] tick error: ${e.message}`);
    }
  }

  _logSkipOnce(reasonKey, msg) {
    // One log per candle per reason, to avoid spam but keep visibility
    const key = `${this.candleStartTs}:${reasonKey}`;
    if (this._loggedSkipKey === key) return;
    this._loggedSkipKey = key;
    log(`[21s-Reversal] ${msg}`);
  }

  _attemptFire() {
    const o = this.candleOpen;
    const c = this.candleClose;
    const mid = (o + c) / 2;
    const body = c - o;
    const bodyBps = mid > 0 ? (Math.abs(body) / mid) * 10_000 : 0;

    if (bodyBps < MIN_BODY_BPS) {
      // If open == close exactly, likely we're reading a static axis label not a live price.
      const isExactlyFlat = Math.abs(body) < 1e-9;
      const lpStats = (function () { try { return livePriceTracker.getStats(); } catch (_e) { return {}; } })();
      const wsLatest = poLivePrice.getLatest();
      const wsAge = poLivePrice.getLatestAge();
      const suffix = isExactlyFlat
        ? ` [possible static label — WS:${wsLatest ? `${wsLatest}(${wsAge}ms)` : 'none'} LiveTrk:${lpStats.lastLivePrice || 'none'} tracked=${lpStats.trackedNodes || 0}]`
        : '';
      this._logSkipOnce('flat', `Indecision candle (body=${bodyBps.toFixed(2)}bps < ${MIN_BODY_BPS}bps threshold) — skip${suffix}`);
      this.firedThisCandle = true;
      return;
    }

    const originalDirection = body > 0 ? 'UP' : 'DOWN';
    const tradeDirection = body > 0 ? 'PUT' : 'CALL';
    const asset = getCurrentAsset() || 'UNKNOWN';
    const amount = state.moneyManagement.currentAmount;

    // NOTE: 21S toggle is self-authorizing — does NOT require the AUTO button.
    // Enabling the 21S button IS explicit consent to execute trades.

    const payout = getPayout();
    if (payout && payout < CONFIG.MIN_PAYOUT) {
      warn(`[21s-Reversal] Payout ${payout}% below min ${CONFIG.MIN_PAYOUT}% — skip`);
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
    info(`[21s-Reversal] Candle ${originalDirection} (body=${bodyBps.toFixed(2)}bps) → FIRE ${tradeDirection} on ${asset} @ $${amount} [${this.config.expirySeconds}s] via ${useWs ? 'WS' : 'DOM'}`);

    const executionPromise = useWs
      ? this._executeViaWs(asset, tradeDirection, amount)
      : this._executeViaDom(tradeDirection, amount);

    executionPromise
      .then((ok) => {
        if (!ok && useWs) {
          warn('[21s-Reversal] WS fire failed — falling back to DOM click');
          return this._executeViaDom(tradeDirection, amount);
        }
        return ok;
      })
      .then((ok) => {
        if (!ok) {
          error('[21s-Reversal] All execution paths failed');
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
          source: `21s-reversal-${useWs ? 'ws' : 'dom'}`,
          payout,
          wasInverted: false,
          meta: {
            candleStart: new Date(this.candleStartTs).toISOString(),
            bodyBps: +bodyBps.toFixed(2),
            fireAtMsLeft: msLeftAtFire,
            expirySeconds: this.config.expirySeconds,
            executionMode: useWs ? 'ws' : 'dom',
          },
        }).catch(() => { /* ignore */ });
      })
      .catch((e) => {
        error(`[21s-Reversal] execution error: ${e.message}`);
      });
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
        success(`[21s-Reversal] WS trade placed: order_id=${resp.order_id || '?'} latency=${resp.latency_ms || '?'}ms`);
        return true;
      }
      warn(`[21s-Reversal] WS trade rejected: ${(resp && resp.error) || 'unknown'}`);
      return false;
    } catch (e) {
      warn(`[21s-Reversal] WS trade network error: ${e.message}`);
      return false;
    }
  }

  async _executeViaDom(direction, amount) {
    try {
      const ok = await executeTrade(direction, amount);
      return !!ok;
    } catch (e) {
      error(`[21s-Reversal] DOM click error: ${e.message}`);
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
