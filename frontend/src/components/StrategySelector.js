/**
 * Comprehensive Strategy Selection Tool
 * Includes timeframe selection, strategy selection, bot controls, and setup guides
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Settings, TrendingUp, X, Check, Play, Square, Zap, Clock, User, Star } from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const StrategySelector = ({ onStrategySelect, onAutoGenerateToggle }) => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1m');
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [selectedAssets, setSelectedAssets] = useState(['EURUSD_OTC']);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [currentStrategyConfig, setCurrentStrategyConfig] = useState(null);
  
  // Custom/Built strategies from Strategy Builder
  const [customStrategies, setCustomStrategies] = useState([]);
  const [isLoadingCustom, setIsLoadingCustom] = useState(false);
  
  // Bot control states
  const [autoGenerateEnabled, setAutoGenerateEnabled] = useState(false);
  const [autoGenerateInterval, setAutoGenerateInterval] = useState('1m');
  const [botActive, setBotActive] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Fetch custom strategies on mount
  useEffect(() => {
    fetchCustomStrategies();
  }, []);
  
  // Fetch custom strategies from backend
  const fetchCustomStrategies = async () => {
    try {
      setIsLoadingCustom(true);
      const response = await axios.get(`${API_URL}/api/custom-strategies`);
      if (response.data.success) {
        setCustomStrategies(response.data.strategies || []);
      }
    } catch (error) {
      console.error('Error fetching custom strategies:', error);
    } finally {
      setIsLoadingCustom(false);
    }
  };
  
  // Get custom strategies filtered by selected timeframe
  const getCustomStrategiesForTimeframe = () => {
    return customStrategies.filter(strategy => {
      // Check if strategy's timeframes includes the selected timeframe
      const strategyTimeframes = strategy.timeframes || [];
      return strategyTimeframes.includes(selectedTimeframe);
    });
  };

  // Available timeframes
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

  // Strategy configurations by timeframe
  const strategiesByTimeframe = {
    '5s': [
      { value: 'pocket_option_5s_pro', name: '⚡ 5-Second Pro', accuracy: '62-70%', note: 'DEFAULT | EMA20+RSI + S/R Reversal + AI Patterns | Documented win rates', recommended: true, isDefault: true },
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels | 2:1 R:R', recommended: true },
      { value: 'fast_supertrend_catch', name: '⚡ Fast Supertrend Catch', accuracy: '85%+', note: 'Supertrend ATR100 + 15 EMA Contrarian | S/R Filter', recommended: true },
      { value: 'enhanced_breakout', name: '🚀 Enhanced Breakout Predictor', accuracy: '80%+', note: '⏳ 10s latency | S/R Levels' },
      { value: 'proven_5s', name: '🎯 Proven RSI+Stoch+BB+EMA', accuracy: '80%+', note: '⏳ 10s latency | 4+ confirmations' },
      { value: 'ultra_v2_5s', name: 'Ultra Precision 5s V2', accuracy: '90%+', note: '⏳ 10s latency applied' },
      { value: 'reversal_5s', name: '5s Reversal Strategy', accuracy: '85%+', note: '⏳ 10s latency applied' },
      { value: 'keltner_fractal', name: 'Keltner Channel + Fractal', accuracy: '85%+', note: '⏳ 10s latency applied' },
      { value: '3ema_crossover', name: '3 EMA Crossover', accuracy: '82%+', note: '⏳ 10s latency applied' },
      { value: 'stochastic_divergence', name: 'Stochastic Divergence', accuracy: '83%+', note: '⏳ 10s latency applied' }
    ],
    '15s': [
      { value: 'pocket_option_5s_pro', name: '⚡ 5-Second Pro', accuracy: '62-70%', note: 'EMA20+RSI + S/R + AI Patterns' },
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'fractal_15s', name: '15s Fractal Strategy', accuracy: '85%+' }
    ],
    '30s': [
      { value: 'pocket_option_5s_pro', name: '⚡ 5-Second Pro', accuracy: '62-70%', note: 'EMA20+RSI + S/R + AI Patterns' },
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'supertrend_30s', name: '30s Supertrend Strategy', accuracy: '80%+' }
    ],
    '1m': [
      { value: 'pocket_option_1m_scalping', name: '⚡ 1-Minute Scalping Pro', accuracy: '70%+', note: 'DEFAULT | EMA+BB+RSI+Volume | 10K+ trades tested', recommended: true, isDefault: true },
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Engulfing, Hammer, Morning Star, Inside Bar patterns' },
      { value: 'rsi_bb_volume', name: 'RSI + BB + Volume', accuracy: '70%+' },
      { value: 'stoch_macd_pattern', name: 'Stochastic + MACD + Pattern', accuracy: '75-80%' },
      { value: 'enhanced_rsi_bb_volume', name: 'Enhanced RSI + BB + Volume V2', accuracy: '85-89%', recommended: true },
      { value: 'enhanced_stoch_macd_pattern', name: 'Enhanced Stochastic + MACD + Pattern V2', accuracy: '85-89%', recommended: true },
      { value: 'smart_money_ict', name: 'Smart Money + ICT', accuracy: '80-95%' },
      { value: 'williams_macd', name: 'Williams %R + MACD', accuracy: '80-95%' },
      { value: 'triple_confirmation', name: 'RSI + BB + MACD Triple', accuracy: '73-90%' }
    ],
    '2m': [
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'multi_layer_2m', name: '2m Multi-Layer Strategy', accuracy: '75%+' }
    ],
    '3m': [
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'multi_layer_3m', name: '3m Multi-Layer Strategy', accuracy: '75%+' }
    ],
    '5m': [
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'trend_5m', name: '5m Trend Following', accuracy: '80%+' }
    ],
    '15m': [
      { value: 'candlestick_bible', name: '📕 Candlestick Bible', accuracy: '72%+', note: 'Pattern recognition at key S/R levels' },
      { value: 'swing_15m', name: '15m Swing Trading', accuracy: '80%+' }
    ]
  };

  // Detailed strategy configs for setup guide
  const strategyConfigs = {
    'rsi_bb_volume': {
      name: 'RSI + Bollinger Bands + Volume',
      timeframe: '1 minute',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD (high volatility pairs)',
      expiry: '60 seconds (1 minute)',
      accuracy: '70%+',
      indicators: [
        { name: 'RSI (Relative Strength Index)', settings: 'Period: 14 or 7', purpose: 'Identifies overbought (>70) and oversold (<30) conditions' },
        { name: 'Bollinger Bands', settings: 'Period: 20, Standard Deviation: 2', purpose: 'Shows price volatility and extremes' },
        { name: 'Volume', settings: 'Default volume bars', purpose: 'Confirms momentum with volume spikes (>150% average)' }
      ],
      callSignal: ['RSI drops below 30 (oversold zone)', 'Price touches lower Bollinger Band', 'Volume spike >150% average', 'Price bouncing upward'],
      putSignal: ['RSI rises above 70 (overbought zone)', 'Price touches upper Bollinger Band', 'Volume spike >150% average', 'Price rejected downward'],
      tips: ['Best during London/New York overlap', 'Wait for volume spike confirmation', 'Avoid flat markets', 'Practice on demo first']
    },
    'stoch_macd_pattern': {
      name: 'Stochastic + MACD + Candlestick Patterns',
      timeframe: '1 minute',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD',
      expiry: '60 seconds',
      accuracy: '75-80%',
      indicators: [
        { name: 'Stochastic Oscillator', settings: 'K: 14, D: 3, Smooth: 3', purpose: 'Momentum extremes and reversals' },
        { name: 'MACD', settings: 'Fast: 12, Slow: 26, Signal: 9', purpose: 'Trend direction and momentum' },
        { name: 'Candlestick Patterns', settings: 'Pattern recognition', purpose: 'Price action validation' }
      ],
      callSignal: ['Stochastic < 20 and turning up', 'MACD bullish crossover', 'Bullish pattern (Hammer, Engulfing)', 'Price near support'],
      putSignal: ['Stochastic > 80 and turning down', 'MACD bearish crossover', 'Bearish pattern (Shooting Star)', 'Price near resistance'],
      tips: ['Wait for all 3 confirmations', 'Patterns add 8-10% accuracy', 'Best in trending markets', 'Backtest 50+ trades']
    },
    'enhanced_rsi_bb_volume': {
      name: 'Enhanced RSI + BB + Volume V2 (85-89% Target)',
      timeframe: '1 minute + 5 minute confirmation',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, BTC/USD (high volatility)',
      expiry: '60 seconds',
      accuracy: '85-89% (with strict filtering)',
      indicators: [
        { name: 'RSI', settings: 'Period: 14, Oversold: 25, Overbought: 75', purpose: 'Extreme momentum detection' },
        { name: 'Bollinger Bands', settings: 'Period: 20, Std Dev: 2', purpose: 'Volatility and extremes' },
        { name: 'Volume', settings: '10-period average', purpose: 'Momentum confirmation' },
        { name: 'ADX', settings: 'Period: 14, Minimum: 25', purpose: 'Trend strength filter' },
        { name: '5-Minute Chart', settings: 'Secondary window', purpose: 'Confirm overall trend' }
      ],
      callSignal: ['1m RSI < 25', 'Price at lower BB (<12%)', 'Volume spike >150%', 'ADX > 25', '5m bullish trend', 'Best hours (8am-5pm UTC)'],
      putSignal: ['1m RSI > 75', 'Price at upper BB (>88%)', 'Volume spike >150%', 'ADX > 25', '5m bearish trend', 'Best hours (8am-5pm UTC)'],
      tips: ['STRICT: All conditions must be met (5+)', 'Multi-timeframe critical', 'Only 2-5 signals/day', 'ADX removes 60-70% false signals']
    },
    'enhanced_stoch_macd_pattern': {
      name: 'Enhanced Stochastic + MACD + Pattern V2 (85-89% Target)',
      timeframe: '1 minute + 5 minute confirmation',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD',
      expiry: '60 seconds',
      accuracy: '85-89%',
      indicators: [
        { name: 'Stochastic', settings: 'K: 14, D: 3, Oversold: 15, Overbought: 85', purpose: 'Extreme momentum' },
        { name: 'MACD', settings: 'Fast: 12, Slow: 26, Signal: 9', purpose: 'Trend confirmation' },
        { name: 'Candlestick Patterns', settings: 'High-reliability patterns', purpose: 'Price action' },
        { name: 'ADX', settings: 'Period: 14, Minimum: 30', purpose: 'Strong trend filter' },
        { name: '5-Minute Chart', settings: 'Secondary', purpose: 'Trend confirmation' }
      ],
      callSignal: ['Stochastic < 15 turning up', 'MACD bullish crossover', 'Bullish pattern', 'ADX > 30', '5m bullish', 'Near support/pivot'],
      putSignal: ['Stochastic > 85 turning down', 'MACD bearish crossover', 'Bearish pattern', 'ADX > 30', '5m bearish', 'Near resistance/pivot'],
      tips: ['Need 4+ confirmations', 'Three Black Crows = 84% accuracy', 'Rejection candles +5%', 'Multi-timeframe mandatory']
    },
    'candlestick_bible': {
      name: 'Candlestick Bible Strategy (Based on The Candlestick Trading Bible)',
      timeframe: 'Multi-timeframe (5s to 15m)',
      chartType: 'Japanese Candlesticks (Required)',
      assets: 'All major pairs - EUR/USD, GBP/USD, BTC/USD, etc.',
      expiry: 'Based on timeframe',
      accuracy: '65-72% (pattern dependent)',
      indicators: [
        { name: 'Candlestick Patterns', settings: 'Automated pattern recognition', purpose: 'Primary signal generator' },
        { name: 'Support/Resistance', settings: 'Swing high/low detection', purpose: 'Key level confirmation (+15% accuracy)' },
        { name: 'Trend Analysis', settings: 'Higher highs/lows detection', purpose: 'Trend alignment filter' }
      ],
      callSignal: [
        '📗 Bullish Engulfing at support (68%)',
        '🔨 Hammer (Pin Bar) at downtrend end (65%)',
        '⭐ Morning Star (3-candle reversal) (72%)',
        '🐉 Dragonfly Doji at support (60%)',
        '🔧 Tweezers Bottom (62%)',
        '👶 Bullish Harami at bottom (55%)',
        '📦 Inside Bar Bullish Breakout (65%)'
      ],
      putSignal: [
        '📕 Bearish Engulfing at resistance (68%)',
        '💫 Shooting Star at uptrend end (65%)',
        '🌙 Evening Star (3-candle reversal) (72%)',
        '🪦 Gravestone Doji at resistance (60%)',
        '🔧 Tweezers Top (62%)',
        '👶 Bearish Harami at top (55%)',
        '📦 Inside Bar Bearish Breakout (65%)'
      ],
      tips: [
        '🎯 Trade ONLY at key support/resistance levels for +10-15% accuracy',
        '📊 Minimum 1:2 risk/reward ratio (TP = 2x Stop Loss)',
        '🔄 Trade WITH the trend for highest probability',
        '📕 Morning/Evening Star = Highest accuracy (72%)',
        '⚠️ Counter-trend patterns need key level confirmation',
        '🚫 Avoid choppy markets - no clear higher/lower highs/lows',
        '💡 Pattern at key level + trend alignment = STRONG signal'
      ]
    },
    'pocket_option_1m_scalping': {
      name: 'Pocket Option 1-Minute Scalping Pro (DEFAULT)',
      timeframe: '1 minute (60 seconds)',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD - High volatility pairs',
      expiry: '60 seconds',
      accuracy: '70%+ (10,000+ trades tested)',
      indicators: [
        { name: 'EMA 5/10/21', settings: 'Periods: 5, 10, 21', purpose: 'Entry signal on EMA(5) cross' },
        { name: 'Bollinger Bands', settings: 'Period: 20, StdDev: 2.0', purpose: 'Reversal zones at band touches' },
        { name: 'RSI', settings: 'Period: 7, Levels: 30/70 (40/60 adjusted)', purpose: 'Momentum and overbought/oversold' },
        { name: 'Volume', settings: '10-period average', purpose: 'Confirm breakouts (150%+ spike)' },
        { name: 'Support/Resistance', settings: 'Dynamic pivot detection', purpose: 'Bounce backs and trend reversals' }
      ],
      callSignal: [
        '📈 RSI < 30 (oversold) or < 40 (low momentum)',
        '📉 Price near lower Bollinger Band (<20%)',
        '↗️ Price crosses above EMA(5)',
        '⬆️ Price above EMA(21) trend line',
        '📊 Volume spike > 150% average',
        '🟢 Near support level (bounce setup)',
        '🔄 RSI turning up from oversold zone',
        '✅ EMA alignment bullish (5>10>21)'
      ],
      putSignal: [
        '📉 RSI > 70 (overbought) or > 60 (high momentum)',
        '📈 Price near upper Bollinger Band (>80%)',
        '↘️ Price crosses below EMA(5)',
        '⬇️ Price below EMA(21) trend line',
        '📊 Volume spike > 150% average',
        '🔴 Near resistance level (reversal setup)',
        '🔄 RSI turning down from overbought zone',
        '✅ EMA alignment bearish (5<10<21)'
      ],
      tips: [
        '⚡ CONFLUENCE IS KEY: Need 3+ confirmations for entry',
        '🎯 4+ confirmations = STRONG signal (75%+ confidence)',
        '📊 Wait for volume spike to confirm breakout momentum',
        '🔄 Trade direction of EMA alignment for best results',
        '⚠️ Avoid trading during news events (high volatility)',
        '📍 Support/Resistance levels add 5-10% to win rate',
        '⏱️ Best during European/US session overlap',
        '💡 RSI < 30 + Lower BB + Support = HIGH PROBABILITY BUY'
      ]
    },
    'pocket_option_5s_pro': {
      name: 'Pocket Option 5-Second Pro Strategy (DEFAULT)',
      timeframe: '5 seconds',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD - High volatility during London/NY hours',
      expiry: '5 seconds',
      accuracy: '62-70% (S/R strategy 62-68% documented)',
      indicators: [
        { name: 'EMA 20', settings: 'Period: 20', purpose: 'Trend direction - UP/DOWN based on price position' },
        { name: 'RSI', settings: 'Period: 14', purpose: 'Momentum - UP: RSI 50-70, DOWN: RSI 30-50' },
        { name: 'Support/Resistance', settings: 'Dynamic pivot detection', purpose: 'Mean reversion entries (62-68% win rate)' },
        { name: 'Candlestick Patterns', settings: 'AI pattern recognition', purpose: 'Reversal detection (engulfing, pin bar, doji)' },
        { name: 'Volume/ATR', settings: 'Volatility analysis', purpose: 'Confirmation of breakout momentum' }
      ],
      callSignal: [
        '📈 Price breaks ABOVE EMA(20)',
        '📊 RSI between 50-70 (momentum rising)',
        '🔄 Price just crossed above EMA(20)',
        '🟢 At SUPPORT level (mean reversion)',
        '🕯️ Bullish pattern (engulfing, hammer, pin bar)',
        '📊 Volume spike confirmation',
        '💹 RSI oversold (<30) turning up'
      ],
      putSignal: [
        '📉 Price breaks BELOW EMA(20)',
        '📊 RSI between 30-50 (momentum falling)',
        '🔄 Price just crossed below EMA(20)',
        '🔴 At RESISTANCE level (mean reversion)',
        '🕯️ Bearish pattern (engulfing, shooting star)',
        '📊 Volume spike confirmation',
        '💹 RSI overbought (>70) turning down'
      ],
      tips: [
        '⚡ USE ONE-CLICK TRADING for precise entry',
        '⏱️ Execute at START of new candle',
        '🔥 BEST TIME: London/NY overlap (13:00-21:00 UTC)',
        '📍 S/R strategy has HIGHEST documented win rate (62-68%)',
        '🎯 PREMIUM signal: 5+ confirmations = 80%+ confidence',
        '🎯 STRONG signal: 4 confirmations = 72% confidence',
        '🎯 MODERATE signal: 3 confirmations = 65% confidence',
        '⚠️ Wait for CONFLUENCE - discipline is key!',
        '🚫 No strategy guarantees wins - manage risk'
      ]
    }
  };

  // Available assets
  const assets = [
    'EURUSD_OTC', 'GBPUSD_OTC', 'USDJPY_OTC', 'AUDUSD_OTC', 'USDCAD_OTC',
    'BTCUSD_OTC', 'ETHUSD_OTC', 'XRPUSD_OTC', 'LTCUSD_OTC',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'
  ];

  const handleTimeframeChange = (timeframe) => {
    setSelectedTimeframe(timeframe);
    setSelectedStrategy(''); // Reset strategy when timeframe changes
  };

  const handleStrategyChange = (strategyKey) => {
    setSelectedStrategy(strategyKey);
    
    // Check if this is a custom strategy
    if (strategyKey.startsWith('custom_')) {
      const strategyId = strategyKey.replace('custom_', '');
      const customStrategy = customStrategies.find(s => s.id === strategyId);
      
      if (customStrategy) {
        // Build a config object from the custom strategy
        const customConfig = {
          name: customStrategy.name,
          timeframe: selectedTimeframe,
          chartType: 'Japanese Candlesticks',
          assets: customStrategy.assets?.join(', ') || 'Any',
          expiry: selectedTimeframe,
          accuracy: 'Custom Strategy',
          indicators: customStrategy.indicators?.map(ind => ({
            name: ind.name,
            settings: `${ind.setting}: ${ind.value}`,
            purpose: ind.condition || 'Signal condition'
          })) || [],
          callSignal: customStrategy.buy_conditions || ['Custom BUY conditions'],
          putSignal: customStrategy.sell_conditions || ['Custom SELL conditions'],
          tips: ['This is your custom-built strategy', 'Test thoroughly on demo account first'],
          isCustom: true,
          customStrategyId: strategyId
        };
        setCurrentStrategyConfig(customConfig);
        toast.success(`Selected custom strategy: ${customStrategy.name}`);
      }
    } else {
      // Default strategy
      const config = strategyConfigs[strategyKey];
      if (config) {
        setCurrentStrategyConfig(config);
        setShowSetupModal(true);
      }
    }
  };

  const handleConfirmSetup = () => {
    setShowSetupModal(false);
    if (onStrategySelect) {
      onStrategySelect(selectedStrategy, selectedTimeframe, currentStrategyConfig);
    }
    toast.success('Strategy configured! Ready to generate signals.');
  };

  const handleAutoGenerateToggle = (enabled) => {
    setAutoGenerateEnabled(enabled);
    if (onAutoGenerateToggle) {
      onAutoGenerateToggle(enabled, autoGenerateInterval);
    }
  };

  const handleForceGenerate = async () => {
    if (!selectedStrategy) {
      toast.error('Please select a strategy first');
      return;
    }
    
    setIsGenerating(true);
    try {
      // Call force generate API
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/signals/force-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assets: selectedAssets,
          expirations: [selectedTimeframe]
        })
      });
      
      const data = await response.json();
      if (data.success) {
        toast.success(`Generated ${data.signals?.length || 0} signal(s)!`);
      } else {
        toast.error(data.message || 'Failed to generate signals');
      }
    } catch (error) {
      toast.error('Error generating signals');
      console.error(error);
    } finally {
      setIsGenerating(false);
    }
  };

  const availableStrategies = strategiesByTimeframe[selectedTimeframe] || [];

  return (
    <>
      <Card className="p-6 glass-dark border-blue-500/30">
        <div className="flex items-center gap-3 mb-6">
          <TrendingUp className="w-6 h-6 text-blue-400" />
          <h3 className="text-2xl font-bold text-white">Strategy Selection & Signal Control</h3>
        </div>
        
        <div className="space-y-6">
          {/* Timeframe Selection */}
          <div>
            <Label className="text-white font-semibold mb-2 block">1. Select Timeframe</Label>
            <Select value={selectedTimeframe} onValueChange={handleTimeframeChange}>
              <SelectTrigger className="w-full bg-gray-800/50 border-gray-700 text-white">
                <SelectValue placeholder="Choose timeframe..." />
              </SelectTrigger>
              <SelectContent>
                {timeframes.map(tf => (
                  <SelectItem key={tf.value} value={tf.value}>
                    {tf.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Strategy Selection */}
          <div>
            <Label className="text-white font-semibold mb-2 block">
              2. Select Strategy for {timeframes.find(t => t.value === selectedTimeframe)?.label}
            </Label>
            {selectedTimeframe === '5s' && (
              <div className="mb-3 bg-blue-900/20 border border-blue-600/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-blue-300 text-sm">
                  <Clock className="w-4 h-4" />
                  <span className="font-semibold">5-Second Timeframe Notice:</span>
                </div>
                <p className="text-blue-200 text-xs mt-1">
                  Signals for 5-second trades include a 10-second processing delay for improved stability and accuracy.
                  This prevents false signals in ultra-fast timeframes.
                </p>
              </div>
            )}
            <Select value={selectedStrategy} onValueChange={handleStrategyChange}>
              <SelectTrigger className="w-full bg-gray-800/50 border-gray-700 text-white">
                <SelectValue placeholder="Choose strategy..." />
              </SelectTrigger>
              <SelectContent className="max-h-80">
                {/* My Built Strategies Section */}
                {getCustomStrategiesForTimeframe().length > 0 && (
                  <>
                    <div className="px-2 py-1.5 text-xs font-semibold text-yellow-400 bg-yellow-500/10 flex items-center gap-2">
                      <Star className="w-3 h-3" />
                      MY BUILT STRATEGIES
                    </div>
                    {getCustomStrategiesForTimeframe().map(strategy => (
                      <SelectItem 
                        key={`custom_${strategy.id}`} 
                        value={`custom_${strategy.id}`}
                      >
                        <div className="flex items-center gap-2">
                          <User className="w-3 h-3 text-yellow-400" />
                          <span>{strategy.name}</span>
                          <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-400/50">
                            Custom
                          </Badge>
                          {strategy.is_active && (
                            <Badge className="text-xs bg-green-500/20 text-green-400">Active</Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                    <div className="border-t border-gray-700 my-1"></div>
                  </>
                )}
                
                {/* Default Strategies Section */}
                <div className="px-2 py-1.5 text-xs font-semibold text-blue-400 bg-blue-500/10">
                  DEFAULT STRATEGIES
                </div>
                {availableStrategies.map(strategy => (
                  <SelectItem key={strategy.value} value={strategy.value}>
                    <div className="flex items-center gap-2">
                      <span>{strategy.name}</span>
                      <span className="text-xs text-green-400">({strategy.accuracy})</span>
                      {strategy.recommended && <span className="text-xs text-yellow-400">🔥 Recommended</span>}
                      {strategy.note && <span className="text-xs text-blue-400">{strategy.note}</span>}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Info about custom strategies */}
            {getCustomStrategiesForTimeframe().length === 0 && customStrategies.length > 0 && (
              <p className="text-xs text-gray-400 mt-2">
                💡 You have {customStrategies.length} custom {customStrategies.length === 1 ? 'strategy' : 'strategies'}, 
                but none are configured for {selectedTimeframe} timeframe. 
                Build one in Strategy Builder with this timeframe selected.
              </p>
            )}
            
            {selectedStrategy && (
              <Button
                onClick={() => setShowSetupModal(true)}
                className="w-full mt-3 bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Settings className="w-4 h-4 mr-2" />
                View Pocket Option Setup Guide
              </Button>
            )}
          </div>

          {/* Asset Selection */}
          <div>
            <Label className="text-white font-semibold mb-2 block">3. Select Assets</Label>
            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-2 bg-gray-900/50 rounded-lg">
              {assets.map(asset => (
                <label
                  key={asset}
                  className="flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-gray-800/50 transition"
                >
                  <input
                    type="checkbox"
                    checked={selectedAssets.includes(asset)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedAssets([...selectedAssets, asset]);
                      } else {
                        setSelectedAssets(selectedAssets.filter(a => a !== asset));
                      }
                    }}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-white">{asset}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Bot Control */}
          <div className="border-t border-gray-700 pt-6">
            <Label className="text-white font-semibold mb-4 block">4. Bot Control</Label>
            
            {/* Force Generate */}
            <div className="space-y-4">
              <Button
                onClick={handleForceGenerate}
                disabled={!selectedStrategy || isGenerating || selectedAssets.length === 0}
                className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-bold py-3"
              >
                {isGenerating ? (
                  <>
                    <Clock className="w-5 h-5 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5 mr-2" />
                    Force Generate Signal Now
                  </>
                )}
              </Button>

              {/* Auto Force Generate */}
              <div className="bg-gray-800/50 rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-white font-semibold">Auto Force Generate</Label>
                    <p className="text-xs text-gray-400 mt-1">Automatically generate signals at intervals</p>
                  </div>
                  <Switch
                    checked={autoGenerateEnabled}
                    onCheckedChange={handleAutoGenerateToggle}
                    disabled={!selectedStrategy}
                  />
                </div>

                {autoGenerateEnabled && (
                  <div>
                    <Label className="text-white text-sm mb-2 block">Generation Interval</Label>
                    <Select value={autoGenerateInterval} onValueChange={setAutoGenerateInterval}>
                      <SelectTrigger className="w-full bg-gray-900/50 border-gray-700 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="30s">Every 30 seconds</SelectItem>
                        <SelectItem value="1m">Every 1 minute</SelectItem>
                        <SelectItem value="2m">Every 2 minutes</SelectItem>
                        <SelectItem value="3m">Every 3 minutes</SelectItem>
                        <SelectItem value="5m">Every 5 minutes</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              {/* Bot Activation */}
              <div className="bg-gray-800/50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <Label className="text-white font-semibold">Trading Bot</Label>
                    <p className="text-xs text-gray-400 mt-1">Start continuous signal monitoring</p>
                  </div>
                  <Switch
                    checked={botActive}
                    onCheckedChange={setBotActive}
                    disabled={!selectedStrategy}
                  />
                </div>
                {botActive && (
                  <div className="flex items-center gap-2 text-green-400 text-sm">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span>Bot Active - Monitoring {selectedTimeframe} signals</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Configuration Summary */}
          {selectedStrategy && (
            <div className="bg-blue-900/20 rounded-lg p-4 border border-blue-600/50">
              <h4 className="text-white font-semibold mb-2">Current Configuration</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between text-gray-300">
                  <span>Strategy:</span>
                  <span className="text-white font-semibold">
                    {availableStrategies.find(s => s.value === selectedStrategy)?.name}
                  </span>
                </div>
                <div className="flex justify-between text-gray-300">
                  <span>Timeframe:</span>
                  <span className="text-white font-semibold">{selectedTimeframe}</span>
                </div>
                <div className="flex justify-between text-gray-300">
                  <span>Assets:</span>
                  <span className="text-white font-semibold">{selectedAssets.length} selected</span>
                </div>
                <div className="flex justify-between text-gray-300">
                  <span>Expected Accuracy:</span>
                  <span className="text-green-400 font-semibold">
                    {availableStrategies.find(s => s.value === selectedStrategy)?.accuracy}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Strategy Setup Modal */}
      {showSetupModal && currentStrategyConfig && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl shadow-2xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-purple-600 p-6 rounded-t-2xl flex justify-between items-center z-10">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Settings className="w-7 h-7" />
                  Setting Up: {currentStrategyConfig.name}
                </h2>
                <p className="text-blue-100 text-sm mt-1">
                  Configure Pocket Option to match bot's technical analysis
                </p>
              </div>
              <button
                onClick={() => setShowSetupModal(false)}
                className="text-white hover:bg-white/20 rounded-full p-2 transition"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Accuracy Badge */}
            <div className="bg-gradient-to-r from-green-900/50 to-emerald-900/50 p-4 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="px-4 py-2 bg-green-600 rounded-lg">
                    <span className="text-white font-bold text-lg">{currentStrategyConfig.accuracy}</span>
                  </div>
                  <div>
                    <div className="text-white font-semibold">Expected Win Rate</div>
                    <div className="text-gray-300 text-sm">Based on backtesting and research</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Introduction */}
              <div className="bg-blue-900/20 rounded-xl p-5 border border-blue-600/50">
                <p className="text-gray-200 leading-relaxed">
                  To align your Pocket Option trades with signals from this strategy, configure your chart to match the bot's technical analysis. 
                  This ensures you're using the same indicators, settings, and conditions for signal generation.
                </p>
              </div>

              {/* 1. Chart Setup */}
              <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                  <span className="text-2xl">1️⃣</span>
                  Chart Setup
                </h3>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Timeframe</div>
                      <div className="text-gray-400 text-sm">
                        Set your chart to <span className="text-blue-400 font-bold">{currentStrategyConfig.timeframe}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Chart Type</div>
                      <div className="text-gray-400 text-sm">
                        Use <span className="text-blue-400 font-bold">{currentStrategyConfig.chartType}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Assets</div>
                      <div className="text-gray-400 text-sm">
                        Apply to <span className="text-blue-400 font-bold">{currentStrategyConfig.assets}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Expiry Time</div>
                      <div className="text-gray-400 text-sm">
                        Set trade expiry to <span className="text-blue-400 font-bold">{currentStrategyConfig.expiry}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. Indicators */}
              <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                  <span className="text-2xl">2️⃣</span>
                  Adding and Configuring Indicators
                </h3>
                <p className="text-gray-300 text-sm mb-4">
                  Access indicators by clicking the "Indicators" icon in the upper left of Pocket Option. 
                  Select an indicator, adjust settings, and apply.
                </p>
                <div className="space-y-4">
                  {currentStrategyConfig.indicators.map((indicator, idx) => (
                    <div key={idx} className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                      <div className="flex items-start gap-3 mb-2">
                        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <div className="text-white font-bold mb-1">{indicator.name}</div>
                          <div className="text-blue-400 text-sm mb-2">
                            <span className="font-semibold">Settings:</span> {indicator.settings}
                          </div>
                          <div className="text-gray-400 text-sm">
                            <span className="font-semibold">Purpose:</span> {indicator.purpose}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 3. Signal Conditions */}
              <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                  <span className="text-2xl">3️⃣</span>
                  Signal Conditions to Match the Bot
                </h3>
                
                {/* CALL/BUY */}
                <div className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="px-3 py-1 bg-green-600 rounded-lg text-white font-bold">
                      CALL / BUY Signal
                    </div>
                  </div>
                  <div className="bg-green-900/20 rounded-lg p-4 border border-green-600/50">
                    <ul className="space-y-2">
                      {currentStrategyConfig.callSignal.map((condition, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-gray-200">
                          <span className="text-green-400 mt-1 font-bold">✓</span>
                          <span>{condition}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* PUT/SELL */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="px-3 py-1 bg-red-600 rounded-lg text-white font-bold">
                      PUT / SELL Signal
                    </div>
                  </div>
                  <div className="bg-red-900/20 rounded-lg p-4 border border-red-600/50">
                    <ul className="space-y-2">
                      {currentStrategyConfig.putSignal.map((condition, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-gray-200">
                          <span className="text-red-400 mt-1 font-bold">✓</span>
                          <span>{condition}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* 4. Tips */}
              <div className="bg-gray-800/50 rounded-xl p-5 border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                  <span className="text-2xl">4️⃣</span>
                  Tips for Success
                </h3>
                <ul className="space-y-3">
                  {currentStrategyConfig.tips.map((tip, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <span className="text-yellow-400 text-xl mt-0.5">💡</span>
                      <span className="text-gray-300">{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Final Note */}
              <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-xl p-5 border border-purple-600/50">
                <p className="text-white font-semibold mb-2">
                  🚀 Ready to trade?
                </p>
                <p className="text-gray-300 text-sm">
                  Open Pocket Option, apply these settings, and use the bot controls above to generate signals. 
                  Practice on demo first with at least 20-50 trades!
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 bg-gray-900 p-6 border-t border-gray-700 flex justify-end gap-3 rounded-b-2xl">
              <Button
                onClick={() => setShowSetupModal(false)}
                className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white"
              >
                Close
              </Button>
              <Button
                onClick={handleConfirmSetup}
                className="px-8 py-3 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 text-white font-bold"
              >
                <Check className="w-5 h-5 mr-2" />
                I've Configured My Chart
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default StrategySelector;
