/**
 * Latency Abstain Gate — Iter 108 (Feb 2026)
 *
 * Central gate that decides whether NEW trades should be allowed based on
 * live network latency.
 *
 * Uses the last snapshot from `networkLatencyPoller` (Iter 103) and compares
 * its p99 against a user-configurable threshold.
 *
 * Contract:
 *   isPaused()          → bool. If true, trade dispatchers MUST abort.
 *   getState()          → 'healthy' | 'paused' | 'off'
 *   getExtra()          → short human-readable status ("p99 = 420ms · limit 300")
 *   setThreshold(ms)    → 0 disables (off). Otherwise trades pause when p99>threshold.
 *   register(renderFn)  → subscribe to state changes; called on every transition
 *                         (not on every check).
 */

import { networkLatencyPoller } from './networkLatencyPoller.js';
import { log, info, warn } from '../core/logger.js';


class LatencyAbstainGate {
  constructor() {
    this.threshold = 300;   // ms. 0 = disabled.
    this._lastState = 'healthy';
    this._lastExtra = '';
    this._subscribers = [];
  }

  setThreshold(ms) {
    const n = Math.max(0, Math.min(5000, parseInt(ms, 10) || 0));
    if (n === this.threshold) return;
    this.threshold = n;
    // Re-evaluate state immediately after threshold change
    this._evaluate();
    info(`[latAbstain] threshold → ${n === 0 ? 'OFF' : n + 'ms'}`);
  }

  getThreshold() { return this.threshold; }

  register(renderFn) {
    if (typeof renderFn === 'function') this._subscribers.push(renderFn);
    // Fire once so the UI reflects the current state
    try { renderFn(this._lastState, this._lastExtra); } catch (_e) { /* silent */ }
  }

  isPaused() { return this._evaluate() === 'paused'; }

  getState() { return this._lastState; }
  getExtra() { return this._lastExtra; }

  /**
   * Return current gate decision AND update `_lastState` + notify subs on
   * transitions. Called from both dispatchers (before fire) and a 4s tick
   * inside index.js so the UI keeps refreshing.
   */
  _evaluate() {
    let newState = 'healthy';
    let extra = '';

    if (this.threshold === 0) {
      newState = 'off';
      extra = '';
    } else {
      let p99 = null;
      try {
        const stats = networkLatencyPoller.getLast();
        // stats can be either { pocketoption: {...} } or a single row
        const row = (stats && stats.pocketoption) ? stats.pocketoption
                    : (stats && typeof stats === 'object' && 'p99_ms' in stats) ? stats
                    : null;
        if (row && row.sample_count > 3 && row.p99_ms != null && isFinite(row.p99_ms)) {
          p99 = Number(row.p99_ms);
        }
      } catch (_e) { /* silent */ }

      if (p99 == null) {
        newState = 'healthy';
        extra = 'no samples yet';
      } else if (p99 > this.threshold) {
        newState = 'paused';
        extra = `p99 = ${Math.round(p99)}ms · limit ${this.threshold}`;
      } else {
        newState = 'healthy';
        extra = `p99 = ${Math.round(p99)}ms`;
      }
    }

    // Notify only on state transition — keeps logs clean
    if (newState !== this._lastState) {
      if (newState === 'paused') {
        warn(`[latAbstain] ⛔ PAUSING new trades — ${extra}`);
      } else if (this._lastState === 'paused') {
        info(`[latAbstain] ✓ resuming trades — ${extra}`);
      }
    }
    this._lastState = newState;
    this._lastExtra = extra;

    // Fire subscribers on EVERY evaluation so the UI ticker stays fresh
    for (const s of this._subscribers) {
      try { s(newState, extra); } catch (_e) { /* silent */ }
    }
    return newState;
  }
}


export const latencyAbstainGate = new LatencyAbstainGate();
export default latencyAbstainGate;
