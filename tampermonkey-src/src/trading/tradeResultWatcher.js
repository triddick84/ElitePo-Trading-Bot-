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

// Iter 148 — Point-to-teach fallback so we're never blind to PO DOM changes.
// The user clicks one resolved WIN row and one resolved LOSS row; we
// capture (a) the row-level CSS class signature and (b) the parent
// container's selector. The watcher then checks those taught signatures
// FIRST, before every heuristic, guaranteeing correct outcome parsing on
// any PO layout the user has actually verified.
const TEACH_GM_KEYS = {
  win: 'ai_elite_teach_win_row',
  loss: 'ai_elite_teach_loss_row',
  container: 'ai_elite_teach_deal_container',
};

function _gmGet(key) {
  try {
    if (typeof GM_getValue === 'function') return GM_getValue(key, null);
    return window.localStorage.getItem(key);
  } catch (_e) { return null; }
}
function _gmSet(key, val) {
  try {
    if (typeof GM_setValue === 'function') GM_setValue(key, val);
    else window.localStorage.setItem(key, val);
  } catch (_e) { /* ignore */ }
}
function _gmDel(key) {
  try {
    if (typeof GM_deleteValue === 'function') GM_deleteValue(key);
    else window.localStorage.removeItem(key);
  } catch (_e) { /* ignore */ }
}

/** Extract a stable CSS-class signature from an element — 2-3 distinctive
 *  classes joined with dots. Filters out utility-noise classes (`ng-*`,
 *  `_ngcontent-*`, hashed CSS-in-JS blobs, etc). */
function _classSignature(el) {
  if (!el || !el.className) return '';
  const classes = String(el.className).split(/\s+/).filter((c) => {
    if (!c) return false;
    if (c.startsWith('_ng') || c.startsWith('ng-')) return false;
    if (/^[a-z0-9]{8,}$/.test(c)) return false;   // hashed CSS-in-JS
    return true;
  });
  return classes.slice(0, 3).join('.');
}

/** Cheap CSS-path builder for a taught element — walks up 4 ancestors
 *  keeping any tag with an id or a class signature. */
function _cssPath(el, maxDepth = 4) {
  const parts = [];
  let cur = el;
  for (let i = 0; i < maxDepth && cur && cur.nodeType === 1; i++) {
    let seg = cur.tagName.toLowerCase();
    if (cur.id) { seg += `#${cur.id}`; parts.unshift(seg); break; }
    const sig = _classSignature(cur);
    if (sig) seg += '.' + sig;
    parts.unshift(seg);
    cur = cur.parentElement;
  }
  return parts.join(' > ');
}

const DEAL_ROW_SELECTOR = [
  '.deals-list .deals-item',
  '[class*="closed-deals"] [class*="item"]',
  '[class*="deals-list"] > div',
  '[class*="deal-item"]',
  '[class*="history"] [class*="item"]',
  // Iter 144 — additional PO markup variants
  '[class*="trades-list"] [class*="trades-item"]',
  '[class*="trades-list"] > div',
  '[data-test*="deal" i]',
  '[class*="operation"] [class*="item"]',
  '[class*="portfolio"] [class*="row"]',
].join(', ');

/** Iter 144 — Wide-net fallback used when the CSS selectors return zero
 *  rows. Walks visible elements looking for anything whose text carries
 *  BOTH a direction indicator (▲▼ / UP-DOWN / CALL-PUT) AND a currency
 *  amount ($X.XX). Returns [] when nothing matches. */
function _wideNetDealRows() {
  try {
    const out = [];
    const seen = new WeakSet();
    const walker = document.querySelectorAll(
      'div, li, tr, span[class], article, section'
    );
    for (const el of walker) {
      if (seen.has(el)) continue;
      // Only look at leaf-ish rows — big containers have too much text
      const txt = (el.textContent || '').replace(/\s+/g, ' ');
      if (txt.length < 8 || txt.length > 400) continue;
      const hasDir = /\b(UP|DOWN|CALL|PUT|HIGHER|LOWER)\b/i.test(txt) || /[▲▼↑↓⬆⬇]/.test(txt);
      const hasMoney = /\$\s*\d/.test(txt);
      if (hasDir && hasMoney) {
        out.push(el);
        seen.add(el);
        if (out.length > 200) break;
      }
    }
    return out;
  } catch (_e) {
    return [];
  }
}

/** Normalize `EURUSD-OTC`, `EUR/USD OTC`, `EURUSDotc` → `EURUSDOTC` */
function _normAsset(a) {
  return String(a || '').toUpperCase().replace(/[\s/_-]/g, '');
}

/** Iter 144 — Minimal balance reader used ONLY as a last-resort resolver
 *  when the deal-row DOM parse failed AND the queue has exactly one arm
 *  (so the balance-delta is unambiguous). */
function _readBalance() {
  try {
    const selectors = [
      '.js-balance-demo-deposit',
      '.js-balance-real-balance',
      '[class*="balance"] [class*="value"]',
      '[class*="balance-value"]',
      '[data-test="balance"]',
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (!el) continue;
      const raw = (el.textContent || '').replace(/[^0-9.\-]/g, '');
      const v = parseFloat(raw);
      if (Number.isFinite(v)) return v;
    }
    return null;
  } catch (_e) { return null; }
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

    // Strategy 0 — Iter 148: taught class signatures win over every
    // heuristic. If the user has clicked "Teach WIN row" once, we know
    // the exact classes PO puts on winning rows for their layout.
    try {
      const taughtWin = _gmGet(TEACH_GM_KEYS.win);
      const taughtLoss = _gmGet(TEACH_GM_KEYS.loss);
      const rowCls = String(row.className || '').split(/\s+/);
      if (taughtWin) {
        const tokens = taughtWin.split('.').filter(Boolean);
        // Check the row's class list AND its descendants — some PO layouts
        // put the win/loss marker on a nested span not the row itself.
        const rowHas = tokens.every((t) => rowCls.includes(t));
        let descendantHas = false;
        if (!rowHas) {
          try { descendantHas = !!row.querySelector('.' + tokens.join('.')); }
          catch (_e) { /* invalid selector */ }
        }
        if (rowHas || descendantHas) isWin = true;
      }
      if (isWin === null && taughtLoss) {
        const tokens = taughtLoss.split('.').filter(Boolean);
        const rowHas = tokens.every((t) => rowCls.includes(t));
        let descendantHas = false;
        if (!rowHas) {
          try { descendantHas = !!row.querySelector('.' + tokens.join('.')); }
          catch (_e) { /* invalid selector */ }
        }
        if (rowHas || descendantHas) isWin = false;
      }
    } catch (_e) { /* never let taught-parse throw */ }

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
    // Iter 144 — also prime wide-net rows so a fallback discovery doesn't
    // treat existing history as "new" trades.
    _wideNetDealRows().forEach(r => this.seenRows.add(_rowId(r)));
    this._installObserver();
    // Iter 144 — expose diagnostic helper for the user to run in DevTools.
    try {
      if (typeof window !== 'undefined') {
        window.__aiEliteDealDiag = () => this._diag();
        // Iter 148 — teach helpers on window for power users
        window.__aiEliteTeachWin = (cb) => this.startTeach('win', cb);
        window.__aiEliteTeachLoss = (cb) => this.startTeach('loss', cb);
        window.__aiEliteTeachDealContainer = (cb) => this.startTeach('container', cb);
        window.__aiEliteClearTeach = (kind) => this.clearTaught(kind);
        window.__aiEliteGetTaught = () => this.getTaught();
      }
    } catch (_e) { /* ignore */ }
    success('[ResultWatcher] enabled — multi-trade queue with wide-net fallback');
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
    // Iter 144 — also prime wide-net so a discovery fallback sees only NEW rows
    _wideNetDealRows().forEach(r => this.seenRows.add(_rowId(r)));

    // Iter 144 — snapshot balance for the delta-fallback (used only when
    // the queue holds exactly ONE arm at the timeout moment).
    try {
      arm.balanceAtArm = _readBalance();
    } catch (_e) { arm.balanceAtArm = null; }

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
    // Iter 148 — taught deal-container has TOP priority. When the user has
    // clicked "Teach Container" once, we know exactly which node holds
    // deal rows on THEIR PO layout — no heuristic scan needed.
    const taughtContainer = _gmGet(TEACH_GM_KEYS.container);
    if (taughtContainer) {
      try {
        const container = document.querySelector(taughtContainer);
        if (container) {
          // Direct children first — the deal-row layer is almost always
          // a direct child pattern. Fall back to `[class]` descendants
          // when there are none (accordions, virtualised lists).
          rows = Array.from(container.children || []);
          if (!rows.length) rows = Array.from(container.querySelectorAll('[class]'));
        }
      } catch (_e) { /* invalid taught selector */ }
    }
    if (!rows) {
      try { rows = Array.from(document.querySelectorAll(DEAL_ROW_SELECTOR)); }
      catch (_e) { rows = []; }
    }
    // Iter 144 — CSS selectors returned nothing? Fall back to a full-DOM
    // heuristic sweep. The moment ANY row parses, we log the winning
    // element so a future selector list update targets it precisely.
    if (rows.length === 0) {
      rows = _wideNetDealRows();
      if (rows.length && !this._widenetLogged) {
        this._widenetLogged = true;
        log(`[ResultWatcher] CSS selectors matched 0 rows — using wide-net fallback (${rows.length} candidates)`);
      }
    }
    let matched = 0;
    for (const row of rows) {
      const id = _rowId(row);
      if (this.seenRows.has(id)) continue;
      const parsed = _parseDealRow(row);
      if (!parsed) continue;
      if (parsed.isWin === null) {
        log(`[ResultWatcher] deferring row (no outcome yet) — ${parsed.direction} ${parsed.asset}`);
        continue;
      }
      this.seenRows.add(id);
      this._matchAndResolve(parsed, row);
      matched++;
    }
    // Iter 144 — expose the last scan for diagnostics
    this._lastScan = {
      css_matches: rows.length,
      resolved_this_tick: matched,
      queue_len: this.armedQueue.length,
      at: Date.now(),
    };
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

    // Iter 151b — EARLY balance-delta resolution. Previously we only used
    // balance-delta at the arm's deadline (expiry + 4 s safety buffer),
    // meaning users saw NO win/loss for 4 s minimum after every trade,
    // even when the balance had already moved. Now: as soon as expiry
    // has elapsed AND the queue has exactly one un-resolved arm, resolve
    // on the first cent of balance change. Safe because with a single
    // arm there's no other trade whose stake/payout could conflate the
    // delta.
    const unresolved = this.armedQueue.filter((a) => !a.resolved);
    if (unresolved.length === 1) {
      const arm = unresolved[0];
      const expiryMs = (Number(arm.trade.expirySeconds) || 5) * 1000;
      const expiryPassed = now > (arm.armedAt + expiryMs);
      if (expiryPassed && arm.balanceAtArm != null) {
        const bal = _readBalance();
        if (bal != null && Math.abs(bal - arm.balanceAtArm) >= 0.01) {
          const isWin = bal > arm.balanceAtArm;
          log(`[ResultWatcher] early balance-delta resolve: ${arm.trade.direction} ${arm.trade.asset} · $${arm.balanceAtArm.toFixed(2)} → $${bal.toFixed(2)}`);
          this._resolve(arm, isWin, 'balance-delta-early');
          this.armedQueue = this.armedQueue.filter((a) => !a.resolved);
        }
      }
    }

    // Timeout expired arms (kept as the last-ditch resolver)
    const still = [];
    for (const arm of this.armedQueue) {
      if (arm.resolved) continue;
      if (now > arm.deadline) {
        // Iter 144 — balance-delta LAST RESORT fallback. Only safe when
        // this arm is the ONLY one currently timing out (else deltas can
        // conflate different trades). Uses the pre-arm balance snapshot.
        const isSoloTimeout = this.armedQueue.filter((a) => !a.resolved && now > a.deadline).length === 1;
        if (isSoloTimeout && arm.balanceAtArm != null) {
          const bal = _readBalance();
          if (bal != null && Math.abs(bal - arm.balanceAtArm) >= 0.01) {
            const isWin = bal > arm.balanceAtArm;
            log(`[ResultWatcher] resolved via balance-delta fallback: ${arm.trade.direction} ${arm.trade.asset} · $${arm.balanceAtArm.toFixed(2)} → $${bal.toFixed(2)}`);
            this._resolve(arm, isWin, 'balance-delta-fallback');
            continue;
          }
        }
        // Iter 151b — extra-loud timeout log so the user knows to run the
        // teach flow. Includes selector match counts to make the fix path
        // obvious.
        warn(
          `[ResultWatcher] TIMEOUT — no outcome for ${arm.trade.direction} ${arm.trade.asset}. ` +
          `Run __aiEliteDealDiag() in DevTools OR use the "Win/Loss Detection Teach" section in the panel's Forex tab.`
        );
        this._timeoutCount = (this._timeoutCount || 0) + 1;
        if (ABANDON_AFTER_TIMEOUT) {
          this._resolve(arm, false, 'timeout-loss');
        }
        continue;
      }
      still.push(arm);
    }
    this.armedQueue = still;

    // Iter 151b — bound seenRows so it can't grow unbounded during long
    // sessions (PO recycles rows; stale ids stay forever otherwise).
    if (this.seenRows.size > 500) {
      const arr = Array.from(this.seenRows);
      this.seenRows = new Set(arr.slice(-250));
    }
  }

  /** Iter 144 — Diagnostic snapshot for `window.__aiEliteDealDiag()`.
   *  Run this in DevTools while a resolved trade is visible; share the
   *  output so we can tighten selectors for your PO layout. */
  _diag() {
    let cssRows = [];
    try { cssRows = Array.from(document.querySelectorAll(DEAL_ROW_SELECTOR)); }
    catch (_e) { /* ignore */ }
    const wideRows = _wideNetDealRows();
    const sample = (rows, k = 3) => rows.slice(-k).map((r) => ({
      tag: r.tagName,
      class: (r.className || '').toString().slice(0, 120),
      text: (r.textContent || '').replace(/\s+/g, ' ').slice(0, 160),
      parsed: _parseDealRow(r),
    }));
    return {
      enabled: this.enabled,
      queue: this.getQueueSnapshot(),
      last_scan: this._lastScan || null,
      css_selector: DEAL_ROW_SELECTOR,
      css_matches: cssRows.length,
      widenet_matches: wideRows.length,
      balance_now: _readBalance(),
      // Iter 148 — surface taught markers so the diag output makes it
      // obvious whether the user has completed the teach flow.
      taught: this.getTaught(),
      sample_css: sample(cssRows),
      sample_widenet: sample(wideRows),
    };
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

  // ─────────────────────────────────────────────────────────────────────
  // Iter 148 — Point-to-teach fallback for win/loss detection
  // ─────────────────────────────────────────────────────────────────────

  /** Start a click-capture; next element the user clicks gets stored under
   *  the appropriate GM key. Kind must be one of 'win' | 'loss' | 'container'.
   *  `onDone` receives { success, kind, selector, classSig }. */
  startTeach(kind, onDone) {
    if (!TEACH_GM_KEYS[kind]) {
      onDone?.({ success: false, error: `unknown teach kind "${kind}"` });
      return;
    }
    info(`[teach] click a resolved ${kind.toUpperCase()} element in your PO deal history (within 30 s)`);
    const handler = (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      document.removeEventListener('click', handler, true);
      let el = ev.target;
      // Walk up to find the enclosing row-ish element for win/loss (not for container)
      if (kind !== 'container') {
        let cur = el, hops = 0;
        while (cur && hops < 6 && cur.tagName !== 'BODY') {
          const txt = (cur.textContent || '').replace(/\s+/g, ' ');
          if (txt.length > 8 && txt.length < 400) { el = cur; break; }
          cur = cur.parentElement; hops++;
        }
      }
      const classSig = _classSignature(el);
      const path = _cssPath(el);
      // Store the class signature for win/loss (used in _parseDealRow) and
      // the full CSS path for the container.
      const val = kind === 'container' ? path : classSig || path;
      if (!val) {
        onDone?.({ success: false, error: 'element has no distinguishing classes' });
        return;
      }
      _gmSet(TEACH_GM_KEYS[kind], val);
      success(`[teach] saved ${kind} → ${val}`);
      onDone?.({ success: true, kind, selector: val, classSig, path });
    };
    document.addEventListener('click', handler, true);
    setTimeout(() => document.removeEventListener('click', handler, true), 30_000);
  }

  /** Wipe one taught marker (or all when kind omitted). */
  clearTaught(kind) {
    if (!kind) {
      Object.values(TEACH_GM_KEYS).forEach(_gmDel);
      log('[teach] cleared ALL taught markers');
      return;
    }
    if (!TEACH_GM_KEYS[kind]) return;
    _gmDel(TEACH_GM_KEYS[kind]);
    log(`[teach] cleared ${kind}`);
  }

  /** Current taught markers snapshot for the UI. */
  getTaught() {
    return {
      win: _gmGet(TEACH_GM_KEYS.win),
      loss: _gmGet(TEACH_GM_KEYS.loss),
      container: _gmGet(TEACH_GM_KEYS.container),
    };
  }

  /**
   * Iter 151b — Watcher health snapshot for the UI. Used by the panel to
   * surface a "🔴 detection unhealthy — please teach" indicator when
   * repeated timeouts happen.
   */
  getStats() {
    const queueLen = this.armedQueue.filter((a) => !a.resolved).length;
    const timeoutCount = this._timeoutCount || 0;
    return {
      enabled: !!this.enabled,
      queueLength: queueLen,
      timeoutCount,
      seenRowsSize: this.seenRows.size,
      // "healthy" ⇔ enabled and never timed out in this session
      healthy: !!this.enabled && timeoutCount === 0,
    };
  }
}

export const tradeResultWatcher = new TradeResultWatcher();
export default tradeResultWatcher;
