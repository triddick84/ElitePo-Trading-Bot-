/**
 * Iter 138 — Stealth Mode
 *
 * Reduces the userscript's observable footprint on the PocketOption tab so
 * their WAF/DDoS layer is less likely to flag the session. When enabled:
 *
 *   1. Every background poller (heartbeat, latency probe, tmSettings) runs
 *      at 3× its default cadence.
 *   2. `waitForElement` retries are scheduled via `requestIdleCallback`
 *      instead of `setTimeout`, so DOM scans don't compete with PO's own
 *      renders.
 *   3. Background probes are **completely skipped** while auto-trade is OFF
 *      (see `shouldSkipBackgroundProbe()` — pollers must consult it).
 *   4. Persisted across reloads via `GM_setValue` (key: `epb_stealth_mode`).
 *
 * Pollers integrate by:
 *   - calling `getMultiplier()` when computing their cadence
 *   - subscribing via `onChange(cb)` to reschedule immediately when the user
 *     flips the toggle
 */

import { log } from './logger.js';

const STORAGE_KEY = 'epb_stealth_mode';
const DEFAULT_MULTIPLIER = 3;

class StealthMode {
  constructor() {
    this._active = false;
    this._multiplier = DEFAULT_MULTIPLIER;
    this._subscribers = new Set();
    this._loaded = false;
  }

  /**
   * Read persisted state. Safe to call from any module during boot; if
   * called before GM is available (very early document-start), no-ops.
   */
  init() {
    if (this._loaded) return;
    try {
      if (typeof GM_getValue === 'function') {
        this._active = !!GM_getValue(STORAGE_KEY, false);
      }
    } catch (_e) { /* ignore */ }
    this._loaded = true;
    log(`[stealth] init — active=${this._active}, multiplier=${this._multiplier}x`);
  }

  isActive() { return !!this._active; }

  /**
   * Cadence multiplier for pollers. Returns 1 when stealth is OFF, so
   * pollers can unconditionally multiply their default by this number.
   */
  getMultiplier() { return this._active ? this._multiplier : 1; }

  /**
   * True when the poller SHOULD skip this tick. Callers pass their own
   * `isUserActive` boolean (derived from the trading toggles they care
   * about) — we keep this module dependency-free.
   *
   *   - Stealth OFF → never skip
   *   - Stealth ON + user idle → skip (saves ALL background traffic)
   *   - Stealth ON + user active → don't skip (trading needs fresh signals)
   */
  shouldSkipBackgroundProbe(isUserActive) {
    if (!this._active) return false;
    return !isUserActive;
  }

  /**
   * Preferred replacement for `setTimeout(cb, ms)` inside `waitForElement`-
   * style DOM scans. When stealth is ON, retries piggyback on
   * `requestIdleCallback` so we don't compete with PO renders.
   */
  scheduleDomRetry(cb, ms) {
    if (!this._active || typeof window === 'undefined' || typeof window.requestIdleCallback !== 'function') {
      return setTimeout(cb, ms);
    }
    // Cap the deadline so we never block trade-time scans excessively.
    const timeout = Math.max(ms, 250);
    return window.requestIdleCallback(() => cb(), { timeout });
  }

  /**
   * Toggle stealth on/off. Persists and notifies subscribers so pollers can
   * reschedule immediately.
   */
  setActive(active) {
    const next = !!active;
    if (next === this._active) return this._active;
    this._active = next;
    try {
      if (typeof GM_setValue === 'function') {
        GM_setValue(STORAGE_KEY, this._active);
      }
    } catch (_e) { /* ignore */ }
    log(`[stealth] ${this._active ? 'ENABLED' : 'DISABLED'} (multiplier now ${this.getMultiplier()}x)`);
    this._notify();
    return this._active;
  }

  toggle() { return this.setActive(!this._active); }

  /**
   * Subscribe to changes. Callback is invoked with `(active, multiplier)`
   * whenever `setActive`/`toggle` flips the state.
   */
  onChange(cb) {
    if (typeof cb === 'function') {
      this._subscribers.add(cb);
      return () => this._subscribers.delete(cb);
    }
    return () => {};
  }

  _notify() {
    const active = this._active;
    const mult = this.getMultiplier();
    for (const cb of this._subscribers) {
      try { cb(active, mult); } catch (_e) { /* subscriber must not break others */ }
    }
  }
}

export const stealthMode = new StealthMode();
export default stealthMode;
