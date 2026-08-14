/**
 * Iter 103 — Network Latency Poller
 *
 * Polls the backend's TCP-RTT probe endpoint every 5s and pushes results
 * into the Live-tab Network Latency widget. Runs continuously once the
 * bot is initialised — cheap (one small GET every 5s).
 *
 * Failure handling:
 *   - Backoff to 15s after 3 consecutive fetch failures, back down to 5s
 *     once the endpoint recovers. Prevents log spam when the backend is
 *     offline or rebooting.
 *
 * The widget rendering itself lives in `ui/panel.js` (`updateNetworkLatency`).
 */

import { get } from '../utils/api.js';
import { log, warn } from '../core/logger.js';

const POLL_MS_HEALTHY = 5_000;
const POLL_MS_BACKOFF = 15_000;
const FAIL_THRESHOLD = 3;


class NetworkLatencyPoller {
  constructor() {
    this.timer = null;
    this.consecutiveFailures = 0;
    this.pollMs = POLL_MS_HEALTHY;
    this.started = false;
    this.lastStats = null;
    this._render = null;
  }

  /**
   * Start the poller. `renderFn` is the panel's updateNetworkLatency
   * function — passed in so the poller stays decoupled from the UI module.
   */
  start(renderFn) {
    if (this.started) return;
    this.started = true;
    this._render = renderFn || null;
    // Immediate probe on start so the widget populates fast
    this._tick();
    this.timer = setInterval(() => this._tick(), this.pollMs);
  }

  stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.started = false;
  }

  async _tick() {
    try {
      const resp = await get('/latency/network');
      if (!resp || resp.success === false) {
        this._onFailure(new Error(resp && resp.error ? resp.error : 'no response'));
        return;
      }
      this.lastStats = resp.stats || null;
      this.consecutiveFailures = 0;
      // Recover polling cadence if we were in backoff
      if (this.pollMs !== POLL_MS_HEALTHY) this._reschedule(POLL_MS_HEALTHY);
      if (this._render) {
        try { this._render(this.lastStats); } catch (e) { warn(`[netlat] render threw: ${e.message}`); }
      }
    } catch (e) {
      this._onFailure(e);
    }
  }

  _onFailure(err) {
    this.consecutiveFailures++;
    if (this.consecutiveFailures === FAIL_THRESHOLD) {
      warn(`[netlat] ${FAIL_THRESHOLD} consecutive failures — backing off to ${POLL_MS_BACKOFF}ms. Last error: ${err && err.message ? err.message : err}`);
      this._reschedule(POLL_MS_BACKOFF);
    }
  }

  _reschedule(newMs) {
    this.pollMs = newMs;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.timer = setInterval(() => this._tick(), this.pollMs);
    log(`[netlat] poll cadence -> ${newMs}ms`);
  }

  getLast() { return this.lastStats; }
}

export const networkLatencyPoller = new NetworkLatencyPoller();
export default networkLatencyPoller;
