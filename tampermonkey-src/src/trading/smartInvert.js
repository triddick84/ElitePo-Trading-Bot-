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
import { state, getConsecutiveSameDirectionLosses, recordAssetResult } from '../core/state.js';
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
   * @param {string} asset - Current asset
   */
  evaluateInversion(asset) {
    if (!CONFIG.AUTO_INVERT_ENABLED) return;

    const now = Date.now();
    const inv = state.inversion;
    const cooldown = CONFIG.INVERT_COOLDOWN_MS;

    // Respect cooldown
    if (now - inv.lastInvertChange < cooldown) return;

    // Don't override manual
    if (inv.manualOverride) return;

    const { count, direction } = getConsecutiveSameDirectionLosses(asset);
    const threshold = CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES;

    if (!inv.isInverted) {
      // Not inverted: check if we should invert
      if (count >= threshold && direction) {
        this._activate(
          `${count} consecutive ${direction} losses on ${asset} - market likely reversed`
        );
      }
    } else {
      // Currently inverted: check if we should revert
      // Revert if inverted trades aren't improving
      if (inv.invertedTradeCount >= CONFIG.INVERT_MAX_INVERTED_TRADES) {
        const invertWinRate = inv.invertedTradeCount > 0
          ? (inv.invertedWins / inv.invertedTradeCount * 100)
          : 0;

        if (invertWinRate < 40) {
          this._deactivate(
            `Inversion not helping (${invertWinRate.toFixed(0)}% win rate over ${inv.invertedTradeCount} trades) - reverting`
          );
        } else {
          // Reset counter but stay inverted (it's working)
          inv.invertedTradeCount = 0;
          inv.invertedWins = 0;
          inv.invertedLosses = 0;
          info(`Inversion confirmed effective - continuing inverted signals`);
        }
      }

      // Also revert if we see consecutive wins in original direction (market found trend)
      const recentHistory = state.assetHistory[asset] || [];
      const lastResults = recentHistory.slice(-3);
      const allWins = lastResults.length >= 3 && lastResults.every(r => r.result === 'WIN');
      if (allWins && inv.invertedTradeCount >= 3) {
        this._deactivate('3 consecutive wins - market trend confirmed, removing inversion');
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
