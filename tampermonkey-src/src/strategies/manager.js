/**
 * Strategy Manager
 * Coordinates multiple strategies and selects best signal.
 * Supports syncing enabled strategies from the app's strategy selection API.
 */

import { log, warn, info } from '../core/logger.js';
import { CONFIG } from '../core/config.js';
import { LocalSignalStrategy } from './localSignal.js';
import { MomentumBusterStrategy } from './momentumBuster.js';
import { HollyCrossoverStrategy } from './hollyCrossover.js';
import { GoldenOneMomentStrategy } from './goldenOneMoment.js';
import { EMA20PullbackReversalStrategy } from './ema20PullbackReversal.js';
import { KeltnerMACDStrategy } from './keltnerMACD.js';
import { IQ720EnsembleStrategy } from './iq720Ensemble.js';
import { get } from '../utils/api.js';

/**
 * Mapping of app strategy IDs -> Tampermonkey strategy names
 */
const APP_TO_LOCAL_MAP = {
  'default': null,
  'ema20_pullback_reversal': 'EMA 20 Pullback Reversal',
  'holly_crossover_5s': 'Holly Crossover',
  'holly_crossover_15s': 'Holly Crossover',
  'holly_crossover_30s': 'Holly Crossover',
  'turbo_precision_5s': 'Local Signal Engine',
  'micro_compression_burst': 'Local Signal Engine',
  'keltner_breakout': 'Local Signal Engine',
  'candlestick_patterns': 'Local Signal Engine',
  'rsi_bb_scalp': 'Local Signal Engine',
  'golden_one_moment': 'Golden One Moment',
  'momentum_buster_15s': 'Momentum Buster',
  'keltner_macd_5s': 'Keltner-MACD 5s',
  'iq720_ensemble': 'IQ-720 Ensemble',
};

class StrategyManager {
  constructor() {
    this.strategies = new Map();
    this.activeAppStrategyId = null;
    this.forceSingle = false;  // When true, only run the matched strategy
    this.initializeStrategies();
  }
  
  initializeStrategies() {
    this.registerStrategy(new LocalSignalStrategy());
    this.registerStrategy(new KeltnerMACDStrategy());
    this.registerStrategy(new IQ720EnsembleStrategy());
    this.registerStrategy(new HollyCrossoverStrategy());
    this.registerStrategy(new GoldenOneMomentStrategy());
    this.registerStrategy(new MomentumBusterStrategy());
    this.registerStrategy(new EMA20PullbackReversalStrategy());
    
    log(`Initialized ${this.strategies.size} trading strategies`);
  }
  
  registerStrategy(strategy) {
    this.strategies.set(strategy.getName(), strategy);
  }
  
  getStrategy(name) {
    return this.strategies.get(name);
  }
  
  getAllStrategies() {
    return Array.from(this.strategies.values());
  }
  
  getEnabledStrategies() {
    return this.getAllStrategies().filter(s => s.isEnabled());
  }
  
  /**
   * Sync strategy selection from the app API.
   * Enables only the strategy matching the user's app selection.
   */
  async syncFromApp() {
    try {
      const response = await get('/strategies/selected');
      
      if (response.success && response.selections) {
        // Use the 5s selection for Tampermonkey (primary timeframe)
        const selected5s = response.selections['5s'] || 'default';
        this.applyAppSelection(selected5s);
        info(`Strategy synced from app: ${selected5s}`);
        return true;
      }
    } catch (e) {
      warn(`Strategy sync failed (using all strategies): ${e.message}`);
    }
    return false;
  }
  
  /**
   * Apply app strategy selection
   * @param {string} appStrategyId - The strategy ID from the app
   */
  applyAppSelection(appStrategyId) {
    this.activeAppStrategyId = appStrategyId;
    
    if (appStrategyId === 'default' || !appStrategyId) {
      // Enable all strategies
      this.forceSingle = false;
      for (const s of this.getAllStrategies()) {
        s.setEnabled(true);
      }
      return;
    }
    
    const localName = APP_TO_LOCAL_MAP[appStrategyId];
    
    if (localName) {
      // Enable only the matching local strategy
      this.forceSingle = true;
      for (const s of this.getAllStrategies()) {
        s.setEnabled(s.getName() === localName);
      }
      log(`Strategy locked to: ${localName} (app: ${appStrategyId})`);
    } else {
      // Unknown strategy - enable all as fallback
      this.forceSingle = false;
      for (const s of this.getAllStrategies()) {
        s.setEnabled(true);
      }
      log(`App strategy "${appStrategyId}" has no local match, using all strategies`);
    }
  }
  
  /**
   * Analyze candles with enabled strategies
   * @param {Object[]} candles - OHLC data
   * @returns {Object|null} Best signal or null
   */
  analyze(candles) {
    const signals = [];
    
    for (const strategy of this.getEnabledStrategies()) {
      try {
        const signal = strategy.analyze(candles);
        if (signal && signal.confidence >= strategy.getMinConfidence()) {
          signals.push(signal);
        }
      } catch (e) {
        warn(`Strategy ${strategy.getName()} error: ${e.message}`);
      }
    }
    
    if (signals.length === 0) {
      return null;
    }
    
    // Sort by confidence and return best
    signals.sort((a, b) => b.confidence - a.confidence);
    
    // If we're using a single forced strategy, just return its signal
    if (this.forceSingle) {
      return signals[0];
    }
    
    // Check for conflicting signals
    const directions = new Set(signals.map(s => s.direction));
    if (directions.size > 1) {
      const topSignal = signals[0];
      const conflictingSignals = signals.filter(s => s.direction !== topSignal.direction);
      
      if (conflictingSignals.length > 0 && conflictingSignals[0].confidence > topSignal.confidence - 10) {
        log(`Conflicting signals detected, skipping`);
        return null;
      }
    }
    
    return signals[0];
  }
  
  /**
   * Get signal from specific strategy
   */
  analyzeWithStrategy(strategyName, candles) {
    const strategy = this.getStrategy(strategyName);
    if (!strategy || !strategy.isEnabled()) {
      return null;
    }
    return strategy.analyze(candles);
  }
  
  /**
   * Enable/disable strategy by name
   */
  setStrategyEnabled(name, enabled) {
    const strategy = this.getStrategy(name);
    if (strategy) {
      strategy.setEnabled(enabled);
    }
  }
  
  /**
   * Get strategy status
   */
  getStatus() {
    return this.getAllStrategies().map(s => ({
      name: s.getName(),
      enabled: s.isEnabled(),
      minConfidence: s.getMinConfidence(),
    }));
  }
  
  /**
   * Get active app strategy ID
   */
  getActiveAppStrategy() {
    return this.activeAppStrategyId;
  }
}

export const strategyManager = new StrategyManager();
export default strategyManager;
