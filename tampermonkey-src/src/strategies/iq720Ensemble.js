/**
 * IQ-720 Ensemble Strategy (Advanced Multi-Indicator)
 * 
 * Combines 8 weighted sub-strategies with:
 * - Market Regime Detection (trending/ranging/volatile)
 * - Session-Aware Trading (London/NY/Asian/Overlap weighting)
 * - Confidence Calibration (anti-overconfidence)
 */

import { BaseStrategy } from './base.js';
import {
  calculateRSI, calculateEMA, calculateSMA,
  calculateStochastic, calculateBollingerBands,
  calculateMACD, calculateATR, detectCandlePatterns,
} from '../utils/indicators.js';
import { calculateADX } from '../utils/indicators.js';

export class IQ720EnsembleStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('IQ-720 Ensemble', {
      minConfidence: 65,
      minScoreDiff: 15,
      ...config,
    });
  }

  _getSessionWeight() {
    const hour = new Date().getUTCHours();
    if (hour >= 13 && hour < 16) return 1.2;      // London/NY overlap
    if (hour >= 8 && hour < 16) return 1.0;        // London
    if (hour >= 13 && hour < 21) return 1.0;       // NY
    if (hour >= 0 && hour < 8) return 0.8;          // Asian
    return 0.6;                                      // Off hours
  }

  _getSessionName() {
    const hour = new Date().getUTCHours();
    if (hour >= 13 && hour < 16) return 'overlap';
    if (hour >= 8 && hour < 16) return 'london';
    if (hour >= 13 && hour < 21) return 'new_york';
    if (hour >= 0 && hour < 8) return 'asian';
    return 'off_hours';
  }

  analyze(candles) {
    if (!candles || candles.length < 50) return null;

    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high || c.close);
    const lows = candles.map(c => c.low || c.close);
    const currentPrice = closes[closes.length - 1];

    // Market Regime Detection
    const emaFast = calculateEMA(closes, 12);
    const emaSlow = calculateEMA(closes, 26);
    const trendDir = emaFast > emaSlow ? 1 : -1;

    // Volatility check
    const returns = [];
    for (let i = Math.max(1, closes.length - 20); i < closes.length; i++) {
      returns.push(Math.abs((closes[i] - closes[i - 1]) / closes[i - 1]));
    }
    const avgVol = returns.reduce((s, v) => s + v, 0) / returns.length;
    const recentVol = returns.slice(-5).reduce((s, v) => s + v, 0) / 5;
    const isHighVol = recentVol > avgVol * 1.5;

    const sessionWeight = this._getSessionWeight();
    let callScore = 0, putScore = 0;
    const confirmations = [];

    // 1. RSI (weight: 20%)
    const rsi = calculateRSI(closes, 14);
    if (rsi < 30) { callScore += 15; confirmations.push('RSI_OVERSOLD'); }
    else if (rsi > 70) { putScore += 15; confirmations.push('RSI_OVERBOUGHT'); }
    else if (rsi < 40) { callScore += 5; }
    else if (rsi > 60) { putScore += 5; }

    // 2. MACD (weight: 20%)
    const macd = calculateMACD(closes, 12, 26, 9);
    if (macd.histogram > 0 && macd.macd > 0) { callScore += 15; confirmations.push('MACD_BULLISH'); }
    else if (macd.histogram > 0) { callScore += 10; }
    if (macd.histogram < 0 && macd.macd < 0) { putScore += 15; confirmations.push('MACD_BEARISH'); }
    else if (macd.histogram < 0) { putScore += 10; }

    // 3. Stochastic (weight: 15%)
    const stoch = calculateStochastic(highs, lows, closes, 14);
    if (stoch.k < 20) { callScore += 15; confirmations.push('STOCH_OVERSOLD'); }
    else if (stoch.k > 80) { putScore += 15; confirmations.push('STOCH_OVERBOUGHT'); }

    // 4. EMA Alignment (weight: 15%)
    const ema5 = calculateEMA(closes, 5);
    const ema10 = calculateEMA(closes, 10);
    const ema20 = calculateEMA(closes, 20);
    if (ema5 > ema10 && ema10 > ema20) { callScore += 15; confirmations.push('EMA_ALIGNED_BULL'); }
    else if (ema5 < ema10 && ema10 < ema20) { putScore += 15; confirmations.push('EMA_ALIGNED_BEAR'); }

    // 5. Bollinger Band Position (weight: 10%)
    const bb = calculateBollingerBands(closes, 20, 2);
    if (bb.percentB < 0.1) { callScore += 10; confirmations.push('BB_OVERSOLD'); }
    else if (bb.percentB > 0.9) { putScore += 10; confirmations.push('BB_OVERBOUGHT'); }

    // 6. ADX Trend Strength (weight: 10%)
    const adx = calculateADX(highs, lows, closes, 14);
    if (adx > 25) {
      if (trendDir > 0) { callScore += 10; confirmations.push('ADX_STRONG_UP'); }
      else { putScore += 10; confirmations.push('ADX_STRONG_DOWN'); }
    }

    // 7. Candlestick patterns (bonus)
    const pattern = detectCandlePatterns(candles);
    if (pattern.pattern && pattern.bullish === true) { callScore += 8; confirmations.push(pattern.pattern.toUpperCase()); }
    if (pattern.pattern && pattern.bullish === false) { putScore += 8; confirmations.push(pattern.pattern.toUpperCase()); }

    // Market Regime Adjustments
    if (trendDir > 0) callScore += 10; else putScore += 10;
    if (isHighVol) { callScore -= 10; putScore -= 10; }

    // Determine Direction
    const minDiff = this.config.minScoreDiff;
    let direction = null;
    let rawConf = 0;

    if (callScore > putScore + minDiff) {
      direction = 'CALL';
      rawConf = 50 + callScore;
    } else if (putScore > callScore + minDiff) {
      direction = 'PUT';
      rawConf = 50 + putScore;
    } else {
      return null;
    }

    // Calibrate Confidence
    let confidence = rawConf * 0.85 * sessionWeight;
    if (isHighVol) confidence -= 10;
    if (confirmations.length >= 3) confidence += 5;
    else if (confirmations.length <= 1) confidence -= 5;
    confidence = Math.max(0, Math.min(95, confidence));

    if (confidence < this.config.minConfidence) return null;

    return {
      direction,
      confidence: Math.round(confidence),
      reason: confirmations.join(', '),
      strategy: this.name,
      confirmations: confirmations.length,
      expiration: 5,
      indicators: {
        rsi,
        stoch_k: stoch.k,
        adx,
        call_score: callScore,
        put_score: putScore,
        session: this._getSessionName(),
        session_weight: sessionWeight,
        regime: trendDir > 0 ? 'trending_up' : 'trending_down',
        high_volatility: isHighVol,
      },
    };
  }
}

export default IQ720EnsembleStrategy;
