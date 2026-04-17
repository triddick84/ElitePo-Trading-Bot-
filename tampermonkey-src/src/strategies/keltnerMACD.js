/**
 * Keltner-MACD 5-Second Strategy
 * Keltner Channel (EMA20, ATR60, x4) + MACD (13/24/11) crossover
 */

import { BaseStrategy } from './base.js';
import { calculateEMA, calculateATR, calculateMACD } from '../utils/indicators.js';

export class KeltnerMACDStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Keltner-MACD 5s', {
      minConfidence: 70,
      emaPeriod: 20,
      atrPeriod: 60,
      atrMultiplier: 4,
      macdFast: 13,
      macdSlow: 24,
      macdSignal: 11,
      ...config,
    });
  }

  analyze(candles) {
    if (!candles || candles.length < 65) return null;

    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high || c.close);
    const lows = candles.map(c => c.low || c.close);
    const currentPrice = closes[closes.length - 1];
    const prevPrice = closes[closes.length - 2];

    // Keltner Channel
    const ema20 = calculateEMA(closes, this.config.emaPeriod);
    const atr = calculateATR(highs, lows, closes, this.config.atrPeriod);
    const upperBand = ema20 + (atr * this.config.atrMultiplier);
    const lowerBand = ema20 - (atr * this.config.atrMultiplier);

    // MACD
    const macdFast = calculateEMA(closes, this.config.macdFast);
    const macdSlow = calculateEMA(closes, this.config.macdSlow);
    const macdLine = macdFast - macdSlow;

    // Previous MACD
    const prevCloses = closes.slice(0, -1);
    const prevMacdFast = calculateEMA(prevCloses, this.config.macdFast);
    const prevMacdSlow = calculateEMA(prevCloses, this.config.macdSlow);
    const prevMacdLine = prevMacdFast - prevMacdSlow;

    // Signal line approximation
    const signalLine = macdLine * 0.85;
    const prevSignalLine = prevMacdLine * 0.85;

    const confirmations = [];
    let direction = null;

    // CALL: price crosses above Keltner middle + MACD bullish crossover
    const crossedAboveMiddle = prevPrice <= ema20 && currentPrice > ema20;
    const macdBullCross = prevMacdLine <= prevSignalLine && macdLine > signalLine;

    // PUT: price crosses below Keltner middle + MACD bearish crossover
    const crossedBelowMiddle = prevPrice >= ema20 && currentPrice < ema20;
    const macdBearCross = prevMacdLine >= prevSignalLine && macdLine < signalLine;

    if (crossedAboveMiddle || currentPrice > ema20) {
      confirmations.push('KC_ABOVE_MIDDLE');
      if (macdBullCross || macdLine > signalLine) {
        confirmations.push('MACD_BULLISH');
        if (currentPrice < upperBand) {
          confirmations.push('ROOM_TO_UPPER');
        }
        direction = 'CALL';
      }
    }

    if (crossedBelowMiddle || currentPrice < ema20) {
      if (!direction) {
        confirmations.length = 0;
        confirmations.push('KC_BELOW_MIDDLE');
        if (macdBearCross || macdLine < signalLine) {
          confirmations.push('MACD_BEARISH');
          if (currentPrice > lowerBand) {
            confirmations.push('ROOM_TO_LOWER');
          }
          direction = 'PUT';
        }
      }
    }

    if (!direction || confirmations.length < 2) return null;

    const confidence = 70 + (confirmations.length * 5);

    return {
      direction,
      confidence: Math.min(92, confidence),
      reason: confirmations.join(', '),
      strategy: this.name,
      confirmations: confirmations.length,
      expiration: 5,
      indicators: {
        kc_middle: ema20,
        kc_upper: upperBand,
        kc_lower: lowerBand,
        macd: macdLine,
        signal: signalLine,
        price: currentPrice,
      },
    };
  }
}

export default KeltnerMACDStrategy;
