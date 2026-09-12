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
 *  Iter 141: Robust WIN/LOSS detection — prefers color/class markers over
 *  numeric parsing because PO's payout column shows `$2.85` (no `+` sign)
 *  for wins and often nothing for losses. Old regex-based approach missed
 *  every WIN.
 *  Returns null only when direction OR asset can't be extracted. When
 *  isWin can't be determined we fall back to the class/color scanner. */
function _parseDealRow(row) {
  try {
    const text = (row.textContent || '').replace(/\s+/g, ' ').trim();

    // ---- Direction ----
    let direction = null;
    if (/\b(UP|CALL|HIGHER|BUY)\b/i.test(text)) direction = 'CALL';
    else if (/\b(DOWN|PUT|LOWER|SELL)\b/i.test(text)) direction = 'PUT';
    // Arrow-based fallback (PO often uses ▲ ▼ or ↑ ↓ icons)
    if (!direction) {
      if (/[▲↑⬆]/.test(text)) direction = 'CALL';
      else if (/[▼↓⬇]/.test(text)) direction = 'PUT';
    }

    // ---- Asset ----
    const upper = row.textContent.match(/\b[A-Z]{3,8}(?:[/_-]?OTC)?\b/g) || [];
    let asset = null;
    for (const cand of upper) {
      const n = _normAsset(cand);
      if (n.length >= 6 && n.length <= 12) { asset = n; break; }
    }

    // ---- Numeric fields (stake + payout) ----
    // Extract every dollar-ish number. Payout is the LAST one (rightmost in
    // the row), stake is one of the earlier ones. On WINS payout > stake;
    // on LOSSES payout is 0 or absent.
    const nums = [...text.matchAll(/([+-]?)\s*\$?\s*(\d+(?:\.\d+)?)/g)]
      .map((m) => ({ sign: m[1], val: parseFloat(m[2]) }))
      .filter((x) => Number.isFinite(x.val) && x.val < 100000);
    // Stake is typically the smallest positive value ≥ 1 that appears
    // before larger numbers, but the simpler heuristic is: take the FIRST
    // dollar-prefixed value or the smallest unsigned value.
    let amount = null;
    if (nums.length >= 1) {
      const unsigned = nums.filter((x) => !x.sign && x.val > 0);
      if (unsigned.length) {
        // Stake ≠ price → stake is usually < 1000 and NOT a decimal quote.
        // Pick the smallest sensible stake candidate (0.5..1000).
        const stakes = unsigned
          .map((x) => x.val)
          .filter((v) => v >= 0.5 && v <= 1000);
        amount = stakes.length ? Math.min(...stakes) : null;
      }
    }

    // ---- WIN / LOSS — try multiple strategies, in order ----
    let isWin = null;
    // Strategy A: explicit +/- sign on a payout number
    const signed = nums.filter((x) => x.sign);
    if (signed.length) {
      const s = signed[signed.length - 1];
      if (s.sign === '+' && s.val > 0) isWin = true;
      else if (s.sign === '-' || s.val === 0) isWin = false;
    }
    // Strategy B: class/color markers on the row itself (most reliable on PO)
    if (isWin === null) {
      const cls = (row.className || '').toLowerCase();
      if (/\b(loss|lost|failed?|red|negative|minus|down)\b/.test(cls)) isWin = false;
      else if (/\b(win|won|success|green|positive|profit|up)\b/.test(cls)) isWin = true;
    }
    // Strategy C: scan child element classes/text — PO often puts the
    // payout in a span with a color class like `.value_up` / `.value_down`
    if (isWin === null) {
      try {
        const winEl = row.querySelector(
          '[class*="win" i], [class*="won" i], [class*="success" i], '
          + '[class*="profit" i], [class*="green" i], [class*="value_up" i]'
        );
        const lossEl = row.querySelector(
          '[class*="loss" i], [class*="lost" i], [class*="fail" i], '
          + '[class*="red" i], [class*="value_down" i]'
        );
        if (winEl && !lossEl) isWin = true;
        else if (lossEl && !winEl) isWin = false;
      } catch (_e) { /* querySelector on odd rows can throw */ }
    }
    // Strategy D: numeric heuristic — if we identified a stake AND there's
    // a LARGER positive number after it in the row, PO paid a profit → WIN.
    if (isWin === null && amount != null && nums.length >= 2) {
      const positives = nums.filter((x) => x.val > 0 && !x.sign);
      const anyLarger = positives.some((x) => x.val > amount * 1.1);
      // Explicit $0.00 anywhere after the stake → loss
      const anyZero = nums.slice(-3).some((x) => x.val === 0);
      if (anyLarger && !anyZero) isWin = true;
      else if (anyZero) isWin = false;
    }
    // Strategy E: RGB color of the row / a descendant — final fallback.
    if (isWin === null && typeof window !== 'undefined' && window.getComputedStyle) {
      try {
        const candidates = [row, ...row.querySelectorAll('*')].slice(0, 12);
        for (const el of candidates) {
          const color = window.getComputedStyle(el).color || '';
          // rgb(46,160,67) / rgb(63,185,80) — greens
          const m = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)/);
          if (m) {
            const [r, g, b] = [+m[1], +m[2], +m[3]];
            if (g > 130 && g > r + 25 && g > b + 25) { isWin = true; break; }
            if (r > 130 && r > g + 25 && r > b + 25) { isWin = false; break; }
          }
        }
      } catch (_e) { /* getComputedStyle can throw on detached nodes */ }
    }

    if (!direction || !asset) return null;
    // isWin may still be null — the caller will decide whether to retry.
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
      const parsed = _parseDealRow(row);
      if (!parsed) continue;
      // Iter 141: if isWin is null the row hasn't fully rendered yet (PO
      // sometimes streams the payout in a second frame). DON'T mark it
      // seen — the next observer tick will re-parse.
      if (parsed.isWin === null) {
        log(`[ResultWatcher] deferring row (no outcome yet) — ${parsed.direction} ${parsed.asset}`);
        continue;
      }
      this.seenRows.add(id);
      this._matchAndResolve(parsed, row);
    }
  }

  /** Find the oldest un-resolved armed trade matching this parsed row.
   *  Iter 141: matching is now LENIENT — asset+direction always required,
   *  amount used only as a tie-breaker when both sides provide one.
   *  Prior behaviour REQUIRED amount match within 5¢, but PO's DOM often
   *  omits the stake in the row summary, causing every trade to go
   *  unmatched. */
  _matchAndResolve(parsed, row) {
    // First pass — exact match on (asset, direction, amount)
    let idx = this.armedQueue.findIndex((a) => {
      if (a.resolved) return false;
      if (_normAsset(a.trade.asset) !== parsed.asset) return false;
      if (a.trade.direction !== parsed.direction) return false;
      if (parsed.amount != null && a.trade.amount != null) {
        if (Math.abs(a.trade.amount - parsed.amount) > 0.05) return false;
      }
      return true;
    });
    // Second pass — same asset+direction, ignore amount (row may not carry it)
    if (idx === -1) {
      idx = this.armedQueue.findIndex((a) => (
        !a.resolved
        && _normAsset(a.trade.asset) === parsed.asset
        && a.trade.direction === parsed.direction
      ));
    }
    if (idx === -1) {
      log(`[ResultWatcher] no armed match for ${parsed.direction} ${parsed.asset} @$${parsed.amount ?? '?'} (queue=${this.armedQueue.length})`);
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
