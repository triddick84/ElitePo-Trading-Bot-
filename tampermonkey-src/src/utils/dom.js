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

export default {
  waitForElement,
  getCurrentAsset,
  getCurrentPrice,
  getPayout,
  setTradeAmount,
  clickCall,
  clickPut,
  executeTrade,
  getFavorites,
  switchAsset,
};
