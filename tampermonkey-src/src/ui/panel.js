/**
 * UI Panel Component - Elite Pocket Option Trading Bot
 * 
 * Uses direct DOM injection with !important inline styles.
 * No Shadow DOM (unreliable in Tampermonkey context on some sites).
 * All CSS classes use __epb__ prefix to avoid Pocket Option conflicts.
 */

import { CONFIG } from '../core/config.js';
import { state, setState, saveState } from '../core/state.js';
import { log, setLogContainer } from '../core/logger.js';

let panelEl = null;
let watchdogInterval = null;
const PREFIX = '__epb__';

/**
 * Inject all panel CSS using GM_addStyle (Tampermonkey API)
 */
function injectCSS() {
  const css = `
    #${PREFIX}host {
      position: fixed !important;
      top: 10px !important;
      right: 10px !important;
      z-index: 2147483647 !important;
      display: block !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;
      width: 300px !important;
      transform: none !important;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
      font-size: 12px !important;
      line-height: 1.4 !important;
      color: #e6edf3 !important;
      box-sizing: border-box !important;
    }
    #${PREFIX}host * {
      box-sizing: border-box !important;
      margin: 0 !important;
      padding: 0 !important;
      font-family: inherit !important;
      line-height: inherit !important;
    }
    #${PREFIX}panel {
      width: 300px !important;
      background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%) !important;
      border: 1px solid #30363d !important;
      border-radius: 12px !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 1px rgba(88,166,255,0.3) !important;
      user-select: none !important;
      overflow: hidden !important;
    }
    .${PREFIX}header {
      display: flex !important;
      justify-content: space-between !important;
      align-items: center !important;
      padding: 10px 12px !important;
      background: linear-gradient(90deg, rgba(56,139,253,0.15) 0%, rgba(0,0,0,0.3) 100%) !important;
      cursor: move !important;
      border-bottom: 1px solid #21262d !important;
    }
    .${PREFIX}title {
      font-weight: 700 !important;
      font-size: 12px !important;
      background: linear-gradient(90deg, #58a6ff, #79c0ff) !important;
      -webkit-background-clip: text !important;
      -webkit-text-fill-color: transparent !important;
      background-clip: text !important;
    }
    .${PREFIX}hright {
      display: flex !important;
      align-items: center !important;
      gap: 8px !important;
    }
    .${PREFIX}minbtn {
      background: none !important;
      border: 1px solid #30363d !important;
      color: #8b949e !important;
      width: 20px !important;
      height: 20px !important;
      border-radius: 4px !important;
      cursor: pointer !important;
      font-size: 12px !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    .${PREFIX}minbtn:hover {
      background: #30363d !important;
      color: #e6edf3 !important;
    }
    .${PREFIX}dot {
      width: 10px !important;
      height: 10px !important;
      border-radius: 50% !important;
      background: #484f58 !important;
      display: inline-block !important;
      transition: background 0.3s !important;
    }
    .${PREFIX}dot.connected { background: #3fb950 !important; box-shadow: 0 0 6px rgba(63,185,80,0.4) !important; }
    .${PREFIX}dot.scanning { background: #58a6ff !important; animation: ${PREFIX}pulse 1s infinite !important; }
    .${PREFIX}dot.trading { background: #d29922 !important; }
    .${PREFIX}dot.error { background: #f85149 !important; }
    @keyframes ${PREFIX}pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .${PREFIX}body {
      padding: 10px !important;
    }
    .${PREFIX}body.collapsed {
      display: none !important;
    }
    .${PREFIX}row {
      display: flex !important;
      gap: 6px !important;
      margin-bottom: 8px !important;
      align-items: center !important;
    }
    .${PREFIX}btn {
      flex: 1 !important;
      padding: 7px 4px !important;
      border: 1px solid #30363d !important;
      border-radius: 6px !important;
      background: #21262d !important;
      color: #e6edf3 !important;
      font-size: 11px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      transition: all 0.2s !important;
      text-align: center !important;
    }
    .${PREFIX}btn:hover {
      background: #30363d !important;
      border-color: #58a6ff !important;
    }
    .${PREFIX}btn.active {
      background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
      border-color: #58a6ff !important;
      box-shadow: 0 0 8px rgba(56,139,253,0.3) !important;
    }
    .${PREFIX}btn-go {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${PREFIX}btn-go:hover {
      background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%) !important;
    }
    .${PREFIX}btn-inv {
      flex: 0 0 80px !important;
    }
    .${PREFIX}btn-inv.active {
      background: linear-gradient(135deg, #9e6a03 0%, #d29922 100%) !important;
      border-color: #d29922 !important;
      box-shadow: 0 0 8px rgba(210,153,34,0.3) !important;
      animation: ${PREFIX}pulse 2s infinite !important;
    }
    .${PREFIX}invst {
      flex: 1 !important;
      font-size: 10px !important;
      color: #8b949e !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      white-space: nowrap !important;
      padding-left: 4px !important;
    }
    .${PREFIX}invst.on { color: #d29922 !important; font-weight: 600 !important; }
    .${PREFIX}stats {
      display: flex !important;
      justify-content: space-between !important;
      padding: 8px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: 8px !important;
    }
    .${PREFIX}stat {
      text-align: center !important;
      flex: 1 !important;
    }
    .${PREFIX}stlbl {
      display: block !important;
      font-size: 9px !important;
      color: #8b949e !important;
      text-transform: uppercase !important;
      letter-spacing: 0.5px !important;
    }
    .${PREFIX}stval {
      font-weight: 700 !important;
      font-size: 13px !important;
      color: #e6edf3 !important;
    }
    .${PREFIX}btn-win {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
      border-color: #3fb950 !important;
    }
    .${PREFIX}btn-loss {
      background: linear-gradient(135deg, #da3633 0%, #f85149 100%) !important;
      border-color: #f85149 !important;
    }
    .${PREFIX}mmrow {
      display: flex !important;
      align-items: center !important;
      gap: 6px !important;
      padding: 6px 8px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px !important;
      margin-bottom: 8px !important;
      font-size: 11px !important;
    }
    .${PREFIX}mmlbl { color: #8b949e !important; }
    .${PREFIX}mminp {
      width: 55px !important;
      padding: 3px 4px !important;
      border: 1px solid #30363d !important;
      border-radius: 4px !important;
      background: #0d1117 !important;
      color: #e6edf3 !important;
      font-size: 11px !important;
    }
    .${PREFIX}loghdr {
      padding: 5px 8px !important;
      background: rgba(0,0,0,0.3) !important;
      border: 1px solid #21262d !important;
      border-radius: 6px 6px 0 0 !important;
      cursor: pointer !important;
      font-size: 11px !important;
      color: #8b949e !important;
    }
    .${PREFIX}logbox {
      max-height: 120px !important;
      overflow-y: auto !important;
      background: rgba(0,0,0,0.4) !important;
      border: 1px solid #21262d !important;
      border-top: none !important;
      border-radius: 0 0 6px 6px !important;
      font-family: 'Consolas', 'Courier New', monospace !important;
      font-size: 10px !important;
      padding: 4px !important;
      color: #8b949e !important;
    }
    .${PREFIX}logbox::-webkit-scrollbar { width: 4px !important; }
    .${PREFIX}logbox::-webkit-scrollbar-thumb { background: #30363d !important; border-radius: 2px !important; }
  `;

  if (typeof GM_addStyle === 'function') {
    try {
      GM_addStyle(css);
    } catch (e) {
      _fallbackInjectCSS(css);
    }
  } else {
    _fallbackInjectCSS(css);
  }
}

function _fallbackInjectCSS(css) {
  const styleEl = document.createElement('style');
  styleEl.setAttribute('type', 'text/css');
  styleEl.setAttribute('id', `${PREFIX}style`);
  styleEl.textContent = css;
  (document.head || document.documentElement).appendChild(styleEl);
}

/**
 * Create the panel DOM element
 */
export function createPanel() {
  console.log('[Elite Bot] Creating panel...');
  injectCSS();
  console.log('[Elite Bot] CSS injected');

  panelEl = document.createElement('div');
  panelEl.id = `${PREFIX}host`;

  panelEl.innerHTML = `
    <div id="${PREFIX}panel">
      <div class="${PREFIX}header" id="${PREFIX}header">
        <span class="${PREFIX}title">${CONFIG.BOT_NAME}</span>
        <div class="${PREFIX}hright">
          <span class="${PREFIX}dot" id="${PREFIX}dot"></span>
          <button class="${PREFIX}minbtn" id="${PREFIX}minbtn">_</button>
        </div>
      </div>
      <div class="${PREFIX}body" id="${PREFIX}body">
        <div class="${PREFIX}row">
          <button id="${PREFIX}scan" class="${PREFIX}btn">SCAN</button>
          <button id="${PREFIX}auto" class="${PREFIX}btn">AUTO</button>
          <button id="${PREFIX}go" class="${PREFIX}btn ${PREFIX}btn-go">GO</button>
        </div>
        <div class="${PREFIX}row">
          <button id="${PREFIX}inv" class="${PREFIX}btn ${PREFIX}btn-inv">INVERT</button>
          <span class="${PREFIX}invst" id="${PREFIX}invst">Normal</span>
        </div>
        <div class="${PREFIX}stats">
          <div class="${PREFIX}stat"><span class="${PREFIX}stlbl">W/L</span><span class="${PREFIX}stval" id="${PREFIX}wl">0/0</span></div>
          <div class="${PREFIX}stat"><span class="${PREFIX}stlbl">Rate</span><span class="${PREFIX}stval" id="${PREFIX}rate">0%</span></div>
          <div class="${PREFIX}stat"><span class="${PREFIX}stlbl">Streak</span><span class="${PREFIX}stval" id="${PREFIX}streak">0</span></div>
          <div class="${PREFIX}stat"><span class="${PREFIX}stlbl">Profit</span><span class="${PREFIX}stval" id="${PREFIX}profit">$0</span></div>
        </div>
        <div class="${PREFIX}row">
          <button id="${PREFIX}win" class="${PREFIX}btn ${PREFIX}btn-win">WIN</button>
          <button id="${PREFIX}loss" class="${PREFIX}btn ${PREFIX}btn-loss">LOSS</button>
        </div>
        <div class="${PREFIX}mmrow">
          <span class="${PREFIX}mmlbl">Amount: $</span>
          <input type="number" id="${PREFIX}amt" class="${PREFIX}mminp" value="1" min="1" max="1000">
          <span class="${PREFIX}mmlbl">Step:</span>
          <span id="${PREFIX}step">0</span>
        </div>
        <div class="${PREFIX}loghdr" id="${PREFIX}logtog">Log <span id="${PREFIX}arrow">&#9660;</span></div>
        <div class="${PREFIX}logbox" id="${PREFIX}log"></div>
      </div>
    </div>
  `;

  startWatchdog();
  console.log('[Elite Bot] Panel DOM created, returning element');
  return panelEl;
}

function q(id) {
  return document.getElementById(`${PREFIX}${id}`);
}

/**
 * Watchdog: re-inject panel if PO removes it
 */
function startWatchdog() {
  if (watchdogInterval) clearInterval(watchdogInterval);

  watchdogInterval = setInterval(() => {
    const host = document.getElementById(`${PREFIX}host`);
    if (!host || !document.body.contains(host)) {
      console.log('[Elite Bot] Panel removed, re-injecting...');
      reInject();
    }
  }, 2000);
}

function reInject() {
  try {
    const old = document.getElementById(`${PREFIX}host`);
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
 * Initialize panel event handlers
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

  // Go
  q('go')?.addEventListener('click', () => callbacks.onGo?.());

  // Invert
  q('inv')?.addEventListener('click', () => callbacks.onInvertToggle?.());

  // Win / Loss
  q('win')?.addEventListener('click', () => callbacks.onWin?.());
  q('loss')?.addEventListener('click', () => callbacks.onLoss?.());

  // Amount
  const amtInput = q('amt');
  if (amtInput) {
    amtInput.addEventListener('change', (e) => {
      callbacks.onAmountChange?.(parseFloat(e.target.value) || 1);
    });
  }

  // Log toggle
  q('logtog')?.addEventListener('click', () => {
    const logEl = q('log');
    const arrow = q('arrow');
    if (logEl && arrow) {
      const expanded = logEl.style.display !== 'none';
      logEl.style.display = expanded ? 'none' : 'block';
      arrow.innerHTML = expanded ? '&#9654;' : '&#9660;';
    }
  });

  // Draggable
  makeDraggable();
}

/**
 * Update stats display
 */
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

/**
 * Update inversion display
 */
export function updateInvertDisplay(isInverted, reason) {
  const btn = q('inv');
  const st = q('invst');

  if (btn) {
    if (isInverted) btn.classList.add('active');
    else btn.classList.remove('active');
    btn.textContent = isInverted ? 'INVERT ON' : 'INVERT';
  }

  if (st) {
    st.textContent = isInverted ? (reason || 'Signals inverted') : 'Normal';
    if (isInverted) st.classList.add('on');
    else st.classList.remove('on');
  }
}

/**
 * Update status dot
 */
export function updateStatusDot(status) {
  const dot = q('dot');
  if (dot) dot.className = `${PREFIX}dot ${status}`;
}

/**
 * Make panel draggable via header
 */
function makeDraggable() {
  const header = q('header');
  const host = document.getElementById(`${PREFIX}host`);
  if (!header || !host) return;

  let dragging = false, ox, oy;

  header.addEventListener('mousedown', (e) => {
    dragging = true;
    ox = e.clientX - host.offsetLeft;
    oy = e.clientY - host.offsetTop;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    host.style.setProperty('left', (e.clientX - ox) + 'px', 'important');
    host.style.setProperty('top', (e.clientY - oy) + 'px', 'important');
    host.style.setProperty('right', 'auto', 'important');
  });

  document.addEventListener('mouseup', () => { dragging = false; });
}

/**
 * Cleanup watchdog
 */
export function cleanupPanel() {
  if (watchdogInterval) {
    clearInterval(watchdogInterval);
    watchdogInterval = null;
  }
}

export default {
  createPanel,
  initPanelEvents,
  updateStatsDisplay,
  updateInvertDisplay,
  updateStatusDot,
  cleanupPanel,
};
