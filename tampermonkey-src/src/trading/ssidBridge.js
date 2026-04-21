/**
 * SSID Bridge — Tampermonkey WebSocket Interceptor
 *
 * Hooks the native WebSocket constructor globally. When PO opens its trading
 * WebSocket and sends the initial `42["auth",{...}]` authentication frame,
 * we capture that message ONCE per session and POST it to our backend at
 *   POST /api/po/ssid/update
 *
 * Then sends a lightweight heartbeat every 10 minutes (re-POSTing the same
 * frame) so the backend knows the session is still alive.
 *
 * Why intercept outgoing WS instead of reading cookies?
 * - PO's auth frame carries the full session + uid + isDemo + platform tuple
 *   that the backend's direct WS client (BinaryOptionsToolsV2) needs.
 * - Cookies alone lack uid/isDemo, which require an extra call to extract.
 * - This hook sees the auth frame EVERY time PO opens a WS (which happens
 *   on every login / account switch / demo↔live toggle), so the bridge is
 *   always up-to-date.
 */

import { CONFIG } from '../core/config.js';
import { log, success, warn, info, debug } from '../core/logger.js';
import { post } from '../utils/api.js';

const AUTH_REGEX = /42\["auth",\{[^}]+\}\]/;
const HEARTBEAT_MS = 10 * 60 * 1000; // 10 min

// Shared price registry — any module can pull the latest price for a symbol
// captured directly from PO's WebSocket frames (Canvas-independent).
const priceRegistry = {
  prices: {},      // { [symbol]: { price, ts } }
  lastAnyPrice: null,
  lastAnyTs: 0,
  listeners: [],
};

function _recordPrice(symbol, price) {
  const ts = Date.now();
  if (!Number.isFinite(price) || price <= 0) return;
  if (symbol) {
    priceRegistry.prices[symbol] = { price, ts };
  }
  priceRegistry.lastAnyPrice = price;
  priceRegistry.lastAnyTs = ts;
  for (const cb of priceRegistry.listeners) {
    try { cb(symbol, price, ts); } catch (_e) { /* ignore */ }
  }
}

export const poLivePrice = {
  getForSymbol(symbol) {
    const rec = priceRegistry.prices[symbol];
    return rec ? rec.price : null;
  },
  getLatest() {
    return priceRegistry.lastAnyPrice;
  },
  getLatestAge() {
    return priceRegistry.lastAnyTs ? Date.now() - priceRegistry.lastAnyTs : null;
  },
  getAll() {
    return { ...priceRegistry.prices };
  },
  onPrice(cb) {
    priceRegistry.listeners.push(cb);
    return () => {
      const i = priceRegistry.listeners.indexOf(cb);
      if (i >= 0) priceRegistry.listeners.splice(i, 1);
    };
  },
};

class SSIDBridge {
  constructor() {
    this.installed = false;
    this.lastAuthMessage = null;
    this.lastSentSession = null;
    this.lastSentAt = 0;
    this.heartbeatId = null;
    this.uploadInFlight = false;
    // Price tick stats
    this.pricesCaptured = 0;
  }

  install() {
    if (this.installed) return;
    this.installed = true;

    try {
      const OriginalWS = window.WebSocket;
      if (!OriginalWS) {
        warn('[SSID-Bridge] window.WebSocket unavailable — bridge not installed');
        return;
      }

      const bridge = this;

      const PatchedWS = function (url, protocols) {
        const ws = protocols !== undefined ? new OriginalWS(url, protocols) : new OriginalWS(url);

        const isPOWS =
          typeof url === 'string' &&
          /pocket|po\.trade|po\.market|\.po\.|pocketoption/i.test(url);

        if (isPOWS) {
          debug(`[SSID-Bridge] hooked WS: ${url}`);
          const originalSend = ws.send.bind(ws);
          ws.send = function (data) {
            try {
              if (typeof data === 'string' && data.indexOf('42["auth"') === 0) {
                bridge._captureAuth(data, url);
              }
            } catch (_e) { /* ignore */ }
            return originalSend(data);
          };

          // Hook incoming messages to capture live price ticks
          ws.addEventListener('message', function (ev) {
            try {
              bridge._captureMessage(ev.data);
            } catch (_e) { /* ignore */ }
          });
        }

        return ws;
      };

      PatchedWS.prototype = OriginalWS.prototype;
      PatchedWS.CONNECTING = OriginalWS.CONNECTING;
      PatchedWS.OPEN = OriginalWS.OPEN;
      PatchedWS.CLOSING = OriginalWS.CLOSING;
      PatchedWS.CLOSED = OriginalWS.CLOSED;

      window.WebSocket = PatchedWS;

      success('[SSID-Bridge] installed — WS hook + price tick capture active');

      this.heartbeatId = setInterval(() => this._heartbeat(), HEARTBEAT_MS);
    } catch (e) {
      warn(`[SSID-Bridge] install failed: ${e.message}`);
    }
  }

  /**
   * Parse incoming PO WS messages to extract live prices.
   * PO uses Engine.IO + Socket.IO frames. Price updates come through multiple
   * event types — we probe them all for any forex-looking float.
   */
  _captureMessage(data) {
    if (!data) return;

    // 1. Binary frames (Blob/ArrayBuffer/Uint8Array) — decode to text first
    if (typeof data !== 'string') {
      // For binary, we'd need async Blob.text() — skip unless already text.
      // Most PO price frames come as text/JSON despite Socket.IO binary mode.
      if (data instanceof ArrayBuffer) {
        try {
          data = new TextDecoder('utf-8', { fatal: false }).decode(new Uint8Array(data));
        } catch (_e) { return; }
      } else if (data && typeof data.text === 'function') {
        // Blob — defer async decode; drop for now (hot path)
        return;
      } else {
        return;
      }
    }

    // 2. Text frames — must look like Socket.IO event payload or JSON
    if (data.length < 10) return;

    // Try common PO payload shapes:
    // - `42["updateStream",[[symbol, ts, price]]]`  or
    // - `42["loadHistoryPeriod", {...}]`
    // - Binary-encoded candle arrays embedded in the JSON
    try {
      // Fast-path: look for the common updateStream / changeSymbol pattern
      if (data.indexOf('updateStream') !== -1 ||
          data.indexOf('loadHistoryPeriod') !== -1 ||
          data.indexOf('"symbol"') !== -1 ||
          data.indexOf('price') !== -1) {
        // Strip Socket.IO prefix `42`
        let json = data;
        if (/^\d+/.test(data)) {
          const braceIdx = data.indexOf('[');
          const curlyIdx = data.indexOf('{');
          const firstIdx = braceIdx === -1 ? curlyIdx : (curlyIdx === -1 ? braceIdx : Math.min(braceIdx, curlyIdx));
          if (firstIdx > 0) json = data.slice(firstIdx);
        }

        // Parse permissively — extract ANY forex-ish number from the payload
        // (avoids brittle schema dependency on PO's exact frame format)
        this._extractPricesFromText(json);
      }
    } catch (_e) { /* ignore */ }
  }

  _extractPricesFromText(text) {
    // Grab currency-like tokens near number tokens:
    //   "symbol":"EURUSD_otc"  ...  <price number>
    // Strategy: find all numbers with 3-6 decimals, and if a nearby "symbol" is
    // present use it; otherwise record as the generic "last price".
    const numberRe = /(-?\d{1,7}\.\d{3,8})/g;
    const symbolRe = /"(?:symbol|asset|active|s)"\s*:\s*"([A-Z]{2,8}(?:_otc)?)"/i;

    const symMatch = text.match(symbolRe);
    const symbol = symMatch ? symMatch[1] : null;

    let m;
    let count = 0;
    const now = Date.now();
    while ((m = numberRe.exec(text)) !== null && count < 20) {
      const val = parseFloat(m[1]);
      // Skip timestamps (large) and integers-ish
      if (!Number.isFinite(val)) continue;
      if (val > 1_000_000) continue; // likely a ms timestamp
      if (val < 0.00001) continue;
      // Skip very common non-price numbers
      if (val === 100 || val === 0) continue;
      _recordPrice(symbol, val);
      count++;
    }
    if (count > 0) {
      this.pricesCaptured += count;
      // Log very first and every 100th
      if (this.pricesCaptured === 1 || this.pricesCaptured % 100 === 0) {
        info(`[SSID-Bridge] captured ${this.pricesCaptured} live price ticks (latest=${priceRegistry.lastAnyPrice}${symbol ? ` symbol=${symbol}` : ''})`);
        // Bump tick timestamp via the last call to _recordPrice; note current age.
      }
    }
  }

  _captureAuth(message, wsUrl) {
    const match = message.match(AUTH_REGEX);
    if (!match) return;

    this.lastAuthMessage = match[0];

    let session = null;
    try {
      const payload = message.match(/42\["auth",(\{.*?\})\]/);
      if (payload) {
        const auth = JSON.parse(payload[1]);
        session = auth.session;
      }
    } catch (_e) { /* ignore */ }

    const now = Date.now();
    const changed = session && session !== this.lastSentSession;
    const stale = now - this.lastSentAt > 60_000;
    if (!changed && !stale) return;

    this._upload(this.lastAuthMessage, session, 'auth-frame', wsUrl);
  }

  async _heartbeat() {
    if (!this.lastAuthMessage) return;
    await this._upload(
      this.lastAuthMessage,
      this.lastSentSession,
      'heartbeat',
      null
    );
  }

  async _upload(authMessage, session, source, wsUrl) {
    if (this.uploadInFlight) return;
    this.uploadInFlight = true;
    try {
      const resp = await post('/po/ssid/update', {
        auth_message: authMessage,
        source: `tampermonkey-${source}`,
        ua: navigator.userAgent,
      });
      if (resp && resp.success) {
        if (resp.updated) {
          info(`[SSID-Bridge] uploaded new SSID (${resp.session_preview || 'hidden'}, uid=${resp.uid}, demo=${resp.is_demo})`);
        } else {
          debug('[SSID-Bridge] heartbeat ack');
        }
        this.lastSentSession = session;
        this.lastSentAt = Date.now();
      } else {
        warn(`[SSID-Bridge] upload rejected: ${resp && resp.error ? resp.error : 'unknown'}`);
      }
    } catch (e) {
      warn(`[SSID-Bridge] upload failed: ${e.message}`);
    } finally {
      this.uploadInFlight = false;
    }
  }

  uninstall() {
    if (this.heartbeatId) {
      clearInterval(this.heartbeatId);
      this.heartbeatId = null;
    }
    this.installed = false;
  }
}

export const ssidBridge = new SSIDBridge();
export default ssidBridge;
