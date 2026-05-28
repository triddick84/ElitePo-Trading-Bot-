/**
 * Trade Executor
 * Handles trade execution with cooldowns, validation, and smart inversion
 */

import { CONFIG } from '../core/config.js';
import { state, setState, recordTradeResult, recordAssetResult, saveState } from '../core/state.js';
import { log, success, error, warn, info } from '../core/logger.js';
import { executeTrade, setTradeAmount, getCurrentAsset, getPayout, getAccountBalance, scanDOMForTradeResult } from '../utils/dom.js';
import { reportTrade, recordPremiumResult, reportTradeOutcome, reportLatency } from '../utils/api.js';
import { smartInvert } from './smartInvert.js';
import { tradeResultWatcher } from './tradeResultWatcher.js';

class TradeExecutor {
  constructor() {
    this.pendingTrades = [];
    this.tradeHistory = [];
  }
  
  /**
   * Check if trading is allowed (cooldown check)
   * @param {string} source - 'scan' or 'app'
   * @returns {boolean}
   */
  canTrade(source = 'scan') {
    const now = Date.now();
    const cooldown = source === 'scan' ? CONFIG.TRADE_COOLDOWN_SCAN : CONFIG.TRADE_COOLDOWN_APP;
    const lastTrade = source === 'scan' ? state.lastScanTradeTime : state.lastAppTradeTime;
    
    if (now - lastTrade < cooldown) {
      const remaining = Math.ceil((cooldown - (now - lastTrade)) / 1000);
      log(`Cooldown active: ${remaining}s remaining`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Validate signal before execution
   * @param {Object} signal - Signal object
   * @returns {boolean}
   */
  validateSignal(signal, opts = {}) {
    const { force = false } = opts;

    if (!signal) {
      warn('No signal provided');
      return false;
    }
    
    if (!signal.direction || !['CALL', 'PUT'].includes(signal.direction.toUpperCase())) {
      warn(`Invalid direction: ${signal.direction}`);
      return false;
    }
    
    // Force mode (GO button / 51S reversal) bypasses confidence gate —
    // the user explicitly asked to fire NOW. Backend's force-generate-v2
    // returns confidence in 52–82% band which can dip below MIN_CONFIDENCE
    // for LOW-quality signals; that's expected behaviour and shouldn't
    // block an explicit user-triggered shot.
    if (!force && signal.confidence < CONFIG.MIN_CONFIDENCE) {
      log(`Signal confidence ${signal.confidence}% below minimum ${CONFIG.MIN_CONFIDENCE}%`);
      return false;
    }
    
    const payout = getPayout();
    if (payout < CONFIG.MIN_PAYOUT) {
      warn(`Payout ${payout}% below minimum ${CONFIG.MIN_PAYOUT}%`);
      return false;
    }
    
    return true;
  }
  
  /**
   * Execute a trade (with smart inversion applied)
   * @param {Object} signal - Signal to trade
   * @param {string} source - 'scan' | 'app' | 'cycle' | 'go-force' | '21s-reversal'
   * @returns {Promise<boolean>} Success
   */
  async execute(signal, source = 'scan') {
    const force = source === 'go-force' || source === '21s-reversal';
    // Iter 56c — latency instrumentation. Captures DOM-click lag (from this
    // entry point → actual click) and exec lag (click → DOM-confirmed trade).
    // Posted fire-and-forget to /api/signals/latency-report.
    const _execStartedAt = performance.now();
    const _signalId = signal?.id || signal?.signal_id || null;
    const _networkRttMs = (signal && typeof signal._fetchRttMs === 'number') ? signal._fetchRttMs : null;

    // Audit: step 1 — signal validation (force mode skips MIN_CONFIDENCE gate)
    if (!this.validateSignal(signal, { force })) {
      log(`[exec:${source}] ✗ signal validation failed`);
      // Latency-report the gate rejection so we can see how often it fires
      reportLatency({
        signalId: _signalId,
        asset: getCurrentAsset(),
        strategy: signal?.strategy,
        networkRttMs: _networkRttMs,
        notes: `gated:${source}:validation`,
      });
      return false;
    }
    log(`[exec:${source}] ✓ signal validated (${signal.direction} ${signal.confidence}%${force ? ' — force mode' : ''})`);

    // Audit: step 2 — trade cooldown/rate limits (skip when force)
    if (!force && !this.canTrade(source)) {
      log(`[exec:${source}] ✗ canTrade returned false (cooldown/rate limit)`);
      reportLatency({
        signalId: _signalId,
        asset: getCurrentAsset(),
        strategy: signal?.strategy,
        networkRttMs: _networkRttMs,
        notes: `gated:${source}:cooldown`,
      });
      return false;
    }
    log(`[exec:${source}] ✓ canTrade check passed`);

    // Audit: step 3 — AUTO gate (skip when force)
    if (!force && !state.autoTradeEnabled) {
      log(`[exec:${source}] ✗ AUTO is OFF — signal stored but not executed (click AUTO to enable)`);
      return false;
    }

    try {
      const originalDirection = signal.direction.toUpperCase();
      const direction = smartInvert.applyInversion(originalDirection);
      const asset = getCurrentAsset();

      if (direction !== originalDirection) {
        info(`[exec:${source}] INVERTING ${originalDirection} → ${direction} on ${asset} (using manual PO amount)`);
      } else {
        log(`[exec:${source}] firing ${direction} on ${asset} (${signal.confidence}%, using manual PO amount)`);
      }

      // Audit: step 4 — click only. Iter 65: trade amount is set MANUALLY in
      // PO's UI by the user. The bot no longer overwrites it. This avoids:
      //   1) DOM-mismatch warnings ("Trade amount input not found")
      //   2) Accidentally placing a wrong-sized trade if PO renames the input
      //   3) Money-management sliders fighting the user's intent
      // The internal `state.moneyManagement.currentAmount` is still tracked
      // for win/loss stats display, but it doesn't drive the UI anymore.
      const amount = state.moneyManagement.currentAmount;  // for logs/reports only
      // Iter 63 — Trade latency offset: positive = sleep N seconds before
      // clicking CALL/PUT. Negative offsets are advisory (applied as freshness-
      // budget widening in the signal poller; here we just log them).
      const _offsetSec = Number(state.latencyOffsetSec || 0);
      if (_offsetSec > 0) {
        log(`[exec:${source}] latency offset +${_offsetSec}s — sleeping before click...`);
        await new Promise((res) => setTimeout(res, _offsetSec * 1000));
      } else if (_offsetSec < 0) {
        log(`[exec:${source}] latency offset ${_offsetSec}s (anticipate mode — applied at poll level)`);
      }
      // Iter 56c — measure DOM click latency precisely around executeTrade()
      const _clickStartedAt = performance.now();
      const executed = await executeTrade(direction);
      const _clickElapsedMs = performance.now() - _clickStartedAt;
      // DOM click lag = time from execute() entry → click actually fired
      const _domClickLagMs = _clickStartedAt - _execStartedAt;

      if (executed) {
        const now = Date.now();
        setState('lastTradeTime', now);
        if (source === 'scan' || source === 'cycle') {
          setState('lastScanTradeTime', now);
        } else {
          setState('lastAppTradeTime', now);
        }

        const trade = {
          timestamp: new Date().toISOString(),
          asset,
          direction,
          originalDirection,
          amount,
          confidence: signal.confidence,
          strategy: signal.strategy || 'Unknown',
          source,
          payout: getPayout(),
          wasInverted: direction !== originalDirection,
        };

        this.tradeHistory.push(trade);
        this.pendingTrades.push(trade);
        state.lastTrade = trade;

        success(`[exec:${source}] ✅ placed ${direction} ${asset} @ $${amount}${trade.wasInverted ? ' [INVERTED]' : ''}`);

        reportTrade(trade).catch(e => {
          // Silent — /api/trades/report 404s here are non-fatal
          warn(`Failed to report trade: ${e.message}`);
        });

        // Iter 56c — fire-and-forget latency report (success path).
        // exec_lag_ms = how long executeTrade() took (click → DOM confirms).
        reportLatency({
          signalId: _signalId,
          asset,
          strategy: signal.strategy,
          networkRttMs: _networkRttMs,
          domClickLagMs: Math.round(_domClickLagMs * 100) / 100,
          execLagMs: Math.round(_clickElapsedMs * 100) / 100,
          notes: `executed:${source}${trade.wasInverted ? ':inverted' : ''}`,
        });

        // Kick off background outcome auto-resolver (balance-poll based).
        // Detects WIN/LOSS ~expiry+3s after the trade and calls recordResult,
        // which in turn posts to /api/trades/outcome so WinRateWidget can
        // compute real rolling accuracy without user WIN/LOSS clicks.
        const expirySeconds = Number(signal?.expiry_seconds) || 60;
        this._scheduleOutcomeResolution(trade, expirySeconds).catch(() => { /* noop */ });

        // Also arm the global trade-result watcher (mutation observer + balance
        // delta + DOM scan triple-source). Whichever resolves first wins.
        try {
          tradeResultWatcher.armResolver({ ...trade, expirySeconds });
        } catch (_e) { /* ignore */ }

        return true;
      } else {
        error(`[exec:${source}] ✗ executeTrade returned false — button click failed`);
        // Iter 56c — report failed-click latency so we can see if it's slow
        // *and* failing, vs just failing
        reportLatency({
          signalId: _signalId,
          asset,
          strategy: signal.strategy,
          networkRttMs: _networkRttMs,
          domClickLagMs: Math.round(_domClickLagMs * 100) / 100,
          execLagMs: Math.round(_clickElapsedMs * 100) / 100,
          notes: `click-failed:${source}`,
        });
        return false;
      }
    } catch (e) {
      error(`[exec:${source}] ✗ exception: ${e.message}`);
      return false;
    }
  }
  
  /**
   * Schedule an outcome auto-resolver for a placed trade.
   * Captures balance snapshots before/after expiry and triggers recordResult.
   * Silently skips if another handler already resolved it (pendingTrades drained).
   * @param {Object} trade - Trade record from execute()
   * @param {number} expirySeconds - Expected trade expiry (default 60s)
   */
  async _scheduleOutcomeResolution(trade, expirySeconds = 60) {
    // Avoid double-resolution if caller already records manually
    trade._autoResolverArmed = true;

    // Snapshot balance ~1.5s post click (after bet deducted)
    await new Promise(r => setTimeout(r, 1500));
    const preBalance = getAccountBalance();
    trade._preBalance = preBalance;

    // Wait expiry + safety buffer (3s)
    const waitMs = (expirySeconds * 1000) + 3000;
    await new Promise(r => setTimeout(r, waitMs));

    // If user already clicked WIN/LOSS manually OR 21s reversal resolved it,
    // pendingTrades no longer contains this trade.
    const stillPending = this.pendingTrades.includes(trade);
    if (!stillPending) return;

    // Poll for up to 10s for a stable post-expiry balance
    let isWin = null;
    const start = Date.now();
    while (Date.now() - start < 10000) {
      const domResult = scanDOMForTradeResult();
      if (domResult === true) { isWin = true; break; }
      if (domResult === false) { isWin = false; break; }

      const current = getAccountBalance();
      if (current > 0 && preBalance > 0) {
        if (current > preBalance) { isWin = true; break; }
        // LOSS = balance unchanged (bet already deducted pre-expiry)
        if (Math.abs(current - preBalance) < 0.01) { isWin = false; break; }
      }
      await new Promise(r => setTimeout(r, 500));
    }

    if (isWin === null) {
      warn(`[auto-resolve] timed out on ${trade.asset} ${trade.direction} — skipping (record manually with WIN/LOSS buttons)`);
      return;
    }

    // Remove from pending so recordResult sees the same trade object
    const idx = this.pendingTrades.indexOf(trade);
    if (idx >= 0) this.pendingTrades.splice(idx, 1);
    // Re-prepend so recordResult still picks it up
    this.pendingTrades.unshift(trade);

    this.recordResult(isWin, { autoResolved: true });
  }

  /**
   * Record trade result with premium tracking and smart inversion evaluation
   * @param {boolean} isWin - Whether trade was won
   * @param {Object} [opts] - optional tagging (e.g. auto-resolved)
   */
  recordResult(isWin, opts = {}) {
    // Core stats
    recordTradeResult(isWin);
    
    // Get the trade we're recording for. Priority: pending trade > last executed trade > last signal
    const trade = this.pendingTrades.length > 0 ? this.pendingTrades.shift() : state.lastTrade;
    const lastSignal = state.lastSignal || {};
    const asset = trade?.asset || lastSignal.symbol || getCurrentAsset() || 'UNKNOWN';
    const direction = trade?.direction || lastSignal.direction || 'UNKNOWN';
    const confidence = trade?.confidence || lastSignal.confidence || 0;
    const strategy = trade?.strategy || lastSignal.strategy || 'Unknown';
    
    if (trade) {
      trade.result = isWin ? 'WIN' : 'LOSS';
      trade.resultTime = new Date().toISOString();
      trade.autoResolved = !!opts.autoResolved;
    }
    
    log(`Recording ${isWin ? 'WIN' : 'LOSS'}: ${asset} ${direction} (conf: ${confidence})${opts.autoResolved ? ' [auto]' : ''}`);
    
    // Record per-asset history (for smart inversion).
    // Use originalDirection so consecutive-loss tracking attributes losses
    // to the SIGNAL's direction (not the post-invert direction we actually fired).
    // Fixes auto-invert "not recognising wins/losses" reported by user.
    const trackingDirection = trade?.originalDirection || direction;
    recordAssetResult(asset, trackingDirection, isWin);

    // v8.56.0: CORRECT ORDER — first record the inverted result so
    // `state.inversion.invertedTradeCount/Wins/Losses` are fresh before
    // `evaluateInversion()` inspects them. Previously evaluate ran on
    // stale counters and mis-decided whether to revert.
    smartInvert.recordInvertedResult(isWin);

    // Trigger an evaluation — checks consecutive same-direction losses
    // and flips smart-invert state when threshold is hit. Runs ONCE (the
    // duplicate call at the bottom of this function was removed in
    // v8.56.0; the double-eval was causing rapid flip-flopping).
    try {
      smartInvert.evaluateInversion(asset);
    } catch (e) {
      warn(`smartInvert.evaluateInversion error: ${e.message}`);
    }
    
    // Send to backend premium result tracker (fire-and-forget)
    recordPremiumResult(asset, direction, isWin, confidence).then(resp => {
      if (resp.success && resp.updated_stats) {
        const stats = resp.updated_stats;
        log(`Premium tracking: Asset WR ${stats.asset_win_rate}% (${stats.asset_total_trades} trades), Hour WR ${stats.hour_win_rate}%`);
      }
    }).catch(() => {
      // Silently fail - don't block trading
    });

    // Post WIN/LOSS to /api/trades/outcome so the WinRate widget can compute
    // real rolling accuracy (matches the most recent tm_trade_reports row).
    const profit = trade
      ? (isWin ? trade.amount * ((trade.payout || 80) / 100) : -trade.amount)
      : null;
    reportTradeOutcome({
      outcome: isWin ? 'WIN' : 'LOSS',
      asset,
      strategy,
      profit,
    }).then(resp => {
      if (resp && resp.success) {
        log(`Outcome synced to backend${resp.matched_trade ? ` (matched ${resp.trade_strategy || 'trade'})` : ' (orphan)'}`);
      }
    }).catch(() => { /* silent */ });
    
    // Money management
    if (isWin) {
      state.moneyManagement.currentStep = 0;
      state.moneyManagement.currentAmount = state.moneyManagement.baseAmount;
      if (trade) {
        state.moneyManagement.totalProfit += trade.amount * (trade.payout / 100);
      }
    } else {
      if (state.moneyManagement.currentStep < CONFIG.MAX_MARTINGALE_STEPS) {
        state.moneyManagement.currentStep++;
        state.moneyManagement.currentAmount = Math.min(
          CONFIG.MAX_TRADE_AMOUNT,
          state.moneyManagement.currentAmount * CONFIG.MARTINGALE_MULTIPLIER
        );
      }
      if (trade) {
        state.moneyManagement.totalProfit -= trade.amount;
      }
    }
    
    log(`Trade result: ${isWin ? 'WIN' : 'LOSS'} | Streak: ${state.stats.currentStreak} | Profit: $${state.moneyManagement.totalProfit.toFixed(2)}`);

    // v8.56.0: the previous duplicate `smartInvert.evaluateInversion(asset)`
    // call that lived here has been removed. It was running AFTER money-
    // management state had already been updated, re-triggering the flip
    // logic with no new input — and on edge cases it toggled the invert
    // state back and forth within the same tick.

    // Save state after each result
    saveState();
  }
  
  /**
   * Get trade history
   * @param {number} limit - Maximum entries
   * @returns {Object[]}
   */
  getHistory(limit = 50) {
    return this.tradeHistory.slice(-limit);
  }
  
  /**
   * Get pending trade count
   * @returns {number}
   */
  getPendingCount() {
    return this.pendingTrades.length;
  }
  
  /**
   * Reset money management
   */
  resetMoneyManagement() {
    state.moneyManagement.currentStep = 0;
    state.moneyManagement.currentAmount = state.moneyManagement.baseAmount;
    log('Money management reset');
  }
  
  /**
   * Set base trade amount
   * @param {number} amount
   */
  setBaseAmount(amount) {
    state.moneyManagement.baseAmount = amount;
    state.moneyManagement.currentAmount = amount;
    log(`Base amount set to $${amount}`);
  }
}

export const tradeExecutor = new TradeExecutor();

export default tradeExecutor;
