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
  const input = document.querySelector('input.amount-input, [data-testid="trade-amount"], .deal-amount input');
  if (!input) {
    warn('Trade amount input not found');
    return false;
  }
  
  // Clear and set new value
  input.value = '';
  input.focus();
  
  // Dispatch events to trigger React updates
  const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setValue.call(input, amount.toString());
  
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  
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
export function executeTrade(direction, amount = null) {
  if (amount) {
    setTradeAmount(amount);
  }
  
  // Small delay to let amount update
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
export function getFavorites() {
  const favorites = [];
  const selectors = [
    '.favorites-panel .asset-item',
    '.favorites .pair-item',
    '[data-testid="favorite-asset"]',
  ];
  
  for (const selector of selectors) {
    const items = document.querySelectorAll(selector);
    items.forEach(item => {
      const text = item.textContent.trim();
      if (text) {
        favorites.push(text.replace(/[\/\s-]/g, '').toUpperCase());
      }
    });
    
    if (favorites.length > 0) break;
  }
  
  return favorites;
}

/**
 * Switch to a different asset
 * @param {string} symbol - Asset symbol
 * @returns {boolean} Success
 */
export function switchAsset(symbol) {
  // Try clicking on favorites bar
  const favorites = document.querySelectorAll('.favorites-panel .asset-item, .favorites .pair-item');
  for (const fav of favorites) {
    if (fav.textContent.includes(symbol.replace('_otc', '').replace('_', '/'))) {
      fav.click();
      log(`Switched to asset: ${symbol}`);
      return true;
    }
  }
  
  // Try search
  const searchInput = document.querySelector('.asset-search input, [data-testid="asset-search"]');
  if (searchInput) {
    searchInput.value = symbol.replace('_otc', '').replace('_', '/');
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    
    // Wait for results and click first match
    setTimeout(() => {
      const result = document.querySelector('.search-results .asset-item');
      if (result) result.click();
    }, 500);
    
    return true;
  }
  
  warn(`Could not switch to asset: ${symbol}`);
  return false;
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
  switchAsset,
  getAccountBalance,
  scanDOMForTradeResult,
  getCandleCountdown,
};
