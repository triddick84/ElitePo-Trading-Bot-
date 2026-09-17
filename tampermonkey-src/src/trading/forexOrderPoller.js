/**
 * Iter 145 — Forex Order Poller
 * ---------------------------------------------------------------------------
 * Long-polls /api/forex/orders/pending and hands each order to mt5Adapter.
 * Reports fill/rejection back to the backend so the position row transitions
 * PENDING → OPEN or REJECTED.
 *
 * Off by default: only starts when the user flips the "Forex" toggle in the
 * TM panel. Cadence is deliberately conservative (5s) since Forex signals
 * are far less frequent than binary options.
 */

import { get, post } from '../utils/api.js';
import { log, warn, info, error } from '../core/logger.js';
import { mt5Adapter } from './mt5Adapter.js';
import { stealthMode } from '../core/stealthMode.js';

const DEFAULT_INTERVAL_MS = 5000;

class ForexOrderPoller {
  constructor() {
    this.timer = null;
    this.inFlight = false;
    this.intervalMs = DEFAULT_INTERVAL_MS;
    this.stats = { picked: 0, placed: 0, rejected: 0, errors: 0 };
  }

  start(intervalMs = DEFAULT_INTERVAL_MS) {
    if (this.timer) return;
    this.intervalMs = intervalMs;
    log(`[fx-poll] starting @ ${intervalMs}ms`);
    this.tick();  // fire once immediately
    this.timer = setInterval(() => this.tick(), intervalMs);
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
      log('[fx-poll] stopped');
    }
  }

  isRunning() { return !!this.timer; }

  getStats() { return { ...this.stats, running: this.isRunning() }; }

  async tick() {
    if (this.inFlight) return;
    if (stealthMode.isActive?.() && stealthMode.shouldThrottle?.('fx-poll')) return;
    this.inFlight = true;
    try {
      const resp = await get('/forex/orders/pending?limit=3');
      if (!resp || !Array.isArray(resp.orders) || resp.orders.length === 0) return;

      for (const order of resp.orders) {
        await this._handleOne(order);
      }
    } catch (e) {
      this.stats.errors++;
      warn(`[fx-poll] tick failed: ${e.message}`);
    } finally {
      this.inFlight = false;
    }
  }

  async _handleOne(order) {
    if (!order || !order.position_id) return;

    // 1. Claim it so a second TM instance skips it
    let claim;
    try {
      claim = await post(`/forex/orders/${order.position_id}/mark-picked`, {});
    } catch (e) {
      this.stats.errors++;
      warn(`[fx-poll] claim failed for ${order.position_id}: ${e.message}`);
      return;
    }
    if (!claim || !claim.claimed) return;   // someone else already picked it
    this.stats.picked++;

    // 2. Ask the MT5 adapter to place the trade
    const placeArgs = {
      symbol: order.symbol,
      side: order.side,
      lots: order.lots,
      sl: order.stop_loss ?? null,
      tp: order.take_profit ?? null,
    };
    info(`[fx-poll] executing ${placeArgs.side} ${placeArgs.symbol} lots=${placeArgs.lots}`);

    let result;
    try {
      result = await mt5Adapter.placeOrder(placeArgs);
    } catch (e) {
      result = { ok: false, reason: `adapter_error:${e.message}` };
    }

    // 3. Report back
    if (result.ok) {
      this.stats.placed++;
      try {
        await post(`/forex/orders/${order.position_id}/mark-filled`, {
          fill_price: result.fill_price ?? null,
          fill_lots: result.fill_lots ?? placeArgs.lots,
          dom_matches: result.matches ?? {},
        });
      } catch (e) {
        warn(`[fx-poll] mark-filled failed: ${e.message}`);
      }
    } else {
      this.stats.rejected++;
      error(`[fx-poll] REJECTED ${placeArgs.symbol}: ${result.reason}`);
      try {
        await post(`/forex/orders/${order.position_id}/mark-rejected`, {
          error: result.reason,
          dom_matches: result.matches ?? {},
        });
      } catch (e) {
        warn(`[fx-poll] mark-rejected failed: ${e.message}`);
      }
    }
  }
}

export const forexOrderPoller = new ForexOrderPoller();

try {
  window.__aiEliteForexPoll = () => forexOrderPoller.getStats();
} catch (_e) { /* ignore */ }

export default forexOrderPoller;
