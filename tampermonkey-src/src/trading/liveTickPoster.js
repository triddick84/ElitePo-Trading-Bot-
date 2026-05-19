/**
 * Live Tick Poster — Iter 58 (v8.63.0, May 17, 2026)
 *
 * Pocket Option's WebSocket frames are intercepted by `ssidBridge` which
 * exposes a per-symbol price registry (`poLivePrice`). This module subscribes
 * to that stream, aggregates ticks into 5-second OHLC candles per symbol,
 * and POSTs flushed candles to the backend every 5 seconds at:
 *
 *   POST /api/signals/collect-otc-candles
 *
 * Why: the backend's MLAccuracyTuner trains on `otc_candles_5s.source='po_live'`
 * docs which give the model the EXACT data distribution PO serves at live entry.
 * Without this wiring, the pool is OANDA-only (different liquidity, different
 * spread microstructure) and live win-rate diverges from backtest.
 *
 * Failure mode: fire-and-forget. Network errors don't impact trading.
 */

import { CONFIG } from '../core/config.js';
import { log, info, warn, debug } from '../core/logger.js';
import { post } from '../utils/api.js';
import { poLivePrice } from './ssidBridge.js';

const CANDLE_SECONDS = 5;
const FLUSH_INTERVAL_MS = 5000;
const POST_TIMEOUT_MS = 4000;
const MAX_QUEUE_CANDLES = 60;          // keep last 5 min if backend is down
const MAX_SYMBOLS = 50;                 // belt-and-braces upper bound

class LiveTickPoster {
  constructor() {
    this.enabled = false;
    this.unhook = null;
    this.flushTimer = null;
    // open candle per symbol: { [symbol]: { o, h, l, c, v, startSec } }
    this.openCandles = {};
    // queue of completed candles, per symbol
    this.queues = {};
    // stats
    this.totalTicks = 0;
    this.totalPosted = 0;
    this.lastPostAt = 0;
    this.lastPostStatus = null;
    this.lastError = null;
  }

  start() {
    if (this.enabled) return;
    this.enabled = true;

    // Subscribe to every captured price tick from the WS bridge
    this.unhook = poLivePrice.onPrice((symbol, price, ts) => {
      this._ingest(symbol, price, ts);
    });

    // Periodic flush
    this.flushTimer = setInterval(() => this._flush(), FLUSH_INTERVAL_MS);
    info('[LiveTickPoster] started — feeding PO ticks → /api/signals/collect-otc-candles');
  }

  stop() {
    this.enabled = false;
    if (this.unhook) { try { this.unhook(); } catch (_e) { /* ignore */ } this.unhook = null; }
    if (this.flushTimer) { clearInterval(this.flushTimer); this.flushTimer = null; }
  }

  _normalizeSymbol(raw) {
    if (!raw || typeof raw !== 'string') return null;
    // PO often emits lowercase (eurusd_otc); normalise to EURUSD_OTC
    let s = raw.toUpperCase().replace(/-/g, '');
    // _otc → _OTC
    s = s.replace(/_OTC$/i, '_OTC');
    // Filter junk
    if (!/^[A-Z]{2,8}(_OTC)?$/.test(s)) return null;
    return s;
  }

  _ingest(symbol, price, ts) {
    if (!this.enabled) return;
    const sym = this._normalizeSymbol(symbol);
    if (!sym) return;
    if (!Number.isFinite(price) || price <= 0) return;
    this.totalTicks++;

    // Cap memory — refuse to track more than MAX_SYMBOLS
    if (!(sym in this.openCandles) && Object.keys(this.openCandles).length >= MAX_SYMBOLS) return;

    const t = Math.floor((ts || Date.now()) / 1000);
    const startSec = t - (t % CANDLE_SECONDS);

    const cur = this.openCandles[sym];
    if (!cur || cur.startSec !== startSec) {
      // Close previous candle (if any) and enqueue
      if (cur) this._enqueue(sym, cur);
      this.openCandles[sym] = { o: price, h: price, l: price, c: price, v: 1, startSec };
      return;
    }

    cur.c = price;
    if (price > cur.h) cur.h = price;
    if (price < cur.l) cur.l = price;
    cur.v += 1;
  }

  _enqueue(symbol, candle) {
    if (!this.queues[symbol]) this.queues[symbol] = [];
    this.queues[symbol].push({
      open: candle.o,
      high: candle.h,
      low: candle.l,
      close: candle.c,
      volume: candle.v,
      timestamp: new Date(candle.startSec * 1000).toISOString(),
    });
    // Trim oldest if backend has been offline
    if (this.queues[symbol].length > MAX_QUEUE_CANDLES) {
      this.queues[symbol] = this.queues[symbol].slice(-MAX_QUEUE_CANDLES);
    }
  }

  async _flush() {
    if (!this.enabled) return;
    // Close any candles that have rolled over (no new tick yet)
    const nowSec = Math.floor(Date.now() / 1000);
    for (const [sym, cur] of Object.entries(this.openCandles)) {
      if (nowSec >= cur.startSec + CANDLE_SECONDS) {
        this._enqueue(sym, cur);
        delete this.openCandles[sym];
      }
    }

    const pending = Object.keys(this.queues).filter((s) => this.queues[s].length > 0);
    if (pending.length === 0) return;

    for (const sym of pending) {
      const batch = this.queues[sym].splice(0, this.queues[sym].length);
      // Fire-and-forget per symbol with bounded timeout. We use a wrapped
      // fetch so the underlying `post` helper's default error handling
      // doesn't pollute the console on transient network blips.
      this._postBatch(sym, batch).catch((e) => {
        // Re-queue on failure (front of queue) so we don't lose data
        this.queues[sym] = [...batch, ...(this.queues[sym] || [])].slice(-MAX_QUEUE_CANDLES);
        this.lastError = String(e && e.message ? e.message : e);
        debug(`[LiveTickPoster] re-queued ${batch.length} for ${sym}: ${this.lastError}`);
      });
    }
  }

  async _postBatch(symbol, candles) {
    try {
      const res = await post('/signals/collect-otc-candles', {
        symbol, timeframe: '5s', candles,
      });
      this.lastPostAt = Date.now();
      this.lastPostStatus = res && res.success !== false ? 'ok' : 'fail';
      this.totalPosted += candles.length;
      if (this.totalPosted === candles.length || this.totalPosted % 50 === 0) {
        info(`[LiveTickPoster] posted ${this.totalPosted} candles total (latest ${symbol} +${candles.length})`);
      }
    } catch (e) {
      throw e;
    }
  }

  getStats() {
    return {
      enabled: this.enabled,
      total_ticks: this.totalTicks,
      total_posted: this.totalPosted,
      last_post_at: this.lastPostAt,
      last_post_status: this.lastPostStatus,
      last_error: this.lastError,
      pending: Object.fromEntries(
        Object.entries(this.queues).map(([k, v]) => [k, v.length]),
      ),
      open_candles: Object.keys(this.openCandles).length,
    };
  }
}

export const liveTickPoster = new LiveTickPoster();
