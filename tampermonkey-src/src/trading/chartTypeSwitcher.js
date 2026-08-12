/**
 * Iter 99 — Chart-type enforcement for Pocket Option.
 *
 * When the app has `chart_type=heikin_ashi` in config, but PO is showing
 * Japanese candles, the TM script switches PO's chart type on the fly
 * before firing the trade — so the human sees the same chart the signal
 * was generated from.
 *
 * The chart-type menu location varies between PO builds and is not
 * addressable via a stable selector. So we use the same point-to-teach
 * pattern as Iter 98 favorites-cycle: user opens PO's chart-type menu,
 * clicks 🎓 Teach Chart Types, then clicks any one of the 4 chart-type
 * options. We capture the SURROUNDING menu container. On each rotation
 * we find the button whose textContent matches one of the four target
 * keywords and click it.
 *
 * Fallback: if teach data isn't present, we scan the whole document for
 * a button whose textContent contains keywords like "Heikin Ashi", "Line",
 * "Bar", "Japanese"/"Candle". This is best-effort and may miss if PO's
 * menu is closed.
 */

import { log, info, warn, success, error } from '../core/logger.js';

const STORAGE_KEY = 'pobot_chartTypeTeachData';

// Iter 99 — chart type aliases → keyword regex used to identify buttons
const CHART_TYPE_KEYWORDS = {
  japanese_candles: /japanese|candle(?!s? .*heikin)/i,
  heikin_ashi:      /heikin[\s-]*ashi/i,
  line:             /\bline\b/i,
  bars:             /\bbars?\b(?!.*heikin)/i,
};

function _readTeachData() {
  try {
    if (typeof GM_getValue !== 'undefined') {
      const raw = GM_getValue(STORAGE_KEY, null);
      if (raw && typeof raw === 'object') return raw;
      if (typeof raw === 'string') return JSON.parse(raw);
    }
    const ls = localStorage.getItem(STORAGE_KEY);
    return ls ? JSON.parse(ls) : null;
  } catch (_e) { return null; }
}

function _writeTeachData(data) {
  try {
    if (typeof GM_setValue !== 'undefined') { GM_setValue(STORAGE_KEY, data); return; }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (_e) { /* silent */ }
}

/**
 * Walk up from the clicked element to find the containing menu.
 * Uses the same shape-clustering heuristic as favoritesCycle.
 */
function _analyzeMenu(target) {
  if (!target) return null;
  let el = target;
  for (let depth = 0; depth < 8 && el && el.parentElement; depth++) {
    el = el.parentElement;
    const kids = Array.from(el.children);
    if (kids.length < 2) continue;
    const shapeOf = (n) => `${n.tagName}.${(n.className || '').split(/\s+/)[0] || ''}`;
    const shapes = new Map();
    for (const k of kids) {
      const s = shapeOf(k);
      shapes.set(s, (shapes.get(s) || 0) + 1);
    }
    const dominant = [...shapes.entries()].sort((a, b) => b[1] - a[1])[0];
    if (dominant && dominant[1] >= 2) {
      // Build CSS selector chain (3 levels up)
      const buildSelector = (node) => {
        if (node.id) return `#${node.id}`;
        if (node.className && typeof node.className === 'string') {
          const cls = node.className.split(/\s+/).filter(c => c && !c.includes('active')).slice(0, 2).join('.');
          if (cls) return `${node.tagName.toLowerCase()}.${cls}`;
        }
        const parent = node.parentElement;
        if (parent) {
          const idx = Array.from(parent.children).indexOf(node) + 1;
          return `${node.tagName.toLowerCase()}:nth-child(${idx})`;
        }
        return node.tagName.toLowerCase();
      };
      const chain = [];
      let n = el;
      for (let i = 0; i < 4 && n && n !== document.body; i++) {
        chain.unshift(buildSelector(n));
        n = n.parentElement;
      }
      return {
        containerSelector: chain.join(' > '),
        tileSelector: `${dominant[0].split('.')[0].toLowerCase()}${dominant[0].split('.')[1] ? '.' + dominant[0].split('.')[1] : ''}`,
        childCount: kids.length,
      };
    }
  }
  return null;
}

class ChartTypeSwitcher {
  constructor() {
    this.teachMode = false;
    this._teachOverlay = null;
    this._teachClickHandler = null;
    this.stats = { switches: 0, misses: 0, lastRequested: null };
  }

  getTeachData() { return _readTeachData(); }

  /**
   * Read the current chart type from PO's DOM by scanning the taught
   * menu's children for the ONE tile marked "active" or "selected" — or
   * fall back to a heuristic scan. Returns one of the CHART_TYPE_KEYWORDS
   * keys, or null if unknown.
   */
  detectCurrent() {
    const data = _readTeachData();
    if (!data || !data.containerSelector) return null;
    const container = document.querySelector(data.containerSelector);
    if (!container) return null;
    const items = Array.from(container.querySelectorAll(data.tileSelector));
    for (const item of items) {
      const cls = (item.className || '') + ' ' + (item.getAttribute('aria-selected') || '');
      if (/active|selected|current/i.test(cls)) {
        const text = (item.textContent || '').trim();
        for (const [key, rx] of Object.entries(CHART_TYPE_KEYWORDS)) {
          if (rx.test(text)) return key;
        }
      }
    }
    return null;
  }

  /**
   * Ensure PO's chart is showing the requested type. Returns
   * { changed:bool, matched:bool, reason:string }.
   */
  async ensure(desired) {
    if (!desired) return { changed: false, matched: true, reason: 'no_target' };
    if (!CHART_TYPE_KEYWORDS[desired]) return { changed: false, matched: false, reason: 'unknown_type' };
    this.stats.lastRequested = desired;

    // Fast path — check if it's already right
    const now = this.detectCurrent();
    if (now === desired) return { changed: false, matched: true, reason: 'already_matches' };

    // Look in the taught menu first, then anywhere on the page.
    const target = await this._findAndClick(desired);
    if (target) {
      this.stats.switches++;
      success(`[chartType] switched PO chart to ${desired}`);
      return { changed: true, matched: true, reason: 'switched' };
    }
    this.stats.misses++;
    warn(`[chartType] could not locate a "${desired}" button in the DOM. Try teaching the menu.`);
    return { changed: false, matched: false, reason: 'not_found' };
  }

  async _findAndClick(desired) {
    const rx = CHART_TYPE_KEYWORDS[desired];
    const data = _readTeachData();

    // 1. Look inside the taught container
    if (data && data.containerSelector) {
      const container = document.querySelector(data.containerSelector);
      if (container) {
        const items = Array.from(container.querySelectorAll(data.tileSelector));
        const hit = items.find(el => rx.test((el.textContent || '').trim()));
        if (hit) {
          this._clickWithMouseEvents(hit);
          return hit;
        }
      }
    }

    // 2. Fallback — best-effort scan of the whole doc
    const allButtons = document.querySelectorAll('button, [role="menuitem"], [role="option"], li, div');
    for (const el of allButtons) {
      const text = (el.textContent || '').trim();
      if (text.length > 40) continue;  // skip long descriptions
      if (rx.test(text)) {
        // Sanity: only click if visible + likely a menu item
        const rect = el.getBoundingClientRect();
        if (rect.width < 20 || rect.height < 20) continue;
        this._clickWithMouseEvents(el);
        return el;
      }
    }
    return null;
  }

  _clickWithMouseEvents(el) {
    try {
      el.click();
      const rect = el.getBoundingClientRect();
      const opts = { bubbles: true, cancelable: true, view: window,
                     clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 };
      el.dispatchEvent(new MouseEvent('mousedown', opts));
      el.dispatchEvent(new MouseEvent('mouseup', opts));
      el.dispatchEvent(new MouseEvent('click', opts));
    } catch (e) {
      warn(`[chartType] click failed: ${e.message}`);
    }
  }

  startTeach(onComplete) {
    if (this.teachMode) { warn('[chartType] already teaching'); return; }
    this.teachMode = true;
    info('[chartType] TEACH MODE — open PO chart-type menu, then click ANY chart type. ESC to cancel.');

    const overlay = document.createElement('div');
    overlay.id = 'pobot_chartteach_overlay';
    overlay.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0',
      'background:linear-gradient(90deg,rgba(139,92,246,0.95),rgba(244,63,94,0.85))',
      'color:#ffffff', 'font-family:system-ui,sans-serif', 'font-weight:800',
      'font-size:14px', 'padding:12px 20px', 'z-index:2147483647',
      'text-align:center', 'box-shadow:0 4px 20px rgba(0,0,0,0.3)',
      'cursor:crosshair',
    ].join(';');
    overlay.textContent = '🎓 TEACH CHART TYPES — open the chart menu in PO, then click any chart-type option (Japanese/Heikin/Line/Bars). ESC to cancel.';
    document.body.appendChild(overlay);
    this._teachOverlay = overlay;

    const cleanup = () => {
      if (this._teachOverlay) { this._teachOverlay.remove(); this._teachOverlay = null; }
      if (this._teachClickHandler) {
        document.removeEventListener('click', this._teachClickHandler, true);
        this._teachClickHandler = null;
      }
      document.removeEventListener('keydown', escHandler, true);
      this.teachMode = false;
    };

    const escHandler = (e) => {
      if (e.key === 'Escape') {
        cleanup();
        warn('[chartType] teach cancelled');
        if (onComplete) onComplete({ success: false, reason: 'cancelled' });
      }
    };
    document.addEventListener('keydown', escHandler, true);

    const handler = (e) => {
      if (e.target.closest && e.target.closest('#pobot_host')) return;
      if (e.target === overlay || overlay.contains(e.target)) return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const analysis = _analyzeMenu(e.target);
      cleanup();
      if (!analysis) {
        error('[chartType] could not identify a menu container. Click a chart-type option with siblings.');
        if (onComplete) onComplete({ success: false, reason: 'no_container' });
        return;
      }
      const data = { ...analysis, taughtAt: Date.now() };
      _writeTeachData(data);
      success(`[chartType] ✓ TEACHED — ${analysis.childCount} chart-type buttons in "${analysis.containerSelector}"`);
      if (onComplete) onComplete({ success: true, data });
    };
    this._teachClickHandler = handler;
    document.addEventListener('click', handler, true);
  }

  clearTeachData() {
    try {
      if (typeof GM_setValue !== 'undefined') GM_setValue(STORAGE_KEY, null);
      localStorage.removeItem(STORAGE_KEY);
    } catch (_e) { /* silent */ }
    info('[chartType] taught chart menu cleared');
  }

  getStats() {
    return {
      teachData: _readTeachData(),
      stats: { ...this.stats },
    };
  }
}

export const chartTypeSwitcher = new ChartTypeSwitcher();
export default chartTypeSwitcher;
