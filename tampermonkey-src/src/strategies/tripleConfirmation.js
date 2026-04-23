/**
 * Triple Confirmation Strategy (BETA)
 * Local mirror of backend strategy_triple_confirmation.py
 *
 * All THREE layers must agree before firing:
 *   Layer 1 — TREND: price vs EMA(slow) + fast/slow EMA alignment + OSMA slope
 *   Layer 2 — ZONE: price in untapped supply (PUT) or demand (CALL) pivot zone
 *   Layer 3 — CONFIRM: reversal candle + Volume Oscillator spike (> +15%)
 *
 * Confidence capped at 85%; tracked as BETA.
 */

import { BaseStrategy } from './base.js';
import { calculateEMA, calculateSMA, calculateMACD } from '../utils/indicators.js';

function bullishReversalCandle(prev, curr) {
  const body = Math.abs(curr.close - curr.open);
  const full = Math.max(curr.high - curr.low, 1e-9);
  const lowerWick = Math.min(curr.open, curr.close) - curr.low;
  const engulfing = prev.close < prev.open && curr.close > curr.open && curr.close > prev.open && curr.open < prev.close;
  const hammer = body / full < 0.35 && lowerWick > body * 2;
  return engulfing || hammer;
}

function bearishReversalCandle(prev, curr) {
  const body = Math.abs(curr.close - curr.open);
  const full = Math.max(curr.high - curr.low, 1e-9);
  const upperWick = curr.high - Math.max(curr.open, curr.close);
  const engulfing = prev.close > prev.open && curr.close < curr.open && curr.close < prev.open && curr.open > prev.close;
  const shootingStar = body / full < 0.35 && upperWick > body * 2;
  return engulfing || shootingStar;
}

function findPivots(candles, left = 2, right = 2) {
  const highs = [], lows = [];
  for (let i = left; i < candles.length - right; i++) {
    const hi = candles[i].high;
    const lo = candles[i].low;
    let isHigh = true, isLow = true;
    for (let j = i - left; j <= i + right; j++) {
      if (j === i) continue;
      if (candles[j].high >= hi) isHigh = false;
      if (candles[j].low <= lo) isLow = false;
    }
    if (isHigh) highs.push(i);
    if (isLow) lows.push(i);
  }
  return { highs, lows };
}

function buildZones(candles, lookback, zoneWidthPct) {
  const window = candles.slice(-lookback);
  if (window.length < 10) return { supply: [], demand: [] };

  const { highs, lows } = findPivots(window, 2, 2);
  const supply = [], demand = [];

  for (const idx of highs) {
    const pivotHi = window[idx].high;
    const zoneLo = pivotHi * (1 - zoneWidthPct);
    const zoneHi = pivotHi * (1 + zoneWidthPct / 2);
    const after = window.slice(idx + 1);
    const maxAfter = after.reduce((m, c) => Math.max(m, c.close), 0);
    if (after.length > 0 && maxAfter < pivotHi * (1 - 0.0003)) supply.push([zoneLo, zoneHi]);
  }
  for (const idx of lows) {
    const pivotLo = window[idx].low;
    const zoneLo = pivotLo * (1 - zoneWidthPct / 2);
    const zoneHi = pivotLo * (1 + zoneWidthPct);
    const after = window.slice(idx + 1);
    const minAfter = after.reduce((m, c) => Math.min(m, c.close), Infinity);
    if (after.length > 0 && minAfter > pivotLo * (1 + 0.0003)) demand.push([zoneLo, zoneHi]);
  }
  return { supply, demand };
}

function inZone(price, zones) {
  return zones.some(([lo, hi]) => price >= lo && price <= hi);
}

export class TripleConfirmationStrategy extends BaseStrategy {
  constructor(config = {}) {
    super('Triple Confirmation', {
      minConfidence: 70,
      fastMa: 9,
      slowMa: 21,
      zoneLookback: 50,
      zoneWidthPct: 0.0012,
      volFast: 5,
      volSlow: 20,
      ...config,
    });
    this.beta = true;
  }

  analyze(candles) {
    const minBars = Math.max(this.config.slowMa, this.config.zoneLookback) + 5;
    if (!candles || candles.length < minBars) return null;

    const last = candles[candles.length - 1];
    const prev = candles[candles.length - 2];
    const price = last.close;
    const closes = candles.map((c) => c.close);

    // Layer 1 — Trend
    const fast = calculateEMA(closes, this.config.fastMa);
    const slow = calculateEMA(closes, this.config.slowMa);
    const macd = calculateMACD(closes);
    // MACD hist = macd - signal; we want the last 3 hist values to detect slope
    const histSeries = macd?.histogramSeries || null;
    let histSlope = 0;
    if (Array.isArray(histSeries) && histSeries.length >= 2) {
      histSlope = histSeries[histSeries.length - 1] - histSeries[histSeries.length - 2];
    } else if (macd && typeof macd.histogram === 'number') {
      // Fallback: approximate slope as histogram sign * magnitude
      histSlope = macd.histogram;
    }
    const trendUp = price > slow && fast > slow && histSlope > 0;
    const trendDn = price < slow && fast < slow && histSlope < 0;

    // Layer 2 — Zone
    const { supply, demand } = buildZones(candles, this.config.zoneLookback, this.config.zoneWidthPct);
    const inSupply = inZone(price, supply);
    const inDemand = inZone(price, demand);

    // Layer 3 — Volume oscillator + reversal candle
    const volumes = candles.map((c) => c.volume || 0);
    const volFast = calculateSMA(volumes, this.config.volFast);
    const volSlow = calculateSMA(volumes, this.config.volSlow);
    const volOsc = volSlow > 0 ? ((volFast - volSlow) / volSlow) * 100 : 0;
    const volSpike = volOsc > 15;

    const bullishCandle = bullishReversalCandle(prev, last);
    const bearishCandle = bearishReversalCandle(prev, last);

    let direction = null, layers = null;
    if (inDemand && trendUp && bullishCandle && volSpike) {
      direction = 'CALL';
      layers = { zone: 'demand', trend: 'up', candle: 'bullish_reversal', volume: volOsc };
    } else if (inSupply && trendDn && bearishCandle && volSpike) {
      direction = 'PUT';
      layers = { zone: 'supply', trend: 'dn', candle: 'bearish_reversal', volume: volOsc };
    } else {
      return null;
    }

    const volBonus = Math.min((volOsc - 15) / 5, 5);
    const trendBonus = Math.min((Math.abs(histSlope) / Math.max(slow, 1e-9)) * 10_000 * 0.5, 5);
    const confidence = Math.min(85, Math.max(70, 70 + volBonus + trendBonus));

    return {
      direction,
      confidence: Math.round(confidence * 10) / 10,
      strategy: 'Triple Confirmation',
      reason: `Triple-agree: ${layers.zone} zone + trend_${layers.trend} + ${layers.candle} + vol_osc=${layers.volume.toFixed(1)}%`,
      beta: true,
      layers,
    };
  }
}

export default TripleConfirmationStrategy;
