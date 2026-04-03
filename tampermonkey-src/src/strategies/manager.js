/**
 * Strategy Manager
 * Coordinates multiple strategies and selects best signal
 */

import { log, warn } from '../core/logger.js';
import { LocalSignalStrategy } from './localSignal.js';
import { MomentumBusterStrategy } from './momentumBuster.js';
import { HollyCrossoverStrategy } from './hollyCrossover.js';
import { GoldenOneMomentStrategy } from './goldenOneMoment.js';

class StrategyManager {
  constructor() {
    this.strategies = new Map();
    this.initializeStrategies();
  }
  
  initializeStrategies() {
    // Register all strategies
    this.registerStrategy(new LocalSignalStrategy());
    this.registerStrategy(new MomentumBusterStrategy());
    this.registerStrategy(new HollyCrossoverStrategy());
    this.registerStrategy(new GoldenOneMomentStrategy());
    
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
   * Analyze candles with all enabled strategies
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
    
    // Check for conflicting signals
    const directions = new Set(signals.map(s => s.direction));
    if (directions.size > 1) {
      // Conflicting signals - only return if top signal has significantly higher confidence
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
   * @param {string} strategyName - Strategy name
   * @param {Object[]} candles - OHLC data
   * @returns {Object|null} Signal or null
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
   * @param {string} name - Strategy name
   * @param {boolean} enabled - Enable state
   */
  setStrategyEnabled(name, enabled) {
    const strategy = this.getStrategy(name);
    if (strategy) {
      strategy.setEnabled(enabled);
    }
  }
  
  /**
   * Get strategy status
   * @returns {Object[]} Array of strategy status objects
   */
  getStatus() {
    return this.getAllStrategies().map(s => ({
      name: s.getName(),
      enabled: s.isEnabled(),
      minConfidence: s.getMinConfidence(),
    }));
  }
}

// Singleton instance
export const strategyManager = new StrategyManager();

export default strategyManager;
