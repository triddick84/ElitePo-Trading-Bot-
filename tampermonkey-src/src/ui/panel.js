/**
 * UI Panel Component - Elite Pocket Option Trading Bot
 * 
 * Mobile + Desktop compatible.
 * Uses direct DOM injection with !important inline styles.
 * All CSS classes use __epb__ prefix to avoid Pocket Option conflicts.
 * Touch events for mobile drag. Responsive sizing.
 */

import { CONFIG } from '../core/config.js';
import { state, setState, saveState } from '../core/state.js';
import { log, setLogContainer } from '../core/logger.js';

let panelEl = null;
let watchdogInterval = null;
const P = '__epb__';

function isMobile() {
  return /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent)
    || window.innerWidth < 500;
}

/**
 * Inject CSS
 */
function injectCSS() {
  const mobile = isMobile();
  const W = mobile ? 220 : 300;
  const FONT = mobile ? 11 : 12;
  const BTN_PAD = mobile ? '10px 6px' : '7px 4px';
  const BTN_FONT = mobile ? 12 : 11;

  const css = `
    #${P}host {
      position: fixed !important;
      top: 5px !important;
      right: 5px !important;
      z-index: 2147483647 !important;
      display: block !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;
      width: ${W}px !important;
      max-width: 90vw !important;
      transform: none !important;
      font-family: -apple-system, 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
      font-size: ${FONT}px !important;
      line-height: 1.4 !important;
      color: #e6edf3 !important;
      box-sizing: border-box !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    #${P}host * {
      box-sizing: border-box !important;
      margin: 0 !important;
      padding: 0 !important;
      font-family: inherit !important;
      line-height: inherit !important;
    }
    #${P}panel {
      width: 100% !important;
      background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%) !important;
      border: 1px solid #30363d !important;
      border-radius: ${mobile ? 8 : 12}px !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 1px rgba(88,166,255,0.3) !important;
      user-select: none !important;
      overflow: hidden !important;
      -webkit-user-select: none !important;
      touch-action: none !important;
    }
    .${P}header {
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      padding: ${mobile ? '8px 10px' : '10px 12px'} !important;
      background: linear-gradient(90deg, rgba(56,139,253,0.15) 0%, rgba(0,0,0,0.3) 100%) !important;
      cursor: move !important;
      border-bottom: 1px solid #21262d !important;
      touch-action: none !important;
    }
    .${P}title {
      font-weight: 700 !important;
      font-size: ${mobile ? 11 : 12}px !important;
      background: linear-gradient(90deg, #58a6ff, #79c0ff) !important;
      -webkit-background-clip: text !important;
      -webkit-text-fill-color: transparent !important;
      background-clip: text !important;
    }
    .${P}hright {
      display: flex !important;
      align-items: center !important;
      gap: 8px !important;
    }
    .${P}minbtn {
      background: none !important;
      border: 1px solid #30363d !important;
      color: #8b949e !important;
      width: ${mobile ? 28 : 20}px !important;
      height: ${mobile ? 28 : 20}px !important;
      border-radius: 4px !important;
      cursor: pointer !important;
      font-size: ${mobile ? 14 : 12}px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      -webkit-tap-highlight-color: transparent !important;
    }
    .${P}minbtn:hover, .${P}minbtn:active {
      background: #30363d !important;
      color: #e6edf3 !important;
    }
    .${P}dot {
      width: ${mobile ? 12 : 10}px !important;
      height: ${mobile ? 12 : 10}px !important;
      border-radius: 50% !important;
      background: #484f58 !important;
      display: inline-block !important;
      transition: background 0.3s !important;
    }
    .${P}dot.connected { background: #3fb950 !important; box-shadow: 0 0 6px rgba(63,185,80,0.4) !important; }
    .${P}dot.scanning { background: #58a6ff !important; animation: ${P}pulse 1s infinite !important; }
    .${P}dot.trading { background: #d29922 !important; }
    .${P}dot.error { background: #f85149 !important; }
    @keyframes ${P}pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .${P}body {
      padding: ${mobile ? '8px' : '10px'} !important;
    }
    .${P}body.collapsed {
      display: none !important;
    }
    .${P}row {
      display: flex !important;
      gap: ${mobile ? '4px' : '6px'} !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      align-items: center !important;
    }
    .${P}btn {
      flex: 1 !important;
      padding: ${BTN_PAD} !important;
      border: 1px solid #30363d !important;
      border-radius: 6px !important;
      background: #21262d !important;
      color: #e6edf3 !important;
      font-size: ${BTN_FONT}px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      transition: all 0.15s !important;
      text-align: center !important;
      -webkit-tap-highlight-color: transparent !important;
      min-height: ${mobile ? 36 : 28}px !important;
    }
    .${P}btn:hover, .${P}btn:active {
      background: #30363d !important;
      border-color: #58a6ff !important;
    }
    .${P}btn.active {
      background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
      border-color: #58a6ff !important;
      box-shadow: 0 0 8px rgba(56,139,253,0.3) !important;
    }
    .${P}btn-go {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${P}btn-go:hover, .${P}btn-go:active {
      background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%) !important;
    }
    .${P}btn-inv {
      flex: 0 0 ${mobile ? 70 : 80}px !important;
    }
    .${P}btn-inv.active {
      background: linear-gradient(135deg, #9e6a03 0%, #d29922 100%) !important;
      border-color: #d29922 !important;
      box-shadow: 0 0 8px rgba(210,153,34,0.3) !important;
      animation: ${P}pulse 2s infinite !important;
    }
    .${P}btn-r21s {
      flex: 0 0 ${mobile ? 60 : 70}px !important;
      background: linear-gradient(135deg, #4c1d95 0%, #6d28d9 100%) !important;
      border-color: #7c3aed !important;
      font-size: ${mobile ? 10 : 11}px !important;
    }
    .${P}btn-r21s.active {
      background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
      border-color: #a855f7 !important;
      box-shadow: 0 0 10px rgba(168,85,247,0.5) !important;
      animation: ${P}pulse 1.5s infinite !important;
    }
    .${P}invst {
      flex: 1 !important;
      font-size: ${mobile ? 9 : 10}px !important;
      color: #8b949e !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      white-space: nowrap !important;
      padding-left: 4px !important;
    }
    .${P}invst.on { color: #d29922 !important; font-weight: 600 !important; }
    .${P}stats {
      display: flex !important;
      justify-content: space-between !important;
      padding: ${mobile ? '6px' : '8px'} !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
    }
    .${P}stat {
      text-align: center !important;
      flex: 1 !important;
    }
    .${P}stlbl {
      display: block !important;
      font-size: ${mobile ? 8 : 9}px !important;
      color: #8b949e !important;
      text-transform: uppercase !important;
      letter-spacing: 0.5px !important;
    }
    .${P}stval {
      font-weight: 700 !important;
      font-size: ${mobile ? 12 : 13}px !important;
      color: #e6edf3 !important;
    }
    .${P}btn-win {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${P}btn-loss {
      background: linear-gradient(135deg, #da3633 0%, #f85149 100%) !important;
      border-color: #f85149 !important;
    }
    .${P}mmrow {
      display: flex !important;
      align-items: center !important;
      gap: ${mobile ? '4px' : '6px'} !important;
      padding: ${mobile ? '5px 6px' : '6px 8px'} !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      font-size: ${mobile ? 10 : 11}px !important;
    }
    .${P}mmlbl { color: #8b949e !important; }
    .${P}mminp {
      width: ${mobile ? 48 : 55}px !important;
      padding: ${mobile ? '4px' : '3px 4px'} !important;
      border: 1px solid #30363d !important;
      border-radius: 4px !important;
      background: #0d1117 !important;
      color: #e6edf3 !important;
      font-size: ${mobile ? 12 : 11}px !important;
      -webkit-appearance: none !important;
    }
    .${P}stratrow {
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
      margin-bottom: ${mobile ? '6px' : '8px'} !important;
      padding: 4px 6px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
    }
    .${P}stratlbl {
      font-size: ${mobile ? 9 : 10}px !important;
      color: #8b949e !important;
      white-space: nowrap !important;
    }
    .${P}stratsel {
      flex: 1 !important;
      padding: ${mobile ? '5px 4px' : '3px 4px'} !important;
      border: 1px solid #30363d !important;
      border-radius: 4px !important;
      background: #0d1117 !important;
      color: #e6edf3 !important;
      font-size: ${mobile ? 11 : 10}px !important;
      -webkit-appearance: none !important;
      appearance: none !important;
      cursor: pointer !important;
      min-height: ${mobile ? 30 : 24}px !important;
    }
    .${P}stratsel option {
      background: #0d1117 !important;
      color: #e6edf3 !important;
    }
    .${P}loghdr {
      padding: 5px 8px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px 6px 0 0 !important;
      cursor: pointer !important;
      font-size: ${mobile ? 10 : 11}px !important;
      color: #8b949e !important;
    }
    .${P}logbox {
      max-height: ${mobile ? 80 : 120}px !important;
      overflow-y: auto !important;
      background: rgba(0,0,0,0.4) !important;
      border: 1px solid #21262d !important;
      border-top: none !important;
      border-radius: 0 0 6px 6px !important;
      font-family: 'Consolas', 'Courier New', monospace !important;
      font-size: ${mobile ? 9 : 10}px !important;
      padding: 4px !important;
      color: #8b949e !important;
      -webkit-overflow-scrolling: touch !important;
    }
    .${P}logbox::-webkit-scrollbar { width: 4px !important; }
    .${P}logbox::-webkit-scrollbar-thumb { background: #30363d !important; border-radius: 2px !important; }
  `;

  if (typeof GM_addStyle === 'function') {
    try { GM_addStyle(css); } catch (e) { _fallbackCSS(css); }
  } else {
    _fallbackCSS(css);
  }
}

function _fallbackCSS(css) {
  const existing = document.getElementById(`${P}style`);
  if (existing) existing.remove();
  const el = document.createElement('style');
  el.setAttribute('type', 'text/css');
  el.setAttribute('id', `${P}style`);
  el.textContent = css;
  (document.head || document.documentElement).appendChild(el);
}

/**
 * Create panel
 */
export function createPanel() {
  console.log('[Elite Bot] Creating panel (mobile=' + isMobile() + ')...');
  injectCSS();
  console.log('[Elite Bot] CSS injected');

  panelEl = document.createElement('div');
  panelEl.id = `${P}host`;

  const titleShort = isMobile() ? 'Elite Bot' : CONFIG.BOT_NAME;

  panelEl.innerHTML = `
    <div id="${P}panel">
      <div class="${P}header" id="${P}header">
        <span class="${P}title">${titleShort}</span>
        <div class="${P}hright">
          <span class="${P}dot" id="${P}dot"></span>
          <button class="${P}minbtn" id="${P}minbtn">_</button>
        </div>
      </div>
      <div class="${P}body" id="${P}body">
        <div class="${P}row">
          <button id="${P}scan" class="${P}btn">SCAN</button>
          <button id="${P}auto" class="${P}btn">AUTO</button>
          <button id="${P}go" class="${P}btn ${P}btn-go">GO</button>
        </div>
        <div class="${P}row">
          <button id="${P}r21s" class="${P}btn ${P}btn-r21s" title="Fire opposite 5s trade at 21s-left on 1m candles">21S</button>
          <span class="${P}invst" id="${P}r21st">Off</span>
        </div>
        <div class="${P}stratrow">
          <span class="${P}stratlbl">Strategy:</span>
          <select id="${P}strat" class="${P}stratsel">
            <option value="default">All Strategies</option>
            <option value="ema20_pullback_reversal">EMA 20 Pullback</option>
          </select>
        </div>
        <div class="${P}row">
          <button id="${P}inv" class="${P}btn ${P}btn-inv">INVERT</button>
          <span class="${P}invst" id="${P}invst">Normal</span>
        </div>
        <div class="${P}stats">
          <div class="${P}stat"><span class="${P}stlbl">W/L</span><span class="${P}stval" id="${P}wl">0/0</span></div>
          <div class="${P}stat"><span class="${P}stlbl">Rate</span><span class="${P}stval" id="${P}rate">0%</span></div>
          <div class="${P}stat"><span class="${P}stlbl">Strk</span><span class="${P}stval" id="${P}streak">0</span></div>
          <div class="${P}stat"><span class="${P}stlbl">P/L</span><span class="${P}stval" id="${P}profit">$0</span></div>
        </div>
        <div class="${P}row">
          <button id="${P}win" class="${P}btn ${P}btn-win">WIN</button>
          <button id="${P}loss" class="${P}btn ${P}btn-loss">LOSS</button>
        </div>
        <div class="${P}mmrow">
          <span class="${P}mmlbl">$</span>
          <input type="number" id="${P}amt" class="${P}mminp" value="1" min="1" max="1000">
          <span class="${P}mmlbl">Step:</span>
          <span id="${P}step">0</span>
        </div>
        <div class="${P}loghdr" id="${P}logtog">Log <span id="${P}arrow">&#9660;</span></div>
        <div class="${P}logbox" id="${P}log"></div>
      </div>
    </div>
  `;

  startWatchdog();
  console.log('[Elite Bot] Panel created');
  return panelEl;
}

function q(id) {
  return document.getElementById(`${P}${id}`);
}

function startWatchdog() {
  if (watchdogInterval) clearInterval(watchdogInterval);
  watchdogInterval = setInterval(() => {
    const host = document.getElementById(`${P}host`);
    if (!host || !document.body.contains(host)) {
      console.log('[Elite Bot] Panel removed, re-injecting...');
      reInject();
    }
  }, 2000);
}

function reInject() {
  try {
    const old = document.getElementById(`${P}host`);
    if (old) old.remove();
    const newPanel = createPanel();
    document.body.appendChild(newPanel);
    if (window._epbCallbacks) {
      initPanelEvents(window._epbCallbacks);
    }
  } catch (e) {
    console.error('[Elite Bot] Re-inject failed:', e);
  }
}

/**
 * Init events (mouse + touch)
 */
export function initPanelEvents(callbacks = {}) {
  window._epbCallbacks = callbacks;
  setLogContainer(q('log'));

  // Minimize
  const minBtn = q('minbtn');
  const body = q('body');
  if (minBtn && body) {
    minBtn.addEventListener('click', () => {
      body.classList.toggle('collapsed');
      minBtn.textContent = body.classList.contains('collapsed') ? '+' : '_';
    });
  }

  // Scan
  const scanBtn = q('scan');
  if (scanBtn) {
    scanBtn.addEventListener('click', () => {
      const isActive = scanBtn.classList.contains('active');
      scanBtn.classList.toggle('active');
      setState('scanEnabled', !isActive);
      callbacks.onScanToggle?.(!isActive);
    });
  }

  // Auto
  const autoBtn = q('auto');
  if (autoBtn) {
    autoBtn.addEventListener('click', () => {
      const isActive = autoBtn.classList.contains('active');
      autoBtn.classList.toggle('active');
      setState('autoTradeEnabled', !isActive);
      callbacks.onAutoToggle?.(!isActive);
    });
  }

  q('go')?.addEventListener('click', () => callbacks.onGo?.());
  q('inv')?.addEventListener('click', () => callbacks.onInvertToggle?.());
  q('win')?.addEventListener('click', () => callbacks.onWin?.());
  q('loss')?.addEventListener('click', () => callbacks.onLoss?.());

  // 21s Reversal toggle
  const r21sBtn = q('r21s');
  if (r21sBtn) {
    r21sBtn.addEventListener('click', () => {
      const isActive = r21sBtn.classList.contains('active');
      r21sBtn.classList.toggle('active');
      callbacks.on21sReversalToggle?.(!isActive);
    });
  }

  // Strategy selector
  const stratSelect = q('strat');
  if (stratSelect) {
    stratSelect.addEventListener('change', (e) => {
      callbacks.onStrategyChange?.(e.target.value);
    });
  }

  const amtInput = q('amt');
  if (amtInput) {
    amtInput.addEventListener('change', (e) => {
      callbacks.onAmountChange?.(parseFloat(e.target.value) || 1);
    });
  }

  q('logtog')?.addEventListener('click', () => {
    const logEl = q('log');
    const arrow = q('arrow');
    if (logEl && arrow) {
      const expanded = logEl.style.display !== 'none';
      logEl.style.display = expanded ? 'none' : 'block';
      arrow.innerHTML = expanded ? '&#9654;' : '&#9660;';
    }
  });

  makeDraggable();
}

export function updateStatsDisplay() {
  const wlEl = q('wl');
  const rateEl = q('rate');
  const streakEl = q('streak');
  const profitEl = q('profit');
  const stepEl = q('step');

  if (wlEl) wlEl.textContent = `${state.stats.wins}/${state.stats.losses}`;

  if (rateEl) {
    const total = state.stats.wins + state.stats.losses;
    const rate = total > 0 ? (state.stats.wins / total * 100).toFixed(1) : 0;
    rateEl.textContent = `${rate}%`;
    rateEl.style.setProperty('color', parseFloat(rate) >= 55 ? '#3fb950' : parseFloat(rate) < 45 ? '#f85149' : '#e6edf3', 'important');
  }

  if (streakEl) {
    const s = state.stats.currentStreak;
    streakEl.textContent = s > 0 ? `+${s}` : String(s);
    streakEl.style.setProperty('color', s > 0 ? '#3fb950' : s < 0 ? '#f85149' : '#e6edf3', 'important');
  }

  if (profitEl) {
    const p = state.moneyManagement.totalProfit;
    profitEl.textContent = `$${p.toFixed(0)}`;
    profitEl.style.setProperty('color', p > 0 ? '#3fb950' : p < 0 ? '#f85149' : '#e6edf3', 'important');
  }

  if (stepEl) stepEl.textContent = String(state.moneyManagement.currentStep);
}

export function updateInvertDisplay(isInverted, reason) {
  const btn = q('inv');
  const st = q('invst');

  if (btn) {
    if (isInverted) btn.classList.add('active');
    else btn.classList.remove('active');
    btn.textContent = isInverted ? 'INV ON' : 'INVERT';
  }

  if (st) {
    st.textContent = isInverted ? (reason || 'Inverted') : 'Normal';
    if (isInverted) st.classList.add('on');
    else st.classList.remove('on');
  }
}

export function update21sReversalDisplay(enabled, stats = null) {
  const btn = q('r21s');
  const st = q('r21st');
  if (btn) {
    if (enabled) btn.classList.add('active');
    else btn.classList.remove('active');
  }
  if (st) {
    if (!enabled) {
      st.textContent = 'Off';
      st.classList.remove('on');
    } else if (stats) {
      st.textContent = `On ${stats.wins}/${stats.losses} (${stats.winRate}%)`;
      st.classList.add('on');
    } else {
      st.textContent = 'On';
      st.classList.add('on');
    }
  }
}

/**
 * Set a toggle button's active class programmatically (without triggering the click callback).
 * Used to restore persisted toggle states after page reload.
 */
export function setToggleActive(buttonId, active) {
  const btn = q(buttonId);
  if (!btn) return;
  if (active) btn.classList.add('active');
  else btn.classList.remove('active');
}

export function updateStatusDot(status) {
  const dot = q('dot');
  if (dot) dot.className = `${P}dot ${status}`;
}

/**
 * Make panel draggable — supports BOTH mouse and touch
 */
function makeDraggable() {
  const header = q('header');
  const host = document.getElementById(`${P}host`);
  if (!header || !host) return;

  let dragging = false, startX, startY, origLeft, origTop;

  function getPos(e) {
    if (e.touches && e.touches.length > 0) {
      return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
  }

  function onStart(e) {
    dragging = true;
    const pos = getPos(e);
    const rect = host.getBoundingClientRect();
    startX = pos.x;
    startY = pos.y;
    origLeft = rect.left;
    origTop = rect.top;
    e.preventDefault();
    e.stopPropagation();
  }

  function onMove(e) {
    if (!dragging) return;
    const pos = getPos(e);
    const dx = pos.x - startX;
    const dy = pos.y - startY;
    const newLeft = Math.max(0, Math.min(window.innerWidth - 50, origLeft + dx));
    const newTop = Math.max(0, Math.min(window.innerHeight - 50, origTop + dy));
    host.style.setProperty('left', newLeft + 'px', 'important');
    host.style.setProperty('top', newTop + 'px', 'important');
    host.style.setProperty('right', 'auto', 'important');
    e.preventDefault();
  }

  function onEnd() {
    dragging = false;
  }

  // Mouse events
  header.addEventListener('mousedown', onStart);
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onEnd);

  // Touch events
  header.addEventListener('touchstart', onStart, { passive: false });
  document.addEventListener('touchmove', onMove, { passive: false });
  document.addEventListener('touchend', onEnd);
}

export function cleanupPanel() {
  if (watchdogInterval) {
    clearInterval(watchdogInterval);
    watchdogInterval = null;
  }
}

/**
 * Populate strategy dropdown from API data
 * @param {Array} strategies - [{id, name, win_rate?}]
 * @param {string} selectedId - Currently active strategy ID
 */
export function populateStrategies(strategies, selectedId) {
  const sel = q('strat');
  if (!sel) return;

  sel.innerHTML = '';

  // Add "All Strategies" default option
  const defOpt = document.createElement('option');
  defOpt.value = 'default';
  defOpt.textContent = 'All Strategies';
  sel.appendChild(defOpt);

  if (strategies && strategies.length > 0) {
    for (const s of strategies) {
      if (s.id === 'default') continue;
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.win_rate ? `${s.name} (${s.win_rate})` : s.name;
      sel.appendChild(opt);
    }
  }

  if (selectedId) {
    sel.value = selectedId;
  }
}

export default {
  createPanel,
  initPanelEvents,
  updateStatsDisplay,
  updateInvertDisplay,
  updateStatusDot,
  cleanupPanel,
  populateStrategies,
};
