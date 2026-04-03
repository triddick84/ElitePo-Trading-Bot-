/**
 * UI Panel Component
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
  // Create host element
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
    'width: 280px !important',
    'transform: none !important',
  ].join('; '));

  // Attach shadow DOM to isolate styles
  shadowRoot = panelHost.attachShadow({ mode: 'open' });

  // Build panel inside shadow
  const panel = document.createElement('div');
  panel.id = 'gpt-bot-panel';
  panel.innerHTML = getPanelHTML();

  // Inject styles into shadow
  const style = document.createElement('style');
  style.textContent = getPanelCSS();
  shadowRoot.appendChild(style);
  shadowRoot.appendChild(panel);

  // Start watchdog to re-inject if removed
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
      console.log('[GPT Bot] Panel was removed, re-injecting...');
      reInjectPanel();
    } else {
      // Ensure visibility even if PO overrides inline styles
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
    // Remove old host if present
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
      'width: 280px !important',
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

    // Re-bind events
    if (window._gptBotCallbacks) {
      initPanelEvents(window._gptBotCallbacks);
    }
  } catch (e) {
    console.error('[GPT Bot] Re-inject failed:', e);
  }
}

/**
 * Get panel HTML content
 * @returns {string}
 */
function getPanelHTML() {
  return `
    <div class="gpt-panel-header" id="gpt-panel-header">
      <span class="gpt-panel-title">GPT Signal Bot v7.7.0</span>
      <div class="gpt-header-right">
        <span class="gpt-status-dot" id="gpt-status-dot"></span>
        <button class="gpt-minimize-btn" id="gpt-minimize-btn">_</button>
      </div>
    </div>
    
    <div class="gpt-panel-body" id="gpt-panel-body">
      <!-- Control Buttons -->
      <div class="gpt-control-row">
        <button id="gpt-btn-scan" class="gpt-btn" data-active="false">
          SCAN
        </button>
        <button id="gpt-btn-auto" class="gpt-btn" data-active="false">
          AUTO
        </button>
        <button id="gpt-btn-go" class="gpt-btn gpt-btn-go">
          GO
        </button>
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

/**
 * Get panel CSS (isolated inside shadow DOM)
 * @returns {string}
 */
function getPanelCSS() {
  return `
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    #gpt-bot-panel {
      width: 280px;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border: 1px solid #0f3460;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #e4e4e4;
      font-size: 12px;
      user-select: none;
      overflow: hidden;
    }
    
    .gpt-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 12px;
      background: rgba(0,0,0,0.3);
      cursor: move;
    }
    
    .gpt-panel-title {
      font-weight: 600;
      font-size: 13px;
      color: #a8dadc;
    }

    .gpt-header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .gpt-minimize-btn {
      background: none;
      border: 1px solid #4a5568;
      color: #a0aec0;
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
      background: #4a5568;
      color: #e4e4e4;
    }
    
    .gpt-status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #666;
      display: inline-block;
      transition: background 0.3s;
    }
    
    .gpt-status-dot.connected { background: #4caf50; }
    .gpt-status-dot.scanning { background: #2196f3; animation: gpt-pulse 1s infinite; }
    .gpt-status-dot.trading { background: #ff9800; }
    .gpt-status-dot.error { background: #f44336; }
    
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
      margin-bottom: 10px;
    }
    
    .gpt-btn {
      flex: 1;
      padding: 8px 4px;
      border: none;
      border-radius: 6px;
      background: #2d3748;
      color: #e4e4e4;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;
    }
    
    .gpt-btn:hover {
      background: #4a5568;
      transform: translateY(-1px);
    }
    
    .gpt-btn[data-active="true"] {
      background: linear-gradient(135deg, #3182ce 0%, #2b6cb0 100%);
      box-shadow: 0 0 10px rgba(49,130,206,0.4);
    }
    
    .gpt-btn-go {
      background: linear-gradient(135deg, #38a169 0%, #2f855a 100%);
    }
    
    .gpt-btn-go:hover {
      background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
    }
    
    .gpt-stats-row {
      display: flex;
      justify-content: space-between;
      padding: 8px;
      background: rgba(0,0,0,0.2);
      border-radius: 6px;
      margin-bottom: 10px;
    }
    
    .gpt-stat {
      text-align: center;
    }
    
    .gpt-stat-label {
      display: block;
      font-size: 10px;
      color: #888;
    }
    
    .gpt-stat-value {
      font-weight: 600;
      font-size: 13px;
    }
    
    .gpt-manual-row {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
    }
    
    .gpt-btn-win {
      background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
    }
    
    .gpt-btn-loss {
      background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
    }
    
    .gpt-mm-row {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px;
      background: rgba(0,0,0,0.2);
      border-radius: 6px;
      margin-bottom: 10px;
      font-size: 11px;
    }
    
    #gpt-mm-amount {
      width: 60px;
      padding: 4px;
      border: 1px solid #4a5568;
      border-radius: 4px;
      background: #2d3748;
      color: #e4e4e4;
      font-size: 11px;
    }
    
    .gpt-log-header {
      padding: 6px 8px;
      background: rgba(0,0,0,0.2);
      border-radius: 6px 6px 0 0;
      cursor: pointer;
      font-size: 11px;
    }
    
    .gpt-log {
      max-height: 150px;
      overflow-y: auto;
      background: rgba(0,0,0,0.3);
      border-radius: 0 0 6px 6px;
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 10px;
      padding: 4px;
    }
    
    .gpt-log::-webkit-scrollbar {
      width: 4px;
    }
    
    .gpt-log::-webkit-scrollbar-thumb {
      background: #4a5568;
      border-radius: 2px;
    }
  `;
}

/**
 * Helper: query inside shadow DOM
 */
function shadowQuery(selector) {
  return shadowRoot ? shadowRoot.querySelector(selector) : null;
}

/**
 * Initialize panel event handlers
 * @param {Object} callbacks - Callback functions
 */
export function initPanelEvents(callbacks = {}) {
  // Store callbacks for re-injection
  window._gptBotCallbacks = callbacks;

  if (!shadowRoot) return;

  // Set log container (inside shadow)
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
  
  // Make panel draggable
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
  const stepEl = shadowQuery('#gpt-mm-step');
  
  if (wlEl) {
    wlEl.textContent = `${state.stats.wins}/${state.stats.losses}`;
  }
  
  if (rateEl) {
    const total = state.stats.wins + state.stats.losses;
    const rate = total > 0 ? (state.stats.wins / total * 100).toFixed(1) : 0;
    rateEl.textContent = `${rate}%`;
  }
  
  if (streakEl) {
    const streak = state.stats.currentStreak;
    streakEl.textContent = streak > 0 ? `+${streak}` : streak.toString();
    streakEl.style.color = streak > 0 ? '#48bb78' : streak < 0 ? '#f56565' : '#e4e4e4';
  }
  
  if (stepEl) {
    stepEl.textContent = state.moneyManagement.currentStep.toString();
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

/**
 * Make the host element draggable via the header inside shadow DOM
 */
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
  updateStatusDot,
  cleanupPanel,
};
