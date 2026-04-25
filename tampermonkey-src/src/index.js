/*
 * Elite Pocket Option Trading Bot v8.0.0
 * Main entry point - coordinates all modules
 */

import { CONFIG } from './core/config.js';
import { state, setState, loadState, saveState, resetStats } from './core/state.js';
import { log, info, warn, success, error } from './core/logger.js';
import { createPanel, initPanelEvents, updateStatsDisplay, updateInvertDisplay, updateStatusDot, cleanupPanel, populateStrategies, update21sReversalDisplay, update1h51sReversalDisplay, setToggleActive } from './ui/panel.js';
import { strategyManager } from './strategies/manager.js';
import { tradeExecutor } from './trading/executor.js';
import { smartInvert } from './trading/smartInvert.js';
import { twentyOneSecondReversal } from './strategies/twentyOneSecondReversal.js';
import { oneHour51sReversal } from './strategies/oneHour51sReversal.js';
import { ssidBridge, poLivePrice } from './trading/ssidBridge.js';
import { livePriceTracker } from './trading/livePriceTracker.js';
import { cycleMode } from './trading/cycleMode.js';
import { appSignalPoller } from './trading/appSignalPoller.js';
import { scanMarkets } from './utils/api.js';
import { get, post } from './utils/api.js';
import { getCurrentAsset, getCurrentPrice, waitForElement } from './utils/dom.js';
import { priceScraper } from './trading/priceScraper.js';

// Install the SSID bridge IMMEDIATELY at module load — before any async init.
// This wraps window.WebSocket so we can capture the first PO auth frame.
// Must run before PO opens its trading socket.
ssidBridge.install();

class EliteTradingBot {
  constructor() {
    this.initialized = false;
    this.scanInterval = null;
    this.statsInterval = null;
    this.dataCollectionInterval = null;
  }
  
  async init() {
    log(`Initializing ${CONFIG.BOT_NAME} v${CONFIG.BOT_VERSION}...`);
    
    // Wait for page to be interactive
    await waitForElement('body', 15000);
    
    // Small delay to let PO finish rendering
    await new Promise(r => setTimeout(r, 2000));
    
    // Load saved state
    loadState();
    
    // Register smart-invert UI callback
    smartInvert.onInvertChange((isInverted, reason) => {
      updateInvertDisplay(isInverted, reason);
    });
    
    // Create and inject UI panel
    this.createUI();
    
    // Start price scraper
    priceScraper.start(500);
    
    // Sync strategy selection from app + populate dropdown
    await this.loadStrategies();
    
    // Start stats update interval
    this.statsInterval = setInterval(() => {
      updateStatsDisplay();
    }, 1000);

    // Periodic auto-save every 15s so stats/inversion/asset-history persist
    // even if the user never clicks a toggle between reloads
    this.autoSaveInterval = setInterval(() => {
      try {
        // Keep the 21S config mirror fresh in case it was tuned via console
        if (twentyOneSecondReversal.config) {
          state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        }
        state._twentyOneSEnabled = twentyOneSecondReversal.isEnabled();
        saveState();
      } catch (_e) { /* ignore */ }
    }, 15_000);
    
    // Restore inversion display from saved state
    if (state.inversion.isInverted) {
      updateInvertDisplay(true, state.inversion.reason);
    }

    // Restore toggle states from saved state (persists across PO reloads)
    this._restoreToggleStates();

    this.initialized = true;
    updateStatusDot('connected');
    success(`${CONFIG.BOT_NAME} initialized successfully`);
    
    // Log available strategies
    const strategies = strategyManager.getStatus();
    info(`Loaded ${strategies.length} strategies: ${strategies.map(s => s.name).join(', ')}`);
  }
  
  createUI() {
    console.log('[Elite Bot] createUI called, appending to body...');
    const panelHost = createPanel();
    document.body.appendChild(panelHost);
    console.log('[Elite Bot] Panel appended to body. Visible:', panelHost.offsetWidth > 0);
    
    initPanelEvents({
      onScanToggle: (enabled) => {
        state.scanEnabled = enabled;
        if (enabled) {
          this.startScanning();
        } else {
          this.stopScanning();
        }
        saveState();
      },
      onAutoToggle: (enabled) => {
        state.autoTradeEnabled = enabled;
        log(`Auto-trade ${enabled ? 'enabled' : 'disabled'}`);
        saveState();
      },
      onGo: () => {
        this.executeSingleScan();
      },
      onInvertToggle: () => {
        smartInvert.manualToggle();
        saveState();
      },
      onStrategyChange: async (strategyId) => {
        log(`Strategy changed to: ${strategyId}`);
        state._selectedStrategy = strategyId;
        strategyManager.applyAppSelection(strategyId);
        saveState();
        try {
          await post('/strategies/select', { timeframe: '5s', strategy_id: strategyId });
          info(`Strategy "${strategyId}" synced to server`);
        } catch (e) {
          warn(`Failed to sync strategy to server: ${e.message}`);
        }
      },
      onWin: () => {
        tradeExecutor.recordResult(true);
        twentyOneSecondReversal.onResultRecorded(true);
        oneHour51sReversal.onResultRecorded(true);
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
        if (oneHour51sReversal.isEnabled()) {
          update1h51sReversalDisplay(true, oneHour51sReversal.getStats());
        }
        saveState();
      },
      onLoss: () => {
        tradeExecutor.recordResult(false);
        twentyOneSecondReversal.onResultRecorded(false);
        oneHour51sReversal.onResultRecorded(false);
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
        if (oneHour51sReversal.isEnabled()) {
          update1h51sReversalDisplay(true, oneHour51sReversal.getStats());
        }
        saveState();
      },
      on21sReversalToggle: (enabled) => {
        if (enabled) {
          twentyOneSecondReversal.enable();
        } else {
          twentyOneSecondReversal.disable();
        }
        state._twentyOneSEnabled = enabled;
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
        update21sReversalDisplay(enabled, enabled ? twentyOneSecondReversal.getStats() : null);
        saveState();
      },
      on1h51sReversalToggle: (enabled) => {
        if (enabled) {
          oneHour51sReversal.enable();
        } else {
          oneHour51sReversal.disable();
        }
        state._oneHour51sEnabled = enabled;
        state._oneHour51sConfig = { ...oneHour51sReversal.config };
        update1h51sReversalDisplay(enabled, enabled ? oneHour51sReversal.getStats() : null);
        saveState();
      },
      onAmountChange: (amount) => {
        tradeExecutor.setBaseAmount(amount);
        saveState();
      },

      onCycleToggle: async (enabled) => {
        state.cycleEnabled = enabled;
        if (enabled) {
          await cycleMode.start();
        } else {
          cycleMode.stop();
        }
        saveState();
      },

      onAppSignalToggle: (enabled) => {
        state.appSignalEnabled = enabled;
        if (enabled) {
          appSignalPoller.start(5_000);
        } else {
          appSignalPoller.stop();
        }
        saveState();
      },

      onAutoInvertToggle: (enabled) => {
        state.autoInvertEnabled = enabled;
        log(`Auto-invert ${enabled ? 'ENABLED' : 'DISABLED'} - smart-invert decisions will ${enabled ? 'apply' : 'be bypassed'}`);
        saveState();
      },
    });
  }
  
  async loadStrategies() {
    try {
      // Fetch available strategies from API
      const available = await get('/strategies/available/5s');
      const strategies = available.strategies || [];
      
      // Fetch current selection
      const selected = await get('/strategies/selected');
      const selectedId = selected.selections?.['5s'] || 'default';
      
      // Populate dropdown UI
      populateStrategies(strategies, selectedId);
      
      // Apply selection locally
      strategyManager.applyAppSelection(selectedId);
      
      info(`Strategies loaded: ${strategies.length} available, active: ${selectedId}`);
    } catch (e) {
      warn(`Strategy load failed (using all): ${e.message}`);
    }
  }

  /**
   * Restore persisted toggle states after UI is ready.
   * Runs after loadState() + createUI() so we can both read the saved values
   * AND mutate the visual state of the newly-created buttons.
   */
  _restoreToggleStates() {
    try {
      // SCAN toggle
      if (state.scanEnabled) {
        setToggleActive('scan', true);
        this.startScanning();
        info('[Restore] SCAN was on before reload — resumed');
      }

      // AUTO toggle
      if (state.autoTradeEnabled) {
        setToggleActive('auto', true);
        info('[Restore] AUTO was on before reload — resumed');
      }

      // AUTO-INVERT toggle (default ON if never saved)
      if (state.autoInvertEnabled) {
        setToggleActive('ainv', true);
      }

      // CYCLE toggle
      if (state.cycleEnabled) {
        setToggleActive('cycle', true);
        cycleMode.start().catch(() => {});
        info('[Restore] CYCLE was on before reload — resumed');
      }

      // APP signal poller toggle
      if (state.appSignalEnabled) {
        setToggleActive('app', true);
        appSignalPoller.start(5_000);
        info('[Restore] APP poller was on before reload — resumed');
      }

      // 21S Reversal
      if (state._twentyOneSConfig) {
        twentyOneSecondReversal.setConfig(state._twentyOneSConfig);
      }
      if (state._twentyOneSEnabled) {
        twentyOneSecondReversal.enable();
        update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        info('[Restore] 21S was on before reload — resumed with saved config');
      }

      // 1H 51s Reversal
      if (state._oneHour51sConfig) {
        oneHour51sReversal.setConfig(state._oneHour51sConfig);
      }
      if (state._oneHour51sEnabled) {
        oneHour51sReversal.enable();
        update1h51sReversalDisplay(true, oneHour51sReversal.getStats());
        info('[Restore] 1H51 was on before reload — resumed with saved config');
      }
    } catch (e) {
      warn(`[Restore] toggle state restoration failed: ${e.message}`);
    }
  }
  
  startScanning() {
    if (this.scanInterval) return;
    
    log('Starting market scan...');
    updateStatusDot('scanning');
    
    this.scanInterval = setInterval(async () => {
      await this.performScan();
    }, CONFIG.SCAN_INTERVAL);
    
    // Run immediately
    this.performScan();
  }
  
  stopScanning() {
    if (this.scanInterval) {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
    }
    updateStatusDot('connected');
    log('Scanning stopped');
  }
  
  async executeSingleScan() {
    info('[GO] Force scan triggered - generating HIGH-ACCURACY signal NOW...');
    try {
      const asset = getCurrentAsset();
      if (!asset) {
        warn('[GO] Could not detect current asset - is a pair selected in PO?');
        return;
      }

      // Call the new force-generate-v2 endpoint — always returns a signal
      log(`[GO] Calling force-generate-v2 for ${asset}...`);
      const resp = await post(`/signals/force-generate-v2?asset=${encodeURIComponent(asset)}&expiry_seconds=60`, {});

      if (!resp || !resp.signal) {
        warn('[GO] force-generate returned no signal - falling back to standard scan');
        await this.performScan({ force: true });
        return;
      }

      const signal = resp.signal;
      state.lastSignal = {
        direction: signal.direction,
        symbol: signal.symbol || asset,
        confidence: signal.confidence,
        strategy: signal.strategy,
      };

      info(
        `[GO] SIGNAL: ${signal.direction} ${signal.symbol || asset} @ ${signal.confidence}% ` +
        `[${signal.quality || 'N/A'}] | confluence=${signal.confluence_score} ` +
        `| agreeing=${signal.agreeing_strategies || 0}/${Object.keys(signal.components || {}).length} ` +
        `| strategy=${signal.strategy}`
      );
      if (signal.reason) log(`[GO] Reason: ${signal.reason}`);
      if (signal.quality === 'LOW') {
        warn('[GO] LOW-quality signal — weak strategy participation. Consider passing.');
      }

      // Always execute via tradeExecutor in force mode (bypasses AUTO gate)
      await tradeExecutor.execute(signal, 'go-force');
    } catch (e) {
      error(`[GO] force-generate error: ${e.message}`);
      console.error('[GO stack]', e);
      // Ultimate fallback — try the old scan path
      try { await this.performScan({ force: true }); } catch (_e) { /* ignore */ }
    }
  }

  async performScan(opts = {}) {
    const isForce = !!opts.force;
    try {
      const asset = getCurrentAsset();
      if (!asset) {
        warn(isForce
          ? '[GO] Could not detect current asset - is a pair selected in PO?'
          : 'Could not detect current asset'
        );
        return;
      }

      // Try local signal generation first
      if (CONFIG.USE_LOCAL_SIGNALS) {
        const candles = priceScraper.getCandles(CONFIG.LOCAL_CANDLE_COUNT);

        if (candles && candles.length >= 30) {
          const signal = strategyManager.analyze(candles);

          if (signal) {
            signal.symbol = asset;
            signal.source = 'local';
            state.lastSignal = { direction: signal.direction, symbol: asset, confidence: signal.confidence, strategy: signal.strategy };

            info(`[${isForce ? 'GO' : 'SCAN'}] Local signal: ${signal.direction} ${asset} @ ${signal.confidence}% [${signal.strategy}]`);

            if (isForce || state.autoTradeEnabled) {
              await tradeExecutor.execute(signal, isForce ? 'go-force' : 'scan');
            }
            return;
          } else if (isForce) {
            log(`[GO] Local candles OK (${candles.length}) but no local strategy produced a signal; trying backend API...`);
          }
        } else if (isForce) {
          log(`[GO] Only ${candles ? candles.length : 0} local candles available (need 30+); falling back to backend API scan...`);
        }
      }

      // Fallback to API scan
      if (isForce) {
        log(`[GO] Querying backend API for ${asset} at min_confidence=${CONFIG.MIN_CONFIDENCE}%...`);
      }
      const response = await scanMarkets([asset], CONFIG.MIN_CONFIDENCE);

      if (!response) {
        if (isForce) warn('[GO] Backend API returned no response (network/CORS issue?)');
        return;
      }
      if (!response.success) {
        if (isForce) warn(`[GO] Backend API rejected scan: ${response.error || 'unknown'}`);
        return;
      }
      if (!response.top_signals || response.top_signals.length === 0) {
        if (isForce) {
          warn(`[GO] Backend API returned no signals (scanned=${response.scanned || 0}, min_conf=${CONFIG.MIN_CONFIDENCE}%). Try lowering MIN_CONFIDENCE or wait for higher confidence setup.`);
        }
        return;
      }

      const signal = response.top_signals[0];
      state.lastSignal = { direction: signal.direction, symbol: signal.symbol || asset, confidence: signal.confidence, strategy: signal.strategy || 'API' };

      info(`[${isForce ? 'GO' : 'SCAN'}] API signal: ${signal.direction} ${signal.symbol || asset} @ ${signal.confidence}% [${signal.strategy || 'API'}]`);

      if (isForce || state.autoTradeEnabled) {
        await tradeExecutor.execute(signal, isForce ? 'go-force' : 'scan');
      } else if (!state.autoTradeEnabled) {
        log('(AUTO off - signal generated but not executed. Click AUTO or use GO for force-execute.)');
      }
    } catch (e) {
      error(`[${isForce ? 'GO' : 'Scan'}] error: ${e.message}`);
      console.error('[Scan stack]', e);
    }
  }
  
  startDataCollection() {
    if (this.dataCollectionInterval) return;
    
    setState('dataCollectionEnabled', true);
    log('Data collection started');
    
    this.dataCollectionInterval = setInterval(() => {
      this.collectAndSendData();
    }, CONFIG.DATA_SEND_INTERVAL);
  }
  
  stopDataCollection() {
    if (this.dataCollectionInterval) {
      clearInterval(this.dataCollectionInterval);
      this.dataCollectionInterval = null;
    }
    setState('dataCollectionEnabled', false);
    log('Data collection stopped');
  }
  
  async collectAndSendData() {
    try {
      const asset = getCurrentAsset();
      if (!asset) return;
      
      const candles = priceScraper.getCandles(100);
      if (candles && candles.length > 0) {
        const { sendCandles } = await import('./utils/api.js');
        await sendCandles(candles, asset, '5s');
      }
    } catch (e) {
      warn(`Data collection error: ${e.message}`);
    }
  }
  
  cleanup() {
    // IMPORTANT: save state FIRST so if disable() resets anything, we still capture it
    try {
      if (twentyOneSecondReversal.config) {
        state._twentyOneSConfig = { ...twentyOneSecondReversal.config };
      }
      state._twentyOneSEnabled = twentyOneSecondReversal.isEnabled();
      if (oneHour51sReversal.config) {
        state._oneHour51sConfig = { ...oneHour51sReversal.config };
      }
      state._oneHour51sEnabled = oneHour51sReversal.isEnabled();
      saveState();
    } catch (_e) { /* ignore */ }

    this.stopScanning();
    this.stopDataCollection();
    priceScraper.stop();
    twentyOneSecondReversal.disable();
    oneHour51sReversal.disable();
    cycleMode.stop();
    appSignalPoller.stop();
    cleanupPanel();

    if (this.statsInterval) clearInterval(this.statsInterval);
    if (this.autoSaveInterval) clearInterval(this.autoSaveInterval);

    log('Bot cleanup complete');
  }
}

// Initialize bot
const bot = new EliteTradingBot();

function startBot() {
  bot.init().catch((e) => {
    console.error(`[${CONFIG.BOT_NAME}] Failed to initialize:`, e);
  });
}

// At @run-at document-start, DOM isn't ready yet.
// Defer bot UI init until DOM is parsed so document.body exists.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startBot, { once: true });
} else {
  startBot();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  bot.cleanup();
});

// Expose for debugging
window.eliteBot = bot;
window.eliteBotTradeExecutor = tradeExecutor;
window.eliteBotSmartInvert = smartInvert;
window.eliteBotPriceScraper = priceScraper;
window.eliteBot21sReversal = twentyOneSecondReversal;
window.eliteBot1h51sReversal = oneHour51sReversal;
window.eliteBotSsidBridge = ssidBridge;
window.eliteBotLivePrice = poLivePrice;
window.eliteBotLivePriceTracker = livePriceTracker;
window.eliteBotCycleMode = cycleMode;
window.eliteBotAppSignal = appSignalPoller;

// One-shot diagnostic — run in console and paste output if prices fail to flow
window.eliteBotDiagnose = function () {
  const out = {
    version: CONFIG.BOT_VERSION,
    url: window.location.href,
    ssidBridge: {
      installed: ssidBridge.installed,
      pricesCaptured: ssidBridge.pricesCaptured,
      lastAuthMessagePresent: !!ssidBridge.lastAuthMessage,
    },
    livePrice: {
      latest: poLivePrice.getLatest(),
      age_ms: poLivePrice.getLatestAge(),
      all: poLivePrice.getAll(),
    },
    livePriceTracker: (function () { try { return livePriceTracker.getStats(); } catch (e) { return `ERR: ${e.message}`; } })(),
    priceScraper: {
      current: (function () { try { return priceScraper.getCurrentPrice(); } catch (e) { return `ERR: ${e.message}`; } })(),
    },
    domPrice: {
      standard: (function () { try { return getCurrentPrice(); } catch (e) { return `ERR: ${e.message}`; } })(),
    },
    currentAsset: (function () { try { return getCurrentAsset(); } catch (e) { return `ERR: ${e.message}`; } })(),
    forexLikeTextNodes: [],
  };
  // Find any text nodes with forex-like numbers for visibility
  try {
    const re = /^\d{1,7}\.\d{2,8}$/;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    let count = 0;
    while ((n = walker.nextNode()) && count < 20) {
      const t = (n.nodeValue || '').trim();
      if (re.test(t)) {
        const el = n.parentElement;
        out.forexLikeTextNodes.push({
          text: t,
          tag: el ? el.tagName : null,
          cls: el ? (el.className || '').toString().slice(0, 80) : null,
        });
        count++;
      }
    }
  } catch (e) { out.forexLikeTextNodes = `ERR: ${e.message}`; }
  // Pretty print
  console.log('%c[Elite Bot Diagnostic]', 'color: #a855f7; font-weight: bold', out);
  return out;
};

export default bot;
