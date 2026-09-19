/**
 * Iter 150 — Risk Guard → TM Bridge
 * ---------------------------------------------------------------------------
 * When the user activates "Start Session" (master toggle → ON) in the TM
 * panel, we ask the backend for the active Risk Guard config and push
 * the trade amount + confidence-tiered stakes into the executor.
 *
 * Result: the same rules the user configured in the web app's Risk Guard
 * page (start amount, per-trade amount, tiered stakes) apply to trades
 * placed by the TM script — no manual re-configuration needed.
 */

import { get } from '../utils/api.js';
import { log, info, warn, success, error } from '../core/logger.js';
import { state, saveState } from '../core/state.js';
import { tradeExecutor } from '../trading/executor.js';

class RiskGuardBridge {
  constructor() {
    this.lastSync = null;
    this.lastConfig = null;
  }

  /**
   * Fetch the current Risk Guard config for the given user and apply the
   * relevant fields to the TM script's trading engine.
   *
   * @param {string} userId — backend user id (defaults to "default")
   * @returns {Promise<{ok: boolean, applied?: object, error?: string}>}
   */
  async syncNow(userId = 'default') {
    try {
      const cfg = await get('/riskguard/tampermonkey/config', { user_id: userId });
      if (!cfg || cfg.ok === false) {
        warn(`[riskguard] sync failed: ${cfg?.error || 'no config'}`);
        return { ok: false, error: cfg?.error || 'no config' };
      }
      this.lastConfig = cfg;
      this.lastSync = Date.now();

      // 1) Apply the per-trade amount to the executor's base amount so
      //    every subsequent fire uses it as the starting stake.
      if (typeof cfg.per_trade_amount === 'number' && cfg.per_trade_amount > 0) {
        tradeExecutor.setBaseAmount(cfg.per_trade_amount);
      }

      // 2) Apply confidence-tiered stakes. `state._stakeTiersConfig` is
      //    read by executor.execute() when it computes the per-signal
      //    stake, so this line makes tiered sizing effective immediately.
      if (Array.isArray(cfg.confidence_tiers) && cfg.confidence_tiers.length) {
        // Convert backend shape → TM shape:
        //   { min_confidence, multiplier } → { min_conf, amount }
        // Amount = per_trade × multiplier so the user's "confidence gets
        // more stake" intent is preserved.
        const base = Number(cfg.per_trade_amount) || 1;
        const tiers = cfg.confidence_tiers
          .filter((t) => typeof t.min_confidence === 'number')
          .sort((a, b) => a.min_confidence - b.min_confidence)
          .map((t) => ({
            min_conf: t.min_confidence,
            amount: Number((base * (t.multiplier || 1)).toFixed(2)),
          }));
        state._stakeTiersConfig = {
          enabled: true,
          fallback: base,
          auto_set: true,
          tiers,
        };
        saveState();
      }

      // 3) Guard-rails — max daily loss + stop-after-losses are honoured
      //    by the existing auto-invert / kill-switch code paths via
      //    state.riskGuard.*
      state.riskGuard = state.riskGuard || {};
      if (typeof cfg.max_daily_loss === 'number') {
        state.riskGuard.maxDailyLoss = cfg.max_daily_loss;
      }
      if (typeof cfg.stop_after_losses === 'number') {
        state.riskGuard.stopAfterLosses = cfg.stop_after_losses;
      }
      saveState();

      const applied = {
        per_trade_amount: cfg.per_trade_amount,
        tiers_count: (cfg.confidence_tiers || []).length,
        max_daily_loss: cfg.max_daily_loss,
        stop_after_losses: cfg.stop_after_losses,
        session_active: cfg.session_active,
      };
      success(`[riskguard] applied — $${cfg.per_trade_amount}/trade, `
              + `${applied.tiers_count} tiers, max loss $${cfg.max_daily_loss}`);
      return { ok: true, applied };
    } catch (e) {
      warn(`[riskguard] sync threw: ${e.message}`);
      return { ok: false, error: e.message };
    }
  }

  getLastSync() {
    return {
      last_sync_ms: this.lastSync,
      last_config: this.lastConfig,
    };
  }
}

export const riskGuardBridge = new RiskGuardBridge();

// Expose on window for DevTools quick-check
try {
  window.__aiEliteRiskGuardSync = (userId) => riskGuardBridge.syncNow(userId);
  window.__aiEliteRiskGuardStatus = () => riskGuardBridge.getLastSync();
} catch (_e) { /* ignore */ }

export default riskGuardBridge;
