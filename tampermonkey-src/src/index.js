/*
 * Elite Pocket Option Trading Bot v8.0.0
 * Main entry point - coordinates all modules
 */

import { CONFIG } from './core/config.js';
import { state, setState, loadState, saveState, resetStats } from './core/state.js';
import { log, info, warn, success, error } from './core/logger.js';
import { createPanel, initPanelEvents, updateStatsDisplay, updateInvertDisplay, updateStatusDot, cleanupPanel, populateStrategies, update21sReversalDisplay } from './ui/panel.js';
import { strategyManager } from './strategies/manager.js';
import { tradeExecutor } from './trading/executor.js';
import { smartInvert } from './trading/smartInvert.js';
import { twentyOneSecondReversal } from './strategies/twentyOneSecondReversal.js';
import { ssidBridge } from './trading/ssidBridge.js';
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
    
    // Restore inversion display from saved state
    if (state.inversion.isInverted) {
      updateInvertDisplay(true, state.inversion.reason);
    }
    
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
        if (enabled) {
          this.startScanning();
        } else {
          this.stopScanning();
        }
      },
      onAutoToggle: (enabled) => {
        log(`Auto-trade ${enabled ? 'enabled' : 'disabled'}`);
      },
      onGo: () => {
        this.executeSingleScan();
      },
      onInvertToggle: () => {
        smartInvert.manualToggle();
      },
      onStrategyChange: async (strategyId) => {
        log(`Strategy changed to: ${strategyId}`);
        // Apply locally in Tampermonkey
        strategyManager.applyAppSelection(strategyId);
        // Also save to backend
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
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
      },
      onLoss: () => {
        tradeExecutor.recordResult(false);
        twentyOneSecondReversal.onResultRecorded(false);
        updateStatsDisplay();
        if (twentyOneSecondReversal.isEnabled()) {
          update21sReversalDisplay(true, twentyOneSecondReversal.getStats());
        }
      },
      on21sReversalToggle: (enabled) => {
        if (enabled) {
          twentyOneSecondReversal.enable();
        } else {
          twentyOneSecondReversal.disable();
        }
        update21sReversalDisplay(enabled, enabled ? twentyOneSecondReversal.getStats() : null);
      },
      onAmountChange: (amount) => {
        tradeExecutor.setBaseAmount(amount);
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
    log('Running single scan...');
    await this.performScan();
  }
  
  async performScan() {
    try {
      const asset = getCurrentAsset();
      if (!asset) {
        warn('Could not detect current asset');
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
            
            // Always store last signal for manual WIN/LOSS tracking
            state.lastSignal = { direction: signal.direction, symbol: asset, confidence: signal.confidence, strategy: signal.strategy };
            
            log(`Local signal: ${signal.direction} ${asset} @ ${signal.confidence}% [${signal.strategy}]`);
            
            if (state.autoTradeEnabled) {
              await tradeExecutor.execute(signal, 'scan');
            }
            return;
          }
        }
      }
      
      // Fallback to API scan
      const response = await scanMarkets([asset], CONFIG.MIN_CONFIDENCE);
      
      if (response.success && response.top_signals && response.top_signals.length > 0) {
        const signal = response.top_signals[0];
        
        // Always store last signal for manual WIN/LOSS tracking
        state.lastSignal = { direction: signal.direction, symbol: signal.symbol || asset, confidence: signal.confidence, strategy: signal.strategy || 'API' };
        
        log(`API signal: ${signal.direction} ${signal.symbol || asset} @ ${signal.confidence}%`);
        
        if (state.autoTradeEnabled) {
          await tradeExecutor.execute(signal, 'scan');
        }
      }
    } catch (e) {
      error(`Scan error: ${e.message}`);
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
    this.stopScanning();
    this.stopDataCollection();
    priceScraper.stop();
    twentyOneSecondReversal.disable();
    cleanupPanel();
    
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
    }
    
    saveState();
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
window.eliteBotSsidBridge = ssidBridge;

export default bot;
