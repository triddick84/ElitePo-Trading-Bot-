/**
 * Iter 98 — Favorites-bar CYCLE with point-to-teach discovery.
 *
 * User bug report (Aug 10, 2026):
 *   "the cycle feature in tampermonkey script is not working properly...
 *    what it is doing is clicking on assets dropdown and scrolling through
 *    the assets and markets not selecting anything, needs to scroll through
 *    the favorites bar above the assets drop down and have a teach function
 *    so it knows where to start and then it needs to cycle every 30 secs
 *    through the favorite bar assets and loop over again"
 *
 * Design:
 *   1. Teach mode: user clicks the "🎓 Teach Favorites" button → panel
 *      enters point-to-teach state → next click on PO's DOM records the
 *      SURROUNDING container of the tile they clicked as the favorites bar
 *      and its child-tile selector. Persisted via GM_setValue.
 *   2. Cycle: every N seconds (default 30, configurable), click the next
 *      tile in the taught container. Loops when it reaches the end.
 *   3. When CYCLE is OFF, this module is dormant. The signal poller (Iter
 *      95) is what switches assets on incoming signals.
 *   4. Replaces the previous Iter 68 CycleMode implementation that opened
 *      the currencies picker and iterated ALL assets — the source of the
 *      user's "clicking dropdown and scrolling" bug.
 */

import { log, info, warn, success, error } from '../core/logger.js';
import { flashCaptureConfirmation as _flashCapture, showTeachToast } from './teachVisuals.js';

const STORAGE_KEY = 'pobot_favoritesTeachData';
const DEFAULT_INTERVAL_MS = 30_000;

/**
 * Read/write the taught container selector + child selector.
 * Stored as { containerSelector, tileSelector, taughtAt }.
 */
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
 * Given an element the user clicked, discover the surrounding favorites
 * bar container by walking upward until we hit a node with >= 2 siblings
 * that all share the same tag/class shape. Then record:
 *   - container CSS selector (using nth-of-type parent chain if needed)
 *   - child selector relative to container
 */
function _analyzeClickedElement(target) {
  if (!target) return null;

  // Walk up: find a parent whose children include the clicked node AND
  // at least one more node with the same tagName + first classToken.
  let el = target;
  let container = null;
  let tileTag = null;
  let tileClass = null;
  for (let depth = 0; depth < 8 && el && el.parentElement; depth++) {
    el = el.parentElement;
    const kids = Array.from(el.children);
    if (kids.length < 2) continue;
    // Cluster by tag+first-class
    const shapeOf = (n) => `${n.tagName}.${(n.className || '').split(/\s+/)[0] || ''}`;
    const shapes = new Map();
    for (const k of kids) {
      const s = shapeOf(k);
      shapes.set(s, (shapes.get(s) || 0) + 1);
    }
    const dominant = [...shapes.entries()].sort((a, b) => b[1] - a[1])[0];
    if (dominant && dominant[1] >= 2) {
      container = el;
      tileTag = dominant[0].split('.')[0];
      tileClass = dominant[0].split('.')[1] || '';
      break;
    }
  }
  if (!container) return null;

  // Build a robust CSS selector for the container by walking up 3 levels
  // and stringifying id/class as anchors. Prefer id > class > tag+nth.
  const buildSelector = (node) => {
    if (node.id) return `#${node.id}`;
    if (node.className && typeof node.className === 'string') {
      const cls = node.className.split(/\s+/).filter(c => c && !c.startsWith('is-') && !c.includes('active')).slice(0, 2).join('.');
      if (cls) return `${node.tagName.toLowerCase()}.${cls}`;
    }
    // fallback nth-child
    const parent = node.parentElement;
    if (parent) {
      const idx = Array.from(parent.children).indexOf(node) + 1;
      return `${node.tagName.toLowerCase()}:nth-child(${idx})`;
    }
    return node.tagName.toLowerCase();
  };
  const chain = [];
  let n = container;
  for (let i = 0; i < 4 && n && n !== document.body; i++) {
    chain.unshift(buildSelector(n));
    n = n.parentElement;
  }
  const containerSelector = chain.join(' > ');

  // Child selector — prefer class-based, else tag-only
  let tileSelector = tileTag.toLowerCase();
  if (tileClass) tileSelector += `.${tileClass}`;

  return { containerSelector, tileSelector };
}


class FavoritesCycle {
  constructor() {
    this.running = false;
    this.rotationTimer = null;
    this.intervalMs = DEFAULT_INTERVAL_MS;
    this.currentIndex = 0;
    this.stats = { rotations: 0, misses: 0 };
    this.teachMode = false;
    this._teachClickHandler = null;
    this._teachOverlay = null;
  }

  isRunning() { return this.running; }
  isTeaching() { return this.teachMode; }

  setInterval(ms) {
    this.intervalMs = Math.max(5_000, Math.min(300_000, Number(ms) || DEFAULT_INTERVAL_MS));
    log(`[favCycle] interval set to ${this.intervalMs}ms`);
    if (this.running) { this.stop(); this.start(); }
  }

  /**
   * Enter point-to-teach mode. Next click on the page will be intercepted
   * and used to derive the favorites container selector.
   *
   * Iter 100 — Adds LIVE HOVER-OUTLINE preview: as the user moves the
   * mouse, we highlight the container that WOULD be captured, so they
   * can visually verify the right DOM row before clicking. After the
   * click we flash a green confirmation pulse on the captured container.
   */
  startTeach(onComplete) {
    if (this.teachMode) { warn('[favCycle] already teaching'); return; }
    this.teachMode = true;
    info('[favCycle] TEACH MODE — hover over your favorites bar to preview, click to capture. ESC to cancel.');

    // Overlay banner so user knows they're in teach mode
    const overlay = document.createElement('div');
    overlay.id = 'pobot_teach_overlay';
    overlay.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0',
      'background:linear-gradient(90deg,rgba(34,211,238,0.95),rgba(52,211,153,0.85))',
      'color:#082f38', 'font-family:system-ui,sans-serif', 'font-weight:800',
      'font-size:14px', 'padding:12px 20px', 'z-index:2147483647',
      'text-align:center', 'box-shadow:0 4px 20px rgba(0,0,0,0.3)',
      'cursor:crosshair',
    ].join(';');
    overlay.textContent = '🎓 TEACH MODE — hover to preview outline, click a tile in your favorites bar to capture. ESC to cancel.';
    document.body.appendChild(overlay);
    this._teachOverlay = overlay;

    // Live hover-outline element (positioned absolutely over the container
    // that WOULD be captured, updated on every mousemove).
    const hoverBox = document.createElement('div');
    hoverBox.id = 'pobot_teach_hover_box';
    hoverBox.style.cssText = [
      'position:fixed', 'pointer-events:none', 'z-index:2147483646',
      'border:3px dashed #22d3ee', 'border-radius:6px',
      'background:rgba(34,211,238,0.10)',
      'box-shadow:0 0 0 2px rgba(8,47,56,0.35), 0 8px 30px rgba(34,211,238,0.35)',
      'transition:top 60ms linear,left 60ms linear,width 60ms linear,height 60ms linear',
      'display:none',
    ].join(';');
    // Tiny caption
    const hoverCaption = document.createElement('div');
    hoverCaption.style.cssText = [
      'position:absolute', 'top:-26px', 'left:0',
      'background:#082f38', 'color:#22d3ee', 'font:600 11px system-ui,sans-serif',
      'padding:3px 8px', 'border-radius:4px', 'white-space:nowrap',
      'box-shadow:0 2px 8px rgba(0,0,0,0.4)',
    ].join(';');
    hoverCaption.textContent = 'preview';
    hoverBox.appendChild(hoverCaption);
    document.body.appendChild(hoverBox);
    this._hoverBox = hoverBox;
    this._hoverCaption = hoverCaption;

    const positionHoverBox = (el, tileCount) => {
      if (!el) { hoverBox.style.display = 'none'; return; }
      const rect = el.getBoundingClientRect();
      if (rect.width < 8 || rect.height < 8) { hoverBox.style.display = 'none'; return; }
      hoverBox.style.display = 'block';
      hoverBox.style.top = `${rect.top - 3}px`;
      hoverBox.style.left = `${rect.left - 3}px`;
      hoverBox.style.width = `${rect.width + 6}px`;
      hoverBox.style.height = `${rect.height + 6}px`;
      hoverCaption.textContent = tileCount != null
        ? `preview → ${tileCount} tile${tileCount === 1 ? '' : 's'}`
        : 'preview';
    };

    let lastPreviewTarget = null;
    const moveHandler = (e) => {
      const t = e.target;
      if (!t || (t.closest && t.closest('#pobot_host'))) { hoverBox.style.display = 'none'; return; }
      if (t === overlay || overlay.contains(t) || t === hoverBox || hoverBox.contains(t)) return;
      if (t === lastPreviewTarget) return;
      lastPreviewTarget = t;
      const analysis = _analyzeClickedElement(t);
      if (!analysis) { hoverBox.style.display = 'none'; return; }
      const container = document.querySelector(analysis.containerSelector);
      if (!container) { hoverBox.style.display = 'none'; return; }
      const tiles = container.querySelectorAll(analysis.tileSelector);
      positionHoverBox(container, tiles.length);
    };
    document.addEventListener('mousemove', moveHandler, true);

    const cleanup = () => {
      if (this._teachOverlay) { this._teachOverlay.remove(); this._teachOverlay = null; }
      if (this._hoverBox) { this._hoverBox.remove(); this._hoverBox = null; this._hoverCaption = null; }
      if (this._teachClickHandler) {
        document.removeEventListener('click', this._teachClickHandler, true);
        this._teachClickHandler = null;
      }
      document.removeEventListener('mousemove', moveHandler, true);
      document.removeEventListener('keydown', escHandler, true);
      this.teachMode = false;
    };

    const escHandler = (e) => {
      if (e.key === 'Escape') {
        cleanup();
        warn('[favCycle] teach mode cancelled');
        if (onComplete) onComplete({ success: false, reason: 'cancelled' });
      }
    };
    document.addEventListener('keydown', escHandler, true);

    const handler = (e) => {
      // Ignore clicks inside the panel itself so users can't teach the panel to itself
      if (e.target.closest && e.target.closest('#pobot_host')) return;
      // Ignore the overlay click
      if (e.target === overlay || overlay.contains(e.target)) return;
      // Ignore the hover-preview overlay
      if (this._hoverBox && (e.target === this._hoverBox || this._hoverBox.contains(e.target))) return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const analysis = _analyzeClickedElement(e.target);
      cleanup();

      if (!analysis) {
        error('[favCycle] could not identify a favorites container from that click. Try clicking a tile with at least one sibling.');
        if (onComplete) onComplete({ success: false, reason: 'no_container' });
        return;
      }

      // Verify the selector actually resolves back to a container with children
      const container = document.querySelector(analysis.containerSelector);
      if (!container) {
        warn(`[favCycle] taught selector didn't resolve: ${analysis.containerSelector}`);
        if (onComplete) onComplete({ success: false, reason: 'selector_broken' });
        return;
      }
      const tiles = container.querySelectorAll(analysis.tileSelector);
      if (tiles.length < 1) {
        warn(`[favCycle] taught container has no tiles matching ${analysis.tileSelector}`);
        if (onComplete) onComplete({ success: false, reason: 'no_tiles' });
        return;
      }

      const data = {
        containerSelector: analysis.containerSelector,
        tileSelector: analysis.tileSelector,
        taughtAt: Date.now(),
        tileCount: tiles.length,
      };
      _writeTeachData(data);
      success(`[favCycle] ✓ TEACHED — ${tiles.length} tiles in "${analysis.containerSelector}" (child: "${analysis.tileSelector}")`);
      // Post-capture confirmation flash — 2s green pulse around the container
      _flashCapture(container, `✓ ${tiles.length} favorites captured`);
      if (onComplete) onComplete({ success: true, data });
    };
    this._teachClickHandler = handler;
    document.addEventListener('click', handler, true);
  }

  getTeachData() { return _readTeachData(); }

  /** Return the currently-taught container's tiles (live NodeList → array). */
  _getTiles() {
    const data = _readTeachData();
    if (!data || !data.containerSelector) return [];
    const container = document.querySelector(data.containerSelector);
    if (!container) return [];
    return Array.from(container.querySelectorAll(data.tileSelector));
  }

  start() {
    if (this.running) { warn('[favCycle] already running'); return; }
    const data = _readTeachData();
    if (!data) {
      error('[favCycle] CANNOT START — no favorites container has been taught yet. Click "🎓 Teach Favorites" first.');
      return false;
    }
    const tiles = this._getTiles();
    if (tiles.length === 0) {
      error(`[favCycle] taught container "${data.containerSelector}" is empty. Re-teach on a valid favorites row.`);
      return false;
    }
    this.running = true;
    this.currentIndex = 0;
    this.stats = { rotations: 0, misses: 0 };
    success(`[favCycle] ✓ CYCLE STARTED — rotating ${tiles.length} favorites every ${this.intervalMs / 1000}s`);
    // Fire one immediately so user sees action
    this._rotate();
    // Then schedule
    this.rotationTimer = setInterval(() => this._rotate(), this.intervalMs);
    return true;
  }

  stop() {
    if (!this.running) return;
    this.running = false;
    if (this.rotationTimer) { clearInterval(this.rotationTimer); this.rotationTimer = null; }
    log('[favCycle] stopped');
  }

  _rotate() {
    if (!this.running) return;
    const tiles = this._getTiles();
    if (tiles.length === 0) {
      this.stats.misses++;
      warn('[favCycle] no tiles found on rotation — has the DOM changed? Re-teach if needed.');
      return;
    }
    // Wrap
    this.currentIndex %= tiles.length;
    const tile = tiles[this.currentIndex];
    const label = (tile.textContent || tile.getAttribute('title') || tile.getAttribute('data-symbol') || `#${this.currentIndex}`).trim().slice(0, 24);
    try {
      tile.click();
      // Also dispatch a proper mouse-event chain in case PO uses handlers
      // that don't fire on .click() (React onClick doesn't listen to that
      // synthetic event in some builds).
      const rect = tile.getBoundingClientRect();
      const opts = { bubbles: true, cancelable: true, view: window,
                     clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 };
      tile.dispatchEvent(new MouseEvent('mousedown', opts));
      tile.dispatchEvent(new MouseEvent('mouseup', opts));
      tile.dispatchEvent(new MouseEvent('click', opts));
      this.stats.rotations++;
      info(`[favCycle] → ${this.currentIndex + 1}/${tiles.length} · ${label}`);
    } catch (e) {
      this.stats.misses++;
      warn(`[favCycle] click failed on tile #${this.currentIndex}: ${e.message}`);
    }
    this.currentIndex = (this.currentIndex + 1) % tiles.length;
  }

  getStats() {
    return {
      running: this.running,
      intervalMs: this.intervalMs,
      currentIndex: this.currentIndex,
      teachData: _readTeachData(),
      stats: { ...this.stats },
    };
  }

  clearTeachData() {
    try {
      if (typeof GM_setValue !== 'undefined') GM_setValue(STORAGE_KEY, null);
      localStorage.removeItem(STORAGE_KEY);
    } catch (_e) { /* silent */ }
    if (this.running) this.stop();
    info('[favCycle] taught favorites cleared');
  }
}

export const favoritesCycle = new FavoritesCycle();
export default favoritesCycle;
