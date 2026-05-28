/**
 * DOM utilities for interacting with Pocket Option interface
 */

import { log, warn } from '../core/logger.js';

/**
 * Wait for an element to appear in the DOM
 * @param {string} selector - CSS selector
 * @param {number} timeout - Timeout in ms
 * @returns {Promise<Element|null>}
 */
export function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    let observer = null;
    let timeoutId = null;
    const cleanup = () => {
      try { observer && observer.disconnect(); } catch (_e) { /* ignore */ }
      if (timeoutId) clearTimeout(timeoutId);
    };

    const startObserver = () => {
      // documentElement is always present (even at @run-at document-start)
      const target = document.documentElement || document;
      observer = new MutationObserver(() => {
        const el = document.querySelector(selector);
        if (el) {
          cleanup();
          resolve(el);
        }
      });
      try {
        observer.observe(target, { childList: true, subtree: true });
      } catch (e) {
        // Extremely early — fall back to polling
        const pollId = setInterval(() => {
          const el = document.querySelector(selector);
          if (el) {
            clearInterval(pollId);
            cleanup();
            resolve(el);
          }
        }, 50);
        timeoutId = setTimeout(() => {
          clearInterval(pollId);
          cleanup();
          resolve(null);
        }, timeout);
        return;
      }
    };

    // If the DOM isn't even ready yet (@run-at document-start), wait for it.
    if (!document.documentElement) {
      document.addEventListener('readystatechange', startObserver, { once: true });
    } else {
      startObserver();
    }

    timeoutId = setTimeout(() => {
      cleanup();
      resolve(null);
    }, timeout);
  });
}

/**
 * Normalize a PO asset name to the canonical backend format.
 *   "USD/IDR OTC" -> "USDIDR_OTC"
 *   "EUR/USD"     -> "EURUSD"
 *   "USDIDR_otc"  -> "USDIDR_OTC"
 */
export function normalizeAssetName(raw) {
  if (!raw) return raw;
  let s = String(raw).trim().toUpperCase();
  // Strip slashes, spaces, dashes
  s = s.replace(/[\s\-/]+/g, '');
  // Detect OTC suffix in any form ("OTC" at end with or without underscore)
  let isOtc = false;
  if (s.endsWith('OTC')) {
    isOtc = true;
    s = s.slice(0, -3).replace(/_+$/, '');
  }
  // Reapply canonical OTC suffix
  if (isOtc) s = s + '_OTC';
  return s;
}

/**
 * Get current asset from Pocket Option UI
 * @returns {string|null} Asset symbol (normalized: e.g. "USDIDR_OTC")
 */
export function getCurrentAsset() {
  const raw = _getCurrentAssetRaw();
  return raw ? normalizeAssetName(raw) : null;
}

/**
 * Get current asset as-displayed (UN-normalized, for UI/logs).
 * @returns {string|null}
 */
export function getCurrentAssetRaw() {
  return _getCurrentAssetRaw();
}

function _getCurrentAssetRaw() {
  // Method 1: Try specific selectors
  const selectors = [
    '.pair-title',
    '.asset-name',
    '[data-testid="asset-name"]',
    '.trading-pair-name',
    '.chart-header-pair',
    '.current-symbol',
    '.symbol-name',
    '.current-symbol span.symbol',
    '.pair-select__value',
    '[class*="pair-title"]',
    '[class*="asset-name"]',
    '[class*="symbol"]',
  ];
  
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent) {
      const text = el.textContent.trim();
      if (text.includes('/') || text.includes('USD') || text.includes('EUR') || text.includes('GBP') || text.includes('JPY') || text.includes('AUD') || text.includes('NZD') || text.includes('CHF') || text.includes('CAD')) {
        return text;
      }
    }
  }

  // Method 2: Search visible elements for currency pair patterns
  const allElements = document.querySelectorAll('*');
  for (const el of allElements) {
    if (!el || !el.offsetParent) continue;
    if (el.children.length > 3) continue;

    const text = (el.textContent || '').trim();
    if (text.length >= 6 && text.length <= 20) {
      // Exact pair patterns: "EUR/USD" or "EUR/USD OTC" or "EURUSD_OTC"
      const pairPattern = /^[A-Z]{3}\/[A-Z]{3}(\s*OTC)?$/i;
      const compactPattern = /^[A-Z]{6}(_OTC)?$/i;

      if (pairPattern.test(text) || compactPattern.test(text)) {
        try {
          const rect = el.getBoundingClientRect();
          if (rect.top < 150 && rect.width > 50) {
            return text;
          }
        } catch (e) { /* ignore */ }
      }

      // Also match "XXX/XXX" anywhere in text, near top of page
      const match = text.match(/([A-Z]{3})\/([A-Z]{3})/i);
      if (match) {
        try {
          const rect = el.getBoundingClientRect();
          if (rect.top < 200 && rect.top > 0) {
            return match[0] + (text.toLowerCase().includes('otc') ? ' OTC' : '');
          }
        } catch (e) { /* ignore */ }
      }
    }
  }

  // Method 3: Check page title
  const title = document.title;
  const titleMatch = title.match(/([A-Z]{3})\/([A-Z]{3})/i);
  if (titleMatch) {
    return titleMatch[0];
  }

  // Method 4: Check URL
  const url = window.location.href;
  const urlMatch = url.match(/[?&]asset=([^&]+)/);
  if (urlMatch) {
    return decodeURIComponent(urlMatch[1]);
  }

  // Default fallback
  return 'EUR/USD OTC';
}

/**
 * Get current price from Pocket Option UI
 * @returns {number|null} Current price
 */
export function getCurrentPrice() {
  // Try multiple selectors for price display
  const priceSelectors = [
    '.current-price',
    '.price-value',
    '[data-testid="current-price"]',
    '.chart-price',
    '.bid-price',
    '.ask-price',
    '.current-symbol-price',
    '.quotation-price',
    '[class*="price"]',
    '[class*="quote"]',
  ];
  
  for (const sel of priceSelectors) {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      if (!el || !el.offsetParent) continue;
      const text = (el.textContent || '').trim();
      // Match forex price patterns like "1.08234" or "108.234"
      const priceMatch = text.match(/(\d+\.\d{3,5})/);
      if (priceMatch) {
        const price = parseFloat(priceMatch[1]);
        if (price > 0.1 && price < 200000) {
          return price;
        }
      }
    }
  }
  
  // Search in chart area elements
  const chartArea = document.querySelector('[class*="chart"]');
  if (chartArea) {
    const priceElements = chartArea.querySelectorAll('text, span, div');
    for (const el of priceElements) {
      const text = (el.textContent || '').trim();
      const priceMatch = text.match(/^(\d+\.\d{3,5})$/);
      if (priceMatch) {
        const price = parseFloat(priceMatch[1]);
        if (price > 0.1 && price < 200000) {
          return price;
        }
      }
    }
  }
  
  return null;
}

/**
 * Get current payout percentage
 * @returns {number|null} Payout percentage
 */
export function getPayout() {
  const selectors = [
    '.payout-value',
    '[data-testid="payout"]',
    '.profit-percent',
    '.option-payout',
  ];
  
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) {
      const text = el.textContent.trim().replace(/[^0-9]/g, '');
      const payout = parseInt(text);
      if (!isNaN(payout) && payout > 0 && payout <= 100) {
        return payout;
      }
    }
  }
  
  return 80; // Default payout
}

/**
 * Set trade amount in Pocket Option UI
 * @param {number} amount - Trade amount
 * @returns {boolean} Success
 */
export function setTradeAmount(amount) {
  // Iter 64: cast a much wider net — PO uses many class variants across themes
  // and mobile/desktop layouts. Selector list ordered by specificity.
  const selectors = [
    'input.amount-input',
    '[data-testid="trade-amount"]',
    '.deal-amount input',
    // Modern PO layouts (April 2026)
    'input.input-control__input',
    'input[class*="amount"]',
    'input[class*="invest"]',
    'input[class*="bet"]',
    'input[class*="deal"]',
    '[class*="amount"] input[type="text"]',
    '[class*="amount"] input[type="number"]',
    '[class*="invest"] input',
    '[class*="bet"] input',
    '[class*="deal"] input',
    '[class*="trade"] input[type="number"]',
    // Generic — the trade amount input is usually the numeric one nearest the BUY/SELL buttons
    'input[type="number"]',
  ];

  let input = null;
  for (const sel of selectors) {
    const candidates = document.querySelectorAll(sel);
    for (const cand of candidates) {
      // Must be visible
      if (!cand.offsetParent || cand.disabled || cand.readOnly) continue;
      // Skip the bot's OWN amount input (lives inside the panel host)
      if (cand.closest('[id^="el-bot-"]')) continue;
      // Skip TIME/expiry inputs (often a sibling)
      const ph = (cand.placeholder || '').toLowerCase();
      const aria = (cand.getAttribute('aria-label') || '').toLowerCase();
      if (/time|expir|second|hour|minute|sec|min/.test(ph + ' ' + aria)) continue;
      // Heuristic: existing value should look like a money amount (1–10000)
      const v = parseFloat(cand.value);
      if (Number.isFinite(v) && (v < 1 || v > 100000)) continue;
      input = cand;
      break;
    }
    if (input) break;
  }

  if (!input) {
    warn(`Trade amount input not found (tried ${selectors.length} selectors)`);
    return false;
  }

  // Set value via React-friendly native setter
  try {
    input.focus();
    const proto = Object.getPrototypeOf(input);
    const setValue = Object.getOwnPropertyDescriptor(proto, 'value')?.set
                  || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setValue.call(input, amount.toString());
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
  } catch (e) {
    warn(`setTradeAmount native setter failed: ${e.message}`);
    return false;
  }

  log(`Set trade amount: $${amount}`);
  return true;
}

/**
 * Strict CALL/PUT button matcher — avoids false positives like 'up'grade,
 * s'up'port, drop'down', 'call' support, etc.
 *
 * A button qualifies as CALL/PUT if ANY of:
 *  - Exact text match: "call", "put", "buy", "sell", "higher", "lower"
 *  - Class contains a known PO indicator: btn-call, btn-put, call-btn, put-btn,
 *    button--up, button--down, pay__button--call, pay__button--put
 *  - data-testid / aria-label has an exact match
 *  - Button is green (CALL) or red (PUT) AND has ▲/▼ arrow text
 *
 * Ignores anything in top-nav / header / sidebar.
 */
const CALL_CLASS_HINTS = [
  'btn-call', 'btn_call', 'button-call', 'button_call',
  'call-btn', 'call_btn', 'callbtn',
  'button--up', 'button--green', 'pay__button--call',
  'payout__button--call', 'trade-button--call', 'trade__button--call',
];
const PUT_CLASS_HINTS = [
  'btn-put', 'btn_put', 'button-put', 'button_put',
  'put-btn', 'put_btn', 'putbtn',
  'button--down', 'button--red', 'pay__button--put',
  'payout__button--put', 'trade-button--put', 'trade__button--put',
];
const CALL_TEXT_EXACT = new Set(['call', 'buy', 'higher', 'up ▲', '▲', 'higher ▲']);
const PUT_TEXT_EXACT = new Set(['put', 'sell', 'lower', 'down ▼', '▼', 'lower ▼']);

function _isInsideNav(el) {
  try {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      const cls = ((cur.className || '') + '').toLowerCase();
      const tag = (cur.tagName || '').toLowerCase();
      if (tag === 'header' || tag === 'nav') return true;
      if (/\b(header|navbar|nav-|top-menu|sidebar|footer|menu-item|menu_item)\b/.test(cls)) return true;
      cur = cur.parentElement;
    }
  } catch (_e) { /* ignore */ }
  return false;
}

function _findTradeButton(direction) {
  const isCall = direction === 'CALL';
  const classHints = isCall ? CALL_CLASS_HINTS : PUT_CLASS_HINTS;
  const exactText = isCall ? CALL_TEXT_EXACT : PUT_TEXT_EXACT;

  // 1. Strict class-based match (most reliable — PO's own class naming)
  try {
    for (const hint of classHints) {
      const el = document.querySelector(`[class*="${hint}"]`);
      if (el && el.offsetParent && !_isInsideNav(el)) {
        return { el, reason: `class:${hint}` };
      }
    }
  } catch (_e) { /* ignore */ }

  // 2. data-testid / aria-label exact match
  try {
    const testIdSel = isCall
      ? '[data-testid="call"],[data-testid="CALL"],[data-testid="buy"],[data-testid="higher"],[aria-label="CALL" i],[aria-label="Buy" i],[aria-label="Higher" i]'
      : '[data-testid="put"],[data-testid="PUT"],[data-testid="sell"],[data-testid="lower"],[aria-label="PUT" i],[aria-label="Sell" i],[aria-label="Lower" i]';
    const el = document.querySelector(testIdSel);
    if (el && el.offsetParent && !_isInsideNav(el)) {
      return { el, reason: 'testid/aria' };
    }
  } catch (_e) { /* ignore */ }

  // 3. Strict text match inside an actionable element
  try {
    const buttons = document.querySelectorAll('button, .btn, [role="button"], [class*="btn"]:not(nav *):not(header *)');
    for (const btn of buttons) {
      if (!btn.offsetParent) continue;
      if (_isInsideNav(btn)) continue;
      const t = (btn.textContent || '').trim().toLowerCase();
      if (t.length > 16) continue;  // buttons should be short
      if (exactText.has(t)) return { el: btn, reason: `text:${t}` };
    }
  } catch (_e) { /* ignore */ }

  // 4. Color-based fallback (green for CALL, red for PUT) restricted to trade area
  try {
    const tradeArea = document.querySelector(
      '[class*="trade-control"],[class*="trading-panel"],[class*="pay"],[class*="payout"],[class*="deal"],[class*="bet"]'
    );
    if (tradeArea) {
      const all = tradeArea.querySelectorAll('button, [role="button"], [class*="btn"]');
      const wantColor = isCall ? 'green' : 'red';
      for (const btn of all) {
        if (!btn.offsetParent) continue;
        const cls = ((btn.className || '') + '').toLowerCase();
        if (cls.includes(wantColor)) return { el: btn, reason: `colour:${wantColor}` };
        try {
          const bg = (window.getComputedStyle(btn).backgroundColor || '').toLowerCase();
          // Crude green/red detection from computed bg
          const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
          if (m) {
            const r = +m[1], g = +m[2], b = +m[3];
            if (isCall && g > 150 && g > r + 40 && g > b + 40) return { el: btn, reason: 'rgb:green' };
            if (!isCall && r > 150 && r > g + 40 && r > b + 40) return { el: btn, reason: 'rgb:red' };
          }
        } catch (_e) { /* ignore */ }
      }
    }
  } catch (_e) { /* ignore */ }

  return null;
}

/**
 * Click CALL button
 * @returns {boolean} Success
 */
export function clickCall() {
  const found = _findTradeButton('CALL');
  if (!found) {
    warn('CALL button not found (strict match). Try pointing bot at the Quick-Trade page or share a DOM dump.');
    return false;
  }
  try {
    // Fire a full click sequence (some PO builds require pointer events)
    found.el.focus && found.el.focus();
    found.el.click();
    log(`Clicked CALL button [${found.reason}]`);
    return true;
  } catch (e) {
    warn(`CALL click failed: ${e.message}`);
    return false;
  }
}

/**
 * Click PUT button
 * @returns {boolean} Success
 */
export function clickPut() {
  const found = _findTradeButton('PUT');
  if (!found) {
    warn('PUT button not found (strict match). Try pointing bot at the Quick-Trade page or share a DOM dump.');
    return false;
  }
  try {
    found.el.focus && found.el.focus();
    found.el.click();
    log(`Clicked PUT button [${found.reason}]`);
    return true;
  } catch (e) {
    warn(`PUT click failed: ${e.message}`);
    return false;
  }
}

/**
 * Execute a trade on Pocket Option
 * @param {string} direction - 'CALL' or 'PUT'
 * @param {number} amount - Trade amount (optional)
 * @returns {boolean} Success
 */
/**
 * Execute a trade on Pocket Option.
 * Iter 65: amount parameter intentionally ignored — user sets the trade
 * amount manually in PO's UI. The bot only clicks CALL / PUT.
 * @param {string} direction - 'CALL' or 'PUT'
 * @returns {boolean} Success
 */
export function executeTrade(direction /* , amount = null */) {
  return new Promise((resolve) => {
    setTimeout(() => {
      const success = direction.toUpperCase() === 'CALL' ? clickCall() : clickPut();
      resolve(success);
    }, 100);
  });
}

/**
 * Get favorites bar assets
 * @returns {string[]} Array of asset symbols
 */
/**
 * Scrape the favorites bar / favorites panel for the asset symbols the user
 * has pinned. Falls through multiple selector families because Pocket Option
 * has rewritten this part of the UI several times.
 *
 * Strategy:
 *   1. Try known class names (legacy + current)
 *   2. Try a structural scan: the favorites container is usually the topmost
 *      horizontal asset bar; symbols look like "EUR/USD OTC" or "GBPJPY"
 *   3. De-duplicate and normalize to the underscore-OTC format the rest of
 *      the codebase uses.
 *
 * Returns an array of normalized symbols, e.g. ["EURUSD_OTC", "GBPJPY_OTC"].
 */
export function getFavorites() {
  const favorites = [];
  const seen = new Set();

  const pushSymbol = (raw) => {
    if (!raw) return;
    const cleaned = raw
      .replace(/\d+%/g, '')              // strip payout % numbers
      .replace(/\s+/g, ' ')
      .trim();
    if (!cleaned) return;
    // Normalize: "EUR/USD OTC" → "EURUSD_OTC", "GBPJPY OTC" → "GBPJPY_OTC"
    const normalized = normalizeAssetName(cleaned);
    if (!normalized || seen.has(normalized)) return;
    // Sanity check: must have at least 6 letters before _OTC suffix or be
    // a recognised crypto/index/commodity code (≥3 chars)
    const symPart = normalized.replace(/_OTC$/, '');
    if (symPart.length < 3 || /[^A-Z0-9]/.test(symPart)) return;
    seen.add(normalized);
    favorites.push(normalized);
  };

  // 1. Known selector families — try each in order
  const SELECTOR_GROUPS = [
    '.favorites-panel .asset-item',
    '.favorites .pair-item',
    '[data-testid="favorite-asset"]',
    '.assets-block__favorites .symbol',
    '.assets-block__favorites [class*="symbol"]',
    '.assets-bar .asset-item',
    '.assets-bar [class*="favorite"]',
    '[class*="favorit"][class*="asset"]',
    '[class*="favorit"][class*="symbol"]',
    '[class*="assets-favorit"] [class*="symbol"]',
    '[class*="assets-favorit"] [class*="text"]',
    '[class*="assets-favorit"] li',
    'header [class*="symbol"]',
    '[class*="header"] [class*="symbol"]',
    'div[class*="symbols"] [class*="item"]',
  ];

  for (const sel of SELECTOR_GROUPS) {
    const items = document.querySelectorAll(sel);
    if (!items || items.length === 0) continue;
    items.forEach((el) => {
      const txt = el.textContent || '';
      pushSymbol(txt);
    });
    if (favorites.length > 0) {
      // log(`[favorites] selector '${sel}' returned ${favorites.length} symbols`);
      break;
    }
  }

  // 2. Structural fallback: walk leaf elements at the top of the page that
  //    look like asset-symbol labels.
  if (favorites.length === 0) {
    try {
      const candidates = document.querySelectorAll('div, span, li, button, a');
      const symbolRe = /^([A-Z]{2,4}\/?[A-Z]{2,4})(\s+OTC)?\b/;
      let scanned = 0;
      for (const el of candidates) {
        if (scanned > 800) break;       // bound work — large pages
        scanned++;
        if (el.children.length > 0) continue;  // leaf only
        const txt = (el.textContent || '').trim();
        if (!txt || txt.length > 18) continue;
        if (symbolRe.test(txt)) {
          pushSymbol(txt);
          if (favorites.length >= 12) break;
        }
      }
      if (favorites.length > 0) {
        log(`[favorites] structural fallback picked up ${favorites.length} symbols`);
      }
    } catch (_e) { /* ignore */ }
  }

  return favorites;
}

/**
 * Switch to a different asset (clicks favorites bar or uses search).
 * @param {string} symbol - normalized asset (e.g. "EURUSD_OTC")
 * @returns {boolean} Success
 */
export function switchAsset(symbol) {
  const target = (symbol || '').toUpperCase().replace(/_OTC$/, '');
  // Build text variants we'll match against
  const variants = new Set();
  variants.add(target);
  if (target.length === 6) variants.add(`${target.slice(0, 3)}/${target.slice(3)}`);
  variants.add(`${target} OTC`);
  if (target.length === 6) variants.add(`${target.slice(0, 3)}/${target.slice(3)} OTC`);

  // Walk up to find a clickable ancestor, preferring elements that have a
  // React __reactProps$ onClick (Iter 63) — favorite slot tiles in PO have
  // the actual handler on the OUTER tile div, not the inner text element.
  const findClickableParent = (el) => {
    let cur = el;
    let bestReactTarget = null;     // highest-up element with a React onClick
    let bestStructuralTarget = el;  // first ancestor matching tag/role/class
    let foundStructural = false;

    for (let i = 0; i < 12 && cur; i++) {
      // 1) React-handler match (best candidate — explicit onClick on this DOM node)
      try {
        const propsKey = Object.keys(cur).find(k => k.startsWith('__reactProps$'));
        if (propsKey && cur[propsKey] && (
          typeof cur[propsKey].onClick === 'function' ||
          typeof cur[propsKey].onMouseDown === 'function' ||
          typeof cur[propsKey].onPointerDown === 'function'
        )) {
          // Always prefer the OUTERMOST React-handler element within 12 levels
          bestReactTarget = cur;
        }
      } catch (_e) { /* ignore */ }

      // 2) Structural match (fallback for non-React listeners or asset slots)
      if (!foundStructural) {
        const role = cur.getAttribute && cur.getAttribute('role');
        const tag = cur.tagName;
        const cls = (cur.className || '').toString();
        if (
          tag === 'A' || tag === 'BUTTON' || tag === 'LI' ||
          role === 'button' || role === 'tab' ||
          /asset-item|favorit|symbol-item|pair-item|tabs__item|asset-slot|asset-tab|active-asset|trading-pair|chart-tab/i.test(cls)
        ) {
          bestStructuralTarget = cur;
          foundStructural = true;
        }
      }
      cur = cur.parentElement;
    }
    return bestReactTarget || bestStructuralTarget;
  };

  // Aggressive React-friendly click (Iter 62, Apr 25, 2026):
  // 1) Walk full fiber chain (16 levels), collect EVERY onClick / onMouseDown / onPointerDown
  //    handler, invoke each in order. Real PO favorite items have onClick on
  //    multiple ancestors (anchor, list-item, container) — invoking only one
  //    sometimes misses the actual React handler that updates the asset.
  // 2) Dispatch a FULL pointer+mouse+touch event sequence at the element's
  //    actual screen coordinates (not 0,0) — some React handlers check
  //    clientX/Y > 0 and isTrusted-like conditions through PointerEvent.
  // 3) Fall back to a synthesized hit-test via elementsFromPoint at the
  //    element center if direct dispatch silently fails.
  const reactClick = (target) => {
    if (!target) return;

    // v8.49.0: Same hard safety net as _reactClickEl — block clicks on
    // TOP UP / DEPOSIT / PROFILE / wallet chrome. This path is used by
    // switchAsset's slot-tile match and retry logic.
    const FORBIDDEN_RE = /\b(TOP[\s-]?UP|DEPOSIT|WITHDRAW|TOPUP|PROFILE|ACCOUNT|SIGN\s*OUT|LOGOUT|CASHIER|WALLET)\b/i;
    try {
      let cur = target;
      for (let i = 0; i < 4 && cur; i++) {
        const txt = (cur.textContent || '').trim();
        if (txt.length > 0 && txt.length < 60 && FORBIDDEN_RE.test(txt)) {
          warn(`[switchAsset] BLOCKED forbidden click: "${txt.slice(0, 40)}"`);
          return;
        }
        cur = cur.parentElement;
      }
      let cur2 = target;
      for (let i = 0; i < 6 && cur2; i++) {
        const cls = ((cur2.className || '') + '').toLowerCase();
        if (/\b(topup|top-up|deposit|withdraw|cashier|wallet|user-menu|profile-menu)\b/.test(cls)) {
          warn(`[switchAsset] BLOCKED — ancestor class: "${cls.slice(0, 40)}"`);
          return;
        }
        cur2 = cur2.parentElement;
      }
    } catch (_e) { /* ignore */ }

    // Resolve coordinates of the element center for realistic events
    let cx = 0, cy = 0;
    try {
      const r = target.getBoundingClientRect();
      cx = Math.round(r.left + r.width / 2);
      cy = Math.round(r.top + r.height / 2);
    } catch (_e) { /* leave 0,0 */ }

    const baseOpts = {
      bubbles: true, cancelable: true, view: window, button: 0, buttons: 1,
      clientX: cx, clientY: cy, screenX: cx, screenY: cy,
      pointerType: 'mouse', isPrimary: true, pointerId: 1,
    };

    // ---- Stage 1: Fiber-handler shotgun ----
    // Collect every onClick / onMouseDown / onPointerDown in the fiber chain
    let handlersInvoked = 0;
    try {
      const fiberKey = Object.keys(target).find(k => k.startsWith('__reactFiber$'));
      const propsKey = Object.keys(target).find(k => k.startsWith('__reactProps$'));

      const synthEvent = (type) => ({
        target, currentTarget: target,
        preventDefault: () => {}, stopPropagation: () => {},
        persist: () => {}, isDefaultPrevented: () => false, isPropagationStopped: () => false,
        nativeEvent: new MouseEvent(type, baseOpts),
        type, button: 0, buttons: 1,
        clientX: cx, clientY: cy, screenX: cx, screenY: cy,
        isTrusted: true, bubbles: true, cancelable: true,
      });

      // Direct props on the target itself
      if (propsKey && target[propsKey]) {
        for (const h of ['onClick', 'onMouseDown', 'onPointerDown']) {
          if (typeof target[propsKey][h] === 'function') {
            try { target[propsKey][h](synthEvent(h.slice(2).toLowerCase())); handlersInvoked++; } catch (_e) {}
          }
        }
      }

      // Walk fiber chain — invoke each ancestor's handler too
      if (fiberKey) {
        let fiber = target[fiberKey];
        for (let i = 0; i < 16 && fiber; i++) {
          const props = fiber.memoizedProps;
          if (props) {
            for (const h of ['onClick', 'onMouseDown', 'onPointerDown']) {
              if (typeof props[h] === 'function') {
                try { props[h](synthEvent(h.slice(2).toLowerCase())); handlersInvoked++; } catch (_e) {}
              }
            }
          }
          fiber = fiber.return;
        }
      }
    } catch (_e) { /* fall through */ }

    // ---- Stage 2: Native event dispatch (pointer + mouse + touch sequence) ----
    const safeDispatch = (el, ev) => { try { el.dispatchEvent(ev); } catch (_e) {} };

    try {
      // Pointer events first (modern React 18 prefers PointerEvent)
      if (typeof PointerEvent !== 'undefined') {
        safeDispatch(target, new PointerEvent('pointerover', baseOpts));
        safeDispatch(target, new PointerEvent('pointerenter', baseOpts));
        safeDispatch(target, new PointerEvent('pointerdown', baseOpts));
        safeDispatch(target, new PointerEvent('pointerup', baseOpts));
      }
      // Mouse events
      safeDispatch(target, new MouseEvent('mouseover', baseOpts));
      safeDispatch(target, new MouseEvent('mousedown', baseOpts));
      safeDispatch(target, new MouseEvent('mouseup', baseOpts));
      // Click last
      safeDispatch(target, new MouseEvent('click', baseOpts));
    } catch (_e) {
      try { target.click(); } catch (_e2) {}
    }

    // ---- Stage 3: Native .click() as last resort (works for <a>/<button>/<input>) ----
    try { target.click?.(); } catch (_e) {}

    // ---- Stage 4 (Iter 64): href-based SPA navigation ----
    // PO's asset slot tiles MAY be <a href="?asset=X"> — if so, the cleanest
    // way to switch is to navigate via the existing SPA router. Walk up
    // looking for any <a> with an href, and call its native click() which
    // PO's router will pick up.
    try {
      let cur = target;
      for (let i = 0; i < 8 && cur; i++) {
        if (cur.tagName === 'A' && cur.href) {
          cur.click();  // native HTMLAnchorElement.click() — triggers SPA routing
          break;
        }
        cur = cur.parentElement;
      }
    } catch (_e) {}

    return { handlersInvoked, cx, cy };
  };

  const before = getCurrentAsset();
  const favSelectors = [
    // PO's "Asset Slot Tiles" at the top of the page (Iter 63 fix).
    // Each tile is the 5-second chart preview with X / pair / % / mini-chart.
    // Multiple class-name variants observed across PO themes.
    '.assets-block__active .assets-block__item',
    '.assets-block__item',
    '[class*="active-assets"] [class*="item"]',
    '[class*="assets-block"] [class*="item"]',
    '[class*="trading-pairs"] [class*="item"]',
    '[class*="tabs__item"]',
    'a[class*="asset-tab"]',
    'div[class*="chart-tab"]',
    // Older / favorites panel
    '.favorites-panel .asset-item',
    '.favorites .pair-item',
    '[data-testid="favorite-asset"]',
    '.assets-block__favorites [class*="symbol"]',
    '.assets-block__favorites .asset-item',
    '.assets-bar .asset-item',
    '[class*="favorit"][class*="asset"]',
    '[class*="favorit"][class*="symbol"]',
    '[class*="assets-favorit"] li',
    '[class*="assets-favorit"] [class*="text"]',
  ];

  // v8.47.0: filter slot-tile candidates to avoid matching balance/topup
  // chrome at the top of the page. A valid tile must:
  //   - Not be inside the page header/nav/sidebar
  //   - Not contain $/USD/EUR money strings
  //   - Have text that LOOKS like a currency pair
  const _SAFE_PAIR_RE = /([A-Z]{3,4}[/\s]?[A-Z]{3,4})/i;
  const _isHeaderChrome = (el) => {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      const tag = (cur.tagName || '').toLowerCase();
      const cls = ((cur.className || '') + '').toLowerCase();
      if (tag === 'header' || tag === 'nav') return true;
      if (/\b(top-?bar|topbar|header|navbar|user-menu|balance|topup|top-up|deposit|profile|account)\b/.test(cls)) return true;
      cur = cur.parentElement;
    }
    return false;
  };

  for (const sel of favSelectors) {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      if (_isHeaderChrome(el)) continue;
      const t = (el.textContent || '').trim().toUpperCase();
      if (!t || t.length > 80) continue;
      // Must look like a currency pair somewhere; reject pure-money strings.
      if (/\$\s?\d/.test(t) && !_SAFE_PAIR_RE.test(t)) continue;
      if (/(TOP\s*UP|DEPOSIT|BALANCE|REAL|DEMO)/.test(t) && !_SAFE_PAIR_RE.test(t)) continue;
      for (const v of variants) {
        if (t.includes(v)) {
          const target = findClickableParent(el);
          // Iter 62: scroll into view BEFORE clicking — some PO themes
          // lazy-render rows so the element exists in DOM but is off-screen
          // and React skips its event handlers.
          try { el.scrollIntoView?.({ block: 'center', inline: 'center' }); } catch (_e) {}
          const r1 = reactClick(target);
          log(`Switched to asset: ${symbol} (matched '${v}' in '${sel}', handlers=${r1?.handlersInvoked || 0})`);

          // Post-click sanity-check at 1.5s — retry on the deeper element + grandparent
          setTimeout(() => {
            const after = getCurrentAsset();
            if (after === before) {
              const r2 = reactClick(el);  // try the deepest text element directly
              log(`switchAsset retry-1 on text element (handlers=${r2?.handlersInvoked || 0})`);
              setTimeout(() => {
                const after2 = getCurrentAsset();
                if (after2 === before && el.parentElement) {
                  const r3 = reactClick(el.parentElement);  // try direct parent
                  log(`switchAsset retry-2 on direct parent (handlers=${r3?.handlersInvoked || 0})`);
                  setTimeout(() => {
                    const after3 = getCurrentAsset();
                    if (after3 === before) {
                      warn(`switchAsset: '${v}' still not switching after 3 attempts. PO may have changed its DOM. Current: ${after3}`);
                    }
                  }, 800);
                }
              }, 800);
            }
          }, 1_500);
          return true;
        }
      }
    }
  }

  // Iter 63: Robust dropdown-search fallback (when symbol not in slot tiles)
  // Two-step: (1) click the asset-name header to open picker, (2) type and click result
  const tryDropdownSearch = () => {
    // Find the live asset name in the chart header — uses the same strict
    // _findAssetHeader as the picker helpers (v8.47.0). Avoids accidental
    // clicks on the page-top balance / TOP UP / profile UI.
    const header = _findAssetHeader();
    if (header) {
      reactClick(findClickableParent(header));
      log(`Opened asset picker via header click`);
    } else {
      warn(`Could not locate asset-name header (strict matcher) — picker fallback may fail`);
    }

    // Wait for dropdown then search
    setTimeout(() => {
      const searchInput = document.querySelector(
        '.asset-search input, [data-testid="asset-search"], ' +
        'input[placeholder*="search" i], input[placeholder*="Search" i], ' +
        '.modal input[type="text"], .picker input[type="text"]'
      );
      if (!searchInput) {
        warn(`No asset-search input found after opening picker`);
        return;
      }
      // Set value via native setter so React picks it up
      try {
        const proto = Object.getPrototypeOf(searchInput);
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(searchInput, target);
        else searchInput.value = target;
      } catch (_e) {
        searchInput.value = target;
      }
      searchInput.dispatchEvent(new Event('input', { bubbles: true }));
      searchInput.dispatchEvent(new Event('change', { bubbles: true }));
      log(`Typed '${target}' into asset search`);

      // Click the first matching result after a short delay
      setTimeout(() => {
        const resultSelectors = [
          '.search-results .asset-item',
          '[class*="search-result"] [class*="item"]',
          '[class*="picker"] [class*="item"]',
          '[class*="dropdown"] [class*="asset"]',
          '[class*="modal"] [class*="row"]',
          '[class*="picker"] [class*="row"]',
        ];
        for (const rs of resultSelectors) {
          const results = document.querySelectorAll(rs);
          for (const r of results) {
            const txt = (r.textContent || '').trim().toUpperCase();
            for (const v of variants) {
              if (txt.includes(v)) {
                reactClick(findClickableParent(r));
                log(`Clicked picker result for ${v}`);
                return;
              }
            }
          }
        }
        warn(`No picker result matched ${variants.join('/')}`);
      }, 500);
    }, 350);
  };

  tryDropdownSearch();
  return true;
}

/**
 * Get current price - ROBUST version.
 * Tries multiple detection strategies to handle desktop + mobile + layout updates.
 * @returns {number|null}
 */
export function getCurrentPriceRobust() {
  // 1. Standard selector-based
  const p1 = getCurrentPrice();
  if (p1 !== null) return p1;

  const inRange = (n) => Number.isFinite(n) && n > 0.01 && n < 200000;

  // 2. Data attributes (PO stores live price on some elements)
  try {
    const attrEls = document.querySelectorAll(
      '[data-price], [data-current-price], [data-value], [data-last-price]'
    );
    for (const el of attrEls) {
      for (const attr of ['data-price', 'data-current-price', 'data-value', 'data-last-price']) {
        const v = parseFloat(el.getAttribute(attr));
        if (inRange(v)) return v;
      }
    }
  } catch (_e) { /* ignore */ }

  // 3. Chart SVG text nodes (TradingView-style price axis)
  try {
    const svgTexts = document.querySelectorAll('svg text, svg tspan');
    const candidates = [];
    for (const t of svgTexts) {
      const s = (t.textContent || '').trim();
      const m = s.match(/^(\d{1,6}(?:\.\d{2,6})?)$/);
      if (m) {
        const v = parseFloat(m[1]);
        if (inRange(v)) {
          try {
            const rect = t.getBoundingClientRect();
            candidates.push({ v, x: rect.left, y: rect.top, w: rect.width });
          } catch (_e) {
            candidates.push({ v, x: 0, y: 0, w: 0 });
          }
        }
      }
    }
    if (candidates.length > 0) {
      candidates.sort((a, b) => b.x - a.x);
      return candidates[0].v;
    }
  } catch (_e) { /* ignore */ }

  // 4. Scan ALL text nodes (including Shadow DOM) for forex-style price numbers.
  //    This is the mobile PO + canvas-chart fallback. Scores by decimal precision
  //    (more decimals = more likely a live price vs. account balance).
  try {
    const forexPattern = /^\d{1,7}\.\d{2,8}$/;
    const candidates = [];
    const scanRoot = (root) => {
      if (!root) return;
      try {
        const walker = document.createTreeWalker(
          root,
          NodeFilter.SHOW_TEXT,
          {
            acceptNode: (node) => {
              const text = (node.nodeValue || '').trim();
              return forexPattern.test(text) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            },
          }
        );
        let node;
        while ((node = walker.nextNode())) {
          const text = (node.nodeValue || '').trim();
          const v = parseFloat(text);
          if (!inRange(v)) continue;
          const parent = node.parentElement;
          if (!parent) continue;
          const decimals = (text.split('.')[1] || '').length;
          let x = 0;
          let y = 0;
          try {
            const rect = parent.getBoundingClientRect();
            x = rect.left;
            y = rect.top;
          } catch (_e) { /* ignore */ }
          candidates.push({ v, decimals, x, y, text });
        }
      } catch (_e) { /* ignore */ }

      // Also traverse Shadow DOM roots
      try {
        const hosts = root.querySelectorAll ? root.querySelectorAll('*') : [];
        for (const el of hosts) {
          if (el.shadowRoot) scanRoot(el.shadowRoot);
        }
      } catch (_e) { /* ignore */ }
    };

    scanRoot(document.body || document.documentElement);

    if (candidates.length > 0) {
      // Prefer more decimals then uppermost-left (chart price axis region)
      candidates.sort((a, b) => b.decimals - a.decimals || a.y - b.y || a.x - b.x);
      return candidates[0].v;
    }
  } catch (_e) { /* ignore */ }

  // 5. Class-pattern fallback (rate/quote/tick/value)
  try {
    const nodes = document.querySelectorAll(
      '[class*="rate"], [class*="quote"], [class*="tick"], [class*="trade"] [class*="value"], [class*="price"]'
    );
    for (const el of nodes) {
      if (!el || !el.offsetParent) continue;
      const text = (el.textContent || '').trim();
      const m = text.match(/(\d+\.\d{3,6})/);
      if (m) {
        const v = parseFloat(m[1]);
        if (inRange(v)) return v;
      }
    }
  } catch (_e) { /* ignore */ }

  return null;
}


/**
 * Get account balance from Pocket Option UI
 * v8.8.1: Comprehensive selector set + deep DOM search
 * @returns {number} Balance or 0
 */
export function getAccountBalance() {
  const selectors = [
    '.balance__value', '.balance-value', '[class*="balance__value"]',
    '[class*="balance-value"]', '.js-balance', '[data-testid="balance"]',
    '.balance span', '.balance', '[class*="balances"] [class*="amount"]',
    '[class*="balance"] [class*="value"]', '[class*="user-balance"]',
    'header [class*="balance"]', '.header__balance', '.main-balance',
    '[class*="BalanceValue"]', '[class*="balanceValue"]',
    '.popover-balance__item-value',
  ];

  for (const sel of selectors) {
    try {
      const elements = document.querySelectorAll(sel);
      for (const el of elements) {
        if (!el || !el.offsetParent) continue;
        const text = el.textContent || '';
        const match = text.match(/\$?\s?([\d\s,]+\.?\d*)/);
        if (match) {
          const balance = parseFloat(match[1].replace(/[\s,]/g, ''));
          if (balance >= 0.01 && balance <= 10000000) return balance;
        }
      }
    } catch (e) { /* skip */ }
  }

  // Deep search in header
  try {
    const header = document.querySelector('header') || document.querySelector('[class*="header"]');
    if (header) {
      for (const el of header.querySelectorAll('span, div')) {
        if (!el || !el.offsetParent || el.children.length > 2) continue;
        const match = (el.textContent || '').match(/\$\s?([\d,]+\.\d{2})/);
        if (match) {
          const bal = parseFloat(match[1].replace(/,/g, ''));
          if (bal >= 1 && bal <= 10000000) return bal;
        }
      }
    }
  } catch (e) { /* skip */ }

  return 0;
}


/**
 * Scan DOM for trade result (win/loss) from deal history or notifications
 * @returns {boolean|null} true=WIN, false=LOSS, null=not found
 */
export function scanDOMForTradeResult() {
  const dealSelectors = [
    '.deals-list .deals-item:first-child',
    '[class*="closed-deals"] [class*="item"]:first-child',
    '[class*="deals-list"] > div:first-child',
    '[class*="deal-item"]:first-child',
    '[class*="history"] [class*="item"]:first-child',
  ];

  for (const sel of dealSelectors) {
    try {
      const deal = document.querySelector(sel);
      if (!deal || !deal.offsetParent) continue;

      const profitEl = deal.querySelector('[class*="profit"], [class*="payout"], [class*="result"], [class*="amount"]');
      if (profitEl) {
        const cls = (profitEl.className || '').toLowerCase();
        const text = (profitEl.textContent || '').trim();
        if (cls.includes('success') || cls.includes('win') || cls.includes('green') || cls.includes('positive')) return true;
        if (cls.includes('fail') || cls.includes('loss') || cls.includes('red') || cls.includes('negative')) return false;
        if (text.match(/^\s*\+/)) return true;
        if (text.match(/^\s*-/) || text === '0') return false;
      }

      const cls = (deal.className || '').toLowerCase();
      if (cls.includes('win') || cls.includes('success') || cls.includes('profit')) return true;
      if (cls.includes('loss') || cls.includes('fail')) return false;
    } catch (e) { /* skip */ }
  }

  // Popup/toast notifications
  const popupSels = ['[class*="notification"][class*="deal"]', '[class*="trade-result"]', '[class*="toast"]'];
  for (const sel of popupSels) {
    try {
      const popup = document.querySelector(sel);
      if (!popup || !popup.offsetParent) continue;
      const cls = (popup.className || '').toLowerCase();
      const text = (popup.textContent || '').trim();
      if (cls.includes('win') || text.match(/\+\s*\$?\s*[\d,.]+/)) return true;
      if (cls.includes('loss') || text.match(/-\s*\$?\s*[\d,.]+/)) return false;
    } catch (e) { /* skip */ }
  }

  return null;
}


/**
 * Scrape the candle-countdown timer from Pocket Option's chart UI.
 * PO renders the "MM:SS" remaining for the active candle in a small label
 * near the price line / chart timer.
 *
 * Returns { totalSeconds, minutes, seconds } or null if not parseable.
 *
 * Selectors tried (in priority order):
 *   - elements bearing "countdown" / "timer" / "expiration" classes
 *   - any text node directly matching /^\s*\d{1,2}:\d{2}\s*$/ that lives
 *     near the chart canvas (filters out unrelated mm:ss text elsewhere)
 */
export function getCandleCountdown() {
  try {
    const SELECTORS = [
      '[class*="countdown" i]',
      '[class*="chart-time" i]',
      '[class*="candle-timer" i]',
      '[class*="period-timer" i]',
      '[data-test*="timer" i]',
    ];
    const re = /^\s*(\d{1,2}):(\d{2})\s*$/;

    for (const sel of SELECTORS) {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        const txt = (el.textContent || '').trim();
        const m = txt.match(re);
        if (m) {
          const minutes = parseInt(m[1], 10);
          const seconds = parseInt(m[2], 10);
          if (seconds < 60 && minutes < 60) {
            return { totalSeconds: minutes * 60 + seconds, minutes, seconds };
          }
        }
      }
    }

    // Fallback: scan all spans/divs that look chart-adjacent
    const candidates = document.querySelectorAll('span, div');
    for (const el of candidates) {
      // Cheap filter: must have only digits + colon
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length > 6 || !txt.includes(':')) continue;
      const m = txt.match(re);
      if (m) {
        const minutes = parseInt(m[1], 10);
        const seconds = parseInt(m[2], 10);
        // Must be at most an hour countdown
        if (seconds < 60 && minutes <= 60) {
          // Filter further — only keep elements that are likely chart timer
          // (avoid e.g. order-history "00:43" labels). Heuristic: must be a
          // leaf-ish element (no children) within the chart container.
          if (el.children.length === 0) {
            // Walk up looking for chart container clue
            let p = el.parentElement;
            for (let i = 0; i < 5 && p; i++) {
              const cls = (p.className || '').toString().toLowerCase();
              if (cls.includes('chart') || cls.includes('countdown') || cls.includes('timer')) {
                return { totalSeconds: minutes * 60 + seconds, minutes, seconds };
              }
              p = p.parentElement;
            }
          }
        }
      }
    }
  } catch (e) {
    /* fail silently — caller decides fallback */
  }
  return null;
}

/**
 * v8.52.0 — Read the current chart timeframe from PO's UI.
 *
 * PO shows the timeframe label like "M1", "M5", "S5", "S15", "S30",
 * "H1", etc. near the chart. This function scans for those label
 * patterns and returns the candle period in seconds.
 *
 * Returns { label, seconds } or null if not detectable.
 *
 * Supported labels:
 *   Sn  (seconds): S5=5, S15=15, S30=30
 *   Mn  (minutes): M1=60, M5=300, M15=900, M30=1800
 *   Hn  (hours):   H1=3600, H4=14400
 *   Dn  (days):    D1=86400
 */
export function getChartTimeframe() {
  try {
    // Common PO timeframe-button/badge selectors (multiple themes)
    const SEL = [
      '[class*="timeframe"] [class*="active"]',
      '[class*="chart-timeframe"] .active',
      '[class*="period-switcher"] .active',
      '[class*="period"] [class*="selected"]',
      '[class*="period"] [class*="active"]',
      '[class*="chart-type"] .active',
      '.timeframes-list .active',
      '.chart-header [class*="period"]',
      'button[class*="period"][class*="active"]',
    ];
    const LABEL_RE = /^\s*([SMHD])\s*(\d{1,3})\s*$/i;

    for (const s of SEL) {
      const els = document.querySelectorAll(s);
      for (const el of els) {
        if (!el || !el.offsetParent) continue;
        const txt = (el.textContent || '').trim();
        const m = txt.match(LABEL_RE);
        if (m) {
          const unit = m[1].toUpperCase();
          const num = parseInt(m[2], 10);
          const mult = { S: 1, M: 60, H: 3600, D: 86400 }[unit] || 60;
          return { label: `${unit}${num}`, seconds: num * mult };
        }
      }
    }

    // Fallback: scan compact badges anywhere in the chart area matching
    // pattern "M1" / "S5" / "H4" etc. Limit to small leaf elements so we
    // don't confuse with an arbitrary "M5" somewhere in copy.
    const leaves = document.querySelectorAll('button, span, div');
    for (const el of leaves) {
      if (!el || !el.offsetParent) continue;
      if (el.children.length > 1) continue;
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length > 5) continue;
      const m = txt.match(LABEL_RE);
      if (!m) continue;
      const unit = m[1].toUpperCase();
      const num = parseInt(m[2], 10);
      // Only accept if element has active-styling class hints (avoid
      // false positives from inactive timeframe buttons).
      const cls = ((el.className || '') + '').toLowerCase();
      const parentCls = ((el.parentElement?.className || '') + '').toLowerCase();
      if (/\b(active|selected|current)\b/.test(cls + ' ' + parentCls)) {
        const mult = { S: 1, M: 60, H: 3600, D: 86400 }[unit] || 60;
        return { label: `${unit}${num}`, seconds: num * mult };
      }
    }
  } catch (_e) { /* ignore */ }
  return null;
}


/**
 * v8.45.0 — Picker-based favorites discovery & switching.
 *
 * PO's mobile + recent desktop layouts hide favorites behind a dropdown
 * picker that is only visible after clicking the asset-name header. The
 * picker has a ★ filter button that narrows the list to user-favorited
 * pairs. These helpers automate that flow so CYCLE mode can reliably
 * find and switch through favorites even when the top "asset slot tiles"
 * bar doesn't show every favorited pair.
 */

const _sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function _findAssetHeader() {
  // v8.47.0: Strict matcher — text MUST look like a currency pair AND must
  // NOT be inside the top header/nav (balance, TOP UP button, etc.).
  // Earlier versions matched generic `[class*="symbol-name"]` selectors
  // which on some PO themes bound to the account-balance label, causing
  // CYCLE to "click" the TOP UP / balance area.
  const PAIR_RE = /^([A-Z]{3,4}[/\s]?[A-Z]{3,4})(\s*OTC)?[\s▼▾▲↓]*$/i;
  const COMPACT_RE = /^[A-Z]{6}(_OTC)?[\s▼▾▲↓]*$/i;

  const isInsideTopNav = (el) => {
    let cur = el;
    for (let i = 0; i < 8 && cur; i++) {
      const tag = (cur.tagName || '').toLowerCase();
      const cls = ((cur.className || '') + '').toLowerCase();
      if (tag === 'header' || tag === 'nav') return true;
      if (/\b(top-?bar|topbar|header|navbar|user-menu|balance|topup|top-up|deposit|profile|account)\b/.test(cls)) return true;
      cur = cur.parentElement;
    }
    return false;
  };

  const looksLikeMoney = (txt) => /\$|usd|eur|€|£|¥/i.test(txt) && /\d+\.\d+/.test(txt);
  const looksLikePair = (txt) => PAIR_RE.test(txt) || COMPACT_RE.test(txt);

  // Try priority selectors first — but every match is now validated against
  // the text-content rules above before being accepted.
  const sels = [
    '.asset-name', '.current-symbol',
    '[class*="active-symbol"]',
    '[class*="chart-header"] [class*="symbol"]',
    '[class*="asset-name"]:not([class*="amount"]):not([class*="balance"])',
    '[class*="symbol-name"]:not([class*="amount"]):not([class*="balance"])',
    '.pair-select__value',
  ];
  for (const s of sels) {
    const els = document.querySelectorAll(s);
    for (const el of els) {
      if (!el || !el.offsetParent) continue;
      if (isInsideTopNav(el)) continue;
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length > 24) continue;
      if (looksLikeMoney(txt)) continue;
      if (!looksLikePair(txt)) continue;
      return el;
    }
  }

  // Fallback: scan leaf text nodes that look like a pair, in the upper-left
  // chart region (top < 250px, left < 60% of viewport). This catches PO's
  // newer layouts where the chart-header asset label has no class hint.
  try {
    const W = window.innerWidth || 1200;
    const candidates = document.querySelectorAll('div, span, button, a');
    for (const el of candidates) {
      if (!el || !el.offsetParent) continue;
      if (el.children.length > 2) continue;        // leaf-ish only
      if (isInsideTopNav(el)) continue;
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length > 24) continue;
      if (looksLikeMoney(txt)) continue;
      if (!looksLikePair(txt)) continue;
      try {
        const r = el.getBoundingClientRect();
        // Must be near the top-left of the chart pane, not in the trade
        // panel on the right or in the bottom mobile-trade row.
        if (r.top < 60 || r.top > 350) continue;
        if (r.left > W * 0.6) continue;
        if (r.width < 40 || r.width > 260) continue;
        return el;
      } catch (_e) { /* ignore */ }
    }
  } catch (_e) { /* ignore */ }

  return null;
}

function _findClickableAncestor(el) {
  let cur = el;
  for (let i = 0; i < 12 && cur; i++) {
    try {
      const propsKey = Object.keys(cur).find((k) => k.startsWith('__reactProps$'));
      if (propsKey && cur[propsKey] && (
        typeof cur[propsKey].onClick === 'function' ||
        typeof cur[propsKey].onMouseDown === 'function' ||
        typeof cur[propsKey].onPointerDown === 'function'
      )) {
        return cur;
      }
    } catch (_e) { /* ignore */ }
    cur = cur.parentElement;
  }
  return el;
}

function _reactClickEl(target) {
  if (!target) return;
  // v8.49.0: Hard safety net — refuse to click any element (or any ancestor
  // within 4 levels) whose text matches the "forbidden chrome" blocklist.
  // Prevents CYCLE/picker fallbacks from accidentally opening the TOP UP
  // modal, triggering a deposit, clicking the profile/avatar menu, etc.
  const FORBIDDEN_RE = /\b(TOP[\s-]?UP|DEPOSIT|WITHDRAW|TOP\s*UP|TOPUP|PROFILE|ACCOUNT|SIGN\s*OUT|LOGOUT|LOG\s*OUT|CASHIER|WALLET)\b/i;
  try {
    let cur = target;
    for (let i = 0; i < 4 && cur; i++) {
      const txt = (cur.textContent || '').trim();
      if (txt.length > 0 && txt.length < 60 && FORBIDDEN_RE.test(txt)) {
        warn(`[safe-click] BLOCKED click on forbidden element: "${txt.slice(0, 40)}"`);
        return;
      }
      cur = cur.parentElement;
    }
    // Also block based on ancestor class hints
    let cur2 = target;
    for (let i = 0; i < 6 && cur2; i++) {
      const cls = ((cur2.className || '') + '').toLowerCase();
      if (/\b(topup|top-up|deposit|withdraw|cashier|wallet|user-menu|profile-menu)\b/.test(cls)) {
        warn(`[safe-click] BLOCKED click — ancestor has forbidden class: "${cls.slice(0, 40)}"`);
        return;
      }
      cur2 = cur2.parentElement;
    }
  } catch (_e) { /* ignore */ }

  let cx = 0, cy = 0;
  try {
    const r = target.getBoundingClientRect();
    cx = Math.round(r.left + r.width / 2);
    cy = Math.round(r.top + r.height / 2);
  } catch (_e) { /* ignore */ }
  const baseOpts = {
    bubbles: true, cancelable: true, view: window, button: 0, buttons: 1,
    clientX: cx, clientY: cy, screenX: cx, screenY: cy,
    pointerType: 'mouse', isPrimary: true, pointerId: 1,
  };

  // Walk fiber chain — invoke each ancestor's React handler
  try {
    const fiberKey = Object.keys(target).find((k) => k.startsWith('__reactFiber$'));
    const propsKey = Object.keys(target).find((k) => k.startsWith('__reactProps$'));
    const synth = (type) => ({
      target, currentTarget: target,
      preventDefault: () => {}, stopPropagation: () => {},
      persist: () => {}, isDefaultPrevented: () => false, isPropagationStopped: () => false,
      nativeEvent: new MouseEvent(type, baseOpts),
      type, button: 0, buttons: 1,
      clientX: cx, clientY: cy, screenX: cx, screenY: cy,
      isTrusted: true, bubbles: true, cancelable: true,
    });
    if (propsKey && target[propsKey]) {
      for (const h of ['onClick', 'onMouseDown', 'onPointerDown']) {
        if (typeof target[propsKey][h] === 'function') {
          try { target[propsKey][h](synth(h.slice(2).toLowerCase())); } catch (_e) {}
        }
      }
    }
    if (fiberKey) {
      let fiber = target[fiberKey];
      for (let i = 0; i < 16 && fiber; i++) {
        const props = fiber.memoizedProps;
        if (props) {
          for (const h of ['onClick', 'onMouseDown', 'onPointerDown']) {
            if (typeof props[h] === 'function') {
              try { props[h](synth(h.slice(2).toLowerCase())); } catch (_e) {}
            }
          }
        }
        fiber = fiber.return;
      }
    }
  } catch (_e) { /* ignore */ }

  const safe = (ev) => { try { target.dispatchEvent(ev); } catch (_e) {} };
  try {
    if (typeof PointerEvent !== 'undefined') {
      safe(new PointerEvent('pointerover', baseOpts));
      safe(new PointerEvent('pointerdown', baseOpts));
      safe(new PointerEvent('pointerup', baseOpts));
    }
    safe(new MouseEvent('mouseover', baseOpts));
    safe(new MouseEvent('mousedown', baseOpts));
    safe(new MouseEvent('mouseup', baseOpts));
    safe(new MouseEvent('click', baseOpts));
  } catch (_e) {}
  try { target.click?.(); } catch (_e) {}
}

/**
 * Open the asset picker dropdown by clicking the chart-header asset name.
 * Returns true if the picker is now open (best effort).
 */
async function openAssetPicker() {
  const header = _findAssetHeader();
  if (!header) {
    warn('[picker] asset-name header not found');
    return false;
  }
  _reactClickEl(_findClickableAncestor(header));
  await _sleep(450);
  // Heuristic check: dropdown root present?
  const dropdown = document.querySelector(
    '[class*="picker"], [class*="modal"], [class*="dropdown"][class*="asset"], ' +
    '[class*="assets-list"], [class*="currencies"], [class*="symbol-list"]'
  );
  return !!dropdown;
}

/**
 * Close any open asset picker dropdown by clicking outside (chart area).
 */
async function closeAssetPicker() {
  // Send Escape — most React modals listen for this
  try {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
  } catch (_e) { /* ignore */ }
  await _sleep(150);
}

/**
 * Click the "Favorites" tab inside the open asset picker.
 *
 * v8.57.0: Based on live PO screenshots, the picker is a left-side panel
 * with tabs "Currencies / Cryptocurrencies / Commodities / Stocks /
 * Indices / Favorites / Schedule". We match the tab by its EXACT text
 * content "Favorites" (with a small icon sibling) — NOT by a star-filter
 * button. Walks up to confirm the tab is inside an open picker container.
 *
 * Returns true if a Favorites tab was found & clicked.
 */
async function clickFavoritesFilter() {
  // Primary: exact "Favorites" text match on small, visible elements
  const clickables = document.querySelectorAll(
    'button, [role="button"], [role="tab"], li, div, span, a'
  );
  for (const el of clickables) {
    if (!el || !el.offsetParent) continue;
    if (el.children.length > 3) continue;  // leaf-ish only (tab has icon + label)
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 20) continue;
    // Match "Favorites" or "Favourites" (both spellings), case-insensitive
    if (!/^\s*Favou?rites\s*$/i.test(txt)) continue;
    // Confirm inside an open picker context by walking ancestors
    let cur = el;
    let inPicker = false;
    for (let i = 0; i < 15 && cur; i++) {
      const c = ((cur.className || '') + '').toLowerCase();
      if (/picker|modal|dropdown|currencies|assets-list|symbol-list|asset-select|categories/.test(c)) {
        inPicker = true; break;
      }
      cur = cur.parentElement;
    }
    // Also accept elements that SIT IN the top-left corner even without
    // matching class hints — PO's newer themes omit class markers.
    if (!inPicker) {
      try {
        const r = el.getBoundingClientRect();
        if (r.left < 400 && r.top < 800 && r.width < 320) inPicker = true;
      } catch (_e) { /* ignore */ }
    }
    if (!inPicker) continue;
    _reactClickEl(_findClickableAncestor(el));
    log(`[picker] clicked Favorites TAB (text="${txt}")`);
    await _sleep(350);
    return true;
  }

  // Fallback: older themes with a class-hint-only favorites filter button
  const candidates = document.querySelectorAll(
    'button, [role="button"], [class*="favorit"], [class*="star"], svg, i'
  );
  for (const el of candidates) {
    if (!el || !el.offsetParent) continue;
    const cls = ((el.className || '') + '').toLowerCase();
    const aria = (el.getAttribute && (el.getAttribute('aria-label') || '')).toLowerCase();
    if (!/favorit|star|heart/.test(cls + ' ' + aria)) continue;
    let cur = el;
    let inPicker = false;
    for (let i = 0; i < 12 && cur; i++) {
      const c = ((cur.className || '') + '').toLowerCase();
      if (/picker|modal|dropdown|currencies|assets-list|symbol-list/.test(c)) {
        inPicker = true; break;
      }
      cur = cur.parentElement;
    }
    if (!inPicker) continue;
    _reactClickEl(_findClickableAncestor(el));
    log(`[picker] clicked favorites filter (${cls.slice(0, 40)})`);
    await _sleep(300);
    return true;
  }
  return false;
}

/**
 * Read the visible asset rows inside the open asset picker dropdown.
 * Returns [{symbol, el}] - el is the <li>/<div> row clickable.
 */
function readPickerItems() {
  const items = [];
  const seen = new Set();
  const symbolRe = /([A-Z]{2,4}\/?[A-Z]{2,4})\b/i;

  // Common dropdown row selectors
  const ROW_SELECTORS = [
    '[class*="picker"] [class*="row"]',
    '[class*="picker"] [class*="item"]',
    '[class*="modal"] [class*="row"]',
    '[class*="dropdown"] [class*="row"]',
    '[class*="dropdown"] [class*="asset"]',
    '[class*="currencies"] [class*="item"]',
    '[class*="currencies"] li',
    '[class*="currencies"] [class*="row"]',
    '[class*="symbol-list"] [class*="item"]',
    '[class*="symbols-list"] [class*="item"]',
    '[class*="assets-list"] [class*="item"]',
  ];

  for (const sel of ROW_SELECTORS) {
    const els = document.querySelectorAll(sel);
    if (!els.length) continue;
    els.forEach((el) => {
      if (!el || !el.offsetParent) return;
      const txt = (el.textContent || '').trim();
      const m = txt.match(symbolRe);
      if (!m) return;
      // Strip payout % numbers from match
      const raw = m[0] + (txt.toUpperCase().includes('OTC') ? ' OTC' : '');
      const normalized = normalizeAssetName(raw);
      if (!normalized || seen.has(normalized)) return;
      const symPart = normalized.replace(/_OTC$/, '');
      if (symPart.length < 5 || /[^A-Z0-9]/.test(symPart)) return;
      seen.add(normalized);
      items.push({ symbol: normalized, el });
    });
    if (items.length) break;
  }
  return items;
}

/**
 * v8.60.0 — Click the "Currencies" tab inside the open asset picker.
 *
 * Same pattern as `clickFavoritesFilter()` but matches the "Currencies"
 * tab text. Used by CYCLE mode to surface the FULL currency-pair list
 * (not just user favorites). Returns true on click.
 */
async function clickCurrenciesTab() {
  return clickPickerTabByText(/^\s*Currenc(y|ies)\s*$/i);
}

/**
 * Iter 68 — Click any picker tab matching a text regex.
 * Used by CYCLE to walk every category tab (Currencies, Crypto, Commodities,
 * Stocks, Indices) so the eligible-asset list isn't FX-only.
 */
async function clickPickerTabByText(textRe) {
  const clickables = document.querySelectorAll(
    'button, [role="button"], [role="tab"], li, div, span, a'
  );
  for (const el of clickables) {
    if (!el || !el.offsetParent) continue;
    if (el.children.length > 3) continue;
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 22) continue;
    if (!textRe.test(txt)) continue;
    let cur = el;
    let inPicker = false;
    for (let i = 0; i < 15 && cur; i++) {
      const c = ((cur.className || '') + '').toLowerCase();
      if (/picker|modal|dropdown|asset-select|categories|tabs/.test(c)) {
        inPicker = true; break;
      }
      cur = cur.parentElement;
    }
    if (!inPicker) {
      try {
        const r = el.getBoundingClientRect();
        if (r.left < 400 && r.top < 800 && r.width < 320) inPicker = true;
      } catch (_e) { /* ignore */ }
    }
    if (!inPicker) continue;
    _reactClickEl(_findClickableAncestor(el));
    log(`[picker] clicked tab (text="${txt}")`);
    await _sleep(350);
    return true;
  }
  return false;
}

/**
 * v8.60.0 — Read the currently visible asset rows inside the open picker
 * AND parse each row's payout percentage from its visible text.
 *
 * Returns: [{symbol, payout, el}] where:
 *   symbol  → normalised asset name like 'EURUSD_OTC'
 *   payout  → integer percent (e.g. 92), or null if unparseable
 *   el      → clickable row element
 *
 * Used by CYCLE to filter to ≥85% pairs without round-tripping through a
 * second picker open.
 */
function readPickerItemsWithPayouts() {
  const rows = readPickerItems();
  const PAYOUT_RE = /\+?\s*(\d{1,3})\s*%/;
  return rows.map((r) => {
    let payout = null;
    try {
      const txt = (r.el?.textContent || '').trim();
      const m = txt.match(PAYOUT_RE);
      if (m) {
        const v = parseInt(m[1], 10);
        if (v >= 1 && v <= 100) payout = v;
      }
    } catch (_e) { /* ignore */ }
    return { symbol: r.symbol, payout, el: r.el };
  });
}

/**
 * v8.60.0 — Pick assets from the OPEN asset picker. Helpers exported
 * for cycleMode use.
 */
export async function openCurrenciesPicker() {
  const opened = await openAssetPicker();
  if (!opened) return false;
  await _sleep(300);
  const tabClicked = await clickCurrenciesTab();
  if (!tabClicked) {
    log('[picker] Currencies tab not found — using whatever tab is active');
  }
  await _sleep(300);
  return true;
}

/**
 * Iter 68 — Open the asset picker and scrape EVERY category tab so we
 * surface the full universe (forex + crypto + commodities + stocks + indices),
 * not just currencies. Used by the rewritten CYCLE mode.
 *
 * Returns: Array<{symbol, payout, el}> deduped by symbol (last write wins).
 * Picker is left CLOSED on exit.
 */
export async function discoverAllAssetsWithPayouts() {
  const opened = await openAssetPicker();
  if (!opened) return [];
  await _sleep(300);

  const TAB_PATTERNS = [
    /^\s*Currenc(y|ies)\s*$/i,
    /^\s*Crypto(currencies)?\s*$/i,
    /^\s*Commodit(y|ies)\s*$/i,
    /^\s*Stocks?\s*$/i,
    /^\s*Indices\s*$/i,
    /^\s*ETF(s)?\s*$/i,
  ];

  const acc = new Map();   // symbol → {symbol, payout, el}

  // Start with whatever tab is currently active (typically "Favorites"/"All")
  const seed = readPickerItemsWithPayouts();
  for (const r of seed) {
    if (r.symbol) acc.set(r.symbol, r);
  }

  for (const re of TAB_PATTERNS) {
    const ok = await clickPickerTabByText(re);
    if (!ok) continue;
    await _sleep(350);
    const rows = readPickerItemsWithPayouts();
    for (const r of rows) {
      if (r.symbol) acc.set(r.symbol, r);
    }
  }

  await closeAssetPicker().catch(() => {});
  return Array.from(acc.values());
}

export function readCurrencyPairsWithPayouts() {
  return readPickerItemsWithPayouts();
}

export async function clickPickerRowEl(el) {
  if (!el) return false;
  try { el.scrollIntoView?.({ block: 'center' }); } catch (_e) {}
  _reactClickEl(_findClickableAncestor(el));
  await _sleep(400);
  return true;
}

/**
 * Click the asset picker's CLOSE button or send Escape to dismiss it.
 * Lighter-weight version of closeAssetPicker for the cycle mode.
 */
export async function dismissPicker() {
  return closeAssetPicker();
}

/**
 * Discover the user's favorited assets by:
 *   1. Opening the asset picker (click chart header)
 *   2. Clicking the ★ favorites filter inside the picker
 *   3. Reading the visible rows
 *   4. Closing the picker
 *
 * Async. Returns array of normalized symbols.
 * Falls back to getFavorites() if picker can't be opened.
 */
export async function getFavoritesViaPicker() {
  try {
    const opened = await openAssetPicker();
    if (!opened) {
      log('[picker] picker did not open — falling back to bar scrape');
      return getFavorites();
    }
    const filtered = await clickFavoritesFilter();
    if (!filtered) {
      log('[picker] favorites filter not found — using all picker rows');
    }
    await _sleep(250);
    const items = readPickerItems();
    log(`[picker] discovered ${items.length} favorites${filtered ? ' (★ filter ON)' : ''}`);
    await closeAssetPicker();
    if (items.length === 0) return getFavorites();
    return items.map((it) => it.symbol);
  } catch (e) {
    warn(`[picker] discovery failed: ${e.message}`);
    try { await closeAssetPicker(); } catch (_e) {}
    return getFavorites();
  }
}

/**
 * Switch to an asset by opening the picker, optionally clicking the ★
 * favorites filter, and clicking the row that matches `symbol`.
 *
 * This is the robust async fallback when slot-tile click fails. Returns
 * true if a row was clicked (success isn't guaranteed — caller should
 * verify via getCurrentAsset() afterwards).
 */
export async function switchAssetViaPicker(symbol) {
  if (!symbol) return false;
  const target = String(symbol).toUpperCase().replace(/_OTC$/, '');
  const variants = new Set([
    target,
    `${target} OTC`,
  ]);
  if (target.length === 6) {
    variants.add(`${target.slice(0, 3)}/${target.slice(3)}`);
    variants.add(`${target.slice(0, 3)}/${target.slice(3)} OTC`);
  }

  try {
    const opened = await openAssetPicker();
    if (!opened) return false;
    // Try favorites filter to narrow noise
    await clickFavoritesFilter();
    await _sleep(250);

    const items = readPickerItems();
    for (const it of items) {
      if (it.symbol === normalizeAssetName(target) ||
          it.symbol === normalizeAssetName(`${target} OTC`)) {
        // Scroll into view first
        try { it.el.scrollIntoView?.({ block: 'center', inline: 'center' }); } catch (_e) {}
        _reactClickEl(_findClickableAncestor(it.el));
        log(`[picker] clicked row for ${it.symbol}`);
        await _sleep(400);
        return true;
      }
    }

    // Fallback: text-match scan inside dropdown
    const dropdown = document.querySelector(
      '[class*="picker"], [class*="modal"], [class*="dropdown"], ' +
      '[class*="currencies"], [class*="assets-list"], [class*="symbol-list"]'
    );
    if (dropdown) {
      const rows = dropdown.querySelectorAll('li, div, button, a, [role="row"], [role="option"]');
      for (const r of rows) {
        if (!r.offsetParent) continue;
        const txt = (r.textContent || '').trim().toUpperCase();
        for (const v of variants) {
          if (txt.includes(v) && txt.length < 100) {
            try { r.scrollIntoView?.({ block: 'center' }); } catch (_e) {}
            _reactClickEl(_findClickableAncestor(r));
            log(`[picker] text-matched row for ${v}`);
            await _sleep(400);
            return true;
          }
        }
      }
    }

    warn(`[picker] no row matched ${target}`);
    await closeAssetPicker();
    return false;
  } catch (e) {
    warn(`[picker] switch failed: ${e.message}`);
    try { await closeAssetPicker(); } catch (_e) {}
    return false;
  }
}

export default {
  waitForElement,
  getCurrentAsset,
  getCurrentAssetRaw,
  normalizeAssetName,
  getCurrentPrice,
  getCurrentPriceRobust,
  getPayout,
  setTradeAmount,
  clickCall,
  clickPut,
  executeTrade,
  getFavorites,
  getFavoritesViaPicker,
  switchAsset,
  switchAssetViaPicker,
  getAccountBalance,
  scanDOMForTradeResult,
  getCandleCountdown,
  getChartTimeframe,
};
