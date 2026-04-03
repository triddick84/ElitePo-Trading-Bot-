/**
 * State management module
 * Centralized state for the trading bot
 */

export const state = {
  // Button states - all default to OFF
  appSignalEnabled: false,
  scanEnabled: false,
  autoTradeEnabled: false,
  dataCollectionEnabled: false,
  
  // Trading state
  lastTradeTime: 0,
  lastScanTradeTime: 0,
  lastAppTradeTime: 0,
  currentSignal: null,
  pendingTrade: null,
  
  // Connection state
  isConnected: false,
  connectionStatus: 'disconnected',
  
  // Statistics
  stats: {
    totalTrades: 0,
    wins: 0,
    losses: 0,
    currentStreak: 0,
    maxWinStreak: 0,
    maxLossStreak: 0,
  },
  
  // Money Management
  moneyManagement: {
    currentStep: 0,
    baseAmount: 1,
    currentAmount: 1,
    totalProfit: 0,
  },
  
  // UI state
  ui: {
    panelVisible: true,
    logExpanded: true,
    soundEnabled: true,
  },
  
  // Data collection
  collectedCandles: [],
  lastDataSend: 0,
};

/**
 * Update state
 * @param {string} key - State key (supports dot notation)
 * @param {any} value - New value
 */
export function setState(key, value) {
  const keys = key.split('.');
  let obj = state;
  
  for (let i = 0; i < keys.length - 1; i++) {
    obj = obj[keys[i]];
  }
  
  obj[keys[keys.length - 1]] = value;
}

/**
 * Get state value
 * @param {string} key - State key (supports dot notation)
 * @returns {any} State value
 */
export function getState(key) {
  const keys = key.split('.');
  let obj = state;
  
  for (const k of keys) {
    obj = obj[k];
    if (obj === undefined) return undefined;
  }
  
  return obj;
}

/**
 * Reset statistics
 */
export function resetStats() {
  state.stats = {
    totalTrades: 0,
    wins: 0,
    losses: 0,
    currentStreak: 0,
    maxWinStreak: 0,
    maxLossStreak: 0,
  };
}

/**
 * Record trade result
 * @param {boolean} isWin - Whether trade was a win
 */
export function recordTradeResult(isWin) {
  state.stats.totalTrades++;
  
  if (isWin) {
    state.stats.wins++;
    state.stats.currentStreak = Math.max(1, state.stats.currentStreak + 1);
    state.stats.maxWinStreak = Math.max(state.stats.maxWinStreak, state.stats.currentStreak);
  } else {
    state.stats.losses++;
    state.stats.currentStreak = Math.min(-1, state.stats.currentStreak - 1);
    state.stats.maxLossStreak = Math.max(state.stats.maxLossStreak, Math.abs(state.stats.currentStreak));
  }
}

/**
 * Save state to GM storage
 */
export function saveState() {
  if (typeof GM_setValue !== 'undefined') {
    GM_setValue('botState', JSON.stringify({
      stats: state.stats,
      moneyManagement: state.moneyManagement,
      ui: state.ui,
    }));
  }
}

/**
 * Load state from GM storage
 */
export function loadState() {
  if (typeof GM_getValue !== 'undefined') {
    try {
      const saved = GM_getValue('botState', null);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.stats) state.stats = { ...state.stats, ...parsed.stats };
        if (parsed.moneyManagement) state.moneyManagement = { ...state.moneyManagement, ...parsed.moneyManagement };
        if (parsed.ui) state.ui = { ...state.ui, ...parsed.ui };
      }
    } catch (e) {
      console.error('Failed to load state:', e);
    }
  }
}

export default state;
