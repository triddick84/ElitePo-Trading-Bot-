/**
 * UI Panel Component
 * Creates and manages the trading bot control panel
 */

import { CONFIG } from '../core/config.js';
import { state, setState, saveState } from '../core/state.js';
import { log, setLogContainer } from '../core/logger.js';

/**
 * Create the main UI panel
 * @returns {HTMLElement}
 */
export function createPanel() {
  const panel = document.createElement('div');
  panel.id = 'gpt-bot-panel';
  panel.innerHTML = getPanelHTML();
  
  // Apply styles
  applyPanelStyles(panel);
  
  return panel;
}

/**
 * Get panel HTML content
 * @returns {string}
 */
function getPanelHTML() {
  return `
    <div class="gpt-panel-header">
      <span class="gpt-panel-title">🤖 GPT Signal Bot v7.7.0</span>
      <span class="gpt-status-dot" id="gpt-status-dot"></span>
    </div>
    
    <div class="gpt-panel-body">
      <!-- Control Buttons -->
      <div class="gpt-control-row">
        <button id="gpt-btn-scan" class="gpt-btn" data-active="false">
          📡 SCAN
        </button>
        <button id="gpt-btn-auto" class="gpt-btn" data-active="false">
          🎯 AUTO
        </button>
        <button id="gpt-btn-go" class="gpt-btn gpt-btn-go">
          ▶️ GO
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
        <button id="gpt-btn-win" class="gpt-btn gpt-btn-win">✅ WIN</button>
        <button id="gpt-btn-loss" class="gpt-btn gpt-btn-loss">❌ LOSS</button>
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
        📋 Log <span id="gpt-log-arrow">▼</span>
      </div>
      <div class="gpt-log" id="gpt-bot-log"></div>
    </div>
  `;
}

/**
 * Apply CSS styles to panel
 * @param {HTMLElement} panel
 */
function applyPanelStyles(panel) {
  const style = document.createElement('style');
  style.textContent = `
    #gpt-bot-panel {
      position: fixed;
      top: 10px;
      right: 10px;
      width: 280px;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border: 1px solid #0f3460;
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      font-family: 'Segoe UI', Arial, sans-serif;
      z-index: 999999;
      color: #e4e4e4;
      font-size: 12px;
      user-select: none;
    }
    
    .gpt-panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 12px;
      background: rgba(0,0,0,0.3);
      border-radius: 12px 12px 0 0;
      cursor: move;
    }
    
    .gpt-panel-title {
      font-weight: 600;
      font-size: 13px;
    }
    
    .gpt-status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #666;
      transition: background 0.3s;
    }
    
    .gpt-status-dot.connected { background: #4caf50; }
    .gpt-status-dot.scanning { background: #2196f3; animation: pulse 1s infinite; }
    .gpt-status-dot.trading { background: #ff9800; }
    .gpt-status-dot.error { background: #f44336; }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    .gpt-panel-body {
      padding: 10px;
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
      font-family: 'Consolas', monospace;
      font-size: 10px;
    }
    
    .gpt-log::-webkit-scrollbar {
      width: 4px;
    }
    
    .gpt-log::-webkit-scrollbar-thumb {
      background: #4a5568;
      border-radius: 2px;
    }
  `;
  
  document.head.appendChild(style);
}

/**
 * Initialize panel event handlers
 * @param {Object} callbacks - Callback functions
 */
export function initPanelEvents(callbacks = {}) {
  const panel = document.getElementById('gpt-bot-panel');
  if (!panel) return;
  
  // Set log container
  setLogContainer(document.getElementById('gpt-bot-log'));
  
  // Scan button
  const scanBtn = document.getElementById('gpt-btn-scan');
  scanBtn?.addEventListener('click', () => {
    const isActive = scanBtn.dataset.active === 'true';
    scanBtn.dataset.active = (!isActive).toString();
    setState('scanEnabled', !isActive);
    callbacks.onScanToggle?.(!isActive);
  });
  
  // Auto button
  const autoBtn = document.getElementById('gpt-btn-auto');
  autoBtn?.addEventListener('click', () => {
    const isActive = autoBtn.dataset.active === 'true';
    autoBtn.dataset.active = (!isActive).toString();
    setState('autoTradeEnabled', !isActive);
    callbacks.onAutoToggle?.(!isActive);
  });
  
  // Go button
  const goBtn = document.getElementById('gpt-btn-go');
  goBtn?.addEventListener('click', () => {
    callbacks.onGo?.();
  });
  
  // Win/Loss buttons
  document.getElementById('gpt-btn-win')?.addEventListener('click', () => {
    callbacks.onWin?.();
  });
  
  document.getElementById('gpt-btn-loss')?.addEventListener('click', () => {
    callbacks.onLoss?.();
  });
  
  // Amount input
  const amountInput = document.getElementById('gpt-mm-amount');
  amountInput?.addEventListener('change', (e) => {
    const amount = parseFloat(e.target.value) || 1;
    callbacks.onAmountChange?.(amount);
  });
  
  // Log toggle
  document.getElementById('gpt-log-toggle')?.addEventListener('click', () => {
    const logEl = document.getElementById('gpt-bot-log');
    const arrowEl = document.getElementById('gpt-log-arrow');
    if (logEl && arrowEl) {
      const isExpanded = logEl.style.display !== 'none';
      logEl.style.display = isExpanded ? 'none' : 'block';
      arrowEl.textContent = isExpanded ? '▶' : '▼';
      setState('ui.logExpanded', !isExpanded);
    }
  });
  
  // Make panel draggable
  makeDraggable(panel);
}

/**
 * Update stats display
 */
export function updateStatsDisplay() {
  const wlEl = document.getElementById('gpt-stat-wl');
  const rateEl = document.getElementById('gpt-stat-rate');
  const streakEl = document.getElementById('gpt-stat-streak');
  const stepEl = document.getElementById('gpt-mm-step');
  
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
  const dot = document.getElementById('gpt-status-dot');
  if (dot) {
    dot.className = `gpt-status-dot ${status}`;
  }
}

/**
 * Make element draggable
 * @param {HTMLElement} element
 */
function makeDraggable(element) {
  const header = element.querySelector('.gpt-panel-header');
  if (!header) return;
  
  let isDragging = false;
  let offsetX, offsetY;
  
  header.addEventListener('mousedown', (e) => {
    isDragging = true;
    offsetX = e.clientX - element.offsetLeft;
    offsetY = e.clientY - element.offsetTop;
  });
  
  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    
    element.style.left = (e.clientX - offsetX) + 'px';
    element.style.top = (e.clientY - offsetY) + 'px';
    element.style.right = 'auto';
  });
  
  document.addEventListener('mouseup', () => {
    isDragging = false;
  });
}

export default {
  createPanel,
  initPanelEvents,
  updateStatsDisplay,
  updateStatusDot,
};
