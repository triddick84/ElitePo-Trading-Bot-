/**
 * State management module
 * Centralized state for the trading bot
 */

export const state = {
  // Button states - all default to OFF
  appSignalEnabled: false,
  scanEnabled: false,
  autoTradeEnabled: false,
  autoInvertEnabled: true,     // explicit toggle: when ON, smart-invert logic applies
  cycleEnabled: false,         // CYCLE mode (rotate through favorites)
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

  // Auto-Invert State
  inversion: {
    isInverted: false,                // Currently inverting signals?
    invertedAt: 0,                    // Timestamp when inversion started
    invertedTradeCount: 0,            // Trades placed while inverted
    invertedWins: 0,                  // Wins while inverted
    invertedLosses: 0,                // Losses while inverted
    lastInvertChange: 0,              // Last time invert state changed
    reason: '',                       // Why we inverted
    manualOverride: false,            // User forced inversion manually
  },

  // Per-asset loss history for smart inversion
  assetHistory: {},
  // Structure: { "EURUSD_OTC": [ { direction: "CALL", result: "LOSS", ts: 123 }, ... ] }

  // Last executed trade details (for result matching)
  lastTrade: null,
  
  // Last scanned signal (for manual WIN/LOSS when no auto-trade)
  lastSignal: null,
  
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
  state.inversion = {
    isInverted: false,
    invertedAt: 0,
    invertedTradeCount: 0,
    invertedWins: 0,
    invertedLosses: 0,
    lastInvertChange: 0,
    reason: '',
    manualOverride: false,
  };
  state.assetHistory = {};
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
 * Record result for a specific asset (for smart inversion)
 * @param {string} asset - Asset symbol
 * @param {string} direction - CALL or PUT
 * @param {boolean} isWin
 */
export function recordAssetResult(asset, direction, isWin) {
  if (!asset) return;
  
  if (!state.assetHistory[asset]) {
    state.assetHistory[asset] = [];
  }
  
  state.assetHistory[asset].push({
    direction,
    result: isWin ? 'WIN' : 'LOSS',
    ts: Date.now(),
  });
  
  // Keep only last N results
  const maxSize = 10;
  if (state.assetHistory[asset].length > maxSize) {
    state.assetHistory[asset] = state.assetHistory[asset].slice(-maxSize);
  }
}

/**
 * Get consecutive same-direction losses for an asset
 * @param {string} asset
 * @returns {{ count: number, direction: string|null }}
 */
export function getConsecutiveSameDirectionLosses(asset) {
  if (!asset || !state.assetHistory[asset] || state.assetHistory[asset].length === 0) {
    return { count: 0, direction: null };
  }
  
  const history = state.assetHistory[asset];
  let count = 0;
  let direction = null;
  
  // Walk backward from most recent
  for (let i = history.length - 1; i >= 0; i--) {
    const entry = history[i];
    if (entry.result !== 'LOSS') break;
    
    if (direction === null) {
      direction = entry.direction;
      count = 1;
    } else if (entry.direction === direction) {
      count++;
    } else {
      break;
    }
  }
  
  return { count, direction };
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
      inversion: state.inversion,
      assetHistory: state.assetHistory,
      // Toggle states — user expects these to survive page reloads
      toggles: {
        scanEnabled: state.scanEnabled,
        autoTradeEnabled: state.autoTradeEnabled,
        autoInvertEnabled: state.autoInvertEnabled,
        cycleEnabled: state.cycleEnabled,
        dataCollectionEnabled: state.dataCollectionEnabled,
        appSignalEnabled: state.appSignalEnabled,
        twentyOneSEnabled: !!state._twentyOneSEnabled,
      },
      // Cycle mode config
      cycleConfig: state._cycleConfig || null,
      // 21S Reversal config (user-tuned thresholds must survive reload)
      twentyOneSConfig: state._twentyOneSConfig || null,
      // Selected strategy (from dropdown)
      selectedStrategy: state._selectedStrategy || null,
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
        if (parsed.inversion) state.inversion = { ...state.inversion, ...parsed.inversion };
        if (parsed.assetHistory) state.assetHistory = parsed.assetHistory;
        if (parsed.toggles) {
          state.scanEnabled = !!parsed.toggles.scanEnabled;
          state.autoTradeEnabled = !!parsed.toggles.autoTradeEnabled;
          // autoInvert defaults to true if never saved
          state.autoInvertEnabled = parsed.toggles.autoInvertEnabled !== undefined
            ? !!parsed.toggles.autoInvertEnabled : true;
          state.cycleEnabled = !!parsed.toggles.cycleEnabled;
          state.dataCollectionEnabled = !!parsed.toggles.dataCollectionEnabled;
          state.appSignalEnabled = !!parsed.toggles.appSignalEnabled;
          state._twentyOneSEnabled = !!parsed.toggles.twentyOneSEnabled;
        }
        if (parsed.cycleConfig) state._cycleConfig = parsed.cycleConfig;
        if (parsed.twentyOneSConfig) state._twentyOneSConfig = parsed.twentyOneSConfig;
        if (parsed.selectedStrategy) state._selectedStrategy = parsed.selectedStrategy;
      }
    } catch (e) {
      console.error('Failed to load state:', e);
    }
  }
}

export default state;
