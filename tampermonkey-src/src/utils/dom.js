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
    
    const observer = new MutationObserver((mutations, obs) => {
      const el = document.querySelector(selector);
      if (el) {
        obs.disconnect();
        resolve(el);
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
    
    setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeout);
  });
}

/**
 * Get current asset from Pocket Option UI
 * @returns {string|null} Asset symbol
 */
export function getCurrentAsset() {
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
 * Click CALL button
 * @returns {boolean} Success
 */
export function clickCall() {
  const buttons = document.querySelectorAll('button, .btn, [role="button"]');
  for (const btn of buttons) {
    const text = btn.textContent.toLowerCase();
    const classes = btn.className.toLowerCase();
    
    if (text.includes('call') || text.includes('higher') || text.includes('up') ||
        classes.includes('call') || classes.includes('green') || classes.includes('up')) {
      btn.click();
      log('Clicked CALL button');
      return true;
    }
  }
  
  warn('CALL button not found');
  return false;
}

/**
 * Click PUT button
 * @returns {boolean} Success
 */
export function clickPut() {
  const buttons = document.querySelectorAll('button, .btn, [role="button"]');
  for (const btn of buttons) {
    const text = btn.textContent.toLowerCase();
    const classes = btn.className.toLowerCase();
    
    if (text.includes('put') || text.includes('lower') || text.includes('down') ||
        classes.includes('put') || classes.includes('red') || classes.includes('down')) {
      btn.click();
      log('Clicked PUT button');
      return true;
    }
  }
  
  warn('PUT button not found');
  return false;
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
 * Get current price — ROBUST version.
 * Tries the original selector-based method first, then falls back to:
 *  - Chart SVG <text> labels (TradingView's rendering)
 *  - Any visible element near the right edge of the chart with a forex-like number
 *  - The latest data attribute on chart elements (data-price, data-value)
 *  - Number scraping near the CALL/PUT button area
 * Returns null only if absolutely nothing resembles a price.
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
      // TradingView renders the live price at the rightmost text node of the price axis
      candidates.sort((a, b) => b.x - a.x);
      return candidates[0].v;
    }
  } catch (_e) { /* ignore */ }

  // 4. Try trading panel's "last price" labels
  try {
    const nodes = document.querySelectorAll(
      '[class*="rate"], [class*="quote"], [class*="tick"], [class*="trade"] [class*="value"]'
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


export default {
  waitForElement,
  getCurrentAsset,
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
};
