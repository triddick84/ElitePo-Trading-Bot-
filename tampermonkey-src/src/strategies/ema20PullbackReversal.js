/**
 * EMA 20 Pullback Reversal Strategy - 5 Second Timeframe
 * 
 * Optimized for Pocket Option Quick Trading (5s expiry).
 * 
 * Key Indicators:
 * - EMA 20: Primary trend filter
 * - RSI 2: Ultra-fast momentum
 * - Bollinger Bands (5, 2.5): Tight reversal zones
 * - Stochastic (3, 1, 1): Crossover confirmation
 * 
 * CALL: Uptrend -> pullback to EMA 20 / lower BB -> bounce up + RSI/Stoch confirm
 * PUT:  Downtrend -> pullback to EMA 20 / upper BB -> reject down + RSI/Stoch confirm
 */

import { BaseStrategy } from './base.js';
import {
  calculateRSI,
  calculateEMA,
  calculateBollingerBands,
  calculateStochastic,
  calculateSupportResistance,
} from '../utils/indicators.js';
import { log } from '../core/logger.js';

export class EMA20PullbackReversalStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('EMA 20 Pullback Reversal', {
      minConfidence: 65,
      minScore: 5,
      emaPeriod: 20,
      rsiPeriod: 2,
      bbPeriod: 5,
      bbStdDev: 2.5,
      stochPeriod: 3,
      ...config,
    });
  }

  analyze(candles) {
    if (!candles || candles.length < 30) return null;

    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const opens = candles.map(c => c.open || c.close);
    const n = closes.length;

    // === Core Indicators ===
    const ema20 = this._emaArray(closes, this.config.emaPeriod);
    const rsi2 = this._rsiArray(closes, this.config.rsiPeriod);
    const bb = calculateBollingerBands(closes, this.config.bbPeriod, this.config.bbStdDev);
    const stoch = calculateStochastic(highs, lows, closes, this.config.stochPeriod);

    const currentPrice = closes[n - 1];

    // === Trend Detection (EMA 20) ===
    let aboveCount = 0;
    for (let i = n - 10; i < n; i++) {
      if (closes[i] > ema20[i]) aboveCount++;
    }
    const isUptrend = aboveCount >= 7 && currentPrice > ema20[n - 1];
    const isDowntrend = aboveCount <= 3 && currentPrice < ema20[n - 1];

    // === Pullback Detection (last 3 candles) ===
    let pullbackEMABull = false, pullbackBBLower = false;
    let pullbackEMABear = false, pullbackBBUpper = false;

    for (let i = n - 3; i < n; i++) {
      // Bull pullback: low touched EMA 20 or lower BB
      if (lows[i] <= ema20[i] * 1.0005) pullbackEMABull = true;
      if (bb.lower && lows[i] <= (bb.lower + (bb.middle - bb.lower) * 0.1)) pullbackBBLower = true;
      // Bear pullback: high touched EMA 20 or upper BB
      if (highs[i] >= ema20[i] * 0.9995) pullbackEMABear = true;
      if (bb.upper && highs[i] >= (bb.upper - (bb.upper - bb.middle) * 0.1)) pullbackBBUpper = true;
    }

    // === Bounce Detection ===
    const bounceUp = (currentPrice > closes[n - 2] &&
                      closes[n - 1] > opens[n - 1] &&
                      currentPrice > highs[n - 2]);
    const bounceDown = (currentPrice < closes[n - 2] &&
                        closes[n - 1] < opens[n - 1] &&
                        currentPrice < lows[n - 2]);

    // === RSI 2 Confirmation ===
    const rsi2Bull = rsi2[n - 1] > 20 && rsi2[n - 2] <= 20;
    const rsi2BullZone = rsi2[n - 1] >= 50 && rsi2[n - 1] <= 70;
    const rsi2Bear = rsi2[n - 1] < 80 && rsi2[n - 2] >= 80;
    const rsi2BearZone = rsi2[n - 1] >= 30 && rsi2[n - 1] <= 50;

    // === Stochastic ===
    const stochK = stoch.k;
    const stochD = stoch.d || stoch.k;
    const stochBullCross = stochK > stochD && stochK < 25;
    const stochBearCross = stochK < stochD && stochK > 75;

    // === S/R Detection ===
    const sr = calculateSupportResistance(highs, lows, 20);
    const nearSupport = sr.support && Math.abs(currentPrice - sr.support) / currentPrice < 0.001;
    const nearResistance = sr.resistance && Math.abs(currentPrice - sr.resistance) / currentPrice < 0.001;

    // === Compression (tight BB) ===
    const bbWidth = bb.upper && bb.lower ? (bb.upper - bb.lower) / bb.middle * 100 : 1;
    const isCompressed = bbWidth < 0.15;

    // === Divergence ===
    const recentLows = lows.slice(-5);
    const recentRsi = rsi2.slice(-5);
    const bullishDivergence = lows[n - 1] < Math.min(...recentLows.slice(0, -1)) &&
                               rsi2[n - 1] > Math.min(...recentRsi.slice(0, -1));
    const bearishDivergence = highs[n - 1] > Math.max(...highs.slice(-5, -1)) &&
                               rsi2[n - 1] < Math.max(...recentRsi.slice(0, -1));

    // === Volatility Filter ===
    const avgRange = candles.slice(-10).reduce((s, c) => s + (c.high - c.low), 0) / 10;
    const currentRange = highs[n - 1] - lows[n - 1];
    const volatilityOk = currentRange < avgRange * 3.0;

    // === Score ===
    let bullScore = 0, bearScore = 0;
    const bullReasons = [], bearReasons = [];

    // CALL
    if (isUptrend) {
      bullScore += 2; bullReasons.push('Uptrend (EMA 20)');
      if (pullbackEMABull) { bullScore += 3; bullReasons.push('Pullback touched EMA 20'); }
      if (pullbackBBLower) { bullScore += 2; bullReasons.push('Pullback touched lower BB'); }
      if (bounceUp) { bullScore += 2; bullReasons.push('Bounce candle confirmed'); }
      if (rsi2Bull) { bullScore += 2; bullReasons.push('RSI-2 crossed above 20'); }
      else if (rsi2BullZone) { bullScore += 1; bullReasons.push('RSI-2 in bull zone'); }
      if (stochBullCross) { bullScore += 1.5; bullReasons.push('Stochastic bullish'); }
      if (nearSupport) { bullScore += 2; bullReasons.push('At support level'); }
      if (bullishDivergence) { bullScore += 2; bullReasons.push('Bullish RSI divergence'); }
      if (isCompressed && bounceUp) { bullScore += 1.5; bullReasons.push('Compression breakout up'); }
    }

    // PUT
    if (isDowntrend) {
      bearScore += 2; bearReasons.push('Downtrend (EMA 20)');
      if (pullbackEMABear) { bearScore += 3; bearReasons.push('Pullback touched EMA 20'); }
      if (pullbackBBUpper) { bearScore += 2; bearReasons.push('Pullback touched upper BB'); }
      if (bounceDown) { bearScore += 2; bearReasons.push('Rejection candle confirmed'); }
      if (rsi2Bear) { bearScore += 2; bearReasons.push('RSI-2 crossed below 80'); }
      else if (rsi2BearZone) { bearScore += 1; bearReasons.push('RSI-2 in bear zone'); }
      if (stochBearCross) { bearScore += 1.5; bearReasons.push('Stochastic bearish'); }
      if (nearResistance) { bearScore += 2; bearReasons.push('At resistance level'); }
      if (bearishDivergence) { bearScore += 2; bearReasons.push('Bearish RSI divergence'); }
      if (isCompressed && bounceDown) { bearScore += 1.5; bearReasons.push('Compression breakout down'); }
    }

    if (!volatilityOk) {
      bullScore *= 0.6;
      bearScore *= 0.6;
    }

    const minScore = this.config.minScore;

    if (bullScore >= minScore && bullScore > bearScore + 2) {
      const confidence = Math.min(95, 55 + bullScore * 4);
      return {
        direction: 'CALL',
        confidence: Math.round(confidence),
        reason: bullReasons.join(' | '),
        strategy: this.name,
        score: Math.round(bullScore * 10) / 10,
      };
    }

    if (bearScore >= minScore && bearScore > bullScore + 2) {
      const confidence = Math.min(95, 55 + bearScore * 4);
      return {
        direction: 'PUT',
        confidence: Math.round(confidence),
        reason: bearReasons.join(' | '),
        strategy: this.name,
        score: Math.round(bearScore * 10) / 10,
      };
    }

    return null;
  }

  /**
   * Calculate EMA as array (for pullback detection at each point)
   */
  _emaArray(prices, period) {
    const ema = new Array(prices.length).fill(prices[0]);
    const k = 2 / (period + 1);
    for (let i = 1; i < prices.length; i++) {
      ema[i] = prices[i] * k + ema[i - 1] * (1 - k);
    }
    return ema;
  }

  /**
   * Calculate RSI as array
   */
  _rsiArray(prices, period) {
    const rsi = new Array(prices.length).fill(50);
    if (prices.length < period + 1) return rsi;

    let avgGain = 0, avgLoss = 0;
    for (let i = 1; i <= period; i++) {
      const diff = prices[i] - prices[i - 1];
      if (diff > 0) avgGain += diff;
      else avgLoss -= diff;
    }
    avgGain /= period;
    avgLoss /= period;

    for (let i = period + 1; i < prices.length; i++) {
      const diff = prices[i] - prices[i - 1];
      avgGain = (avgGain * (period - 1) + (diff > 0 ? diff : 0)) / period;
      avgLoss = (avgLoss * (period - 1) + (diff < 0 ? -diff : 0)) / period;
      if (avgLoss === 0) rsi[i] = 100;
      else rsi[i] = 100 - 100 / (1 + avgGain / avgLoss);
    }
    return rsi;
  }
}

export default EMA20PullbackReversalStrategy;
