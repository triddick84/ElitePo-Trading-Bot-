/**
 * Base Strategy Class
 * All strategies inherit from this
 */

import { log } from '../core/logger.js';

export class BaseStrategy {
  constructor(name, config = {}) {
    this.name = name;
    this.config = {
      minConfidence: 65,
      enabled: true,
      ...config,
    };
  }
  
  /**
   * Analyze candles and generate signal
   * @param {Object[]} candles - OHLC candle data
   * @returns {Object|null} Signal { direction, confidence, reason }
   */
  analyze(candles) {
    throw new Error('analyze() must be implemented by subclass');
  }
  
  /**
   * Check if strategy is enabled
   * @returns {boolean}
   */
  isEnabled() {
    return this.config.enabled;
  }
  
  /**
   * Enable/disable strategy
   * @param {boolean} enabled
   */
  setEnabled(enabled) {
    this.config.enabled = enabled;
    log(`${this.name} ${enabled ? 'enabled' : 'disabled'}`);
  }
  
  /**
   * Get strategy name
   * @returns {string}
   */
  getName() {
    return this.name;
  }
  
  /**
   * Get minimum confidence for this strategy
   * @returns {number}
   */
  getMinConfidence() {
    return this.config.minConfidence;
  }
}

export default BaseStrategy;
