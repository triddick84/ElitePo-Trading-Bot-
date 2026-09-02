/**
 * Tampermonkey Settings Poller — Iter 118
 *
 * Fetches `/api/tampermonkey/stake-tiers` every 30s and drops the config
 * into `state._stakeTiersConfig` so the trade executor can:
 *   - Look up the correct trade amount per confidence bucket
 *   - Auto-write that amount into PO's input box (when `auto_set` is on)
 *
 * Backoff on 3 consecutive failures → 120s. Recovers on next success.
 */

import { get } from '../utils/api.js';
import { log, warn } from '../core/logger.js';
import { state } from '../core/state.js';

const HEALTHY_MS = 30_000;
const BACKOFF_MS = 120_000;
const FAIL_THRESHOLD = 3;


class TmSettingsPoller {
  constructor() {
    this.timer = null;
    this.failures = 0;
    this.pollMs = HEALTHY_MS;
    this.started = false;
  }

  start() {
    if (this.started) return;
    this.started = true;
    this._tick();
    this.timer = setInterval(() => this._tick(), this.pollMs);
    log('[tmSettings] poller started — /api/tampermonkey/stake-tiers every ' + this.pollMs + 'ms');
  }

  stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.started = false;
  }

  async _tick() {
    try {
      const resp = await get('/tampermonkey/stake-tiers');
      if (!resp || resp.success === false) {
        this._onFailure(new Error('stake-tiers success=false'));
        return;
      }
      state._stakeTiersConfig = {
        enabled: !!resp.enabled,
        auto_set: resp.auto_set !== false,
        fallback: Number(resp.fallback) || 1.0,
        tiers: Array.isArray(resp.tiers) ? resp.tiers : [],
      };
      this.failures = 0;
      if (this.pollMs !== HEALTHY_MS) this._reschedule(HEALTHY_MS);
    } catch (e) {
      this._onFailure(e);
    }
  }

  _onFailure(err) {
    this.failures++;
    if (this.failures === FAIL_THRESHOLD) {
      warn(`[tmSettings] ${FAIL_THRESHOLD} failures — backing off to ${BACKOFF_MS}ms. Last: ${err && err.message ? err.message : err}`);
      this._reschedule(BACKOFF_MS);
    }
  }

  _reschedule(newMs) {
    this.pollMs = newMs;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.timer = setInterval(() => this._tick(), this.pollMs);
  }
}


export const tmSettingsPoller = new TmSettingsPoller();
export default tmSettingsPoller;
