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
import { post as apiPost } from '../utils/api.js';

// Iter 122 — Bug 2 diagnostic: post every auto-invert transition to the
// backend so we have an audit trail when users report "it says it's working
// but doesn't switch". Fire-and-forget; never blocks the trading path.
function _logInvertEvent(event, asset, extra = {}) {
  try {
    const inv = state.inversion;
    const lossStreak = state.stats.currentStreak < 0 ? Math.abs(state.stats.currentStreak) : 0;
    const payload = {
      event,
      reason: (extra.reason || inv.reason || '').toString().slice(0, 200),
      is_inverted: !!inv.isInverted,
      auto_invert_enabled: !!state.autoInvertEnabled,
      config_enabled: !!CONFIG.AUTO_INVERT_ENABLED,
      manual_override: !!inv.manualOverride,
      current_streak: state.stats.currentStreak || 0,
      loss_streak: lossStreak,
      threshold: CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES || 2,
      inverted_trade_count: inv.invertedTradeCount || 0,
      inverted_wins: inv.invertedWins || 0,
      inverted_losses: inv.invertedLosses || 0,
      asset: asset || null,
      tm_version: (typeof GM_info !== 'undefined' && GM_info?.script?.version) || null,
      blockers: extra.blockers || null,
    };
    apiPost('/tampermonkey/invert-events/log', payload).catch(() => {});
  } catch (_e) { /* never throw from telemetry */ }
}

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
   * Iter 113 — Auto-invert wasn't firing for some users. Root cause was
   * silent early-returns from guards. We now WARN loudly with the exact
   * reason so users can see WHY auto-invert didn't fire (visible in the
   * TM script's console + AI-Analysis tab).
   *
   * @param {string} asset - Current asset (kept for reason text only)
   */
  evaluateInversion(asset) {
    // Iter 113 — surface every guard so users can debug why it doesn't fire
    if (!CONFIG.AUTO_INVERT_ENABLED) {
      warn(`[AutoInvert] BLOCKED — CONFIG.AUTO_INVERT_ENABLED is false`);
      _logInvertEvent('BLOCKED', asset, { reason: 'CONFIG.AUTO_INVERT_ENABLED=false', blockers: ['config_disabled'] });
      return;
    }
    if (!state.autoInvertEnabled) {
      warn(`[AutoInvert] BLOCKED — state.autoInvertEnabled is false (A-INV button OFF)`);
      _logInvertEvent('BLOCKED', asset, { reason: 'state.autoInvertEnabled=false', blockers: ['user_toggle_off'] });
      return;
    }

    const inv = state.inversion;
    if (inv.manualOverride) {
      warn(`[AutoInvert] BLOCKED — manualOverride is true (user forced INVERT). ` +
           `Tap INVERT again to release manual lock.`);
      _logInvertEvent('BLOCKED', asset, { reason: 'manualOverride=true', blockers: ['manual_override'] });
      return;
    }

    // Global consecutive-loss streak (negative when losing).
    // Stats.currentStreak is decremented on every loss in core/state.js.
    const lossStreak = state.stats.currentStreak < 0
      ? Math.abs(state.stats.currentStreak)
      : 0;
    const threshold = CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES;  // default 2

    info(`[AutoInvert] check: lossStreak=${lossStreak} · threshold=${threshold} · ` +
         `isInverted=${inv.isInverted} · autoInvertEnabled=${state.autoInvertEnabled} · ` +
         `currentStreak=${state.stats.currentStreak}`);
    // Iter 122 — audit every evaluation so users can prove the engine is
    // actually being called after each loss.
    _logInvertEvent('EVALUATED', asset, {
      reason: `lossStreak=${lossStreak}/${threshold}`,
    });

    if (!inv.isInverted) {
      // Not inverted: invert as soon as the threshold is hit, no matter what.
      if (lossStreak >= threshold) {
        this._activate(
          `${lossStreak} consecutive losses (any asset/direction) — flipping signal`
        );
      } else if (lossStreak > 0) {
        info(`[AutoInvert] ${lossStreak}/${threshold} losses — need ${threshold - lossStreak} more to flip`);
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
    _logInvertEvent('ACTIVATED', null, { reason });
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
    _logInvertEvent('DEACTIVATED', null, { reason });
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

  /**
   * Iter 113 — Diagnostic snapshot for the AI-Analysis tab + console.
   * Returns everything a user needs to see to understand WHY auto-invert
   * is or isn't firing. Also exposed as `window.__aiEliteInvertDiag()` so
   * the user can drop that into DevTools console.
   */
  diagnose() {
    const inv = state.inversion;
    const lossStreak = state.stats.currentStreak < 0
      ? Math.abs(state.stats.currentStreak)
      : 0;
    const threshold = CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES;
    const reasons = [];
    if (!CONFIG.AUTO_INVERT_ENABLED) reasons.push("CONFIG.AUTO_INVERT_ENABLED=false");
    if (!state.autoInvertEnabled) reasons.push("state.autoInvertEnabled=false (A-INV button OFF)");
    if (inv.manualOverride) reasons.push("manualOverride=true (release with INVERT tap)");
    if (lossStreak < threshold) reasons.push(`streak ${lossStreak} < threshold ${threshold}`);
    return {
      ok: reasons.length === 0 && lossStreak >= threshold,
      lossStreak,
      threshold,
      currentStreak: state.stats.currentStreak,
      isInverted: inv.isInverted,
      autoInvertEnabled: state.autoInvertEnabled,
      configEnabled: CONFIG.AUTO_INVERT_ENABLED,
      manualOverride: inv.manualOverride,
      wouldFire: !inv.isInverted && lossStreak >= threshold && reasons.length === 0,
      blockers: reasons,
    };
  }

  /**
   * Iter 113 — Test the pipeline end-to-end. Simulates N losses via
   * `recordTradeResult(false)` and calls `evaluateInversion`. Called by
   * the "Test Auto-Invert" button in the panel Config tab.
   */
  runSelfTest(n = null) {
    const t = n || CONFIG.INVERT_AFTER_CONSECUTIVE_LOSSES || 1;
    const before = { streak: state.stats.currentStreak,
                     isInverted: state.inversion.isInverted };
    // Prime a loss streak
    for (let i = 0; i < t; i++) {
      state.stats.currentStreak = Math.min(-1, state.stats.currentStreak - 1);
    }
    this.evaluateInversion("__SELF_TEST__");
    const after = { streak: state.stats.currentStreak,
                    isInverted: state.inversion.isInverted };
    return { before, after,
             fired: after.isInverted && !before.isInverted,
             threshold: t };
  }
}

export const smartInvert = new SmartInvertEngine();
export default smartInvert;
