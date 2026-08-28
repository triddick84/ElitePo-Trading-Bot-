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
  // Seconds Number Strategy (formerly 51S Reversal). Default OFF — user can
  // enable explicitly via the "SNS" panel button. Iter 64.
  _twentyOneSEnabled: false,
  
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

  // Iter 62 — Per-model probability thresholds (0 = no gating).
  // Applied client-side by sending min_conf_* query params to force-generate-v2.
  modelThresholds: {
    confluence: 0,      // any TA strategy
    improved_v2: 0,     // Improved v2 ML
    maximized_v3: 0,    // Maximized v3 ML
    iq720: 0,           // IQ-720 ensemble
  },

  // Iter 63 — Trade latency offset in seconds (-15..+15).
  // Positive: wait N seconds AFTER the bot decides to fire before clicking
  //   CALL/PUT (useful when PO chart lags or your wifi has consistent delay).
  // Negative: fire N seconds EARLIER on the polling cycle (anticipate signal
  //   staleness; widens the freshness budget for last-tick signals).
  // v8.73.0 — Default raised to +3.5s and supports 0.5s steps so EVERY
  // signal (scan/cycle/app/GO/SNS) gets a uniform +3.5s arming delay
  // unless the user explicitly drags the slider elsewhere.
  latencyOffsetSec: 3.5,
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
 * @param {Object} [meta] - Optional {direction, amount, asset, profit}
 */
export function recordTradeResult(isWin, meta = {}) {
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

  // Append to rolling trade_history for backend Session-Statistics card
  if (!Array.isArray(state.stats.trade_history)) state.stats.trade_history = [];
  state.stats.trade_history.push({
    result: isWin ? 'win' : 'loss',
    direction: meta.direction || null,
    amount: typeof meta.amount === 'number' ? meta.amount : null,
    asset: meta.asset || null,
    profit: typeof meta.profit === 'number' ? meta.profit : null,
    ts: Date.now(),
  });
  if (state.stats.trade_history.length > 50) {
    state.stats.trade_history = state.stats.trade_history.slice(-50);
  }
  if (typeof meta.profit === 'number') {
    state.stats.session_profit = (state.stats.session_profit || 0) + meta.profit;
  }
  state.stats.last_result = isWin ? 'win' : 'loss';

  // Iter 116 — Push to backend so the Mobile Auto-Trader page's Session
  // Statistics card fills in (previously always 0). Fire-and-forget.
  try {
    // Backend origin: prefer BACKEND_URL constant from ../config if present,
    // else fall back to the current tab origin (works when TM runs against
    // production directly and against preview from the same origin).
    const backend =
      (typeof window !== 'undefined' && window.__ELITE_PO_BACKEND__) ||
      'https://elitepotradingbot.com';
    fetch(`${backend}/api/tampermonkey/stats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wins: state.stats.wins,
        losses: state.stats.losses,
        consecutive_wins: state.stats.currentStreak > 0 ? state.stats.currentStreak : 0,
        consecutive_losses: state.stats.currentStreak < 0 ? Math.abs(state.stats.currentStreak) : 0,
        session_profit: state.stats.session_profit || 0,
        last_result: state.stats.last_result,
        auto_invert_active: !!(state.inversion && state.inversion.isInverted),
        trade_history: state.stats.trade_history,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch (_e) {
    /* silent — TM script never blocks trading on telemetry push */
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
      // 51s Reversal config (user-tuned thresholds must survive reload)
      twentyOneSConfig: state._twentyOneSConfig || null,
      // Selected strategy (from dropdown)
      selectedStrategy: state._selectedStrategy || null,
      // Iter 96 — Selected timeframe for the strategy picker
      selectedStrategyTf: state._selectedStrategyTf || '5s',
      // Iter 62 — per-model probability thresholds (TM panel sliders)
      modelThresholds: state.modelThresholds || null,
      // Iter 63 — trade latency offset (sec, range -15..+15)
      latencyOffsetSec: typeof state.latencyOffsetSec === 'number' ? state.latencyOffsetSec : 0,
      // Iter 107 — Auto-Invert Threshold slider
      invertThreshold: typeof state._invertThreshold === 'number' ? state._invertThreshold : null,
      // Iter 108 — Latency-Driven Abstain gate threshold (ms; 0 = OFF)
      latencyAbstainThreshold: typeof state._latencyAbstainThreshold === 'number' ? state._latencyAbstainThreshold : null,
      // Iter 109 — Elite Score gate config
      eliteGateThreshold: typeof state._eliteGateThreshold === 'number' ? state._eliteGateThreshold : null,
      eliteGateEnforceDirection: typeof state._eliteGateEnforceDirection === 'boolean' ? state._eliteGateEnforceDirection : null,
      // Save schema version so future migrations can reset cleanly
      _v: 7,
      _savedAt: Date.now(),
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
        const loadedVersion = parsed._v || 1;
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
          // Seconds Number Strategy (formerly "51S Reversal" / "21S Reversal")
          // Iter 64 — Per user request, this is no longer hard-locked ON at
          // startup. We now honor the saved toggle so the strategy is only
          // running when the user explicitly enables it. Defaults to OFF for
          // brand-new installs.
          state._twentyOneSEnabled = parsed.toggles.twentyOneSEnabled !== undefined
            ? !!parsed.toggles.twentyOneSEnabled : false;
        }
        if (parsed.cycleConfig) state._cycleConfig = parsed.cycleConfig;
        if (parsed.twentyOneSConfig) state._twentyOneSConfig = parsed.twentyOneSConfig;
        if (parsed.selectedStrategy) state._selectedStrategy = parsed.selectedStrategy;
        if (parsed.selectedStrategyTf) state._selectedStrategyTf = parsed.selectedStrategyTf;
        // Iter 62 — per-model thresholds
        if (parsed.modelThresholds && typeof parsed.modelThresholds === 'object') {
          state.modelThresholds = {
            confluence: Number(parsed.modelThresholds.confluence) || 0,
            improved_v2: Number(parsed.modelThresholds.improved_v2) || 0,
            maximized_v3: Number(parsed.modelThresholds.maximized_v3) || 0,
            iq720: Number(parsed.modelThresholds.iq720) || 0,
          };
        }
        // Iter 63 — restore latency offset (now float, 0.5s precision)
        if (typeof parsed.latencyOffsetSec === 'number') {
          let v = Math.max(-15, Math.min(15, parsed.latencyOffsetSec));
          // Snap legacy integer saves onto the 0.5 grid
          v = Math.round(v * 2) / 2;
          state.latencyOffsetSec = v;
        }
        // Iter 107/108/109 — Restore gate thresholds so slider positions
        // survive page reloads
        if (typeof parsed.invertThreshold === 'number') {
          state._invertThreshold = parsed.invertThreshold;
        }
        if (typeof parsed.latencyAbstainThreshold === 'number') {
          state._latencyAbstainThreshold = parsed.latencyAbstainThreshold;
        }
        if (typeof parsed.eliteGateThreshold === 'number') {
          state._eliteGateThreshold = parsed.eliteGateThreshold;
        }
        if (typeof parsed.eliteGateEnforceDirection === 'boolean') {
          state._eliteGateEnforceDirection = parsed.eliteGateEnforceDirection;
        }
        // Expose meta for debug / restore log
        state._lastSavedAt = parsed._savedAt || null;
        state._stateSchemaVersion = loadedVersion;
      }
    } catch (e) {
      console.error('Failed to load state:', e);
    }
  }
}

export default state;
