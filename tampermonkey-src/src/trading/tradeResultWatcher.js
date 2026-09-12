/**
 * Trade Result Watcher — Iter 136 rewrite (multi-trade, no balance dependency)
 * ---------------------------------------------------------------------------
 * OLD design (v8.146.0 and earlier):
 *   Single global `this.armed` slot + balance-delta polling.
 *   BUG: overlapping trades break balance detection because trade B's stake
 *   deduction masks trade A's payout ("balance stays" or "balance drops").
 *   Also: only one trade could be armed at a time — a second trade wiped
 *   the first arm before it settled → previous outcome silently lost.
 *
 * NEW design (Iter 136):
 *   1. FIFO queue of armed trades (no single slot).
 *   2. Balance polling REMOVED — the balance signal is unreliable with
 *      overlapping trades. Detection is now purely DOM-based.
 *   3. Per-row identity tracking — `seenRows` set snapshots existing deal
 *      rows at arm time, then every new row that appears is parsed for
 *      (asset, direction, amount, outcome) and matched back to the oldest
 *      armed trade with the same signature. That specific trade resolves.
 *   4. Timeout still fires (expiry + safety-buffer) but only on the trade
 *      that hit its deadline — others in the queue keep waiting.
 */

import { log, info, warn, success, error } from '../core/logger.js';
import { scanDOMForTradeResult } from '../utils/dom.js';
import { tradeExecutor } from './executor.js';

const POLL_INTERVAL_MS = 800;
const SAFETY_BUFFER_MS = 4_000;
const ABANDON_AFTER_TIMEOUT = false;
const MAX_QUEUE = 16;              // don't leak if PO stalls a bunch of trades

const DEAL_ROW_SELECTOR = [
  '.deals-list .deals-item',
  '[class*="closed-deals"] [class*="item"]',
  '[class*="deals-list"] > div',
  '[class*="deal-item"]',
  '[class*="history"] [class*="item"]',
].join(', ');

/** Normalize `EURUSD-OTC`, `EUR/USD OTC`, `EURUSDotc` → `EURUSDOTC` */
function _normAsset(a) {
  return String(a || '').toUpperCase().replace(/[\s/_-]/g, '');
}

/** Extract a stable-ish per-row identity — textContent is idempotent across
 *  mutations of unrelated siblings; adding a "starts-with-timestamp" bucket
 *  reduces false collapse when two identical trades resolve in a row. */
function _rowId(el) {
  const t = (el.textContent || '').replace(/\s+/g, '').substring(0, 160);
  // Some rows carry a data-id attr from PO — prefer it when present
  const explicit = el.getAttribute && (el.getAttribute('data-id') || el.getAttribute('id'));
  return explicit ? `id:${explicit}` : `t:${t}`;
}

/** Parse a deal row into { asset, direction, amount, isWin }.
 *  Returns null when any critical field can't be extracted so we don't
 *  match a random row to the wrong armed trade. */
function _parseDealRow(row) {
  try {
    const text = (row.textContent || '').replace(/\s+/g, ' ').trim();

    // Direction — PO rows always contain UP/CALL/HIGHER or DOWN/PUT/LOWER
    let direction = null;
    if (/\b(UP|CALL|HIGHER|BUY)\b/i.test(text)) direction = 'CALL';
    else if (/\b(DOWN|PUT|LOWER|SELL)\b/i.test(text)) direction = 'PUT';

    // Asset — pick the longest all-caps token 3-8 chars that looks like a pair
    const upper = row.textContent.match(/\b[A-Z]{3,8}(?:[/_-]?OTC)?\b/g) || [];
    let asset = null;
    for (const cand of upper) {
      const n = _normAsset(cand);
      if (n.length >= 6 && n.length <= 12) { asset = n; break; }
    }

    // Amount + outcome from the row's numeric fields
    // PO usually shows: "<stake>  <payout>" where payout is 0 on loss.
    const nums = [...text.matchAll(/([+-]?)\s*\$?\s*(\d+(?:\.\d+)?)/g)]
      .map(m => ({ sign: m[1], val: parseFloat(m[2]) }))
      .filter(x => Number.isFinite(x.val));
    let amount = null;
    let isWin = null;
    // The stake is the LARGEST unsigned positive < 10000. The payout is
    // signed. Fall back to the DOM class-based scanner for isWin.
    if (nums.length >= 2) {
      const unsigned = nums.filter(x => !x.sign && x.val > 0);
      amount = unsigned.length ? Math.max(...unsigned.map(x => x.val)) : null;
      const signed = nums.filter(x => x.sign);
      if (signed.length) {
        const s = signed[signed.length - 1];   // last signed = final payout
        if (s.sign === '+' && s.val > 0) isWin = true;
        else if (s.sign === '-' || s.val === 0) isWin = false;
      }
    }

    // Fallback: class-based
    if (isWin === null) {
      const cls = (row.className || '').toLowerCase();
      if (/\b(loss|lost|failed?|red|negative|minus)\b/.test(cls)) isWin = false;
      else if (/\b(win|won|success|green|positive)\b/.test(cls)) isWin = true;
    }

    if (!direction || !asset || isWin === null) return null;
    return { asset, direction, amount, isWin };
  } catch (_e) {
    return null;
  }
}

class TradeResultWatcher {
  constructor() {
    this.enabled = false;
    this.observer = null;
    this.pollId = null;
    this.armedQueue = [];          // FIFO of { trade, armedAt, deadline, resolved }
    this.seenRows = new Set();     // rows already on the page (or already matched)
  }

  enable() {
    if (this.enabled) return;
    this.enabled = true;
    // Prime seenRows with existing deal rows so we don't fire on historical rows
    document.querySelectorAll(DEAL_ROW_SELECTOR).forEach(r => {
      this.seenRows.add(_rowId(r));
    });
    this._installObserver();
    success('[ResultWatcher] enabled — multi-trade queue, DOM-only (no balance)');
  }

  disable() {
    if (!this.enabled) return;
    this.enabled = false;
    if (this.observer) { this.observer.disconnect(); this.observer = null; }
    if (this.pollId) { clearInterval(this.pollId); this.pollId = null; }
    this.armedQueue = [];
    this.seenRows.clear();
  }

  isEnabled() { return this.enabled; }

  /**
   * Arm the watcher for `trade`. Multiple arms are supported — they all wait
   * for their matching deal row to appear.
   */
  armResolver(trade) {
    if (!this.enabled || !trade) return;
    // Bump global fire count (as before)
    try {
      const w = (typeof window !== 'undefined') ? window : null;
      if (w && typeof w.__eliteBotIncFireCount === 'function') {
        w.__eliteBotIncFireCount(trade.asset);
      }
    } catch (_e) { /* ignore */ }

    // Enforce max queue length so a stuck trade doesn't leak the queue.
    while (this.armedQueue.length >= MAX_QUEUE) {
      const dropped = this.armedQueue.shift();
      warn(`[ResultWatcher] dropped oldest arm (queue full) — ${dropped.trade.direction} ${dropped.trade.asset}`);
    }

    const expirySec = Number(trade.expirySeconds) || 5;
    const arm = {
      trade,
      normAsset: _normAsset(trade.asset),
      armedAt: Date.now(),
      deadline: Date.now() + (expirySec * 1000) + SAFETY_BUFFER_MS,
      resolved: false,
    };
    this.armedQueue.push(arm);
    log(`[ResultWatcher] armed #${this.armedQueue.length}: ${trade.direction} ${trade.asset} @$${trade.amount} exp=${expirySec}s`);

    // Refresh seenRows to include everything currently visible (so only
    // rows appearing AFTER this arm count as candidates). Preserves
    // in-flight arms' matchability because unseen rows are still unseen.
    document.querySelectorAll(DEAL_ROW_SELECTOR).forEach(r => {
      this.seenRows.add(_rowId(r));
    });

    if (!this.pollId) {
      this.pollId = setInterval(() => this._poll(), POLL_INTERVAL_MS);
    }
  }

  // -- Internals -----------------------------------------------------------

  _installObserver() {
    if (this.observer) return;
    try {
      this.observer = new MutationObserver(() => {
        if (!this.armedQueue.length) return;
        this._scanNewRows();
      });
      this.observer.observe(document.body, {
        childList: true, subtree: true,
      });
    } catch (e) {
      warn(`[ResultWatcher] observer install failed: ${e.message}`);
    }
  }

  _scanNewRows() {
    let rows;
    try { rows = document.querySelectorAll(DEAL_ROW_SELECTOR); }
    catch (_e) { return; }
    for (const row of rows) {
      const id = _rowId(row);
      if (this.seenRows.has(id)) continue;
      this.seenRows.add(id);
      const parsed = _parseDealRow(row);
      if (!parsed) continue;
      this._matchAndResolve(parsed, row);
    }
  }

  /** Find the oldest un-resolved armed trade matching this parsed row.
   *  Matches on (asset, direction) and — when amount is available — also
   *  the stake within a 5-cent tolerance. Falls back to (asset, direction)
   *  only when the row didn't yield a clean amount. */
  _matchAndResolve(parsed, row) {
    const idx = this.armedQueue.findIndex(a => {
      if (a.resolved) return false;
      if (_normAsset(a.trade.asset) !== parsed.asset) return false;
      if (a.trade.direction !== parsed.direction) return false;
      if (parsed.amount != null && a.trade.amount != null) {
        if (Math.abs(a.trade.amount - parsed.amount) > 0.05) return false;
      }
      return true;
    });
    if (idx === -1) {
      log(`[ResultWatcher] no armed match for ${parsed.direction} ${parsed.asset} @$${parsed.amount ?? '?'}`);
      return;
    }
    const arm = this.armedQueue[idx];
    this._resolve(arm, parsed.isWin, 'deal-row-match');
  }

  _poll() {
    if (!this.armedQueue.length) {
      clearInterval(this.pollId);
      this.pollId = null;
      return;
    }
    const now = Date.now();
    // Belt-and-suspenders: rescan deal rows in case a mutation was missed
    this._scanNewRows();

    // Timeout expired arms
    const still = [];
    for (const arm of this.armedQueue) {
      if (arm.resolved) continue;
      if (now > arm.deadline) {
        warn(`[ResultWatcher] timeout: ${arm.trade.direction} ${arm.trade.asset} — no deal row matched`);
        if (ABANDON_AFTER_TIMEOUT) {
          this._resolve(arm, false, 'timeout-loss');
        }
        // else drop silently
        continue;
      }
      still.push(arm);
    }
    this.armedQueue = still;
  }

  _resolve(arm, isWin, source) {
    if (arm.resolved) return;
    arm.resolved = true;
    const t = arm.trade;
    success(`[ResultWatcher] ${isWin ? '✓ WIN' : '✗ LOSS'} · ${t.direction} ${t.asset} @$${t.amount} (via ${source})`);
    try {
      tradeExecutor.recordResult(isWin, {
        autoResolved: true,
        tradeContext: t,        // tell the executor exactly which trade resolved
      });
    } catch (e) {
      error(`[ResultWatcher] recordResult failed: ${e.message}`);
    }
    // Prune resolved arms out of the queue
    this.armedQueue = this.armedQueue.filter(a => !a.resolved);
  }

  /** Debug helper — expose queue state so the AI panel can render it. */
  getQueueSnapshot() {
    return this.armedQueue.map(a => ({
      asset: a.trade.asset,
      direction: a.trade.direction,
      amount: a.trade.amount,
      armedAt: a.armedAt,
      deadline: a.deadline,
      remaining_ms: Math.max(0, a.deadline - Date.now()),
    }));
  }
}

export const tradeResultWatcher = new TradeResultWatcher();
export default tradeResultWatcher;
