/**
 * Technical Analysis Utilities
 * Common indicators used by all strategies
 */

/**
 * Calculate RSI (Relative Strength Index)
 * @param {number[]} prices - Array of close prices
 * @param {number} period - RSI period (default 14)
 * @returns {number} RSI value (0-100)
 */
export function calculateRSI(prices, period = 14) {
  if (prices.length < period + 1) return 50;
  
  let gains = 0, losses = 0;
  for (let i = prices.length - period; i < prices.length; i++) {
    const change = prices[i] - prices[i - 1];
    if (change > 0) gains += change;
    else losses -= change;
  }
  
  if (losses === 0) return 100;
  if (gains === 0) return 0;
  
  const rs = gains / losses;
  return 100 - (100 / (1 + rs));
}

/**
 * Calculate EMA (Exponential Moving Average)
 * @param {number[]} prices - Array of prices
 * @param {number} period - EMA period
 * @returns {number} EMA value
 */
export function calculateEMA(prices, period) {
  if (prices.length < period) return prices[prices.length - 1];
  
  const k = 2 / (period + 1);
  let ema = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;
  
  for (let i = period; i < prices.length; i++) {
    ema = prices[i] * k + ema * (1 - k);
  }
  return ema;
}

/**
 * Calculate SMA (Simple Moving Average)
 * @param {number[]} prices - Array of prices
 * @param {number} period - SMA period
 * @returns {number} SMA value
 */
export function calculateSMA(prices, period) {
  if (prices.length < period) return prices[prices.length - 1];
  
  const slice = prices.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

/**
 * Calculate WMA (Weighted Moving Average)
 * @param {number[]} prices - Array of prices
 * @param {number} period - WMA period
 * @returns {number} WMA value
 */
export function calculateWMA(prices, period) {
  if (prices.length < period) return prices[prices.length - 1];
  
  const slice = prices.slice(-period);
  let weightSum = 0;
  let valueSum = 0;
  
  for (let i = 0; i < slice.length; i++) {
    const weight = i + 1;
    weightSum += weight;
    valueSum += slice[i] * weight;
  }
  
  return valueSum / weightSum;
}

/**
 * Calculate Stochastic Oscillator
 * @param {number[]} highs - Array of high prices
 * @param {number[]} lows - Array of low prices
 * @param {number[]} closes - Array of close prices
 * @param {number} period - Stochastic period
 * @returns {Object} { k, d } values
 */
export function calculateStochastic(highs, lows, closes, period = 14) {
  if (closes.length < period) return { k: 50, d: 50 };
  
  const recentHighs = highs.slice(-period);
  const recentLows = lows.slice(-period);
  const highestHigh = Math.max(...recentHighs);
  const lowestLow = Math.min(...recentLows);
  const currentClose = closes[closes.length - 1];
  
  const range = highestHigh - lowestLow;
  const k = range > 0 ? ((currentClose - lowestLow) / range) * 100 : 50;
  
  // D is typically a 3-period SMA of K, simplified here
  return { k, d: k };
}

/**
 * Calculate Bollinger Bands
 * @param {number[]} prices - Array of close prices
 * @param {number} period - BB period (default 20)
 * @param {number} stdDev - Standard deviation multiplier
 * @returns {Object} { upper, middle, lower, width, percentB }
 */
export function calculateBollingerBands(prices, period = 20, stdDev = 2) {
  if (prices.length < period) {
    const lastPrice = prices[prices.length - 1];
    return { upper: lastPrice, middle: lastPrice, lower: lastPrice, width: 0, percentB: 0.5 };
  }
  
  const slice = prices.slice(-period);
  const middle = slice.reduce((a, b) => a + b, 0) / period;
  
  // Calculate standard deviation
  const squaredDiffs = slice.map(p => Math.pow(p - middle, 2));
  const variance = squaredDiffs.reduce((a, b) => a + b, 0) / period;
  const sd = Math.sqrt(variance);
  
  const upper = middle + (sd * stdDev);
  const lower = middle - (sd * stdDev);
  const width = (upper - lower) / middle;
  
  const currentPrice = prices[prices.length - 1];
  const percentB = (upper - lower) > 0 ? (currentPrice - lower) / (upper - lower) : 0.5;
  
  return { upper, middle, lower, width, percentB };
}

/**
 * Calculate MACD
 * @param {number[]} prices - Array of close prices
 * @param {number} fastPeriod - Fast EMA period (default 12)
 * @param {number} slowPeriod - Slow EMA period (default 26)
 * @param {number} signalPeriod - Signal line period (default 9)
 * @returns {Object} { macd, signal, histogram }
 */
export function calculateMACD(prices, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  if (prices.length < slowPeriod) {
    return { macd: 0, signal: 0, histogram: 0 };
  }
  
  const fastEMA = calculateEMA(prices, fastPeriod);
  const slowEMA = calculateEMA(prices, slowPeriod);
  const macd = fastEMA - slowEMA;
  
  // Calculate signal line (simplified)
  const signal = macd * 0.9; // Approximation
  const histogram = macd - signal;
  
  return { macd, signal, histogram };
}

/**
 * Calculate ATR (Average True Range)
 * @param {number[]} highs - Array of high prices
 * @param {number[]} lows - Array of low prices
 * @param {number[]} closes - Array of close prices
 * @param {number} period - ATR period
 * @returns {number} ATR value
 */
export function calculateATR(highs, lows, closes, period = 14) {
  if (highs.length < period + 1) return 0;
  
  const trueRanges = [];
  for (let i = 1; i < highs.length; i++) {
    const tr = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
    trueRanges.push(tr);
  }
  
  const recentTR = trueRanges.slice(-period);
  return recentTR.reduce((a, b) => a + b, 0) / period;
}

/**
 * Calculate ADX (Average Directional Index)
 * @param {number[]} highs - Array of high prices
 * @param {number[]} lows - Array of low prices
 * @param {number[]} closes - Array of close prices
 * @param {number} period - ADX period
 * @returns {number} ADX value
 */
export function calculateADX(highs, lows, closes, period = 14) {
  if (highs.length < period * 2) return 0;

  const len = highs.length;
  let plusDM = 0, minusDM = 0, tr = 0;

  for (let i = len - period; i < len; i++) {
    const upMove = highs[i] - highs[i - 1];
    const downMove = lows[i - 1] - lows[i];
    plusDM += (upMove > downMove && upMove > 0) ? upMove : 0;
    minusDM += (downMove > upMove && downMove > 0) ? downMove : 0;
    tr += Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
  }

  if (tr === 0) return 0;
  const plusDI = (plusDM / tr) * 100;
  const minusDI = (minusDM / tr) * 100;
  const diSum = plusDI + minusDI;
  if (diSum === 0) return 0;

  return Math.abs(plusDI - minusDI) / diSum * 100;
}

/**
 * Detect candlestick patterns
 * @param {Object[]} candles - Array of candle objects
 * @returns {Object} Pattern detection results
 */
export function detectCandlePatterns(candles) {
  if (candles.length < 3) return { pattern: null, bullish: null };
  
  const current = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const prev2 = candles[candles.length - 3];
  
  const bodySize = Math.abs(current.close - current.open);
  const upperWick = current.high - Math.max(current.open, current.close);
  const lowerWick = Math.min(current.open, current.close) - current.low;
  const totalSize = current.high - current.low;
  
  const isBullish = current.close > current.open;
  const isPrevBullish = prev.close > prev.open;
  
  // Doji
  if (bodySize < totalSize * 0.1) {
    return { pattern: 'doji', bullish: null };
  }
  
  // Hammer / Hanging Man
  if (lowerWick > bodySize * 2 && upperWick < bodySize * 0.5) {
    return { pattern: isBullish ? 'hammer' : 'hanging_man', bullish: isBullish };
  }
  
  // Shooting Star / Inverted Hammer
  if (upperWick > bodySize * 2 && lowerWick < bodySize * 0.5) {
    return { pattern: isBullish ? 'inverted_hammer' : 'shooting_star', bullish: isBullish };
  }
  
  // Engulfing
  if (isBullish && !isPrevBullish && current.close > prev.open && current.open < prev.close) {
    return { pattern: 'bullish_engulfing', bullish: true };
  }
  if (!isBullish && isPrevBullish && current.close < prev.open && current.open > prev.close) {
    return { pattern: 'bearish_engulfing', bullish: false };
  }
  
  return { pattern: null, bullish: null };
}

/**
 * Calculate support and resistance levels
 * @param {number[]} highs - Array of high prices
 * @param {number[]} lows - Array of low prices
 * @param {number} lookback - Lookback period
 * @returns {Object} { resistance, support }
 */
export function calculateSupportResistance(highs, lows, lookback = 20) {
  const recentHighs = highs.slice(-lookback);
  const recentLows = lows.slice(-lookback);
  
  return {
    resistance: Math.max(...recentHighs),
    support: Math.min(...recentLows),
  };
}

export default {
  calculateRSI,
  calculateEMA,
  calculateSMA,
  calculateWMA,
  calculateStochastic,
  calculateBollingerBands,
  calculateMACD,
  calculateATR,
  calculateADX,
  detectCandlePatterns,
  calculateSupportResistance,
};
