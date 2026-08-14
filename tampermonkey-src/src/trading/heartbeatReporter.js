/**
 * Heartbeat Reporter — Iter 106 (Feb 2026)
 *
 * Pushes a lightweight status ping to `/api/tampermonkey/heartbeat` every
 * 15 seconds so the Mobile Auto-Trader dashboard can show REAL connection
 * health (not just a stale "disconnected" pill).
 *
 * Payload:
 *   {
 *     script_version:    GM_info.script.version || "unknown",
 *     ssid_bridge_active: bool,     // has ssidBridge captured a live SSID?
 *     current_asset:     "EURUSD_OTC",
 *     current_timeframe: "1m",
 *     chart_type:        "candles",
 *     user_agent:        navigator.userAgent (short),
 *     page_url:          location.host,
 *   }
 *
 * Backoff on failure:
 *   - 3 failures in a row → back off to 60s
 *   - Recovers to 15s on next success
 *
 * Non-blocking: uses the same GM_xmlhttpRequest transport as other API calls.
 */

import { log, info, warn } from '../core/logger.js';
import { post } from '../utils/api.js';
import { state } from '../core/state.js';
import { ssidBridge } from './ssidBridge.js';
import { getCurrentAsset } from '../utils/dom.js';

const HEALTHY_MS = 15_000;
const BACKOFF_MS = 60_000;
const FAIL_THRESHOLD = 3;


function _shortUA() {
  try {
    const ua = String(navigator.userAgent || '');
    return ua.length > 120 ? ua.slice(0, 120) : ua;
  } catch (_e) { return ''; }
}

function _scriptVersion() {
  try {
    // eslint-disable-next-line no-undef
    if (typeof GM_info !== 'undefined' && GM_info?.script?.version) {
      return String(GM_info.script.version);
    }
  } catch (_e) { /* fall through */ }
  return 'unknown';
}


class HeartbeatReporter {
  constructor() {
    this.timer = null;
    this.failures = 0;
    this.pollMs = HEALTHY_MS;
    this.started = false;
    this.lastAckAt = 0;
    this.lastPayload = null;
  }

  start() {
    if (this.started) return;
    this.started = true;
    // Fire immediately then on cadence
    this._tick();
    this.timer = setInterval(() => this._tick(), this.pollMs);
    info('[heartbeat] reporter started — pinging /api/tampermonkey/heartbeat every ' + this.pollMs + 'ms');
  }

  stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.started = false;
  }

  getLastAckAt() { return this.lastAckAt; }
  getLastPayload() { return this.lastPayload; }

  async _tick() {
    // Build fresh payload every tick — reflects LIVE state
    let currentAsset = '';
    try { currentAsset = getCurrentAsset() || ''; } catch (_e) { /* silent */ }

    const payload = {
      script_version: _scriptVersion(),
      ssid_bridge_active: !!(ssidBridge && (ssidBridge.hasValidSSID?.() || ssidBridge.ready === true)),
      current_asset: currentAsset,
      current_timeframe: (state && state.selectedTimeframe) || '',
      chart_type: (state && state.chartType) || '',
      user_agent: _shortUA(),
      page_url: (typeof location !== 'undefined' ? location.host : ''),
      // Extra breadcrumbs for debug UIs
      panel_visible: !!document.getElementById('__epb__host'),
      toggle_states: {
        scan:   !!(state && state.scanEnabled),
        auto:   !!(state && state.autoEnabled),
        sns:    !!(state && state.snsEnabled),
        cycle:  !!(state && state.cycleEnabled),
        app:    !!(state && state.appEnabled),
        invert: !!(state && state.invertEnabled),
      },
    };
    this.lastPayload = payload;

    try {
      const resp = await post('/tampermonkey/heartbeat', payload);
      if (resp && resp.success !== false) {
        this.lastAckAt = Date.now();
        this.failures = 0;
        if (this.pollMs !== HEALTHY_MS) this._reschedule(HEALTHY_MS);
      } else {
        this._onFailure(new Error((resp && resp.message) || 'unknown'));
      }
    } catch (e) {
      this._onFailure(e);
    }
  }

  _onFailure(err) {
    this.failures++;
    if (this.failures === FAIL_THRESHOLD) {
      warn(`[heartbeat] ${FAIL_THRESHOLD} consecutive failures — backing off to ${BACKOFF_MS}ms. Last error: ${err && err.message ? err.message : err}`);
      this._reschedule(BACKOFF_MS);
    }
  }

  _reschedule(newMs) {
    this.pollMs = newMs;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.timer = setInterval(() => this._tick(), this.pollMs);
    log(`[heartbeat] cadence -> ${newMs}ms`);
  }
}


export const heartbeatReporter = new HeartbeatReporter();
export default heartbeatReporter;
