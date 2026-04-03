/**
 * GPT Signal Bot - Pocket Option Auto Trader
 * Main Entry Point (Modular Build)
 * 
 * @version 7.7.0
 */

// Core imports
import { CONFIG, updateConfig } from './core/config.js';
import { state, loadState, saveState, setState } from './core/state.js';
import { log, success, error, warn, info } from './core/logger.js';

// UI imports
import { createPanel, initPanelEvents, updateStatsDisplay, updateStatusDot } from './ui/panel.js';

// Strategy imports
import { strategyManager } from './strategies/manager.js';

// Trading imports
import { tradeExecutor } from './trading/executor.js';
import { priceScraper } from './trading/priceScraper.js';

// Utils imports
import { getCurrentAsset, waitForElement } from './utils/dom.js';
import { scanMarkets, sendCandles } from './utils/api.js';

/**
 * Main application class
 */
class GPTSignalBot {
  constructor() {
    this.scanInterval = null;
    this.statsInterval = null;
    this.dataCollectionInterval = null;
    this.initialized = false;
  }
  
  /**
   * Initialize the bot
   */
  async init() {
    log('🚀 Initializing GPT Signal Bot v7.7.0...');
    
    // Wait for page to load
    await waitForElement('.trading-panel, .chart-container, body', 15000);
    
    // Load saved state
    loadState();
    
    // Create and inject UI panel
    this.createUI();
    
    // Start price scraper
    priceScraper.start(500);
    
    // Start stats update interval
    this.statsInterval = setInterval(() => {
      updateStatsDisplay();
    }, 1000);
    
    this.initialized = true;
    updateStatusDot('connected');
    success('GPT Signal Bot initialized successfully');
    
    // Log available strategies
    const strategies = strategyManager.getStatus();
    info(`Loaded ${strategies.length} strategies: ${strategies.map(s => s.name).join(', ')}`);
  }
  
  /**
   * Create and inject UI
   */
  createUI() {
    const panel = createPanel();
    document.body.appendChild(panel);
    
    // Initialize event handlers
    initPanelEvents({
      onScanToggle: (enabled) => this.toggleScan(enabled),
      onAutoToggle: (enabled) => this.toggleAuto(enabled),
      onGo: () => this.manualScan(),
      onWin: () => this.recordWin(),
      onLoss: () => this.recordLoss(),
      onAmountChange: (amount) => tradeExecutor.setBaseAmount(amount),
    });
    
    log('UI panel created');
  }
  
  /**
   * Toggle scanning
   * @param {boolean} enabled
   */
  toggleScan(enabled) {
    setState('scanEnabled', enabled);
    
    if (enabled) {
      log('📡 Scan mode ENABLED');
      updateStatusDot('scanning');
      this.startScanning();
    } else {
      log('📡 Scan mode DISABLED');
      updateStatusDot('connected');
      this.stopScanning();
    }
  }
  
  /**
   * Toggle auto trading
   * @param {boolean} enabled
   */
  toggleAuto(enabled) {
    setState('autoTradeEnabled', enabled);
    log(`🎯 Auto-trade ${enabled ? 'ENABLED' : 'DISABLED'}`);
  }
  
  /**
   * Start continuous scanning
   */
  startScanning() {
    if (this.scanInterval) {
      clearInterval(this.scanInterval);
    }
    
    this.scanInterval = setInterval(() => {
      this.performScan();
    }, CONFIG.SCAN_INTERVAL);
    
    // Immediate first scan
    this.performScan();
  }
  
  /**
   * Stop scanning
   */
  stopScanning() {
    if (this.scanInterval) {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
    }
  }
  
  /**
   * Perform a market scan
   */
  async performScan() {
    if (!state.scanEnabled) return;
    
    try {
      // Get candles from price scraper
      const candles = priceScraper.getCandles(50);
      
      if (candles.length < 30) {
        log('Insufficient candles for analysis, waiting...');
        return;
      }
      
      // Local strategy analysis
      const localSignal = strategyManager.analyze(candles);
      
      if (localSignal && localSignal.confidence >= CONFIG.MIN_CONFIDENCE) {
        log(`🎯 Local signal: ${localSignal.direction} @ ${localSignal.confidence}% (${localSignal.strategy})`);
        
        if (state.autoTradeEnabled) {
          await tradeExecutor.execute(localSignal, 'scan');
        }
        return;
      }
      
      // Fallback to backend scan
      const currentAsset = getCurrentAsset();
      if (currentAsset) {
        const backendResult = await scanMarkets([currentAsset], CONFIG.MIN_CONFIDENCE);
        
        if (backendResult.success && backendResult.top_signals?.length > 0) {
          const signal = backendResult.top_signals[0];
          log(`🎯 Backend signal: ${signal.direction} @ ${signal.confidence}% (${signal.strategy || 'Backend'})`);
          
          if (state.autoTradeEnabled) {
            await tradeExecutor.execute(signal, 'scan');
          }
        }
      }
    } catch (e) {
      error(`Scan error: ${e.message}`);
    }
  }
  
  /**
   * Manual scan (GO button)
   */
  async manualScan() {
    log('▶️ Manual scan triggered');
    updateStatusDot('scanning');
    
    await this.performScan();
    
    updateStatusDot(state.scanEnabled ? 'scanning' : 'connected');
  }
  
  /**
   * Record manual win
   */
  recordWin() {
    tradeExecutor.recordResult(true);
    updateStatsDisplay();
    saveState();
    success('WIN recorded');
  }
  
  /**
   * Record manual loss
   */
  recordLoss() {
    tradeExecutor.recordResult(false);
    updateStatsDisplay();
    saveState();
    warn('LOSS recorded');
  }
  
  /**
   * Start data collection
   * @param {string} timeframe - Candle timeframe
   */
  startDataCollection(timeframe = '5s') {
    if (this.dataCollectionInterval) {
      clearInterval(this.dataCollectionInterval);
    }
    
    setState('dataCollectionEnabled', true);
    log(`📊 Data collection started (${timeframe})`);
    
    this.dataCollectionInterval = setInterval(async () => {
      const candles = priceScraper.getCandles(100);
      const asset = getCurrentAsset();
      
      if (candles.length > 0 && asset) {
        const result = await sendCandles(candles, asset, timeframe);
        if (result.success) {
          log(`📊 Sent ${candles.length} candles`);
        }
      }
    }, CONFIG.DATA_SEND_INTERVAL);
  }
  
  /**
   * Stop data collection
   */
  stopDataCollection() {
    if (this.dataCollectionInterval) {
      clearInterval(this.dataCollectionInterval);
      this.dataCollectionInterval = null;
    }
    setState('dataCollectionEnabled', false);
    log('📊 Data collection stopped');
  }
  
  /**
   * Cleanup on unload
   */
  cleanup() {
    this.stopScanning();
    this.stopDataCollection();
    priceScraper.stop();
    
    if (this.statsInterval) {
      clearInterval(this.statsInterval);
    }
    
    saveState();
    log('Bot cleanup complete');
  }
}

// Create and initialize bot
const bot = new GPTSignalBot();

// Wait for DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => bot.init());
} else {
  bot.init();
}

// Cleanup on unload
window.addEventListener('beforeunload', () => bot.cleanup());

// Export for console access
window.GPTBot = bot;
window.strategyManager = strategyManager;
window.tradeExecutor = tradeExecutor;
window.priceScraper = priceScraper;

export default bot;
