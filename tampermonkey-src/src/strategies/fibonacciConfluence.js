/**
 * Fibonacci Confluence Strategy (BETA)
 * Local mirror of backend strategy_fibonacci_confluence.py
 *
 * Combines:
 *   - Rolling swing anchor (last 30 bars)
 *   - Fibonacci retracement levels (23.6/38.2/50/61.8/78.6)
 *   - Trend filter (EMA20)
 *   - Reversal candle (engulfing / hammer / shooting star)
 *   - Volume spike (current vol > 1.2 * 20-bar avg)
 *
 * Fires CALL/PUT when 3+ of 4 confirms align.
 * Confidence capped at 82%; tracked as BETA.
 */

import { BaseStrategy } from './base.js';
import { calculateEMA } from '../utils/indicators.js';

const FIB_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786];

function isBullishEngulfing(prev, curr) {
  return (
    prev.close < prev.open &&
    curr.close > curr.open &&
    curr.close > prev.open &&
    curr.open < prev.close
  );
}

function isBearishEngulfing(prev, curr) {
  return (
    prev.close > prev.open &&
    curr.close < curr.open &&
    curr.close < prev.open &&
    curr.open > prev.close
  );
}

function isHammer(bar) {
  const body = Math.abs(bar.close - bar.open);
  const full = Math.max(bar.high - bar.low, 1e-9);
  const lowerWick = Math.min(bar.open, bar.close) - bar.low;
  const upperWick = bar.high - Math.max(bar.open, bar.close);
  return body / full < 0.35 && lowerWick > body * 2 && upperWick < body * 0.6;
}

function isShootingStar(bar) {
  const body = Math.abs(bar.close - bar.open);
  const full = Math.max(bar.high - bar.low, 1e-9);
  const upperWick = bar.high - Math.max(bar.open, bar.close);
  const lowerWick = Math.min(bar.open, bar.close) - bar.low;
  return body / full < 0.35 && upperWick > body * 2 && lowerWick < body * 0.6;
}

export class FibonacciConfluenceStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Fibonacci Confluence', {
      minConfidence: 65,
      swingLookback: 30,
      trendEma: 20,
      fibTolerancePct: 0.0015,
      minConfirms: 3,
      ...config,
    });
    this.beta = true;
  }

  analyze(candles) {
    const minBars = this.config.swingLookback + this.config.trendEma + 2;
    if (!candles || candles.length < minBars) return null;

    const last = candles[candles.length - 1];
    const prev = candles[candles.length - 2];
    const price = last.close;

    // 1. Recent swing anchor
    const window = candles.slice(-this.config.swingLookback);
    let hiIdx = 0, loIdx = 0;
    let swingHi = window[0].high, swingLo = window[0].low;
    for (let i = 0; i < window.length; i++) {
      if (window[i].high > swingHi) { swingHi = window[i].high; hiIdx = i; }
      if (window[i].low < swingLo) { swingLo = window[i].low; loIdx = i; }
    }
    if (swingHi <= swingLo) return null;

    const impulseUp = loIdx < hiIdx;

    // 2. Fibonacci levels
    const rng = swingHi - swingLo;
    const fibs = impulseUp
      ? FIB_RATIOS.map((r) => ({ ratio: r, level: swingHi - r * rng }))
      : FIB_RATIOS.map((r) => ({ ratio: r, level: swingLo + r * rng }));

    // Check if price is at any Fib zone (prefer deeper)
    let fibHit = null;
    for (const { ratio, level } of [...fibs].reverse()) {  // deepest first
      if (level <= 0) continue;
      if (Math.abs(price - level) / level <= this.config.fibTolerancePct) {
        fibHit = ratio.toFixed(3);
        break;
      }
    }
    if (!fibHit) return null;

    // 3. Trend filter (EMA20)
    const closes = candles.map((c) => c.close);
    const ema20 = calculateEMA(closes, this.config.trendEma);
    const aboveEma = price > ema20;
    const belowEma = price < ema20;

    // 4. Reversal candle
    const bullishReversal = isBullishEngulfing(prev, last) || isHammer(last);
    const bearishReversal = isBearishEngulfing(prev, last) || isShootingStar(last);

    // 5. Volume confirmation (avg last 20 bars)
    const volWindow = candles.slice(-20);
    const avgVol = volWindow.reduce((s, c) => s + (c.volume || 0), 0) / Math.max(volWindow.length, 1);
    const volConfirms = avgVol > 0 ? (last.volume || 0) > avgVol * 1.2 : true;

    // Decide
    let direction, confirms;
    if (impulseUp) {
      direction = 'PUT';
      confirms = {
        fib_zone: !!fibHit,
        bearish_candle: bearishReversal,
        trend_aligned: belowEma,
        volume: volConfirms,
      };
    } else {
      direction = 'CALL';
      confirms = {
        fib_zone: !!fibHit,
        bullish_candle: bullishReversal,
        trend_aligned: aboveEma,
        volume: volConfirms,
      };
    }

    const passed = Object.values(confirms).filter(Boolean).length;
    if (passed < this.config.minConfirms) return null;

    const depthBonus = { '0.236': 0, '0.382': 2, '0.500': 4, '0.618': 6, '0.786': 5 }[fibHit] || 0;
    const confidence = Math.min(
      82,
      Math.max(65, 60 + (passed - this.config.minConfirms) * 5 + depthBonus)
    );

    return {
      direction,
      confidence: Math.round(confidence * 10) / 10,
      strategy: 'Fibonacci Confluence',
      reason: `Fib ${fibHit} rejection on impulse_${impulseUp ? 'up' : 'dn'} | ${passed}/${Object.keys(confirms).length} confirms`,
      beta: true,
      fib_level: fibHit,
      confirms,
    };
  }
}

export default FibonacciConfluenceStrategy;
