import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { toast } from 'sonner';
import { 
  Plus, Trash2, Copy, Save, Play, Settings, TrendingUp, Activity,
  BarChart3, Layers, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Circle, Zap, ArrowUp, ArrowDown
} from 'lucide-react';
import { AssetPicker } from './shared/AssetPicker';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// =====================================================
// INDICATOR TEMPLATES - TradingView Style
// =====================================================
// Each indicator has pre-built condition types that make sense for that indicator

const INDICATOR_TEMPLATES = {
  // Moving Averages
  EMA: {
    name: 'EMA (Exponential Moving Average)',
    category: 'trend',
    icon: '📈',
    description: 'Exponential Moving Average - gives more weight to recent prices',
    parameters: {
      period: { label: 'Period', type: 'number', default: 9, min: 1, max: 200 }
    },
    conditions: [
      { id: 'price_crosses_above', label: 'Price crosses above EMA', signal: 'CALL', description: 'Bullish signal when price moves above the EMA' },
      { id: 'price_crosses_below', label: 'Price crosses below EMA', signal: 'PUT', description: 'Bearish signal when price moves below the EMA' },
      { id: 'price_above', label: 'Price is above EMA', signal: 'CALL', description: 'Bullish when price stays above EMA' },
      { id: 'price_below', label: 'Price is below EMA', signal: 'PUT', description: 'Bearish when price stays below EMA' },
    ]
  },
  
  EMA_CROSSOVER: {
    name: 'EMA Crossover',
    category: 'trend',
    icon: '✖️',
    description: 'Two EMAs crossing - classic trend signal',
    parameters: {
      fast_period: { label: 'Fast EMA', type: 'number', default: 7, min: 1, max: 100 },
      slow_period: { label: 'Slow EMA', type: 'number', default: 21, min: 1, max: 200 }
    },
    conditions: [
      { id: 'golden_cross', label: 'Fast EMA crosses above Slow EMA (Golden Cross)', signal: 'CALL', description: 'Strong bullish signal - short-term momentum turning up' },
      { id: 'death_cross', label: 'Fast EMA crosses below Slow EMA (Death Cross)', signal: 'PUT', description: 'Strong bearish signal - short-term momentum turning down' },
      { id: 'fast_above_slow', label: 'Fast EMA is above Slow EMA', signal: 'CALL', description: 'Uptrend confirmed' },
      { id: 'fast_below_slow', label: 'Fast EMA is below Slow EMA', signal: 'PUT', description: 'Downtrend confirmed' },
    ]
  },

  SMA: {
    name: 'SMA (Simple Moving Average)',
    category: 'trend',
    icon: '📊',
    description: 'Simple Moving Average - equal weight to all prices',
    parameters: {
      period: { label: 'Period', type: 'number', default: 20, min: 1, max: 200 }
    },
    conditions: [
      { id: 'price_crosses_above', label: 'Price crosses above SMA', signal: 'CALL', description: 'Bullish crossover' },
      { id: 'price_crosses_below', label: 'Price crosses below SMA', signal: 'PUT', description: 'Bearish crossover' },
      { id: 'price_above', label: 'Price is above SMA', signal: 'CALL', description: 'Uptrend filter' },
      { id: 'price_below', label: 'Price is below SMA', signal: 'PUT', description: 'Downtrend filter' },
    ]
  },

  // Oscillators
  RSI: {
    name: 'RSI (Relative Strength Index)',
    category: 'momentum',
    icon: '📉',
    description: 'Measures overbought/oversold conditions (0-100)',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 2, max: 50 },
      overbought: { label: 'Overbought Level', type: 'number', default: 70, min: 50, max: 95 },
      oversold: { label: 'Oversold Level', type: 'number', default: 30, min: 5, max: 50 }
    },
    conditions: [
      { id: 'crosses_above_oversold', label: 'RSI crosses above oversold level', signal: 'CALL', description: 'Exit oversold - potential reversal up' },
      { id: 'crosses_below_overbought', label: 'RSI crosses below overbought level', signal: 'PUT', description: 'Exit overbought - potential reversal down' },
      { id: 'enters_oversold', label: 'RSI enters oversold zone', signal: 'CALL', description: 'Extreme oversold - look for bounce' },
      { id: 'enters_overbought', label: 'RSI enters overbought zone', signal: 'PUT', description: 'Extreme overbought - look for drop' },
      { id: 'above_50', label: 'RSI is above 50 (bullish momentum)', signal: 'CALL', description: 'Bullish momentum filter' },
      { id: 'below_50', label: 'RSI is below 50 (bearish momentum)', signal: 'PUT', description: 'Bearish momentum filter' },
    ]
  },

  STOCHASTIC: {
    name: 'Stochastic Oscillator',
    category: 'momentum',
    icon: '🔄',
    description: 'Compares closing price to price range (0-100)',
    parameters: {
      k_period: { label: '%K Period', type: 'number', default: 14, min: 1, max: 50 },
      d_period: { label: '%D Period', type: 'number', default: 3, min: 1, max: 20 },
      overbought: { label: 'Overbought', type: 'number', default: 80, min: 50, max: 95 },
      oversold: { label: 'Oversold', type: 'number', default: 20, min: 5, max: 50 }
    },
    conditions: [
      { id: 'k_crosses_above_d_oversold', label: '%K crosses above %D in oversold zone', signal: 'CALL', description: 'Strong buy signal' },
      { id: 'k_crosses_below_d_overbought', label: '%K crosses below %D in overbought zone', signal: 'PUT', description: 'Strong sell signal' },
      { id: 'exits_oversold', label: 'Stochastic exits oversold zone', signal: 'CALL', description: 'Bullish momentum starting' },
      { id: 'exits_overbought', label: 'Stochastic exits overbought zone', signal: 'PUT', description: 'Bearish momentum starting' },
    ]
  },

  MACD: {
    name: 'MACD',
    category: 'momentum',
    icon: '📶',
    description: 'Moving Average Convergence Divergence - trend & momentum',
    parameters: {
      fast_period: { label: 'Fast Period', type: 'number', default: 12, min: 1, max: 50 },
      slow_period: { label: 'Slow Period', type: 'number', default: 26, min: 1, max: 100 },
      signal_period: { label: 'Signal Period', type: 'number', default: 9, min: 1, max: 30 }
    },
    conditions: [
      { id: 'macd_crosses_above_signal', label: 'MACD line crosses above Signal line', signal: 'CALL', description: 'Bullish crossover - momentum turning up' },
      { id: 'macd_crosses_below_signal', label: 'MACD line crosses below Signal line', signal: 'PUT', description: 'Bearish crossover - momentum turning down' },
      { id: 'histogram_turns_positive', label: 'Histogram turns positive', signal: 'CALL', description: 'Bullish momentum increasing' },
      { id: 'histogram_turns_negative', label: 'Histogram turns negative', signal: 'PUT', description: 'Bearish momentum increasing' },
      { id: 'macd_crosses_above_zero', label: 'MACD crosses above zero line', signal: 'CALL', description: 'Trend turning bullish' },
      { id: 'macd_crosses_below_zero', label: 'MACD crosses below zero line', signal: 'PUT', description: 'Trend turning bearish' },
    ]
  },

  // Volatility
  BOLLINGER_BANDS: {
    name: 'Bollinger Bands',
    category: 'volatility',
    icon: '🎯',
    description: 'Volatility bands around a moving average',
    parameters: {
      period: { label: 'Period', type: 'number', default: 20, min: 5, max: 50 },
      std_dev: { label: 'Std Deviations', type: 'number', default: 2, min: 1, max: 4, step: 0.5 }
    },
    conditions: [
      { id: 'price_breaks_above_upper', label: 'Price breaks above Upper Band', signal: 'CALL', description: 'Breakout - strong bullish momentum' },
      { id: 'price_breaks_below_lower', label: 'Price breaks below Lower Band', signal: 'PUT', description: 'Breakdown - strong bearish momentum' },
      { id: 'price_touches_lower_reversal', label: 'Price touches Lower Band (reversal)', signal: 'CALL', description: 'Mean reversion buy - oversold bounce' },
      { id: 'price_touches_upper_reversal', label: 'Price touches Upper Band (reversal)', signal: 'PUT', description: 'Mean reversion sell - overbought drop' },
      { id: 'price_crosses_above_middle', label: 'Price crosses above Middle Band', signal: 'CALL', description: 'Bullish - above average' },
      { id: 'price_crosses_below_middle', label: 'Price crosses below Middle Band', signal: 'PUT', description: 'Bearish - below average' },
      { id: 'bands_squeeze', label: 'Bands squeezing (low volatility)', signal: 'NEUTRAL', description: 'Breakout imminent - prepare for move' },
    ]
  },

  // Keltner Channel (for 5s strategy)
  KELTNER_CHANNEL: {
    name: 'Keltner Channel',
    category: 'volatility',
    icon: '📊',
    description: 'ATR-based channel around EMA - excellent for 5s scalping',
    parameters: {
      ema_period: { label: 'EMA Period', type: 'number', default: 20, min: 5, max: 50 },
      atr_period: { label: 'ATR Period', type: 'number', default: 60, min: 10, max: 100 },
      multiplier: { label: 'Multiplier', type: 'number', default: 4, min: 1, max: 10, step: 0.5 }
    },
    conditions: [
      { id: 'price_crosses_above_middle', label: 'Price crosses above Middle (EMA)', signal: 'CALL', description: 'Bullish breakout above EMA - key 5s entry' },
      { id: 'price_crosses_below_middle', label: 'Price crosses below Middle (EMA)', signal: 'PUT', description: 'Bearish breakdown below EMA - key 5s entry' },
      { id: 'price_above_middle', label: 'Price above Middle line', signal: 'CALL', description: 'Bullish trend - price above EMA' },
      { id: 'price_below_middle', label: 'Price below Middle line', signal: 'PUT', description: 'Bearish trend - price below EMA' },
      { id: 'price_touches_upper', label: 'Price touches Upper Band', signal: 'PUT', description: 'Overbought - potential reversal' },
      { id: 'price_touches_lower', label: 'Price touches Lower Band', signal: 'CALL', description: 'Oversold - potential reversal' },
    ]
  },

  ATR: {
    name: 'ATR (Average True Range)',
    category: 'volatility',
    icon: '📏',
    description: 'Measures market volatility',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 1, max: 50 }
    },
    conditions: [
      { id: 'high_volatility', label: 'High volatility (ATR above average)', signal: 'NEUTRAL', description: 'Market is volatile - wider stops needed' },
      { id: 'low_volatility', label: 'Low volatility (ATR below average)', signal: 'NEUTRAL', description: 'Market is quiet - tighter stops possible' },
    ]
  },

  // Trend
  SUPERTREND: {
    name: 'SuperTrend',
    category: 'trend',
    icon: '🚀',
    description: 'Trend-following indicator based on ATR',
    parameters: {
      period: { label: 'ATR Period', type: 'number', default: 10, min: 1, max: 50 },
      multiplier: { label: 'Multiplier', type: 'number', default: 3, min: 1, max: 10, step: 0.5 }
    },
    conditions: [
      { id: 'turns_bullish', label: 'SuperTrend turns bullish (green)', signal: 'CALL', description: 'Trend changed to up' },
      { id: 'turns_bearish', label: 'SuperTrend turns bearish (red)', signal: 'PUT', description: 'Trend changed to down' },
      { id: 'price_above_supertrend', label: 'Price is above SuperTrend', signal: 'CALL', description: 'Uptrend active' },
      { id: 'price_below_supertrend', label: 'Price is below SuperTrend', signal: 'PUT', description: 'Downtrend active' },
    ]
  },

  ADX: {
    name: 'ADX (Average Directional Index)',
    category: 'trend',
    icon: '💪',
    description: 'Measures trend strength (not direction)',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 5, max: 50 },
      threshold: { label: 'Trend Threshold', type: 'number', default: 25, min: 15, max: 50 }
    },
    conditions: [
      { id: 'strong_trend', label: 'ADX above threshold (strong trend)', signal: 'NEUTRAL', description: 'Trend is strong - follow momentum' },
      { id: 'weak_trend', label: 'ADX below threshold (weak trend)', signal: 'NEUTRAL', description: 'No clear trend - range trading' },
      { id: 'plus_di_above_minus', label: '+DI above -DI (bullish trend)', signal: 'CALL', description: 'Buyers in control' },
      { id: 'minus_di_above_plus', label: '-DI above +DI (bearish trend)', signal: 'PUT', description: 'Sellers in control' },
    ]
  },

  // Volume
  VOLUME: {
    name: 'Volume',
    category: 'volume',
    icon: '📊',
    description: 'Trading volume analysis',
    parameters: {
      ma_period: { label: 'MA Period', type: 'number', default: 20, min: 5, max: 50 }
    },
    conditions: [
      { id: 'above_average', label: 'Volume above average (high interest)', signal: 'NEUTRAL', description: 'Confirms price movement' },
      { id: 'volume_spike', label: 'Volume spike (2x average)', signal: 'NEUTRAL', description: 'Significant activity' },
    ]
  },

  // Support/Resistance
  SUPPORT_RESISTANCE: {
    name: 'Support/Resistance Levels',
    category: 'pattern',
    icon: '🎚️',
    description: 'Key price levels where reversals may occur',
    parameters: {
      lookback: { label: 'Lookback Period', type: 'number', default: 50, min: 10, max: 200 }
    },
    conditions: [
      { id: 'bounces_off_support', label: 'Price bounces off Support', signal: 'CALL', description: 'Support holding - bullish' },
      { id: 'breaks_below_support', label: 'Price breaks below Support', signal: 'PUT', description: 'Support broken - bearish' },
      { id: 'rejected_at_resistance', label: 'Price rejected at Resistance', signal: 'PUT', description: 'Resistance holding - bearish' },
      { id: 'breaks_above_resistance', label: 'Price breaks above Resistance', signal: 'CALL', description: 'Resistance broken - bullish' },
    ]
  },

  // Price Action
  CANDLESTICK: {
    name: 'Candlestick Patterns',
    category: 'pattern',
    icon: '🕯️',
    description: 'Classic candlestick reversal patterns',
    parameters: {},
    conditions: [
      { id: 'bullish_engulfing', label: 'Bullish Engulfing pattern', signal: 'CALL', description: 'Strong reversal signal' },
      { id: 'bearish_engulfing', label: 'Bearish Engulfing pattern', signal: 'PUT', description: 'Strong reversal signal' },
      { id: 'hammer', label: 'Hammer (bullish)', signal: 'CALL', description: 'Reversal at bottom' },
      { id: 'shooting_star', label: 'Shooting Star (bearish)', signal: 'PUT', description: 'Reversal at top' },
      { id: 'doji', label: 'Doji (indecision)', signal: 'NEUTRAL', description: 'Potential reversal' },
      { id: 'morning_star', label: 'Morning Star (bullish)', signal: 'CALL', description: 'Three-candle reversal' },
      { id: 'evening_star', label: 'Evening Star (bearish)', signal: 'PUT', description: 'Three-candle reversal' },
    ]
  },

  // Williams %R
  WILLIAMS_R: {
    name: 'Williams %R',
    category: 'momentum',
    icon: '📈',
    description: 'Momentum indicator similar to Stochastic',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 5, max: 50 },
      overbought: { label: 'Overbought', type: 'number', default: -20, min: -10, max: -30 },
      oversold: { label: 'Oversold', type: 'number', default: -80, min: -70, max: -90 }
    },
    conditions: [
      { id: 'exits_oversold', label: 'Exits oversold zone (above -80)', signal: 'CALL', description: 'Bullish momentum' },
      { id: 'exits_overbought', label: 'Exits overbought zone (below -20)', signal: 'PUT', description: 'Bearish momentum' },
    ]
  },

  CCI: {
    name: 'CCI (Commodity Channel Index)',
    category: 'momentum',
    icon: '🌊',
    description: 'Measures current price vs average price',
    parameters: {
      period: { label: 'Period', type: 'number', default: 20, min: 5, max: 50 },
      overbought: { label: 'Overbought', type: 'number', default: 100, min: 50, max: 200 },
      oversold: { label: 'Oversold', type: 'number', default: -100, min: -200, max: -50 }
    },
    conditions: [
      { id: 'crosses_above_oversold', label: 'CCI crosses above oversold', signal: 'CALL', description: 'Bullish reversal' },
      { id: 'crosses_below_overbought', label: 'CCI crosses below overbought', signal: 'PUT', description: 'Bearish reversal' },
      { id: 'crosses_above_zero', label: 'CCI crosses above zero', signal: 'CALL', description: 'Bullish momentum' },
      { id: 'crosses_below_zero', label: 'CCI crosses below zero', signal: 'PUT', description: 'Bearish momentum' },
    ]
  },

  // Momentum Indicator (NEW)
  MOMENTUM: {
    name: 'Momentum Indicator',
    category: 'momentum',
    icon: '⚡',
    description: 'Measures rate of price change - identifies trend strength and potential reversals',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 1, max: 50 },
      threshold: { label: 'Threshold', type: 'number', default: 0, min: -50, max: 50 },
      smoothing: { label: 'Smoothing (EMA)', type: 'number', default: 3, min: 1, max: 20 },
      signal_type: { label: 'Signal Type (1=cross, 2=zone)', type: 'number', default: 1, min: 1, max: 2 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'Momentum crosses above zero', signal: 'CALL', description: 'Bullish momentum shift - price acceleration turning positive' },
      { id: 'crosses_below_zero', label: 'Momentum crosses below zero', signal: 'PUT', description: 'Bearish momentum shift - price acceleration turning negative' },
      { id: 'strong_positive', label: 'Strong positive momentum', signal: 'CALL', description: 'Momentum above threshold - strong upward pressure' },
      { id: 'strong_negative', label: 'Strong negative momentum', signal: 'PUT', description: 'Momentum below threshold - strong downward pressure' },
      { id: 'momentum_increasing', label: 'Momentum increasing (acceleration)', signal: 'CALL', description: 'Momentum slope positive - trend strengthening' },
      { id: 'momentum_decreasing', label: 'Momentum decreasing (deceleration)', signal: 'PUT', description: 'Momentum slope negative - trend weakening' },
      { id: 'bullish_divergence', label: 'Bullish divergence (price down, momentum up)', signal: 'CALL', description: 'Hidden bullish signal - potential reversal up' },
      { id: 'bearish_divergence', label: 'Bearish divergence (price up, momentum down)', signal: 'PUT', description: 'Hidden bearish signal - potential reversal down' },
    ]
  },

  // Parabolic SAR
  PARABOLIC_SAR: {
    name: 'Parabolic SAR',
    category: 'trend',
    icon: '⭐',
    description: 'Stop and Reverse - trend following',
    parameters: {
      acceleration: { label: 'Acceleration', type: 'number', default: 0.02, min: 0.01, max: 0.1, step: 0.01 },
      maximum: { label: 'Maximum', type: 'number', default: 0.2, min: 0.1, max: 0.5, step: 0.05 }
    },
    conditions: [
      { id: 'sar_flips_below', label: 'SAR flips below price (bullish)', signal: 'CALL', description: 'Trend changed to up' },
      { id: 'sar_flips_above', label: 'SAR flips above price (bearish)', signal: 'PUT', description: 'Trend changed to down' },
    ]
  },

  // Ichimoku
  ICHIMOKU: {
    name: 'Ichimoku Cloud',
    category: 'trend',
    icon: '☁️',
    description: 'Complete trading system with multiple signals',
    parameters: {
      tenkan: { label: 'Tenkan Period', type: 'number', default: 9, min: 5, max: 30 },
      kijun: { label: 'Kijun Period', type: 'number', default: 26, min: 10, max: 60 },
      senkou: { label: 'Senkou Span B', type: 'number', default: 52, min: 20, max: 120 }
    },
    conditions: [
      { id: 'price_above_cloud', label: 'Price above Cloud (bullish)', signal: 'CALL', description: 'Strong uptrend' },
      { id: 'price_below_cloud', label: 'Price below Cloud (bearish)', signal: 'PUT', description: 'Strong downtrend' },
      { id: 'tenkan_crosses_kijun_up', label: 'Tenkan crosses above Kijun', signal: 'CALL', description: 'Bullish TK cross' },
      { id: 'tenkan_crosses_kijun_down', label: 'Tenkan crosses below Kijun', signal: 'PUT', description: 'Bearish TK cross' },
      { id: 'cloud_turns_bullish', label: 'Cloud turns bullish (green)', signal: 'CALL', description: 'Future trend bullish' },
      { id: 'cloud_turns_bearish', label: 'Cloud turns bearish (red)', signal: 'PUT', description: 'Future trend bearish' },
    ]
  },

  // ============================================================
  // POCKET OPTION NATIVE INDICATORS
  // ============================================================

  // Alligator (Bill Williams)
  ALLIGATOR: {
    name: 'Alligator (Bill Williams)',
    category: 'trend',
    icon: '🐊',
    description: 'Three smoothed MAs (Jaws/Teeth/Lips) - PO native trend filter',
    parameters: {
      jaws_period: { label: 'Jaws Period', type: 'number', default: 13, min: 5, max: 50 },
      jaws_shift: { label: 'Jaws Shift', type: 'number', default: 8, min: 0, max: 20 },
      teeth_period: { label: 'Teeth Period', type: 'number', default: 8, min: 3, max: 30 },
      teeth_shift: { label: 'Teeth Shift', type: 'number', default: 5, min: 0, max: 20 },
      lips_period: { label: 'Lips Period', type: 'number', default: 5, min: 2, max: 20 },
      lips_shift: { label: 'Lips Shift', type: 'number', default: 3, min: 0, max: 20 }
    },
    conditions: [
      { id: 'awake_bullish', label: 'Alligator awake (bullish: Lips > Teeth > Jaws)', signal: 'CALL', description: 'Strong uptrend confirmed by Alligator alignment' },
      { id: 'awake_bearish', label: 'Alligator awake (bearish: Lips < Teeth < Jaws)', signal: 'PUT', description: 'Strong downtrend confirmed by Alligator alignment' },
      { id: 'lips_crosses_above_teeth', label: 'Lips crosses above Teeth (early bullish)', signal: 'CALL', description: 'First sign of awakening uptrend' },
      { id: 'lips_crosses_below_teeth', label: 'Lips crosses below Teeth (early bearish)', signal: 'PUT', description: 'First sign of awakening downtrend' },
      { id: 'sleeping', label: 'Alligator sleeping (lines intertwined)', signal: 'NEUTRAL', description: 'No trend - skip trades' },
    ]
  },

  // Awesome Oscillator
  AWESOME_OSCILLATOR: {
    name: 'Awesome Oscillator (AO)',
    category: 'momentum',
    icon: '💥',
    description: 'Momentum histogram (5 vs 34 SMA of midpoint) - PO native',
    parameters: {
      fast_period: { label: 'Fast Period', type: 'number', default: 5, min: 2, max: 50 },
      slow_period: { label: 'Slow Period', type: 'number', default: 34, min: 10, max: 100 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'AO crosses above zero', signal: 'CALL', description: 'Bullish momentum shift' },
      { id: 'crosses_below_zero', label: 'AO crosses below zero', signal: 'PUT', description: 'Bearish momentum shift' },
      { id: 'twin_peaks_bullish', label: 'Twin Peaks bullish (saucer)', signal: 'CALL', description: 'Bullish saucer pattern below zero' },
      { id: 'twin_peaks_bearish', label: 'Twin Peaks bearish (saucer)', signal: 'PUT', description: 'Bearish saucer pattern above zero' },
      { id: 'green_above_zero', label: 'Green bar above zero', signal: 'CALL', description: 'Strong bullish momentum building' },
      { id: 'red_below_zero', label: 'Red bar below zero', signal: 'PUT', description: 'Strong bearish momentum building' },
    ]
  },

  // Williams Fractal
  FRACTAL: {
    name: 'Fractal (Bill Williams)',
    category: 'pattern',
    icon: '🔻',
    description: '5-bar reversal pattern - PO native chart marker',
    parameters: {
      period: { label: 'Period (each side)', type: 'number', default: 2, min: 1, max: 5 }
    },
    conditions: [
      { id: 'up_fractal_formed', label: 'Up Fractal formed (resistance)', signal: 'PUT', description: 'High point - potential reversal down' },
      { id: 'down_fractal_formed', label: 'Down Fractal formed (support)', signal: 'CALL', description: 'Low point - potential reversal up' },
      { id: 'breaks_up_fractal', label: 'Price breaks above Up Fractal', signal: 'CALL', description: 'Bullish breakout above resistance' },
      { id: 'breaks_down_fractal', label: 'Price breaks below Down Fractal', signal: 'PUT', description: 'Bearish breakdown below support' },
    ]
  },

  // DeMarker
  DEMARKER: {
    name: 'DeMarker (DeM)',
    category: 'momentum',
    icon: '📐',
    description: 'Oscillator (0-1) for overbought/oversold - PO native',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 5, max: 50 },
      overbought: { label: 'Overbought', type: 'number', default: 0.7, min: 0.5, max: 0.95, step: 0.05 },
      oversold: { label: 'Oversold', type: 'number', default: 0.3, min: 0.05, max: 0.5, step: 0.05 }
    },
    conditions: [
      { id: 'enters_oversold', label: 'DeMarker enters oversold (<0.3)', signal: 'CALL', description: 'Reversal up imminent' },
      { id: 'enters_overbought', label: 'DeMarker enters overbought (>0.7)', signal: 'PUT', description: 'Reversal down imminent' },
      { id: 'crosses_above_oversold', label: 'DeMarker crosses above oversold', signal: 'CALL', description: 'Confirmed bullish reversal' },
      { id: 'crosses_below_overbought', label: 'DeMarker crosses below overbought', signal: 'PUT', description: 'Confirmed bearish reversal' },
    ]
  },

  // Donchian Channel
  DONCHIAN_CHANNEL: {
    name: 'Donchian Channel',
    category: 'volatility',
    icon: '📦',
    description: 'Highest high / lowest low channel - PO native breakout',
    parameters: {
      period: { label: 'Period', type: 'number', default: 20, min: 5, max: 100 }
    },
    conditions: [
      { id: 'price_breaks_upper', label: 'Price breaks above Upper Band', signal: 'CALL', description: 'Bullish breakout - new high' },
      { id: 'price_breaks_lower', label: 'Price breaks below Lower Band', signal: 'PUT', description: 'Bearish breakdown - new low' },
      { id: 'price_touches_lower', label: 'Price touches Lower Band (reversal)', signal: 'CALL', description: 'Mean reversion bounce' },
      { id: 'price_touches_upper', label: 'Price touches Upper Band (reversal)', signal: 'PUT', description: 'Mean reversion drop' },
    ]
  },

  // Envelopes
  ENVELOPES: {
    name: 'Envelopes',
    category: 'volatility',
    icon: '✉️',
    description: 'Percent-deviation channel around MA - PO native',
    parameters: {
      period: { label: 'MA Period', type: 'number', default: 14, min: 5, max: 100 },
      deviation: { label: 'Deviation %', type: 'number', default: 0.1, min: 0.05, max: 5.0, step: 0.05 }
    },
    conditions: [
      { id: 'price_breaks_upper', label: 'Price breaks above Upper Envelope', signal: 'CALL', description: 'Bullish breakout' },
      { id: 'price_breaks_lower', label: 'Price breaks below Lower Envelope', signal: 'PUT', description: 'Bearish breakdown' },
      { id: 'price_touches_upper', label: 'Price touches Upper (bounce)', signal: 'PUT', description: 'Reversal down from upper band' },
      { id: 'price_touches_lower', label: 'Price touches Lower (bounce)', signal: 'CALL', description: 'Reversal up from lower band' },
    ]
  },

  // OsMA (Moving Average of Oscillator)
  OSMA: {
    name: 'OsMA (MA of Oscillator)',
    category: 'momentum',
    icon: '🌊',
    description: 'MACD - Signal Line difference (histogram) - PO native',
    parameters: {
      fast_period: { label: 'Fast EMA', type: 'number', default: 12, min: 1, max: 50 },
      slow_period: { label: 'Slow EMA', type: 'number', default: 26, min: 1, max: 100 },
      signal_period: { label: 'Signal SMA', type: 'number', default: 9, min: 1, max: 30 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'OsMA crosses above zero', signal: 'CALL', description: 'Bullish momentum acceleration' },
      { id: 'crosses_below_zero', label: 'OsMA crosses below zero', signal: 'PUT', description: 'Bearish momentum acceleration' },
      { id: 'increasing_above_zero', label: 'OsMA increasing above zero', signal: 'CALL', description: 'Strong bullish momentum' },
      { id: 'decreasing_below_zero', label: 'OsMA decreasing below zero', signal: 'PUT', description: 'Strong bearish momentum' },
    ]
  },

  // Aroon
  AROON: {
    name: 'Aroon',
    category: 'trend',
    icon: '🏹',
    description: 'Time since highest high/lowest low - PO native trend',
    parameters: {
      period: { label: 'Period', type: 'number', default: 25, min: 5, max: 100 }
    },
    conditions: [
      { id: 'aroon_up_crosses_above_down', label: 'Aroon Up crosses above Aroon Down', signal: 'CALL', description: 'Trend changes bullish' },
      { id: 'aroon_down_crosses_above_up', label: 'Aroon Down crosses above Aroon Up', signal: 'PUT', description: 'Trend changes bearish' },
      { id: 'aroon_up_above_70', label: 'Aroon Up above 70 (strong uptrend)', signal: 'CALL', description: 'Confirmed strong uptrend' },
      { id: 'aroon_down_above_70', label: 'Aroon Down above 70 (strong downtrend)', signal: 'PUT', description: 'Confirmed strong downtrend' },
    ]
  },

  // Vortex
  VORTEX: {
    name: 'Vortex Indicator (VI)',
    category: 'trend',
    icon: '🌀',
    description: 'VI+/VI- crossovers identify trend reversals',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 5, max: 50 }
    },
    conditions: [
      { id: 'vi_plus_crosses_above_minus', label: 'VI+ crosses above VI-', signal: 'CALL', description: 'Bullish trend reversal' },
      { id: 'vi_minus_crosses_above_plus', label: 'VI- crosses above VI+', signal: 'PUT', description: 'Bearish trend reversal' },
      { id: 'vi_plus_dominant', label: 'VI+ dominant (uptrend)', signal: 'CALL', description: 'Sustained uptrend' },
      { id: 'vi_minus_dominant', label: 'VI- dominant (downtrend)', signal: 'PUT', description: 'Sustained downtrend' },
    ]
  },

  // ROC
  ROC: {
    name: 'ROC (Rate of Change)',
    category: 'momentum',
    icon: '📈',
    description: 'Speed of price change - PO native',
    parameters: {
      period: { label: 'Period', type: 'number', default: 9, min: 1, max: 50 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'ROC crosses above zero', signal: 'CALL', description: 'Bullish momentum starts' },
      { id: 'crosses_below_zero', label: 'ROC crosses below zero', signal: 'PUT', description: 'Bearish momentum starts' },
      { id: 'strongly_positive', label: 'ROC strongly positive (>1%)', signal: 'CALL', description: 'Strong bullish momentum' },
      { id: 'strongly_negative', label: 'ROC strongly negative (<-1%)', signal: 'PUT', description: 'Strong bearish momentum' },
    ]
  },

  // OBV
  OBV: {
    name: 'OBV (On-Balance Volume)',
    category: 'volume',
    icon: '📊',
    description: 'Cumulative volume flow - PO native',
    parameters: {},
    conditions: [
      { id: 'rising', label: 'OBV rising (volume confirms uptrend)', signal: 'CALL', description: 'Buying pressure dominant' },
      { id: 'falling', label: 'OBV falling (volume confirms downtrend)', signal: 'PUT', description: 'Selling pressure dominant' },
      { id: 'bullish_divergence', label: 'OBV bullish divergence (price down, OBV up)', signal: 'CALL', description: 'Hidden bullish - reversal up' },
      { id: 'bearish_divergence', label: 'OBV bearish divergence (price up, OBV down)', signal: 'PUT', description: 'Hidden bearish - reversal down' },
    ]
  },

  // MFI
  MFI: {
    name: 'MFI (Money Flow Index)',
    category: 'volume',
    icon: '💰',
    description: 'Volume-weighted RSI (0-100) - PO native',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 5, max: 50 },
      overbought: { label: 'Overbought', type: 'number', default: 80, min: 60, max: 95 },
      oversold: { label: 'Oversold', type: 'number', default: 20, min: 5, max: 40 }
    },
    conditions: [
      { id: 'crosses_above_oversold', label: 'MFI crosses above oversold (20)', signal: 'CALL', description: 'Volume-confirmed bullish reversal' },
      { id: 'crosses_below_overbought', label: 'MFI crosses below overbought (80)', signal: 'PUT', description: 'Volume-confirmed bearish reversal' },
      { id: 'above_50', label: 'MFI above 50 (bullish flow)', signal: 'CALL', description: 'Net buying pressure' },
      { id: 'below_50', label: 'MFI below 50 (bearish flow)', signal: 'PUT', description: 'Net selling pressure' },
    ]
  },

  // VWAP
  VWAP: {
    name: 'VWAP',
    category: 'volume',
    icon: '⚖️',
    description: 'Volume Weighted Average Price - PO native',
    parameters: {},
    conditions: [
      { id: 'price_crosses_above', label: 'Price crosses above VWAP', signal: 'CALL', description: 'Bullish - above fair value' },
      { id: 'price_crosses_below', label: 'Price crosses below VWAP', signal: 'PUT', description: 'Bearish - below fair value' },
      { id: 'price_above', label: 'Price above VWAP', signal: 'CALL', description: 'Bullish bias - institutional buying' },
      { id: 'price_below', label: 'Price below VWAP', signal: 'PUT', description: 'Bearish bias - institutional selling' },
    ]
  },

  // Standard Deviation
  STANDARD_DEVIATION: {
    name: 'Standard Deviation',
    category: 'volatility',
    icon: '📏',
    description: 'Volatility measure - PO native',
    parameters: {
      period: { label: 'Period', type: 'number', default: 20, min: 5, max: 100 }
    },
    conditions: [
      { id: 'expanding', label: 'StdDev expanding (rising volatility)', signal: 'NEUTRAL', description: 'Big move incoming' },
      { id: 'contracting', label: 'StdDev contracting (falling volatility)', signal: 'NEUTRAL', description: 'Squeeze - breakout pending' },
    ]
  },

  // WMA
  WMA: {
    name: 'WMA (Weighted Moving Average)',
    category: 'trend',
    icon: '📊',
    description: 'Linearly-weighted MA - PO native',
    parameters: {
      period: { label: 'Period', type: 'number', default: 14, min: 1, max: 200 }
    },
    conditions: [
      { id: 'price_crosses_above', label: 'Price crosses above WMA', signal: 'CALL', description: 'Bullish crossover' },
      { id: 'price_crosses_below', label: 'Price crosses below WMA', signal: 'PUT', description: 'Bearish crossover' },
      { id: 'price_above', label: 'Price above WMA', signal: 'CALL', description: 'Uptrend filter' },
      { id: 'price_below', label: 'Price below WMA', signal: 'PUT', description: 'Downtrend filter' },
    ]
  },

  // Bulls Power
  BULLS_POWER: {
    name: 'Bulls Power',
    category: 'momentum',
    icon: '🐂',
    description: 'High - EMA(13) - measures buying pressure',
    parameters: {
      period: { label: 'EMA Period', type: 'number', default: 13, min: 5, max: 50 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'Bulls Power crosses above zero', signal: 'CALL', description: 'Bulls take control' },
      { id: 'rising_above_zero', label: 'Bulls Power rising above zero', signal: 'CALL', description: 'Strengthening bullish pressure' },
      { id: 'crosses_below_zero', label: 'Bulls Power crosses below zero', signal: 'PUT', description: 'Bulls lose control' },
    ]
  },

  // Bears Power
  BEARS_POWER: {
    name: 'Bears Power',
    category: 'momentum',
    icon: '🐻',
    description: 'Low - EMA(13) - measures selling pressure',
    parameters: {
      period: { label: 'EMA Period', type: 'number', default: 13, min: 5, max: 50 }
    },
    conditions: [
      { id: 'crosses_above_zero', label: 'Bears Power crosses above zero', signal: 'CALL', description: 'Bears lose control' },
      { id: 'crosses_below_zero', label: 'Bears Power crosses below zero', signal: 'PUT', description: 'Bears take control' },
      { id: 'falling_below_zero', label: 'Bears Power falling below zero', signal: 'PUT', description: 'Strengthening bearish pressure' },
    ]
  },

  // ZigZag
  ZIGZAG: {
    name: 'ZigZag',
    category: 'pattern',
    icon: '⚡',
    description: 'Filters minor price movements - PO native',
    parameters: {
      depth: { label: 'Depth', type: 'number', default: 12, min: 3, max: 50 },
      deviation: { label: 'Deviation %', type: 'number', default: 5, min: 1, max: 20 },
      backstep: { label: 'Backstep', type: 'number', default: 3, min: 1, max: 10 }
    },
    conditions: [
      { id: 'new_swing_high', label: 'New swing high formed', signal: 'PUT', description: 'Potential reversal down' },
      { id: 'new_swing_low', label: 'New swing low formed', signal: 'CALL', description: 'Potential reversal up' },
      { id: 'higher_high', label: 'Higher high (uptrend confirmed)', signal: 'CALL', description: 'Bullish swing structure' },
      { id: 'lower_low', label: 'Lower low (downtrend confirmed)', signal: 'PUT', description: 'Bearish swing structure' },
    ]
  },

  // Heikin Ashi
  HEIKIN_ASHI: {
    name: 'Heikin Ashi',
    category: 'pattern',
    icon: '🕯️',
    description: 'Smoothed candles - PO native chart type',
    parameters: {},
    conditions: [
      { id: 'green_candle', label: 'HA candle turns green', signal: 'CALL', description: 'Bullish trend candle' },
      { id: 'red_candle', label: 'HA candle turns red', signal: 'PUT', description: 'Bearish trend candle' },
      { id: 'three_green', label: '3 consecutive green HA candles', signal: 'CALL', description: 'Strong bullish trend' },
      { id: 'three_red', label: '3 consecutive red HA candles', signal: 'PUT', description: 'Strong bearish trend' },
      { id: 'green_no_lower_wick', label: 'Green HA with no lower wick', signal: 'CALL', description: 'Very strong bullish momentum' },
      { id: 'red_no_upper_wick', label: 'Red HA with no upper wick', signal: 'PUT', description: 'Very strong bearish momentum' },
    ]
  },
};

// Timeframe options
const timeframes = [
  { value: '5s', label: '5 Seconds' },
  { value: '15s', label: '15 Seconds' },
  { value: '30s', label: '30 Seconds' },
  { value: '1m', label: '1 Minute' },
  { value: '2m', label: '2 Minutes' },
  { value: '3m', label: '3 Minutes' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '30m', label: '30 Minutes' },
  { value: '1h', label: '1 Hour' }
];

// Asset options (abbreviated - full list from before)
const assets = [
  // Forex Major
  { value: 'EURUSD', label: 'EUR/USD', category: 'Forex Major', market: 'regular' },
  { value: 'GBPUSD', label: 'GBP/USD', category: 'Forex Major', market: 'regular' },
  { value: 'USDJPY', label: 'USD/JPY', category: 'Forex Major', market: 'regular' },
  { value: 'AUDUSD', label: 'AUD/USD', category: 'Forex Major', market: 'regular' },
  { value: 'USDCHF', label: 'USD/CHF', category: 'Forex Major', market: 'regular' },
  { value: 'USDCAD', label: 'USD/CAD', category: 'Forex Major', market: 'regular' },
  { value: 'NZDUSD', label: 'NZD/USD', category: 'Forex Major', market: 'regular' },
  // Forex Minor
  { value: 'EURGBP', label: 'EUR/GBP', category: 'Forex Minor', market: 'regular' },
  { value: 'EURJPY', label: 'EUR/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'GBPJPY', label: 'GBP/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'AUDJPY', label: 'AUD/JPY', category: 'Forex Minor', market: 'regular' },
  { value: 'CADJPY', label: 'CAD/JPY', category: 'Forex Minor', market: 'regular' },
  // Crypto
  { value: 'BTCUSD', label: 'BTC/USD', category: 'Crypto', market: 'regular' },
  { value: 'ETHUSD', label: 'ETH/USD', category: 'Crypto', market: 'regular' },
  { value: 'LTCUSD', label: 'LTC/USD', category: 'Crypto', market: 'regular' },
  { value: 'SOLUSD', label: 'SOL/USD', category: 'Crypto', market: 'regular' },
  { value: 'DOGEUSD', label: 'DOGE/USD', category: 'Crypto', market: 'regular' },
  // Commodities
  { value: 'XAUUSD', label: 'XAU/USD - Gold', category: 'Commodities', market: 'regular' },
  { value: 'XAGUSD', label: 'XAG/USD - Silver', category: 'Commodities', market: 'regular' },
  // Indices
  { value: 'US100', label: 'NASDAQ 100', category: 'Indices', market: 'regular' },
  { value: 'US30', label: 'Dow Jones', category: 'Indices', market: 'regular' },
  { value: 'SPX500', label: 'S&P 500', category: 'Indices', market: 'regular' },
  // OTC
  { value: 'EURUSD_OTC', label: '🟢 EUR/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'GBPUSD_OTC', label: '🟢 GBP/USD OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'USDJPY_OTC', label: '🟢 USD/JPY OTC', category: 'OTC Forex', market: 'otc' },
  { value: 'BTCUSD_OTC', label: '🟢 BTC/USD OTC', category: 'OTC Crypto', market: 'otc' },
  { value: 'XAUUSD_OTC', label: '🟢 Gold OTC', category: 'OTC Commodities', market: 'otc' },
];

// =====================================================
// CONDITION CARD COMPONENT
// =====================================================
const ConditionCard = ({ condition, onRemove, onUpdate, index }) => {
  const template = INDICATOR_TEMPLATES[condition.indicator];
  const selectedCondition = template?.conditions.find(c => c.id === condition.conditionType);
  
  // Get the effective signal direction (considering reversal)
  const isReversed = condition.reversal === true;
  const effectiveSignal = selectedCondition?.signal ? 
    (isReversed ? (selectedCondition.signal === 'CALL' ? 'PUT' : selectedCondition.signal === 'PUT' ? 'CALL' : selectedCondition.signal) : selectedCondition.signal) 
    : null;

  return (
    <div className={`p-4 rounded-lg border-2 ${
      effectiveSignal === 'CALL' ? 'border-green-500/30 bg-green-500/5' :
      effectiveSignal === 'PUT' ? 'border-red-500/30 bg-red-500/5' :
      'border-slate-600/30 bg-slate-800/30'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{template?.icon || '📊'}</span>
          <span className="font-medium text-white">{template?.name || condition.indicator}</span>
          {selectedCondition && (
            <Badge className={
              effectiveSignal === 'CALL' ? 'bg-green-500/20 text-green-400' :
              effectiveSignal === 'PUT' ? 'bg-red-500/20 text-red-400' :
              'bg-slate-500/20 text-slate-400'
            }>
              {isReversed && <span className="mr-1">🔄</span>}
              {effectiveSignal}
              {isReversed && <span className="ml-1 text-xs">(reversed)</span>}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Reversal Toggle */}
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-700/50 border border-slate-600">
            <span className="text-xs text-slate-400">Reverse</span>
            <Switch
              checked={isReversed}
              onCheckedChange={(checked) => onUpdate({ ...condition, reversal: checked })}
              className="data-[state=checked]:bg-purple-500"
            />
          </div>
          <Button variant="ghost" size="sm" onClick={onRemove} className="text-red-400 hover:bg-red-500/20">
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Indicator Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <Label className="text-xs text-slate-400">Indicator</Label>
          <Select value={condition.indicator} onValueChange={(v) => onUpdate({ ...condition, indicator: v, conditionType: '' })}>
            <SelectTrigger className="bg-slate-700/50 border-slate-600">
              <SelectValue placeholder="Select indicator..." />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-600 max-h-80">
              {Object.entries(INDICATOR_TEMPLATES).map(([key, ind]) => (
                <SelectItem key={key} value={key}>
                  <span className="flex items-center gap-2">
                    <span>{ind.icon}</span>
                    {ind.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Condition Selection */}
        {template && (
          <div>
            <Label className="text-xs text-slate-400">Condition</Label>
            <Select value={condition.conditionType} onValueChange={(v) => onUpdate({ ...condition, conditionType: v })}>
              <SelectTrigger className="bg-slate-700/50 border-slate-600">
                <SelectValue placeholder="Select condition..." />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600 max-h-80">
                {template.conditions.map((cond) => (
                  <SelectItem key={cond.id} value={cond.id}>
                    <span className="flex items-center gap-2">
                      {cond.signal === 'CALL' && <ArrowUp className="w-3 h-3 text-green-400" />}
                      {cond.signal === 'PUT' && <ArrowDown className="w-3 h-3 text-red-400" />}
                      {cond.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* Parameters */}
      {template && Object.keys(template.parameters).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          {Object.entries(template.parameters).map(([key, param]) => (
            <div key={key}>
              <Label className="text-xs text-slate-500">{param.label}</Label>
              <Input
                type="number"
                value={condition.parameters?.[key] ?? param.default}
                onChange={(e) => onUpdate({
                  ...condition,
                  parameters: { ...condition.parameters, [key]: parseFloat(e.target.value) || param.default }
                })}
                min={param.min}
                max={param.max}
                step={param.step || 1}
                className="h-8 bg-slate-700/50 border-slate-600 text-sm"
              />
            </div>
          ))}
        </div>
      )}

      {/* Description */}
      {selectedCondition && (
        <div className="text-xs text-slate-400 italic">
          💡 {selectedCondition.description}
          {isReversed && (
            <span className="ml-2 text-purple-400">
              🔄 Signal will be reversed ({selectedCondition.signal} → {effectiveSignal})
            </span>
          )}
        </div>
      )}
    </div>
  );
};

// =====================================================
// MAIN STRATEGY BUILDER COMPONENT
// =====================================================
const StrategyBuilder = () => {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('quick-select');
  
  // Quick Strategy Selection state
  const [availableStrategies, setAvailableStrategies] = useState({});
  const [selectedStrategies, setSelectedStrategies] = useState({});
  const [loadingStrategies, setLoadingStrategies] = useState(true);

  // Strategy form state
  const [strategyForm, setStrategyForm] = useState({
    name: 'New Strategy',
    description: '',
    conditions: [], // Simplified condition list
    timeframes: ['1m'],
    assets: ['EURUSD'],
    min_confidence: 75,
    max_signals_per_hour: 10,
    cooldown_seconds: 60,
    is_active: false
  });

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      setIsLoading(true);
      const response = await axios.get(`${API_URL}/api/custom-strategies`);
      setStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('Error fetching strategies:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const addCondition = () => {
    setStrategyForm(prev => ({
      ...prev,
      conditions: [...prev.conditions, {
        id: `cond_${Date.now()}`,
        indicator: 'RSI',
        conditionType: 'crosses_above_oversold',
        parameters: {},
        reversal: false  // Default: no reversal
      }]
    }));
  };

  const updateCondition = (index, updated) => {
    setStrategyForm(prev => {
      const newConditions = [...prev.conditions];
      newConditions[index] = updated;
      return { ...prev, conditions: newConditions };
    });
  };

  const removeCondition = (index) => {
    setStrategyForm(prev => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index)
    }));
  };

  const saveStrategy = async () => {
    try {
      setIsSaving(true);
      
      // Convert our simplified format to the backend format
      // Consider reversal: if reversed, swap CALL/PUT assignment
      const callConditions = strategyForm.conditions
        .filter(c => {
          const template = INDICATOR_TEMPLATES[c.indicator];
          const cond = template?.conditions.find(x => x.id === c.conditionType);
          const originalSignal = cond?.signal;
          // If reversed, CALL becomes PUT signal condition, so we want original PUT here
          // If not reversed, we want original CALL
          return c.reversal ? originalSignal === 'PUT' : originalSignal === 'CALL';
        })
        .map(c => ({
          id: c.id,
          conditions: [{
            id: `${c.id}_inner`,
            indicator: c.indicator,
            parameters: c.parameters || {},
            conditionType: c.conditionType,
            reversal: c.reversal || false  // Include reversal flag
          }],
          logical_operator: 'AND'
        }));

      const putConditions = strategyForm.conditions
        .filter(c => {
          const template = INDICATOR_TEMPLATES[c.indicator];
          const cond = template?.conditions.find(x => x.id === c.conditionType);
          const originalSignal = cond?.signal;
          // If reversed, PUT becomes CALL signal condition, so we want original CALL here
          // If not reversed, we want original PUT
          return c.reversal ? originalSignal === 'CALL' : originalSignal === 'PUT';
        })
        .map(c => ({
          id: c.id,
          conditions: [{
            id: `${c.id}_inner`,
            indicator: c.indicator,
            parameters: c.parameters || {},
            conditionType: c.conditionType,
            reversal: c.reversal || false  // Include reversal flag
          }],
          logical_operator: 'AND'
        }));

      const payload = {
        name: strategyForm.name,
        description: strategyForm.description,
        call_conditions: callConditions,
        put_conditions: putConditions,
        timeframes: strategyForm.timeframes,
        assets: strategyForm.assets,
        min_confidence: strategyForm.min_confidence,
        max_signals_per_hour: strategyForm.max_signals_per_hour,
        cooldown_seconds: strategyForm.cooldown_seconds,
        is_active: strategyForm.is_active
      };

      if (selectedStrategy) {
        await axios.put(`${API_URL}/api/custom-strategies/${selectedStrategy.id}`, payload);
        toast.success('Strategy updated!');
      } else {
        await axios.post(`${API_URL}/api/custom-strategies`, payload);
        toast.success('Strategy created!');
      }
      
      fetchStrategies();
      resetForm();
    } catch (error) {
      console.error('Error saving strategy:', error);
      toast.error('Failed to save strategy');
    } finally {
      setIsSaving(false);
    }
  };

  const resetForm = () => {
    setSelectedStrategy(null);
    setStrategyForm({
      name: 'New Strategy',
      description: '',
      conditions: [],
      timeframes: ['1m'],
      assets: ['EURUSD'],
      min_confidence: 75,
      max_signals_per_hour: 10,
      cooldown_seconds: 60,
      is_active: false
    });
  };

  const toggleTimeframe = (tf) => {
    setStrategyForm(prev => {
      const current = prev.timeframes || [];
      if (current.includes(tf)) {
        return { ...prev, timeframes: current.filter(t => t !== tf) };
      } else {
        return { ...prev, timeframes: [...current, tf] };
      }
    });
  };

  // =====================================================
  // QUICK STRATEGY SELECTION FUNCTIONS
  // =====================================================
  
  const fetchAvailableStrategies = useCallback(async () => {
    try {
      setLoadingStrategies(true);
      const response = await axios.get(`${API_URL}/api/strategies/available`);
      if (response.data.success) {
        setAvailableStrategies(response.data.strategies);
      }
    } catch (error) {
      console.error('Failed to fetch available strategies:', error);
      toast.error('Failed to load strategies');
    } finally {
      setLoadingStrategies(false);
    }
  }, []);

  const fetchSelectedStrategies = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/strategies/selected`);
      if (response.data.success) {
        setSelectedStrategies(response.data.selections || {});
      }
    } catch (error) {
      console.error('Failed to fetch selected strategies:', error);
    }
  }, []);

  const selectStrategyForTimeframe = async (timeframe, strategyId) => {
    try {
      await axios.post(`${API_URL}/api/strategies/select`, {
        timeframe,
        strategy_id: strategyId
      });
      
      setSelectedStrategies(prev => ({
        ...prev,
        [timeframe]: strategyId
      }));
      
      const strategyName = availableStrategies[timeframe]?.find(s => s.id === strategyId)?.name || strategyId;
      toast.success(`${timeframe}: ${strategyName} selected`);
    } catch (error) {
      toast.error('Failed to select strategy');
    }
  };

  useEffect(() => {
    fetchAvailableStrategies();
    fetchSelectedStrategies();
  }, [fetchAvailableStrategies, fetchSelectedStrategies]);

  // =====================================================
  // QUICK STRATEGY SELECTION COMPONENT
  // =====================================================
  
  const QuickStrategySelector = () => {
    const timeframeOrder = ['5s', '15s', '30s', '1m', '2m', '3m', '5m'];
    
    if (loadingStrategies) {
      return (
        <div className="flex items-center justify-center p-12">
          <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      );
    }
    
    return (
      <div className="space-y-6">
        <Alert className="bg-purple-900/30 border-purple-600">
          <Zap className="w-4 h-4" />
          <AlertTitle>Quick Strategy Selection</AlertTitle>
          <AlertDescription>
            Select a pre-built trading strategy for each timeframe. Strategies marked with ⭐ are from your uploaded PDFs.
          </AlertDescription>
        </Alert>
        
        <div className="grid gap-4">
          {timeframeOrder.map(tf => {
            const strategies = availableStrategies[tf] || [];
            const currentSelection = selectedStrategies[tf] || 'default';
            
            return (
              <Card key={tf} className="bg-slate-800/50 border-slate-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-white text-lg flex items-center gap-2">
                      <Badge variant="outline" className="border-purple-500 text-purple-400">
                        {tf}
                      </Badge>
                      Timeframe Strategy
                    </CardTitle>
                    <Badge className={currentSelection !== 'default' ? 'bg-green-600' : 'bg-slate-600'}>
                      {currentSelection !== 'default' ? '✓ Custom' : 'Default'}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-2">
                    {strategies.map(strategy => (
                      <div
                        key={strategy.id}
                        onClick={() => selectStrategyForTimeframe(tf, strategy.id)}
                        className={`p-3 rounded-lg cursor-pointer transition-all ${
                          currentSelection === strategy.id
                            ? 'bg-purple-600/30 border-2 border-purple-500'
                            : 'bg-slate-700/50 border border-slate-600 hover:border-purple-500/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium text-white flex items-center gap-2">
                              {strategy.name}
                              {strategy.win_rate && (
                                <Badge className="bg-green-600 text-xs">{strategy.win_rate}</Badge>
                              )}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">{strategy.description}</div>
                          </div>
                          {currentSelection === strategy.id && (
                            <CheckCircle className="w-5 h-5 text-green-400" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    );
  };

  const toggleAsset = (asset) => {
    setStrategyForm(prev => {
      const current = prev.assets || [];
      if (current.includes(asset)) {
        return { ...prev, assets: current.filter(a => a !== asset) };
      } else {
        return { ...prev, assets: [...current, asset] };
      }
    });
  };

  const deleteStrategy = async (strategyId) => {
    if (!window.confirm('Delete this strategy?')) return;
    try {
      await axios.delete(`${API_URL}/api/custom-strategies/${strategyId}`);
      toast.success('Strategy deleted');
      fetchStrategies();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  // Quick Templates
  const applyTemplate = (templateName) => {
    const templates = {
      'EMA Crossover': {
        name: 'EMA 7/21 Crossover',
        description: 'Classic EMA crossover strategy',
        conditions: [
          { id: 'c1', indicator: 'EMA_CROSSOVER', conditionType: 'golden_cross', parameters: { fast_period: 7, slow_period: 21 } },
          { id: 'c2', indicator: 'EMA_CROSSOVER', conditionType: 'death_cross', parameters: { fast_period: 7, slow_period: 21 } }
        ]
      },
      'RSI Reversal': {
        name: 'RSI Oversold/Overbought',
        description: 'Buy oversold, sell overbought',
        conditions: [
          { id: 'c1', indicator: 'RSI', conditionType: 'crosses_above_oversold', parameters: { period: 14, oversold: 30, overbought: 70 } },
          { id: 'c2', indicator: 'RSI', conditionType: 'crosses_below_overbought', parameters: { period: 14, oversold: 30, overbought: 70 } }
        ]
      },
      'Bollinger Breakout': {
        name: 'Bollinger Bands Breakout',
        description: 'Trade breakouts from BB',
        conditions: [
          { id: 'c1', indicator: 'BOLLINGER_BANDS', conditionType: 'price_breaks_above_upper', parameters: { period: 20, std_dev: 2 } },
          { id: 'c2', indicator: 'BOLLINGER_BANDS', conditionType: 'price_breaks_below_lower', parameters: { period: 20, std_dev: 2 } }
        ]
      },
      'MACD Signal': {
        name: 'MACD Crossover',
        description: 'MACD line crosses signal line',
        conditions: [
          { id: 'c1', indicator: 'MACD', conditionType: 'macd_crosses_above_signal', parameters: { fast_period: 12, slow_period: 26, signal_period: 9 } },
          { id: 'c2', indicator: 'MACD', conditionType: 'macd_crosses_below_signal', parameters: { fast_period: 12, slow_period: 26, signal_period: 9 } }
        ]
      },
      'SuperTrend': {
        name: 'SuperTrend Trend Follow',
        description: 'Follow SuperTrend signals',
        conditions: [
          { id: 'c1', indicator: 'SUPERTREND', conditionType: 'turns_bullish', parameters: { period: 10, multiplier: 3 } },
          { id: 'c2', indicator: 'SUPERTREND', conditionType: 'turns_bearish', parameters: { period: 10, multiplier: 3 } }
        ]
      },
      'Momentum Crossover': {
        name: 'Momentum Zero-Line Cross',
        description: 'Trade momentum zero-line crossovers',
        conditions: [
          { id: 'c1', indicator: 'MOMENTUM', conditionType: 'crosses_above_zero', parameters: { period: 14, smoothing: 3, threshold: 0, signal_type: 1 } },
          { id: 'c2', indicator: 'MOMENTUM', conditionType: 'crosses_below_zero', parameters: { period: 14, smoothing: 3, threshold: 0, signal_type: 1 } }
        ]
      },
      'Momentum + RSI': {
        name: 'Momentum with RSI Filter',
        description: 'Momentum signals filtered by RSI',
        conditions: [
          { id: 'c1', indicator: 'MOMENTUM', conditionType: 'strong_positive', parameters: { period: 10, smoothing: 3, threshold: 5, signal_type: 2 } },
          { id: 'c2', indicator: 'RSI', conditionType: 'above_50', parameters: { period: 14, overbought: 70, oversold: 30 } },
          { id: 'c3', indicator: 'MOMENTUM', conditionType: 'strong_negative', parameters: { period: 10, smoothing: 3, threshold: -5, signal_type: 2 } },
          { id: 'c4', indicator: 'RSI', conditionType: 'below_50', parameters: { period: 14, overbought: 70, oversold: 30 } }
        ]
      },
      'Keltner-MACD 5s': {
        name: 'Keltner-MACD 5-Second Strategy',
        description: 'Professional 5s scalping: Keltner Channel (EMA20, ATR60, x4) + MACD (13,24,11)',
        conditions: [
          { id: 'c1', indicator: 'KELTNER_CHANNEL', conditionType: 'price_crosses_above_middle', parameters: { ema_period: 20, atr_period: 60, multiplier: 4 } },
          { id: 'c2', indicator: 'MACD', conditionType: 'bullish_crossover', parameters: { fast: 13, slow: 24, signal: 11 } },
          { id: 'c3', indicator: 'KELTNER_CHANNEL', conditionType: 'price_crosses_below_middle', parameters: { ema_period: 20, atr_period: 60, multiplier: 4 } },
          { id: 'c4', indicator: 'MACD', conditionType: 'bearish_crossover', parameters: { fast: 13, slow: 24, signal: 11 } }
        ]
      },
      'IQ-720 Ensemble': {
        name: 'IQ-720 Advanced Ensemble',
        description: 'AI-powered: Market Regime + Session-aware + 8 weighted strategies + Kelly sizing + 60+ features',
        conditions: [
          { id: 'c1', indicator: 'RSI', conditionType: 'crosses_above_oversold', parameters: { period: 14, oversold: 30, overbought: 70 } },
          { id: 'c2', indicator: 'MACD', conditionType: 'macd_crosses_above_signal', parameters: { fast_period: 12, slow_period: 26, signal_period: 9 } },
          { id: 'c3', indicator: 'BOLLINGER_BANDS', conditionType: 'price_below_lower', parameters: { period: 20, std_dev: 2 } },
          { id: 'c4', indicator: 'EMA_CROSSOVER', conditionType: 'golden_cross', parameters: { fast_period: 12, slow_period: 26 } },
          { id: 'c5', indicator: 'STOCHASTIC', conditionType: 'k_crosses_above_d_oversold', parameters: { k_period: 14, d_period: 3, overbought: 80, oversold: 20 } },
          { id: 'c6', indicator: 'KELTNER_CHANNEL', conditionType: 'price_crosses_above_middle', parameters: { ema_period: 20, atr_period: 20, multiplier: 2 } }
        ]
      }
    };

    if (templates[templateName]) {
      setStrategyForm(prev => ({
        ...prev,
        ...templates[templateName]
      }));
      toast.success(`Applied "${templateName}" template`);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Strategy Builder</h2>
          <p className="text-slate-400">Create custom trading strategies with TradingView-style conditions</p>
        </div>
        <Button onClick={resetForm} variant="outline" className="border-slate-600">
          <Plus className="w-4 h-4 mr-2" />
          New Strategy
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-800/50 grid grid-cols-4 w-full max-w-2xl">
          <TabsTrigger value="quick-select">⚡ Quick Select</TabsTrigger>
          <TabsTrigger value="builder">🛠️ Builder</TabsTrigger>
          <TabsTrigger value="templates">📋 Templates</TabsTrigger>
          <TabsTrigger value="strategies">💾 Saved ({strategies.length})</TabsTrigger>
        </TabsList>

        {/* Quick Strategy Selection Tab */}
        <TabsContent value="quick-select" className="mt-6">
          <QuickStrategySelector />
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Quick Start Templates</CardTitle>
              <CardDescription>Click a template to instantly apply it</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {['EMA Crossover', 'RSI Reversal', 'Bollinger Breakout', 'MACD Signal', 'SuperTrend', 'Momentum Crossover', 'Momentum + RSI', 'Keltner-MACD 5s', 'IQ-720 Ensemble'].map(name => (
                  <Card 
                    key={name} 
                    className="cursor-pointer hover:border-purple-500/50 transition-colors border-slate-600"
                    onClick={() => { applyTemplate(name); setActiveTab('builder'); }}
                  >
                    <CardContent className="p-4">
                      <div className="font-medium text-white">{name}</div>
                      <div className="text-sm text-slate-400 mt-1">Click to use this strategy</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Builder Tab */}
        <TabsContent value="builder" className="space-y-6">
          {/* Strategy Name */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Strategy Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>Strategy Name</Label>
                  <Input
                    value={strategyForm.name}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, name: e.target.value }))}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
                <div>
                  <Label>Description</Label>
                  <Input
                    value={strategyForm.description}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, description: e.target.value }))}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Conditions */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                📊 Trading Conditions
                <Badge variant="outline">{strategyForm.conditions.length} conditions</Badge>
              </CardTitle>
              <CardDescription>
                Add indicators and select when to trigger CALL (buy) or PUT (sell) signals
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {strategyForm.conditions.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p>No conditions yet. Add an indicator to get started!</p>
                </div>
              ) : (
                strategyForm.conditions.map((condition, index) => (
                  <ConditionCard
                    key={condition.id}
                    condition={condition}
                    index={index}
                    onUpdate={(updated) => updateCondition(index, updated)}
                    onRemove={() => removeCondition(index)}
                  />
                ))
              )}

              <Button onClick={addCondition} variant="outline" className="w-full border-dashed">
                <Plus className="w-4 h-4 mr-2" />
                Add Condition
              </Button>

              {/* Summary */}
              {strategyForm.conditions.length > 0 && (
                <div className="p-4 bg-slate-800/50 rounded-lg">
                  <div className="text-sm font-medium text-white mb-2">Signal Summary:</div>
                  <div className="flex gap-4 flex-wrap">
                    <div className="flex items-center gap-2">
                      <ArrowUp className="w-4 h-4 text-green-400" />
                      <span className="text-green-400">
                        {strategyForm.conditions.filter(c => {
                          const t = INDICATOR_TEMPLATES[c.indicator];
                          const originalSignal = t?.conditions.find(x => x.id === c.conditionType)?.signal;
                          // Account for reversal
                          return c.reversal ? originalSignal === 'PUT' : originalSignal === 'CALL';
                        }).length} CALL conditions
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <ArrowDown className="w-4 h-4 text-red-400" />
                      <span className="text-red-400">
                        {strategyForm.conditions.filter(c => {
                          const t = INDICATOR_TEMPLATES[c.indicator];
                          const originalSignal = t?.conditions.find(x => x.id === c.conditionType)?.signal;
                          // Account for reversal
                          return c.reversal ? originalSignal === 'CALL' : originalSignal === 'PUT';
                        }).length} PUT conditions
                      </span>
                    </div>
                    {/* Show reversed count */}
                    {strategyForm.conditions.some(c => c.reversal) && (
                      <div className="flex items-center gap-2">
                        <span className="text-purple-400">
                          🔄 {strategyForm.conditions.filter(c => c.reversal).length} reversed
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Trading Parameters */}
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <CardTitle className="text-white">Trading Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Timeframes */}
              <div>
                <Label className="mb-2 block">Timeframes</Label>
                <div className="flex flex-wrap gap-2">
                  {timeframes.map(tf => (
                    <Button
                      key={tf.value}
                      variant={strategyForm.timeframes.includes(tf.value) ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleTimeframe(tf.value)}
                      className={strategyForm.timeframes.includes(tf.value) 
                        ? 'bg-purple-500/20 text-purple-400 border-purple-500/50'
                        : 'border-slate-600'}
                    >
                      {tf.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Assets — Iter 83: reusable AssetPicker with market bulk-select */}
              <div>
                <AssetPicker
                  value={strategyForm.assets || []}
                  onChange={(next) => setStrategyForm(prev => ({ ...prev, assets: next }))}
                  testIdPrefix="strategy-builder-asset-picker"
                  title="Assets & Markets"
                  description="Pick individual symbols, entire markets (Regular / OTC), or specific asset classes."
                  maxHeight="max-h-96"
                />
              </div>

              {/* Risk Settings */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label>Min Confidence ({strategyForm.min_confidence}%)</Label>
                  <Slider
                    value={[strategyForm.min_confidence]}
                    onValueChange={(v) => setStrategyForm(prev => ({ ...prev, min_confidence: v[0] }))}
                    min={50}
                    max={99}
                    className="mt-2"
                  />
                </div>
                <div>
                  <Label>Max Signals/Hour</Label>
                  <Input
                    type="number"
                    value={strategyForm.max_signals_per_hour}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, max_signals_per_hour: parseInt(e.target.value) || 10 }))}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
                <div>
                  <Label>Cooldown (seconds)</Label>
                  <Input
                    type="number"
                    value={strategyForm.cooldown_seconds}
                    onChange={(e) => setStrategyForm(prev => ({ ...prev, cooldown_seconds: parseInt(e.target.value) || 60 }))}
                    className="bg-slate-800/50 border-slate-600"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex gap-3">
            <Button
              onClick={saveStrategy}
              disabled={isSaving || strategyForm.conditions.length === 0}
              className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
            >
              <Save className="w-4 h-4 mr-2" />
              {isSaving ? 'Saving...' : 'Save Strategy'}
            </Button>
          </div>
        </TabsContent>

        {/* Strategies List Tab */}
        <TabsContent value="strategies">
          <Card className="glass-dark border-slate-700/50">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-white">My Strategies</CardTitle>
                  <CardDescription>
                    <span className="block">
                      <span className="text-cyan-400 font-semibold">Publish</span> to make a strategy selectable in the timeframe strategy picker (React + Tampermonkey).
                    </span>
                    <span className="block">
                      <span className="text-emerald-400 font-semibold">On/Off</span> controls whether it is allowed to fire signals.
                    </span>
                  </CardDescription>
                </div>
                <Button
                  data-testid="deactivate-all-strategies"
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    try {
                      // Deactivate all strategies
                      await Promise.all(
                        strategies
                          .filter(s => s.is_active)
                          .map(s => axios.post(`${API_URL}/api/custom-strategies/${s.id}/toggle?is_active=false`))
                      );
                      fetchStrategies();
                      toast.success('All strategies deactivated');
                    } catch (error) {
                      toast.error('Failed to deactivate');
                    }
                  }}
                  className="border-orange-500/50 text-orange-400 hover:bg-orange-500/20"
                >
                  Deactivate All
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="text-center py-8 text-slate-400">Loading...</div>
              ) : strategies.length === 0 ? (
                <div className="text-center py-8 text-slate-400">No strategies yet</div>
              ) : (
                <div className="space-y-3">
                  {strategies.map(strategy => {
                    const isActive = strategy.is_active === true;
                    const isPublished = strategy.is_published === true;
                    return (
                      <div
                        key={strategy.id}
                        data-testid={`saved-strategy-${strategy.id}`}
                        className={`p-4 rounded-lg border transition-all ${
                          isActive
                            ? 'bg-emerald-900/20 border-emerald-500/50'
                            : 'bg-slate-800/50 border-slate-600/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-white truncate">{strategy.name}</span>
                              {isActive && (
                                <Badge data-testid={`strategy-active-badge-${strategy.id}`} className="bg-emerald-600 text-xs shrink-0">Active</Badge>
                              )}
                              {isPublished ? (
                                <Badge
                                  data-testid={`strategy-published-badge-${strategy.id}`}
                                  className="bg-cyan-600 text-xs shrink-0"
                                  title="Selectable in the timeframe strategy picker (React + TM)"
                                >
                                  Published
                                </Badge>
                              ) : (
                                <Badge
                                  data-testid={`strategy-draft-badge-${strategy.id}`}
                                  variant="outline"
                                  className="border-amber-500/50 text-amber-400 text-xs shrink-0"
                                  title="Draft — hidden from the timeframe strategy picker"
                                >
                                  Draft
                                </Badge>
                              )}
                            </div>
                            <div className="text-sm text-slate-400 mt-1">{strategy.description}</div>
                            <div className="flex gap-2 mt-2 flex-wrap">
                              {strategy.timeframes?.map(tf => (
                                <Badge key={tf} variant="outline" className="text-xs">{tf}</Badge>
                              ))}
                              {strategy.assets?.slice(0, 3).map(a => (
                                <Badge key={a} variant="outline" className="text-xs border-blue-500/50 text-blue-400">{a}</Badge>
                              ))}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 ml-4 shrink-0">
                            <Button
                              data-testid={`strategy-publish-toggle-${strategy.id}`}
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                try {
                                  const res = await axios.post(`${API_URL}/api/custom-strategies/${strategy.id}/toggle-publish`);
                                  const newState = res.data?.strategy?.is_published;
                                  fetchStrategies();
                                  toast.success(
                                    newState
                                      ? `"${strategy.name}" published — now selectable in the timeframe picker`
                                      : `"${strategy.name}" unpublished — hidden from the timeframe picker`
                                  );
                                } catch (error) {
                                  toast.error('Failed to toggle publish state');
                                }
                              }}
                              className={isPublished
                                ? 'border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/20'
                                : 'border-amber-500/50 text-amber-400 hover:bg-amber-500/20'
                              }
                              title={isPublished ? 'Click to unpublish (return to Draft)' : 'Click to publish (make selectable)'}
                            >
                              {isPublished ? 'Unpublish' : 'Publish'}
                            </Button>
                            <Button
                              data-testid={`strategy-toggle-${strategy.id}`}
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                try {
                                  const newState = !isActive;
                                  await axios.post(`${API_URL}/api/custom-strategies/${strategy.id}/toggle?is_active=${newState}`);
                                  // Refresh strategies list
                                  fetchStrategies();
                                  toast.success(newState ? `"${strategy.name}" activated` : `"${strategy.name}" deactivated`);
                                } catch (error) {
                                  toast.error('Failed to toggle strategy');
                                }
                              }}
                              className={isActive
                                ? 'border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/20'
                                : 'border-slate-500/50 text-slate-400 hover:bg-slate-500/20'
                              }
                            >
                              {isActive ? <CheckCircle className="w-4 h-4" /> : <Circle className="w-4 h-4" />}
                              <span className="ml-1">{isActive ? 'On' : 'Off'}</span>
                            </Button>
                            <Button
                              data-testid={`strategy-edit-${strategy.id}`}
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedStrategy(strategy);
                                setStrategyForm({
                                  name: strategy.name || 'New Strategy',
                                  description: strategy.description || '',
                                  conditions: (strategy.call_conditions || []).map(c => ({
                                    id: c.conditions?.[0]?.id || `c${Date.now()}`,
                                    indicator: c.conditions?.[0]?.indicator || 'RSI',
                                    conditionType: c.conditions?.[0]?.conditionType || 'crosses_above_oversold',
                                    parameters: c.conditions?.[0]?.parameters || {},
                                    reversal: c.conditions?.[0]?.reversal || false
                                  })),
                                  timeframes: strategy.timeframes || ['1m'],
                                  assets: strategy.assets || ['EURUSD'],
                                  min_confidence: strategy.min_confidence || 75,
                                  max_signals_per_hour: strategy.max_signals_per_hour || 10,
                                  cooldown_seconds: strategy.cooldown_seconds || 60,
                                  is_active: strategy.is_active || false
                                });
                                setActiveTab('builder');
                                toast.info(`Editing "${strategy.name}"`);
                              }}
                              className="border-blue-500/50 text-blue-400"
                            >
                              <Settings className="w-4 h-4" />
                            </Button>
                            <Button
                              data-testid={`strategy-delete-${strategy.id}`}
                              variant="outline"
                              size="sm"
                              onClick={() => deleteStrategy(strategy.id)}
                              className="border-red-500/50 text-red-400"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default StrategyBuilder;
