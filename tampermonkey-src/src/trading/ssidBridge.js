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

class SSIDBridge {
  constructor() {
    this.installed = false;
    this.lastAuthMessage = null;
    this.lastSentSession = null;
    this.lastSentAt = 0;
    this.heartbeatId = null;
    this.uploadInFlight = false;
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

      // Proxy-wrap the WebSocket constructor so we see every outgoing frame.
      const PatchedWS = function (url, protocols) {
        const ws = protocols !== undefined ? new OriginalWS(url, protocols) : new OriginalWS(url);

        // Only hook PO-origin WebSockets. They hit api-*.po.* or trade-*.
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
            } catch (_e) {
              // never let our hook break PO's traffic
            }
            return originalSend(data);
          };
        }

        return ws;
      };

      // Keep static properties / prototype so instanceof checks pass
      PatchedWS.prototype = OriginalWS.prototype;
      PatchedWS.CONNECTING = OriginalWS.CONNECTING;
      PatchedWS.OPEN = OriginalWS.OPEN;
      PatchedWS.CLOSING = OriginalWS.CLOSING;
      PatchedWS.CLOSED = OriginalWS.CLOSED;

      window.WebSocket = PatchedWS;

      success('[SSID-Bridge] installed — waiting for PO auth frame');

      // Periodic heartbeat so the backend knows our session is still live
      this.heartbeatId = setInterval(() => this._heartbeat(), HEARTBEAT_MS);
    } catch (e) {
      warn(`[SSID-Bridge] install failed: ${e.message}`);
    }
  }

  _captureAuth(message, wsUrl) {
    const match = message.match(AUTH_REGEX);
    if (!match) return;

    this.lastAuthMessage = match[0];

    // Pull session for dedup
    let session = null;
    try {
      const payload = message.match(/42\["auth",(\{.*?\})\]/);
      if (payload) {
        const auth = JSON.parse(payload[1]);
        session = auth.session;
      }
    } catch (_e) { /* ignore */ }

    // Only upload if the session changed or it's been >1min since last upload
    const now = Date.now();
    const changed = session && session !== this.lastSentSession;
    const stale = now - this.lastSentAt > 60_000;
    if (!changed && !stale) return;

    this._upload(this.lastAuthMessage, session, 'auth-frame', wsUrl);
  }

  async _heartbeat() {
    if (!this.lastAuthMessage) return;
    // Heartbeat: re-send the latest known auth frame so backend updates last_seen_at
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
    // Note: we do NOT revert window.WebSocket because PO may already hold
    // references to PatchedWS; un-patching could break their reconnection logic.
    this.installed = false;
  }
}

export const ssidBridge = new SSIDBridge();
export default ssidBridge;
