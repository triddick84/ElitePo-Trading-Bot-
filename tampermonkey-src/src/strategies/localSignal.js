/**
 * Local Signal Engine Strategy
 * Generates signals using local technical analysis
 */

import { BaseStrategy } from './base.js';
import {
  calculateRSI,
  calculateEMA,
  calculateStochastic,
  calculateBollingerBands,
  calculateSMA,
  detectCandlePatterns,
} from '../utils/indicators.js';
import { log } from '../core/logger.js';

export class LocalSignalStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Local Signal Engine', {
      minConfidence: 65,
      minConfirmations: 3,
      rsiPeriod: 2,
      stochPeriod: 5,
      ...config,
    });
  }
  
  analyze(candles) {
    if (!candles || candles.length < 30) {
      return null;
    }
    
    // Extract price arrays
    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    
    // Calculate indicators
    const rsi2 = calculateRSI(closes, 2);
    const rsi14 = calculateRSI(closes, 14);
    const stoch = calculateStochastic(highs, lows, closes, this.config.stochPeriod);
    const bb = calculateBollingerBands(closes, 20, 2);
    const ema5 = calculateEMA(closes, 5);
    const ema10 = calculateEMA(closes, 10);
    const sma20 = calculateSMA(closes, 20);
    
    const currentPrice = closes[closes.length - 1];
    const prevPrice = closes[closes.length - 2];
    
    // Track confirmations
    let bullConfirmations = 0;
    let bearConfirmations = 0;
    const reasons = [];
    
    // RSI-2 Oversold/Overbought
    if (rsi2 < 10) {
      bullConfirmations += 2;
      reasons.push('RSI-2 oversold');
    } else if (rsi2 > 90) {
      bearConfirmations += 2;
      reasons.push('RSI-2 overbought');
    } else if (rsi2 < 20) {
      bullConfirmations += 1;
      reasons.push('RSI-2 low');
    } else if (rsi2 > 80) {
      bearConfirmations += 1;
      reasons.push('RSI-2 high');
    }
    
    // Stochastic
    if (stoch.k < 20) {
      bullConfirmations += 1;
      reasons.push('Stochastic oversold');
    } else if (stoch.k > 80) {
      bearConfirmations += 1;
      reasons.push('Stochastic overbought');
    }
    
    // Bollinger Bands
    if (bb.percentB < 0.1) {
      bullConfirmations += 1;
      reasons.push('Price at lower BB');
    } else if (bb.percentB > 0.9) {
      bearConfirmations += 1;
      reasons.push('Price at upper BB');
    }
    
    // EMA Crossover
    if (ema5 > ema10 && closes[closes.length - 2] <= calculateEMA(closes.slice(0, -1), 10)) {
      bullConfirmations += 1;
      reasons.push('EMA bullish cross');
    } else if (ema5 < ema10 && closes[closes.length - 2] >= calculateEMA(closes.slice(0, -1), 10)) {
      bearConfirmations += 1;
      reasons.push('EMA bearish cross');
    }
    
    // Price vs SMA20
    if (currentPrice < sma20 * 0.995) {
      bullConfirmations += 0.5;
    } else if (currentPrice > sma20 * 1.005) {
      bearConfirmations += 0.5;
    }
    
    // Candlestick patterns
    const pattern = detectCandlePatterns(candles);
    if (pattern.pattern) {
      if (pattern.bullish === true) {
        bullConfirmations += 1;
        reasons.push(`${pattern.pattern} pattern`);
      } else if (pattern.bullish === false) {
        bearConfirmations += 1;
        reasons.push(`${pattern.pattern} pattern`);
      }
    }
    
    // Volatility filter
    const avgRange = candles.slice(-10).reduce((sum, c) => sum + (c.high - c.low), 0) / 10;
    const currentRange = candles[candles.length - 1].high - candles[candles.length - 1].low;
    
    if (currentRange > avgRange * 2.5) {
      // Too volatile, reduce confidence
      bullConfirmations *= 0.7;
      bearConfirmations *= 0.7;
    }
    
    // Check minimum confirmations
    const minConfs = this.config.minConfirmations;
    
    if (bullConfirmations >= minConfs && bullConfirmations > bearConfirmations + 1) {
      const confidence = Math.min(90, 55 + bullConfirmations * 7);
      return {
        direction: 'CALL',
        confidence: Math.round(confidence),
        reason: reasons.join(', '),
        strategy: this.name,
        confirmations: bullConfirmations,
      };
    }
    
    if (bearConfirmations >= minConfs && bearConfirmations > bullConfirmations + 1) {
      const confidence = Math.min(90, 55 + bearConfirmations * 7);
      return {
        direction: 'PUT',
        confidence: Math.round(confidence),
        reason: reasons.join(', '),
        strategy: this.name,
        confirmations: bearConfirmations,
      };
    }
    
    return null;
  }
}

export default LocalSignalStrategy;
