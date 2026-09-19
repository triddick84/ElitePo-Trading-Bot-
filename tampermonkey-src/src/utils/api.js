/**
 * HTTP Request utilities
 * Wrapper around GM_xmlhttpRequest for API calls
 */

import { CONFIG } from '../core/config.js';
import { log, error as logError } from '../core/logger.js';

/**
 * Make an HTTP request using GM_xmlhttpRequest
 * @param {Object} options - Request options
 * @returns {Promise<Object>} Response data
 */
export function request(options) {
  return new Promise((resolve, reject) => {
    const {
      method = 'GET',
      url,
      headers = {},
      data = null,
      timeout = 30000,
    } = options;
    
    GM_xmlhttpRequest({
      method,
      url,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...headers,
      },
      data: data ? JSON.stringify(data) : null,
      timeout,
      onload: (response) => {
        try {
          if (response.status >= 200 && response.status < 300) {
            const result = JSON.parse(response.responseText);
            resolve(result);
          } else {
            reject(new Error(`HTTP ${response.status}: ${response.statusText}`));
          }
        } catch (e) {
          reject(new Error(`Failed to parse response: ${e.message}`));
        }
      },
      onerror: (error) => {
        reject(new Error(`Network error: ${error.message || 'Unknown error'}`));
      },
      ontimeout: () => {
        reject(new Error('Request timeout'));
      },
    });
  });
}

/**
 * GET request
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Query parameters
 * @returns {Promise<Object>} Response data
 */
export async function get(endpoint, params = {}) {
  const url = new URL(`${CONFIG.API_URL}${endpoint}`);
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.append(key, value);
  });
  
  return request({ method: 'GET', url: url.toString() });
}

/**
 * POST request
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body
 * @returns {Promise<Object>} Response data
 */
export async function post(endpoint, data = {}) {
  return request({
    method: 'POST',
    url: `${CONFIG.API_URL}${endpoint}`,
    data,
  });
}

/**
 * Fetch signal from backend
 * @param {string} symbol - Trading symbol
 * @returns {Promise<Object|null>} Signal or null
 */
export async function fetchSignal(symbol = null) {
  try {
    // Iter 150 — include the user's manual chart-type preference so the
    // backend can filter/route signals for the actual chart the user is
    // trading on (japanese_candles / heikin_ashi / line / bar / area).
    let chartType = null;
    try {
      chartType = (typeof GM_getValue === 'function')
        ? GM_getValue('manualChartType', null)
        : window.localStorage.getItem('manualChartType');
    } catch (_e) { /* ignore */ }
    const params = symbol ? { symbol } : {};
    if (chartType && chartType !== 'auto') params.chart_type = chartType;

    // Iter 56c: capture client-side RTT so the poller can attribute network
    // overhead vs server processing in latency reports.
    const t0 = performance.now();
    const response = await get('/signals/latest', params);
    const rttMs = performance.now() - t0;

    if (response.success && response.signal) {
      // Stash RTT on the signal (non-enumerable so it doesn't pollute downstream consumers)
      try {
        Object.defineProperty(response.signal, '_fetchRttMs', {
          value: Math.round(rttMs * 100) / 100,
          enumerable: false,
        });
      } catch (_e) { /* read-only signal? just skip */ }
      return response.signal;
    }
    return null;
  } catch (e) {
    logError(`Failed to fetch signal: ${e.message}`);
    return null;
  }
}

/**
 * Scan markets for signals
 * @param {string[]} assets - Assets to scan
 * @param {number} minConfidence - Minimum confidence threshold
 * @returns {Promise<Object>} Scan results
 */
export async function scanMarkets(assets, minConfidence = 65) {
  try {
    // Guard: normalize + URL-encode each asset to avoid slashes/spaces breaking the URL
    const safeAssets = (assets || [])
      .filter(Boolean)
      .map((a) => String(a).trim().replace(/[\s\-/]+/g, '').toUpperCase())
      .map((a) => a.endsWith('OTC') && !a.endsWith('_OTC') ? a.slice(0, -3) + '_OTC' : a);
    const response = await get('/signals/scan-markets', {
      assets: safeAssets.join(','),
      min_confidence: minConfidence,
    });
    return response;
  } catch (e) {
    logError(`Market scan failed: ${e.message}`);
    return { success: false, error: e.message };
  }
}

/**
 * Send candle data to backend for storage
 * @param {Object[]} candles - Candle data
 * @param {string} symbol - Symbol name
 * @param {string} timeframe - Timeframe
 * @returns {Promise<Object>} Storage result
 */
export async function sendCandles(candles, symbol, timeframe = '5s') {
  try {
    const response = await post(`/tampermonkey/candles?symbol=${symbol}&timeframe=${timeframe}`, candles);
    return response;
  } catch (e) {
    logError(`Failed to send candles: ${e.message}`);
    return { success: false, error: e.message };
  }
}

/**
 * Report trade result to backend
 * @param {Object} trade - Trade details
 * @returns {Promise<Object>} Report result
 */
export async function reportTrade(trade) {
  try {
    return await post('/trades/report', trade);
  } catch (e) {
    logError(`Failed to report trade: ${e.message}`);
    return { success: false, error: e.message };
  }
}

/**
 * Record premium trade result for win-rate tracking (session/hour/asset learning)
 * @param {string} symbol - Asset symbol
 * @param {string} direction - CALL or PUT
 * @param {boolean} isWin - Win or loss
 * @param {number} confidence - Signal confidence at time of trade
 * @returns {Promise<Object>} Updated stats
 */
export async function recordPremiumResult(symbol, direction, isWin, confidence = 0) {
  try {
    const response = await post('/signals/record-premium-result', {
      symbol: symbol || 'UNKNOWN',
      direction: direction || 'CALL',
      is_win: isWin,
      confidence: confidence,
    });
    return response;
  } catch (e) {
    logError(`Failed to record premium result: ${e.message}`);
    return { success: false, error: e.message };
  }
}

/**
 * Report WIN/LOSS outcome for the most recent TM trade so backend
 * /signals/win-rate-stats can compute real rolling accuracy.
 * Matches the last trade report for the same asset that has no outcome yet.
 * @param {Object} params
 * @param {'WIN'|'LOSS'} params.outcome
 * @param {string} [params.asset]
 * @param {string} [params.strategy]
 * @param {number} [params.profit]
 * @returns {Promise<Object>}
 */
export async function reportTradeOutcome({ outcome, asset = null, strategy = null, profit = null }) {
  try {
    return await post('/trades/outcome', { outcome, asset, strategy, profit });
  } catch (e) {
    logError(`Failed to report trade outcome: ${e.message}`);
    return { success: false, error: e.message };
  }
}

/**
 * Report client-side execution latency for a signal (Iter 56c).
 * Fire-and-forget; never throws — instrumentation must not impact trading.
 * Server collects these into `signal_latency_log_client` for end-to-end analysis.
 *
 * @param {Object} timings
 * @param {string|null} timings.signalId - Signal id (matched against server log)
 * @param {string|null} timings.asset
 * @param {string|null} timings.strategy
 * @param {number|null} timings.networkRttMs - Polling request → response received
 * @param {number|null} timings.domClickLagMs - Response received → DOM click dispatched
 * @param {number|null} timings.execLagMs - DOM click → PO confirms trade open
 * @param {string|null} timings.notes - Free-form tag (e.g. 'auto-skip-cooldown')
 */
export function reportLatency(timings) {
  try {
    if (!timings || typeof timings !== 'object') return;
    const body = {
      signal_id: timings.signalId ?? null,
      asset: timings.asset ?? null,
      strategy: timings.strategy ?? null,
      network_rtt_ms: typeof timings.networkRttMs === 'number' ? timings.networkRttMs : null,
      dom_click_lag_ms: typeof timings.domClickLagMs === 'number' ? timings.domClickLagMs : null,
      exec_lag_ms: typeof timings.execLagMs === 'number' ? timings.execLagMs : null,
      notes: timings.notes ?? null,
    };
    // Drop completely-empty reports (no metric to record)
    if (body.network_rtt_ms == null && body.dom_click_lag_ms == null && body.exec_lag_ms == null) {
      return;
    }
    // Fire-and-forget — no await, never throw on failure
    post('/signals/latency-report', body).catch(() => { /* silent — non-essential */ });
  } catch (_e) {
    // Never let latency reporting break trading
  }
}

/**
 * Iter 95 — Fetch the app-side active trading target.
 * Returns {asset, timeframe, expiry_seconds, source} or null on failure.
 * This is the ONE source of truth for what asset the TM should fire on —
 * independent of what PO's chart currently displays.
 */
export async function fetchActiveTarget() {
  try {
    const response = await get('/tampermonkey/active-target');
    if (response && response.success && response.asset) {
      return {
        asset: response.asset,
        timeframe: response.timeframe || '1m',
        expiry_seconds: Number(response.expiry_seconds || 60),
        source: response.source || 'unknown',
      };
    }
    return null;
  } catch (e) {
    // Silent — TM poller will fall back to fetchSignal(null)
    return null;
  }
}


export default {
  request,
  get,
  post,
  fetchSignal,
  fetchActiveTarget,
  scanMarkets,
  sendCandles,
  reportTrade,
  recordPremiumResult,
  reportTradeOutcome,
  reportLatency,
};
