/**
 * Momentum Buster 15s Strategy
 * High-frequency momentum reversal strategy for 15-second expiries
 */

import { BaseStrategy } from './base.js';
import { calculateRSI, calculateEMA } from '../utils/indicators.js';

export class MomentumBusterStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Momentum Buster 15s', {
      minConfidence: 70,
      momentumPeriod: 3,
      minConsecutive: 3,
      expirySeconds: 15,
      ...config,
    });
  }
  
  analyze(candles) {
    if (!candles || candles.length < 10) {
      return null;
    }
    
    const recentCandles = candles.slice(-10);
    const closes = recentCandles.map(c => c.close);
    
    // Count consecutive green/red bars
    let consecutiveGreen = 0;
    let consecutiveRed = 0;
    
    for (let i = recentCandles.length - 1; i >= 1; i--) {
      const current = recentCandles[i];
      const isGreen = current.close > current.open;
      const isRed = current.close < current.open;
      
      if (isGreen && consecutiveRed === 0) {
        consecutiveGreen++;
      } else if (isRed && consecutiveGreen === 0) {
        consecutiveRed++;
      } else {
        break;
      }
    }
    
    // Check momentum exhaustion
    const momentum = closes[closes.length - 1] - closes[closes.length - this.config.momentumPeriod];
    const rsi = calculateRSI(closes, 5);
    
    // Generate signal on momentum exhaustion
    if (consecutiveGreen >= this.config.minConsecutive && rsi > 70) {
      // After strong up move, expect reversal
      const confidence = Math.min(85, 65 + consecutiveGreen * 5);
      return {
        direction: 'PUT',
        confidence: Math.round(confidence),
        reason: `${consecutiveGreen} green bars, RSI ${rsi.toFixed(1)}`,
        strategy: this.name,
        expirySeconds: this.config.expirySeconds,
      };
    }
    
    if (consecutiveRed >= this.config.minConsecutive && rsi < 30) {
      // After strong down move, expect reversal
      const confidence = Math.min(85, 65 + consecutiveRed * 5);
      return {
        direction: 'CALL',
        confidence: Math.round(confidence),
        reason: `${consecutiveRed} red bars, RSI ${rsi.toFixed(1)}`,
        strategy: this.name,
        expirySeconds: this.config.expirySeconds,
      };
    }
    
    return null;
  }
}

export default MomentumBusterStrategy;
