/**
 * UI Panel Component - Elite Pocket Option Trading Bot
 * Creates and manages the trading bot control panel
 * Uses Shadow DOM for CSS isolation from Pocket Option styles
 */

import { CONFIG } from '../core/config.js';
import { state, setState, saveState } from '../core/state.js';
import { log, setLogContainer } from '../core/logger.js';

let shadowRoot = null;
let panelHost = null;
let watchdogInterval = null;

/**
 * Create the main UI panel using Shadow DOM for CSS isolation
 * @returns {HTMLElement} The host element containing the shadow panel
 */
export function createPanel() {
  panelHost = document.createElement('div');
  panelHost.id = 'gpt-bot-host';
  panelHost.setAttribute('style', [
    'position: fixed !important',
    'top: 10px !important',
    'right: 10px !important',
    'z-index: 2147483647 !important',
    'display: block !important',
    'visibility: visible !important',
    'opacity: 1 !important',
    'pointer-events: auto !important',
    'width: 300px !important',
    'transform: none !important',
  ].join('; '));

  shadowRoot = panelHost.attachShadow({ mode: 'open' });

  const panel = document.createElement('div');
  panel.id = 'gpt-bot-panel';
  panel.innerHTML = getPanelHTML();

  const style = document.createElement('style');
  style.textContent = getPanelCSS();
  shadowRoot.appendChild(style);
  shadowRoot.appendChild(panel);

  startWatchdog();

  return panelHost;
}

/**
 * Watchdog: re-inject panel if Pocket Option removes it
 */
function startWatchdog() {
  if (watchdogInterval) clearInterval(watchdogInterval);

  watchdogInterval = setInterval(() => {
    const host = document.getElementById('gpt-bot-host');
    if (!host || !document.body.contains(host)) {
      console.log('[Elite Bot] Panel was removed, re-injecting...');
      reInjectPanel();
    } else {
      host.style.setProperty('display', 'block', 'important');
      host.style.setProperty('visibility', 'visible', 'important');
      host.style.setProperty('opacity', '1', 'important');
      host.style.setProperty('z-index', '2147483647', 'important');
    }
  }, 2000);
}

/**
 * Re-inject the panel from scratch
 */
function reInjectPanel() {
  try {
    const old = document.getElementById('gpt-bot-host');
    if (old) old.remove();

    panelHost = document.createElement('div');
    panelHost.id = 'gpt-bot-host';
    panelHost.setAttribute('style', [
      'position: fixed !important',
      'top: 10px !important',
      'right: 10px !important',
      'z-index: 2147483647 !important',
      'display: block !important',
      'visibility: visible !important',
      'opacity: 1 !important',
      'pointer-events: auto !important',
      'width: 300px !important',
      'transform: none !important',
    ].join('; '));

    shadowRoot = panelHost.attachShadow({ mode: 'open' });

    const panel = document.createElement('div');
    panel.id = 'gpt-bot-panel';
    panel.innerHTML = getPanelHTML();

    const style = document.createElement('style');
    style.textContent = getPanelCSS();
    shadowRoot.appendChild(style);
    shadowRoot.appendChild(panel);

    document.body.appendChild(panelHost);

    if (window._gptBotCallbacks) {
      initPanelEvents(window._gptBotCallbacks);
    }
  } catch (e) {
    console.error('[Elite Bot] Re-inject failed:', e);
  }
}

function getPanelHTML() {
  return `
    <div class="gpt-panel-header" id="gpt-panel-header">
      <span class="gpt-panel-title">${CONFIG.BOT_NAME}</span>
      <div class="gpt-header-right">
        <span class="gpt-status-dot" id="gpt-status-dot"></span>
        <button class="gpt-minimize-btn" id="gpt-minimize-btn">_</button>
      </div>
    </div>
    
    <div class="gpt-panel-body" id="gpt-panel-body">
      <!-- Control Buttons Row 1 -->
      <div class="gpt-control-row">
        <button id="gpt-btn-scan" class="gpt-btn" data-active="false">SCAN</button>
        <button id="gpt-btn-auto" class="gpt-btn" data-active="false">AUTO</button>
        <button id="gpt-btn-go" class="gpt-btn gpt-btn-go">GO</button>
      </div>
      
      <!-- Control Buttons Row 2 - Invert -->
      <div class="gpt-control-row">
        <button id="gpt-btn-invert" class="gpt-btn gpt-btn-invert" data-active="false">INVERT</button>
        <span class="gpt-invert-status" id="gpt-invert-status">Normal</span>
      </div>
      
      <!-- Stats Display -->
      <div class="gpt-stats-row">
        <div class="gpt-stat">
          <span class="gpt-stat-label">W/L</span>
          <span class="gpt-stat-value" id="gpt-stat-wl">0/0</span>
        </div>
        <div class="gpt-stat">
          <span class="gpt-stat-label">Rate</span>
          <span class="gpt-stat-value" id="gpt-stat-rate">0%</span>
        </div>
        <div class="gpt-stat">
          <span class="gpt-stat-label">Streak</span>
          <span class="gpt-stat-value" id="gpt-stat-streak">0</span>
        </div>
        <div class="gpt-stat">
          <span class="gpt-stat-label">Profit</span>
          <span class="gpt-stat-value" id="gpt-stat-profit">$0</span>
        </div>
      </div>
      
      <!-- Manual Win/Loss Buttons -->
      <div class="gpt-manual-row">
        <button id="gpt-btn-win" class="gpt-btn gpt-btn-win">WIN</button>
        <button id="gpt-btn-loss" class="gpt-btn gpt-btn-loss">LOSS</button>
      </div>
      
      <!-- Money Management -->
      <div class="gpt-mm-row">
        <span class="gpt-mm-label">Amount: $</span>
        <input type="number" id="gpt-mm-amount" value="1" min="1" max="1000">
        <span class="gpt-mm-label">Step:</span>
        <span id="gpt-mm-step">0</span>
      </div>
      
      <!-- Log Container -->
      <div class="gpt-log-header" id="gpt-log-toggle">
        Log <span id="gpt-log-arrow">&#9660;</span>
      </div>
      <div class="gpt-log" id="gpt-bot-log"></div>
    </div>
  `;
}

function getPanelCSS() {
  return `
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    #gpt-bot-panel {
      width: 300px;
      background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
      border: 1px solid #30363d;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 1px rgba(88,166,255,0.3);
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #e6edf3;
      font-size: 12px;
      user-select: none;
      overflow: hidden;
    }
    
    .gpt-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 12px;
      background: linear-gradient(90deg, rgba(56,139,253,0.15) 0%, rgba(0,0,0,0.3) 100%);
      cursor: move;
      border-bottom: 1px solid #21262d;
    }
    
    .gpt-panel-title {
      font-weight: 700;
      font-size: 12px;
      background: linear-gradient(90deg, #58a6ff, #79c0ff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .gpt-header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .gpt-minimize-btn {
      background: none;
      border: 1px solid #30363d;
      color: #8b949e;
      width: 20px;
      height: 20px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gpt-minimize-btn:hover {
      background: #30363d;
      color: #e6edf3;
    }
    
    .gpt-status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #484f58;
      display: inline-block;
      transition: background 0.3s;
    }
    
    .gpt-status-dot.connected { background: #3fb950; box-shadow: 0 0 6px rgba(63,185,80,0.4); }
    .gpt-status-dot.scanning { background: #58a6ff; animation: gpt-pulse 1s infinite; }
    .gpt-status-dot.trading { background: #d29922; box-shadow: 0 0 6px rgba(210,153,34,0.4); }
    .gpt-status-dot.error { background: #f85149; }
    
    @keyframes gpt-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    
    .gpt-panel-body {
      padding: 10px;
    }

    .gpt-panel-body.collapsed {
      display: none;
    }
    
    .gpt-control-row {
      display: flex;
      gap: 6px;
      margin-bottom: 8px;
      align-items: center;
    }
    
    .gpt-btn {
      flex: 1;
      padding: 7px 4px;
      border: 1px solid #30363d;
      border-radius: 6px;
      background: #21262d;
      color: #e6edf3;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;
    }
    
    .gpt-btn:hover {
      background: #30363d;
      border-color: #58a6ff;
    }
    
    .gpt-btn[data-active="true"] {
      background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
      border-color: #58a6ff;
      box-shadow: 0 0 8px rgba(56,139,253,0.3);
    }
    
    .gpt-btn-go {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
      border-color: #3fb950;
    }
    
    .gpt-btn-go:hover {
      background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%);
    }

    .gpt-btn-invert {
      flex: 0 0 80px;
    }

    .gpt-btn-invert[data-active="true"] {
      background: linear-gradient(135deg, #9e6a03 0%, #d29922 100%);
      border-color: #d29922;
      box-shadow: 0 0 8px rgba(210,153,34,0.3);
      animation: gpt-pulse 2s infinite;
    }

    .gpt-invert-status {
      flex: 1;
      font-size: 10px;
      color: #8b949e;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      padding-left: 4px;
    }

    .gpt-invert-status.active {
      color: #d29922;
      font-weight: 600;
    }
    
    .gpt-stats-row {
      display: flex;
      justify-content: space-between;
      padding: 8px;
      background: rgba(0,0,0,0.3);
      border: 1px solid #21262d;
      border-radius: 6px;
      margin-bottom: 8px;
    }
    
    .gpt-stat {
      text-align: center;
      flex: 1;
    }
    
    .gpt-stat-label {
      display: block;
      font-size: 9px;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    .gpt-stat-value {
      font-weight: 700;
      font-size: 13px;
      color: #e6edf3;
    }
    
    .gpt-manual-row {
      display: flex;
      gap: 6px;
      margin-bottom: 8px;
    }
    
    .gpt-btn-win {
      background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
      border-color: #3fb950;
    }
    
    .gpt-btn-loss {
      background: linear-gradient(135deg, #da3633 0%, #f85149 100%);
      border-color: #f85149;
    }
    
    .gpt-mm-row {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      background: rgba(0,0,0,0.3);
      border: 1px solid #21262d;
      border-radius: 6px;
      margin-bottom: 8px;
      font-size: 11px;
    }
    
    .gpt-mm-label {
      color: #8b949e;
    }
    
    #gpt-mm-amount {
      width: 55px;
      padding: 3px 4px;
      border: 1px solid #30363d;
      border-radius: 4px;
      background: #0d1117;
      color: #e6edf3;
      font-size: 11px;
    }
    
    .gpt-log-header {
      padding: 5px 8px;
      background: rgba(0,0,0,0.3);
      border: 1px solid #21262d;
      border-radius: 6px 6px 0 0;
      cursor: pointer;
      font-size: 11px;
      color: #8b949e;
    }
    
    .gpt-log {
      max-height: 120px;
      overflow-y: auto;
      background: rgba(0,0,0,0.4);
      border: 1px solid #21262d;
      border-top: none;
      border-radius: 0 0 6px 6px;
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 10px;
      padding: 4px;
    }
    
    .gpt-log::-webkit-scrollbar {
      width: 4px;
    }
    
    .gpt-log::-webkit-scrollbar-thumb {
      background: #30363d;
      border-radius: 2px;
    }
  `;
}

function shadowQuery(selector) {
  return shadowRoot ? shadowRoot.querySelector(selector) : null;
}

/**
 * Initialize panel event handlers
 * @param {Object} callbacks
 */
export function initPanelEvents(callbacks = {}) {
  window._gptBotCallbacks = callbacks;

  if (!shadowRoot) return;

  setLogContainer(shadowQuery('#gpt-bot-log'));

  // Minimize button
  const minimizeBtn = shadowQuery('#gpt-minimize-btn');
  const body = shadowQuery('#gpt-panel-body');
  minimizeBtn?.addEventListener('click', () => {
    if (body) {
      body.classList.toggle('collapsed');
      minimizeBtn.textContent = body.classList.contains('collapsed') ? '+' : '_';
    }
  });

  // Scan button
  const scanBtn = shadowQuery('#gpt-btn-scan');
  scanBtn?.addEventListener('click', () => {
    const isActive = scanBtn.dataset.active === 'true';
    scanBtn.dataset.active = (!isActive).toString();
    setState('scanEnabled', !isActive);
    callbacks.onScanToggle?.(!isActive);
  });
  
  // Auto button
  const autoBtn = shadowQuery('#gpt-btn-auto');
  autoBtn?.addEventListener('click', () => {
    const isActive = autoBtn.dataset.active === 'true';
    autoBtn.dataset.active = (!isActive).toString();
    setState('autoTradeEnabled', !isActive);
    callbacks.onAutoToggle?.(!isActive);
  });
  
  // Go button
  const goBtn = shadowQuery('#gpt-btn-go');
  goBtn?.addEventListener('click', () => {
    callbacks.onGo?.();
  });

  // Invert button
  const invertBtn = shadowQuery('#gpt-btn-invert');
  invertBtn?.addEventListener('click', () => {
    callbacks.onInvertToggle?.();
  });
  
  // Win/Loss buttons
  shadowQuery('#gpt-btn-win')?.addEventListener('click', () => {
    callbacks.onWin?.();
  });
  
  shadowQuery('#gpt-btn-loss')?.addEventListener('click', () => {
    callbacks.onLoss?.();
  });
  
  // Amount input
  const amountInput = shadowQuery('#gpt-mm-amount');
  amountInput?.addEventListener('change', (e) => {
    const amount = parseFloat(e.target.value) || 1;
    callbacks.onAmountChange?.(amount);
  });
  
  // Log toggle
  shadowQuery('#gpt-log-toggle')?.addEventListener('click', () => {
    const logEl = shadowQuery('#gpt-bot-log');
    const arrowEl = shadowQuery('#gpt-log-arrow');
    if (logEl && arrowEl) {
      const isExpanded = logEl.style.display !== 'none';
      logEl.style.display = isExpanded ? 'none' : 'block';
      arrowEl.innerHTML = isExpanded ? '&#9654;' : '&#9660;';
      setState('ui.logExpanded', !isExpanded);
    }
  });
  
  makeDraggable();
}

/**
 * Update stats display
 */
export function updateStatsDisplay() {
  if (!shadowRoot) return;

  const wlEl = shadowQuery('#gpt-stat-wl');
  const rateEl = shadowQuery('#gpt-stat-rate');
  const streakEl = shadowQuery('#gpt-stat-streak');
  const profitEl = shadowQuery('#gpt-stat-profit');
  const stepEl = shadowQuery('#gpt-mm-step');
  
  if (wlEl) {
    wlEl.textContent = `${state.stats.wins}/${state.stats.losses}`;
  }
  
  if (rateEl) {
    const total = state.stats.wins + state.stats.losses;
    const rate = total > 0 ? (state.stats.wins / total * 100).toFixed(1) : 0;
    rateEl.textContent = `${rate}%`;
    rateEl.style.color = parseFloat(rate) >= 55 ? '#3fb950' : parseFloat(rate) < 45 ? '#f85149' : '#e6edf3';
  }
  
  if (streakEl) {
    const streak = state.stats.currentStreak;
    streakEl.textContent = streak > 0 ? `+${streak}` : streak.toString();
    streakEl.style.color = streak > 0 ? '#3fb950' : streak < 0 ? '#f85149' : '#e6edf3';
  }

  if (profitEl) {
    const profit = state.moneyManagement.totalProfit;
    profitEl.textContent = `$${profit.toFixed(0)}`;
    profitEl.style.color = profit > 0 ? '#3fb950' : profit < 0 ? '#f85149' : '#e6edf3';
  }
  
  if (stepEl) {
    stepEl.textContent = state.moneyManagement.currentStep.toString();
  }
}

/**
 * Update inversion display
 * @param {boolean} isInverted
 * @param {string} reason
 */
export function updateInvertDisplay(isInverted, reason) {
  if (!shadowRoot) return;

  const btn = shadowQuery('#gpt-btn-invert');
  const statusEl = shadowQuery('#gpt-invert-status');

  if (btn) {
    btn.dataset.active = isInverted.toString();
    btn.textContent = isInverted ? 'INVERT ON' : 'INVERT';
  }

  if (statusEl) {
    if (isInverted) {
      statusEl.textContent = reason || 'Signals inverted';
      statusEl.classList.add('active');
    } else {
      statusEl.textContent = 'Normal';
      statusEl.classList.remove('active');
    }
  }
}

/**
 * Update status dot
 * @param {string} status - 'connected', 'scanning', 'trading', 'error'
 */
export function updateStatusDot(status) {
  if (!shadowRoot) return;
  const dot = shadowQuery('#gpt-status-dot');
  if (dot) {
    dot.className = `gpt-status-dot ${status}`;
  }
}

function makeDraggable() {
  if (!shadowRoot || !panelHost) return;

  const header = shadowQuery('#gpt-panel-header');
  if (!header) return;
  
  let isDragging = false;
  let offsetX, offsetY;
  
  header.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - panelHost.offsetLeft;
    offsetY = e.clientY - panelHost.offsetTop;
    e.preventDefault();
  });
  
  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    panelHost.style.setProperty('left', (e.clientX - offsetX) + 'px', 'important');
    panelHost.style.setProperty('top', (e.clientY - offsetY) + 'px', 'important');
    panelHost.style.setProperty('right', 'auto', 'important');
  });
  
  document.addEventListener('mouseup', () => {
    isDragging = false;
  });
}

/**
 * Cleanup watchdog on unload
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
