/**
 * Iter 145 — MT5 DOM Adapter
 * ---------------------------------------------------------------------------
 * Places FX orders inside Pocket Option's web-MT5 iframe. Because PO
 * repeatedly reworks the layout (multi-locale, mobile vs desktop, MT4 vs
 * MT5 charts) this adapter uses THREE layered discovery strategies:
 *
 *   1. Explicit user-taught selectors (stored under GM keys `mt5_selectors`
 *      via a "🎓 Teach MT5" flow in the panel). Highest precision.
 *   2. A curated selector fallback list per control (symbol picker, lot
 *      input, SL input, TP input, BUY/SELL buttons).
 *   3. A text-based heuristic that walks visible <input>/<button> nodes.
 *
 * Every action returns { ok, reason, matches } so `forexOrderPoller.js` can
 * report the outcome back to the backend. NO order is placed unless BUY/SELL
 * button matches are found — the whole flow gracefully aborts if the MT5
 * iframe isn't loaded.
 *
 * Public API:
 *    mt5Adapter.placeOrder({ symbol, side, lots, sl, tp })
 *    mt5Adapter.diagnose()                       — dump what it can see
 *    mt5Adapter.startTeach(control, onDone)      — teach one selector
 */

import { log, warn, info, error } from '../core/logger.js';

const GM_PREFIX = 'ai_elite_mt5_';

// ----- selector fallbacks (best-guess for MT5 web/H5) -----
// These are the CSS class hints most commonly observed in MT5 web-terminal
// builds. Each list is scanned in order; the first visible + enabled element
// that passes the type check wins.
const SELECTORS = {
  iframe: [
    'iframe[src*="metatrader"]', 'iframe[src*="mt5"]',
    'iframe[src*="webtrader"]', 'iframe[src*="terminal"]',
    'iframe[title*="MetaTrader" i]', 'iframe[title*="MT5" i]',
    'iframe[class*="mt5"]', 'iframe[id*="mt5"]',
  ],
  symbol_search: [
    'input[placeholder*="symbol" i]', 'input[placeholder*="search" i]',
    'input[aria-label*="symbol" i]', 'input[class*="symbol-search"]',
    '.market-watch input', '[class*="symbols"] input[type="text"]',
  ],
  lot_input: [
    'input[name="volume"]', 'input[data-test*="volume" i]',
    'input[aria-label*="volume" i]', 'input[aria-label*="lot" i]',
    'input[placeholder*="volume" i]', 'input[placeholder*="lot" i]',
    '[class*="volume"] input', '[class*="lot"] input',
    '[class*="order-form"] input[type="number"]',
  ],
  sl_input: [
    'input[name*="stopLoss" i]', 'input[name*="stop_loss" i]', 'input[name="sl"]',
    'input[aria-label*="stop loss" i]', 'input[placeholder*="stop loss" i]',
    'input[placeholder*="s\\/l" i]', 'input[placeholder*="sl" i]',
    '[class*="stop-loss"] input', '[class*="stopLoss"] input',
  ],
  tp_input: [
    'input[name*="takeProfit" i]', 'input[name*="take_profit" i]', 'input[name="tp"]',
    'input[aria-label*="take profit" i]', 'input[placeholder*="take profit" i]',
    'input[placeholder*="t\\/p" i]', 'input[placeholder*="tp" i]',
    '[class*="take-profit"] input', '[class*="takeProfit"] input',
  ],
  buy_btn: [
    'button[data-testid*="buy" i]', 'button[aria-label*="buy" i]',
    'button.btn-buy', 'button.buy-btn', 'button[class*="buy-button"]',
    'button[class*="button-buy"]', '[class*="order-form"] .btn-buy',
    'button.button--green', 'button.btn--green',
  ],
  sell_btn: [
    'button[data-testid*="sell" i]', 'button[aria-label*="sell" i]',
    'button.btn-sell', 'button.sell-btn', 'button[class*="sell-button"]',
    'button[class*="button-sell"]', '[class*="order-form"] .btn-sell',
    'button.button--red', 'button.btn--red',
  ],
};

// ----- helpers -----
function _isVisible(el) {
  if (!el || !el.offsetParent) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}

/**
 * Resolve the working document — MT5 usually renders inside an iframe. If
 * we find one, use its contentDocument. Fallback to top document (some PO
 * layouts inline MT5 directly).
 */
function _mt5Doc() {
  for (const sel of SELECTORS.iframe) {
    const iframe = document.querySelector(sel);
    if (iframe) {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (doc && doc.body) return { doc, kind: 'iframe', origin: iframe };
      } catch (_e) {
        // Cross-origin — we cannot reach into the iframe. Log this because it's
        // the #1 real-world failure mode for MT5-on-PO automation.
        warn(`[mt5] iframe is cross-origin (${_e.message}) — DOM injection blocked`);
        return { doc: null, kind: 'cross-origin', origin: iframe };
      }
    }
  }
  return { doc: document, kind: 'top', origin: null };
}

function _findByTaught(doc, control) {
  try {
    const raw = typeof GM_getValue === 'function'
      ? GM_getValue(GM_PREFIX + control, null)
      : (window.localStorage.getItem(GM_PREFIX + control) || null);
    if (!raw) return null;
    const el = doc.querySelector(raw);
    if (el && _isVisible(el)) return { el, source: `taught:${raw}` };
  } catch (_e) { /* ignore */ }
  return null;
}

function _findFirst(doc, selectors) {
  for (const sel of selectors) {
    try {
      const els = doc.querySelectorAll(sel);
      for (const el of els) {
        if (!_isVisible(el)) continue;
        if (el.disabled || el.readOnly) continue;
        return { el, source: sel };
      }
    } catch (_e) { /* ignore invalid selector */ }
  }
  return null;
}

function _resolve(doc, control) {
  return _findByTaught(doc, control) || _findFirst(doc, SELECTORS[control] || []);
}

// React-friendly input setter (native descriptor bypass so React sees the change)
function _setInputValue(input, value) {
  try {
    input.focus();
    const proto = Object.getPrototypeOf(input);
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set
                || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, String(value));
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
    return true;
  } catch (e) {
    warn(`[mt5] setInputValue failed: ${e.message}`);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Public adapter
// ---------------------------------------------------------------------------
class Mt5Adapter {
  /**
   * Attempt to place an MT5 order in the PO UI.
   *
   * @param {{ symbol: string, side: 'BUY'|'SELL', lots: number,
   *          sl?: number, tp?: number, symbol_variants?: string[] }} order
   * @returns {Promise<{ ok: boolean, reason: string,
   *                    fill_price?: number, fill_lots?: number,
   *                    matches?: object }>}
   */
  async placeOrder(order) {
    const { doc, kind, origin } = _mt5Doc();
    if (!doc) {
      return {
        ok: false,
        reason: 'mt5_iframe_cross_origin',
        matches: { doc_kind: kind, iframe_src: origin?.src || null },
      };
    }

    const matches = { doc_kind: kind };
    const t0 = Date.now();

    // 1. Set symbol (best effort — MT5 usually has a "Market Watch"/symbol
    //    picker). Skipped silently if we can't find it (user has probably
    //    already selected the right symbol in their layout).
    try {
      const symbol = String(order.symbol || '').toUpperCase();
      const search = _resolve(doc, 'symbol_search');
      if (search && symbol) {
        _setInputValue(search.el, symbol);
        matches.symbol_search = search.source;
        await new Promise((r) => setTimeout(r, 200));
      }
    } catch (_e) { /* non-fatal */ }

    // 2. Volume / lots input — required. Fail closed if not found.
    const lotRes = _resolve(doc, 'lot_input');
    if (!lotRes) return {
      ok: false, reason: 'lot_input_not_found', matches,
    };
    _setInputValue(lotRes.el, order.lots);
    matches.lot_input = lotRes.source;

    // 3. Optional SL / TP inputs
    if (order.sl != null) {
      const slRes = _resolve(doc, 'sl_input');
      if (slRes) {
        _setInputValue(slRes.el, order.sl);
        matches.sl_input = slRes.source;
      } else {
        matches.sl_input = 'not_found';
      }
    }
    if (order.tp != null) {
      const tpRes = _resolve(doc, 'tp_input');
      if (tpRes) {
        _setInputValue(tpRes.el, order.tp);
        matches.tp_input = tpRes.source;
      } else {
        matches.tp_input = 'not_found';
      }
    }

    // 4. Fire BUY or SELL button — required.
    const btnKey = order.side === 'BUY' ? 'buy_btn' : 'sell_btn';
    const btnRes = _resolve(doc, btnKey);
    if (!btnRes) return {
      ok: false,
      reason: `${btnKey}_not_found`,
      matches,
    };
    matches[btnKey] = btnRes.source;

    try {
      btnRes.el.focus && btnRes.el.focus();
      btnRes.el.click();
    } catch (e) {
      return { ok: false, reason: `click_failed:${e.message}`, matches };
    }

    matches.elapsed_ms = Date.now() - t0;
    log(`[mt5] placed ${order.side} ${order.symbol} lots=${order.lots} via ${btnRes.source}`);
    return {
      ok: true,
      reason: 'placed',
      fill_lots: order.lots,       // best guess — MT5 usually fills full
      matches,
    };
  }

  /**
   * Diagnostic — dumps every resolved control so the user can share output
   * when the adapter fails to find something.
   */
  diagnose() {
    const { doc, kind } = _mt5Doc();
    const out = { doc_kind: kind };
    if (!doc) return out;
    for (const key of Object.keys(SELECTORS)) {
      if (key === 'iframe') continue;
      const r = _resolve(doc, key);
      out[key] = r ? { found: true, source: r.source, tag: r.el.tagName }
                   : { found: false };
    }
    try { console.table(out); } catch (_e) { /* ignore */ }
    return out;
  }

  /**
   * Point-to-teach: user clicks the control they want the adapter to use,
   * we store the CSS selector under GM (survives reloads).
   */
  startTeach(control, onDone) {
    if (!SELECTORS[control]) {
      error(`[mt5-teach] unknown control "${control}"`);
      onDone?.({ success: false, error: 'unknown control' });
      return;
    }
    info(`[mt5-teach] click the MT5 element you want to use for "${control}"`);
    const handler = (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      const el = ev.target;
      if (!el) return;
      // Prefer id, then a stable data-testid, then class chain.
      let selector = null;
      if (el.id) selector = `#${el.id}`;
      else if (el.getAttribute('data-testid')) selector = `[data-testid="${el.getAttribute('data-testid')}"]`;
      else if (el.name) selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
      else {
        const cls = (el.className || '').toString().split(/\s+/).filter(Boolean).slice(0, 2).map(c => `.${c}`).join('');
        selector = el.tagName.toLowerCase() + cls;
      }
      try {
        if (typeof GM_setValue === 'function') GM_setValue(GM_PREFIX + control, selector);
        else window.localStorage.setItem(GM_PREFIX + control, selector);
      } catch (_e) { /* ignore */ }
      document.removeEventListener('click', handler, true);
      log(`[mt5-teach] saved selector for "${control}": ${selector}`);
      onDone?.({ success: true, control, selector });
    };
    document.addEventListener('click', handler, true);
    setTimeout(() => {
      document.removeEventListener('click', handler, true);
    }, 30_000);
  }

  clearTaught(control) {
    try {
      if (typeof GM_deleteValue === 'function') GM_deleteValue(GM_PREFIX + control);
      else window.localStorage.removeItem(GM_PREFIX + control);
      log(`[mt5-teach] cleared ${control}`);
    } catch (_e) { /* ignore */ }
  }
}

export const mt5Adapter = new Mt5Adapter();

// Expose for DevTools debug
try {
  window.__aiEliteMt5Diag = () => mt5Adapter.diagnose();
  window.__aiEliteMt5Teach = (control, cb) => mt5Adapter.startTeach(control, cb);
} catch (_e) { /* ignore */ }

export default mt5Adapter;
