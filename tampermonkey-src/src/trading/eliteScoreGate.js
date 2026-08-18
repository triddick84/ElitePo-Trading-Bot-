/**
 * Elite Score Gate — Iter 109 (Feb 2026)
 *
 * Fetches the Elite Composite Score for a given asset on-demand and decides
 * whether a NEW trade should be allowed to fire.
 *
 * Usage:
 *   await eliteScoreGate.check(asset)  →  { allow, score, direction, reason }
 *
 * If gate is OFF (`threshold === 0`) → always returns { allow: true }.
 * Otherwise fetches /api/screener/score?asset=X and compares elite_score.
 *
 * A local 30-second TTL cache prevents hammering the endpoint when signals
 * come in bursts. Cache is keyed per-asset.
 */

import api from '../utils/api.js';
import { log, info, warn } from '../core/logger.js';


class EliteScoreGate {
  constructor() {
    this.threshold = 0;             // 0 = disabled. 1-100 = min score to allow.
    this.enforceDirection = true;   // if true, signal.direction must match Elite direction
    this._cache = new Map();        // asset → { ts, score, direction, reason }
    this._cacheTtlMs = 30_000;
    this._lastEvent = null;
    this._subscribers = [];
  }

  setThreshold(score) {
    const n = Math.max(0, Math.min(100, parseInt(score, 10) || 0));
    if (n === this.threshold) return;
    this.threshold = n;
    info(`[eliteGate] threshold → ${n === 0 ? 'OFF' : n}`);
    this._notify();
  }

  getThreshold() { return this.threshold; }

  setEnforceDirection(v) {
    this.enforceDirection = !!v;
    this._notify();
  }

  register(renderFn) {
    if (typeof renderFn === 'function') this._subscribers.push(renderFn);
    try { renderFn(this._lastEvent); } catch (_e) { /* silent */ }
  }

  _notify() {
    for (const s of this._subscribers) {
      try { s(this._lastEvent); } catch (_e) { /* silent */ }
    }
  }

  /**
   * Fetch (or read cached) Elite Score for `asset`. Returns:
   *   { score, direction, sub_scores, reason, cached }
   * Score is 0 when the endpoint failed or returned insufficient_data.
   */
  async fetchScore(asset) {
    if (!asset) return { score: 0, direction: 'NEUTRAL', reason: 'no_asset' };
    const now = Date.now();
    const cached = this._cache.get(asset);
    if (cached && (now - cached.ts) < this._cacheTtlMs) {
      return { ...cached, cached: true };
    }
    try {
      const res = await api.get(`/screener/score?asset=${encodeURIComponent(asset)}`);
      const r = (res && res.result) || {};
      const score = Number(r.elite_score || 0);
      const direction = String(r.direction || 'NEUTRAL').toUpperCase();
      const sub_scores = r.sub_scores || {};
      const reason = r.reason || '';
      const entry = { ts: now, score, direction, sub_scores, reason };
      this._cache.set(asset, entry);
      return { ...entry, cached: false };
    } catch (e) {
      warn(`[eliteGate] fetch failed for ${asset}: ${e.message}`);
      return { score: 0, direction: 'NEUTRAL', reason: 'fetch_error' };
    }
  }

  /**
   * Check whether a signal for `asset` (and optional `direction`) should
   * fire. Returns { allow, score, direction, reason }.
   *
   *  - gate disabled (threshold=0) → allow always
   *  - score < threshold → block
   *  - enforceDirection=true and CALL/PUT mismatch → block
   */
  async check(asset, signalDirection = null) {
    if (this.threshold === 0) {
      this._lastEvent = { asset, allow: true, score: null, reason: 'gate_off' };
      this._notify();
      return this._lastEvent;
    }
    const { score, direction, reason } = await this.fetchScore(asset);
    let allow = true;
    let blockReason = '';
    if (score < this.threshold) {
      allow = false;
      blockReason = `score ${score.toFixed(1)} < ${this.threshold}`;
    } else if (this.enforceDirection && signalDirection && direction !== 'NEUTRAL') {
      const sd = String(signalDirection || '').toUpperCase();
      if (sd && direction !== sd) {
        allow = false;
        blockReason = `elite dir ${direction} ≠ signal ${sd}`;
      }
    }
    this._lastEvent = {
      asset, allow, score, direction,
      threshold: this.threshold,
      reason: allow ? (reason || 'ok') : blockReason,
    };
    if (!allow) warn(`[eliteGate] ⛔ ABORT ${asset} — ${blockReason}`);
    else info(`[eliteGate] ✓ ALLOW ${asset} — Elite ${score.toFixed(1)} · ${direction}`);
    this._notify();
    return this._lastEvent;
  }

  getLastEvent() { return this._lastEvent; }

  clearCache() { this._cache.clear(); }
}


export const eliteScoreGate = new EliteScoreGate();
export default eliteScoreGate;
