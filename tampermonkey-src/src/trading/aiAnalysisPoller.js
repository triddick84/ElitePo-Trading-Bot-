/**
 * AI Analysis Poller — Iter 107 (Feb 2026)
 *
 * Feeds the AI tab in the panel with a merged snapshot from four backend
 * sources on a 3-second cadence:
 *
 *   1. GET /signals/latest             → signal direction/confidence + indicators
 *   2. GET /signals/preview            → strategy votes (top 3 by confidence)
 *   3. GET /microstructure/models      → Kyle λ + Glosten-Milgrom α (Iter 105)
 *   4. GET /trades/recent-outcomes?limit=5 → recent trade log for the "AI · trades" card
 *
 * All 4 fetches happen in parallel via Promise.allSettled so a single flake
 * doesn't blank the whole tab. Missing sources render as "—".
 *
 * Backoff:
 *   - 3 consecutive full-fetch failures → back off to 15s.
 *   - Recovers to 3s on next successful merged payload.
 */

import { get } from '../utils/api.js';
import { log, warn } from '../core/logger.js';
import { state } from '../core/state.js';

const HEALTHY_MS = 3_000;
const BACKOFF_MS = 15_000;
const FAIL_THRESHOLD = 3;


class AIAnalysisPoller {
  constructor() {
    this.timer = null;
    this.failures = 0;
    this.pollMs = HEALTHY_MS;
    this.started = false;
    this._render = null;
    this.lastPayload = null;
  }

  start(renderFn) {
    if (this.started) return;
    this.started = true;
    this._render = renderFn || null;
    this._tick();
    this.timer = setInterval(() => this._tick(), this.pollMs);
  }

  stop() {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.started = false;
  }

  getLast() { return this.lastPayload; }

  async _tick() {
    // Iter 125 — Bug 1 fix: /microstructure/models now REQUIRES an asset param.
    // When state.currentAsset is empty (script just loaded, no chart selected),
    // fall back to a sensible default so the tab isn't blank.
    const asset = (state && state.currentAsset) || 'EURUSD_OTC';
    const params = new URLSearchParams();
    if (asset) params.set('asset', asset);

    // Fire 4 requests concurrently — each independent
    const [sigR, prevR, msR, recR] = await Promise.allSettled([
      get('/signals/latest' + (asset ? `?asset=${encodeURIComponent(asset)}` : '')),
      get('/signals/preview' + (asset ? `?asset=${encodeURIComponent(asset)}` : '')),
      get(`/microstructure/models?asset=${encodeURIComponent(asset)}`),
      get('/trades/recent-outcomes?limit=5'),
    ]);

    // Detect total failure (all rejected)
    const allFailed = [sigR, prevR, msR, recR].every(r => r.status !== 'fulfilled');
    if (allFailed) {
      this._onFailure(new Error('all 4 AI-tab sources failed'));
      return;
    }
    this.failures = 0;
    if (this.pollMs !== HEALTHY_MS) this._reschedule(HEALTHY_MS);

    // Merge into a single payload the panel understands
    const payload = { signal: {}, votes: [], indicators: {}, microstructure: {}, recent_trades: [] };

    if (sigR.status === 'fulfilled' && sigR.value) {
      const s = sigR.value.signal || sigR.value.data || sigR.value;
      if (s && typeof s === 'object') {
        // Iter 114 — normalise confidence (backend sends 0.78 fraction)
        let sconf = Number(s.confidence ?? 0);
        if (!Number.isFinite(sconf)) sconf = 0;
        if (sconf > 0 && sconf <= 1) sconf *= 100;
        payload.signal = {
          direction: s.direction,
          confidence: sconf,
          symbol: s.symbol || s.asset,
          strategy: s.strategy,
        };
        if (s.indicators && typeof s.indicators === 'object') {
          Object.assign(payload.indicators, s.indicators);
        }
      }
    }

    if (prevR.status === 'fulfilled' && prevR.value) {
      const p = prevR.value;
      // /signals/preview may return { votes: [...] } OR { strategies: [...] }
      const raw = Array.isArray(p.votes) ? p.votes
                 : Array.isArray(p.strategies) ? p.strategies
                 : Array.isArray(p.data) ? p.data : [];
      payload.votes = raw
        .map((v) => {
          // Iter 114 — normalise confidence to 0-100 for the panel.
          // Backend sends 0.78 (fraction); panel renders `Math.round(conf)%`
          // and would show "1%". Multiply so 0.78 → 78.
          let conf = Number(v.confidence ?? v.conf ?? 0);
          if (!Number.isFinite(conf)) conf = 0;
          if (conf > 0 && conf <= 1) conf *= 100;
          return {
            name: v.name || v.strategy || v.strategy_name || 'unknown',
            direction: (v.direction || v.signal || '').toString().toUpperCase(),
            confidence: conf,
          };
        })
        .filter((v) => v.direction === 'CALL' || v.direction === 'PUT')
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 3);
    }

    if (msR.status === 'fulfilled' && msR.value) {
      const m = msR.value;
      const k = m.kyle_result?.kyle || m.kyle || {};
      const g = m.gm_result?.gm || m.gm || {};
      payload.microstructure = {
        kyle_lambda: k.lambda,
        kyle_illiq_bps: k.illiquidity_bps,
        gm_adverse_selection_pct: g.adverse_selection_pct,
        gm_alpha_informed: g.alpha_informed,
      };
    }

    if (recR.status === 'fulfilled' && recR.value) {
      const r = recR.value;
      const rows = Array.isArray(r.outcomes) ? r.outcomes
                   : Array.isArray(r.trades) ? r.trades
                   : Array.isArray(r.data) ? r.data : [];
      payload.recent_trades = rows.slice(0, 5).map((t) => ({
        time: t.time || t.timestamp || t.at,
        asset: t.asset || t.symbol || '',
        direction: (t.direction || '').toString().toUpperCase(),
        result: (t.result || t.outcome || '').toString().toUpperCase(),
      }));
    }

    this.lastPayload = payload;
    if (this._render) {
      try { this._render(payload); } catch (e) { warn(`[aiPoller] render threw: ${e.message}`); }
    }
  }

  _onFailure(err) {
    this.failures++;
    if (this.failures === FAIL_THRESHOLD) {
      warn(`[aiPoller] ${FAIL_THRESHOLD} consecutive failures — backing off to ${BACKOFF_MS}ms. Last: ${err && err.message ? err.message : err}`);
      this._reschedule(BACKOFF_MS);
    }
  }

  _reschedule(newMs) {
    this.pollMs = newMs;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    this.timer = setInterval(() => this._tick(), this.pollMs);
    log(`[aiPoller] cadence -> ${newMs}ms`);
  }
}


export const aiAnalysisPoller = new AIAnalysisPoller();
export default aiAnalysisPoller;
