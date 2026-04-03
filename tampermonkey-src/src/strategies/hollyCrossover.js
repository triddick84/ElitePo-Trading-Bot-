/**
 * Holly Crossover Strategy
 * EMA(12) x WMA(23) crossover with S/R confirmation
 * Works on 5s, 15s, and 30s expiries
 */

import { BaseStrategy } from './base.js';
import { calculateEMA, calculateWMA, calculateSupportResistance } from '../utils/indicators.js';

export class HollyCrossoverStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Holly Crossover', {
      minConfidence: 70,
      emaPeriod: 12,
      wmaPeriod: 23,
      lookbackPeriod: 20,
      ...config,
    });
  }
  
  analyze(candles) {
    if (!candles || candles.length < 30) {
      return null;
    }
    
    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    
    // Current values
    const ema12 = calculateEMA(closes, this.config.emaPeriod);
    const wma23 = calculateWMA(closes, this.config.wmaPeriod);
    
    // Previous values (for crossover detection)
    const prevCloses = closes.slice(0, -1);
    const prevEma12 = calculateEMA(prevCloses, this.config.emaPeriod);
    const prevWma23 = calculateWMA(prevCloses, this.config.wmaPeriod);
    
    // Support/Resistance
    const sr = calculateSupportResistance(highs, lows, this.config.lookbackPeriod);
    const currentPrice = closes[closes.length - 1];
    
    // Check for crossovers
    const bullishCross = prevEma12 <= prevWma23 && ema12 > wma23;
    const bearishCross = prevEma12 >= prevWma23 && ema12 < wma23;
    
    // Proximity to S/R levels
    const nearSupport = currentPrice <= sr.support * 1.002;
    const nearResistance = currentPrice >= sr.resistance * 0.998;
    
    if (bullishCross) {
      let confidence = 70;
      const reasons = ['EMA(12) crossed above WMA(23)'];
      
      if (nearSupport) {
        confidence += 10;
        reasons.push('Near support level');
      }
      
      // Trend confirmation
      if (ema12 > calculateEMA(closes, 50)) {
        confidence += 5;
        reasons.push('Above EMA(50)');
      }
      
      return {
        direction: 'CALL',
        confidence: Math.min(90, Math.round(confidence)),
        reason: reasons.join(', '),
        strategy: this.name,
        expiryOptions: [5, 15, 30],
      };
    }
    
    if (bearishCross) {
      let confidence = 70;
      const reasons = ['EMA(12) crossed below WMA(23)'];
      
      if (nearResistance) {
        confidence += 10;
        reasons.push('Near resistance level');
      }
      
      // Trend confirmation
      if (ema12 < calculateEMA(closes, 50)) {
        confidence += 5;
        reasons.push('Below EMA(50)');
      }
      
      return {
        direction: 'PUT',
        confidence: Math.min(90, Math.round(confidence)),
        reason: reasons.join(', '),
        strategy: this.name,
        expiryOptions: [5, 15, 30],
      };
    }
    
    return null;
  }
}

export default HollyCrossoverStrategy;
