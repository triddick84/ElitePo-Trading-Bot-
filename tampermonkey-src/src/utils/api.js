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
    const params = symbol ? { symbol } : {};
    const response = await get('/signals/latest', params);
    
    if (response.success && response.signal) {
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

export default {
  request,
  get,
  post,
  fetchSignal,
  scanMarkets,
  sendCandles,
  reportTrade,
  recordPremiumResult,
};
