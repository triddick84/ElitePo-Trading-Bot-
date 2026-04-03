/**
 * Golden One Moment 30s Strategy
 * RSI(2) + Stochastic(4,3,3) mean reversion for 30-second expiry
 */

import { BaseStrategy } from './base.js';
import { calculateRSI, calculateStochastic, calculateSMA } from '../utils/indicators.js';

export class GoldenOneMomentStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Golden One Moment 30s', {
      minConfidence: 72,
      rsiPeriod: 2,
      stochPeriod: 4,
      stochSmooth: 3,
      expirySeconds: 30,
      ...config,
    });
  }
  
  analyze(candles) {
    if (!candles || candles.length < 20) {
      return null;
    }
    
    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    
    // Calculate indicators
    const rsi2 = calculateRSI(closes, this.config.rsiPeriod);
    const stoch = calculateStochastic(highs, lows, closes, this.config.stochPeriod);
    const sma10 = calculateSMA(closes, 10);
    const currentPrice = closes[closes.length - 1];
    
    // Mean reversion signals
    // Oversold: RSI-2 < 10 AND Stochastic K < 20
    // Overbought: RSI-2 > 90 AND Stochastic K > 80
    
    if (rsi2 < 10 && stoch.k < 20) {
      // Strong oversold - expect bounce
      let confidence = 72;
      const reasons = [`RSI-2: ${rsi2.toFixed(1)}`, `Stoch K: ${stoch.k.toFixed(1)}`];
      
      // Extra confirmation if below SMA
      if (currentPrice < sma10) {
        confidence += 5;
        reasons.push('Below SMA(10)');
      }
      
      // Extra strong signal
      if (rsi2 < 5 && stoch.k < 10) {
        confidence += 8;
        reasons.push('Extreme oversold');
      }
      
      return {
        direction: 'CALL',
        confidence: Math.min(90, Math.round(confidence)),
        reason: reasons.join(', '),
        strategy: this.name,
        expirySeconds: this.config.expirySeconds,
      };
    }
    
    if (rsi2 > 90 && stoch.k > 80) {
      // Strong overbought - expect pullback
      let confidence = 72;
      const reasons = [`RSI-2: ${rsi2.toFixed(1)}`, `Stoch K: ${stoch.k.toFixed(1)}`];
      
      // Extra confirmation if above SMA
      if (currentPrice > sma10) {
        confidence += 5;
        reasons.push('Above SMA(10)');
      }
      
      // Extra strong signal
      if (rsi2 > 95 && stoch.k > 90) {
        confidence += 8;
        reasons.push('Extreme overbought');
      }
      
      return {
        direction: 'PUT',
        confidence: Math.min(90, Math.round(confidence)),
        reason: reasons.join(', '),
        strategy: this.name,
        expirySeconds: this.config.expirySeconds,
      };
    }
    
    return null;
  }
}

export default GoldenOneMomentStrategy;
