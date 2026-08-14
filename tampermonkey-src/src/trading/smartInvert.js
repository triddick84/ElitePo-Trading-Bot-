/**
 * Smart Auto-Invert Engine
 * 
 * Detects when signals are consistently wrong (losses at S/R reversals)
 * and automatically inverts signal direction until the market confirms.
 * 
 * Logic:
 * - Tracks per-asset direction + win/loss history
 * - After N consecutive same-direction losses -> invert
 * - After inversion: if wins confirm, stay inverted
 * - After inversion: if still losing, revert (market is choppy, not trending)
 * - Cooldown prevents rapid flip-flopping
 * - Manual override button lets user force invert/revert
 */

import { CONFIG } from '../core/config.js';
import { state } from '../core/state.js';
import { log, warn, info, success } from '../core/logger.js';

class SmartInvertEngine {
  constructor() {
    this.invertCallbacks = [];
  }

  /**
   * Register callback for inversion state changes
   * @param {Function} cb - Callback(isInverted, reason)
   */
  onInvertChange(cb) {
    this.invertCallbacks.push(cb);
  }

  /**
   * Notify callbacks of inversion change
   */
  _notifyChange() {
    const { isInverted, reason } = state.inversion;
    for (const cb of this.invertCallbacks) {
      try { cb(isInverted, reason); } catch (e) { /* ignore */ }
    }
  }

  /**
   * Check if we should invert signals based on recent loss patterns.
   * Called AFTER each trade result is recorded.
   *
   * Iter 64 — Per user request, the trigger is now PURE: any 2 consecutive
   * losses (global, ANY asset, ANY direction) → flip immediately. No cooldown.
   * Same-direction grouping and per-asset gating have been removed.
   *
   * @param {string} asset - Current asset (kept for reason text only)
   */
  evaluateInversion(asset) {
    if (!CONFIG.AUTO_INVERT_ENABLED) return;
    if (!state.autoInvertEnabled) return;

    const inv = state.inversion;
    if (inv.manualOverride) return;

    // Global consecutive-loss streak (negative when losing).
    // Stats.currentStreak is decremented on every loss in core/state.js.
    const lossStreak = state.stats.currentStreak < 0
      ? Math.abs(state.stats.currentStreak)
      : 0;
    const threshold = CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES;  // default 2

    if (lossStreak > 0) {
      info(`Auto-Invert check: global loss streak = ${lossStreak} (threshold: ${threshold})`);
    }

    if (!inv.isInverted) {
      // Not inverted: invert as soon as the threshold is hit, no matter what.
      if (lossStreak >= threshold) {
        this._activate(
          `${lossStreak} consecutive losses (any asset/direction) — flipping signal`
        );
      }
    } else {
      // Currently inverted — revert when inversion has played out.
      // Two ways to come back to normal:
      //   1) we hit `INVERT_MAX_INVERTED_TRADES` inverted trades and the
      //      inverted win-rate is poor (< 40%); the market is choppy, give up.
      //   2) we see 3 consecutive WINs while inverted — the inversion worked,
      //      the original direction was wrong, and the new direction is now
      //      the trend; lock it back to normal.
      if (inv.invertedTradeCount >= CONFIG.INVERT_MAX_INVERTED_TRADES) {
        const invertWinRate = inv.invertedTradeCount > 0
          ? (inv.invertedWins / inv.invertedTradeCount * 100)
          : 0;
        if (invertWinRate < 40) {
          this._deactivate(
            `Inversion not helping (${invertWinRate.toFixed(0)}% over ${inv.invertedTradeCount} trades) — reverting`
          );
        } else {
          inv.invertedTradeCount = 0;
          inv.invertedWins = 0;
          inv.invertedLosses = 0;
          info(`Inversion confirmed effective — continuing inverted signals`);
        }
      }

      // Also revert if we see N consecutive losses while INVERTED — meaning
      // the flip itself is now losing, so flip back. Iter 107: threshold is
      // now user-tunable via CONFIG.INVERT_REVERT_AFTER_LOSSES (default 1
      // for snappy reaction — was hardcoded 2).
      const revertThreshold = Math.max(1, CONFIG.INVERT_REVERT_AFTER_LOSSES || 1);
      const recentHistory = state.assetHistory[asset] || [];
      const lastN = recentHistory.slice(-revertThreshold);
      const nLossesInverted = lastN.length === revertThreshold
        && lastN.every(r => r.result === 'LOSS');
      if (nLossesInverted && inv.invertedTradeCount >= revertThreshold) {
        this._deactivate(`${revertThreshold} consecutive loss${revertThreshold === 1 ? '' : 'es'} while inverted — flipping back`);
      }
    }
  }

  /**
   * Activate inversion
   */
  _activate(reason) {
    const inv = state.inversion;
    inv.isInverted = true;
    inv.invertedAt = Date.now();
    inv.invertedTradeCount = 0;
    inv.invertedWins = 0;
    inv.invertedLosses = 0;
    inv.lastInvertChange = Date.now();
    inv.reason = reason;
    inv.manualOverride = false;

    warn(`INVERT ACTIVATED: ${reason}`);
    this._notifyChange();
  }

  /**
   * Deactivate inversion
   */
  _deactivate(reason) {
    const inv = state.inversion;
    inv.isInverted = false;
    inv.invertedAt = 0;
    inv.invertedTradeCount = 0;
    inv.invertedWins = 0;
    inv.invertedLosses = 0;
    inv.lastInvertChange = Date.now();
    inv.reason = '';
    inv.manualOverride = false;

    info(`INVERT DEACTIVATED: ${reason}`);
    this._notifyChange();
  }

  /**
   * Manual toggle (from INVERT button)
   */
  manualToggle() {
    const inv = state.inversion;
    if (inv.isInverted) {
      inv.manualOverride = false;
      this._deactivate('Manual revert by user');
    } else {
      inv.manualOverride = true;
      this._activate('Manual inversion by user');
    }
  }

  /**
   * Apply inversion to a signal direction
   * @param {string} direction - Original CALL or PUT
   * @returns {string} Possibly inverted direction
   */
  applyInversion(direction) {
    // Respect the explicit AUTO-INVERT toggle. When off, bypass inversion entirely.
    if (!state.autoInvertEnabled) return direction;
    if (!state.inversion.isInverted) return direction;

    const inverted = direction === 'CALL' ? 'PUT' : 'CALL';
    log(`Signal inverted: ${direction} -> ${inverted} (${state.inversion.reason})`);
    return inverted;
  }

  /**
   * Record a result while inverted (track inversion effectiveness)
   * @param {boolean} isWin
   */
  recordInvertedResult(isWin) {
    if (!state.inversion.isInverted) return;

    state.inversion.invertedTradeCount++;
    if (isWin) {
      state.inversion.invertedWins++;
    } else {
      state.inversion.invertedLosses++;
    }
  }

  /**
   * Get current inversion status for display
   * @returns {Object}
   */
  getStatus() {
    const inv = state.inversion;
    return {
      isInverted: inv.isInverted,
      reason: inv.reason,
      invertedTrades: inv.invertedTradeCount,
      invertedWinRate: inv.invertedTradeCount > 0
        ? Math.round(inv.invertedWins / inv.invertedTradeCount * 100)
        : 0,
      manualOverride: inv.manualOverride,
    };
  }
}

export const smartInvert = new SmartInvertEngine();
export default smartInvert;
