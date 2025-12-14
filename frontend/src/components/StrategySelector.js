/**
 * Strategy Selector with Setup Guide
 * Shows strategy configuration popup when user selects or changes strategy
 */

import React, { useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Settings, TrendingUp, X, Check } from 'lucide-react';

const StrategySelector = ({ onStrategySelect }) => {
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [currentStrategyConfig, setCurrentStrategyConfig] = useState(null);

  // Strategy configurations
  const strategies = {
    'rsi_bb_volume': {
      name: 'RSI + Bollinger Bands + Volume',
      timeframe: '1 minute',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD (high volatility pairs)',
      expiry: '60 seconds (1 minute)',
      accuracy: '70%+',
      indicators: [
        {
          name: 'RSI (Relative Strength Index)',
          settings: 'Period: 14 or 7 (for faster signals)',
          purpose: 'Identifies overbought (>70) and oversold (<30) conditions'
        },
        {
          name: 'Bollinger Bands',
          settings: 'Period: 20, Standard Deviation: 2',
          purpose: 'Shows price volatility and extremes'
        },
        {
          name: 'Volume',
          settings: 'Default volume bars or indicators',
          purpose: 'Confirms momentum with volume spikes (>150% average)'
        }
      ],
      callSignal: [
        'RSI drops below 30 (oversold zone)',
        'Price touches or penetrates lower Bollinger Band',
        'Volume spike >150% of 10-period average',
        'Price starts bouncing upward from lower band'
      ],
      putSignal: [
        'RSI rises above 70 (overbought zone)',
        'Price touches or penetrates upper Bollinger Band',
        'Volume spike >150% of 10-period average',
        'Price gets rejected downward from upper band'
      ],
      tips: [
        'Best during London/New York session overlap (high volatility)',
        'Wait for volume spike confirmation - it increases accuracy by 10-15%',
        'Avoid flat markets with tight Bollinger Bands (low volatility)',
        'Practice on demo with 20+ trades before going live'
      ]
    },
    'stoch_macd_pattern': {
      name: 'Stochastic + MACD + Candlestick Patterns',
      timeframe: '1 minute',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD, BTC/USD (high liquidity pairs)',
      expiry: '60 seconds (1 minute)',
      accuracy: '75-80%',
      indicators: [
        {
          name: 'Stochastic Oscillator',
          settings: 'K Period: 14, D Period: 3, Smoothing: 3',
          purpose: 'Identifies momentum extremes and reversals'
        },
        {
          name: 'MACD (Moving Average Convergence Divergence)',
          settings: 'Fast: 12, Slow: 26, Signal: 9',
          purpose: 'Confirms trend direction and momentum'
        },
        {
          name: 'Candlestick Patterns (Visual)',
          settings: 'Enable pattern recognition or observe manually',
          purpose: 'Validates price action (Hammer, Engulfing, Shooting Star, etc.)'
        }
      ],
      callSignal: [
        'Stochastic drops below 20 (oversold) and starts turning up',
        'MACD histogram expanding positively or bullish crossover',
        'Bullish candlestick pattern (Hammer, Bullish Engulfing, Morning Star)',
        'Price near support level'
      ],
      putSignal: [
        'Stochastic rises above 80 (overbought) and starts turning down',
        'MACD histogram expanding negatively or bearish crossover',
        'Bearish candlestick pattern (Shooting Star, Bearish Engulfing, Evening Star)',
        'Price near resistance level'
      ],
      tips: [
        'Wait for all 3 confirmations before entering (Stoch + MACD + Pattern)',
        'Candlestick patterns increase accuracy by 8-10% when combined',
        'Best results during trending markets (not ranging)',
        'Backtest with 50+ trades to achieve 75%+ win rate'
      ]
    },
    'enhanced_rsi_bb_volume': {
      name: 'Enhanced RSI + BB + Volume V2 (85-89% Target)',
      timeframe: '1 minute + 5 minute confirmation',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, BTC/USD (high volatility)',
      expiry: '60 seconds (1 minute)',
      accuracy: '85-89% (with strict filtering)',
      indicators: [
        {
          name: 'RSI (Relative Strength Index)',
          settings: 'Period: 14, Oversold: 25, Overbought: 75 (stricter)',
          purpose: 'Extreme momentum detection'
        },
        {
          name: 'Bollinger Bands',
          settings: 'Period: 20, Std Dev: 2',
          purpose: 'Volatility and price extremes'
        },
        {
          name: 'Volume',
          settings: 'Volume bars with 10-period average',
          purpose: 'Momentum confirmation'
        },
        {
          name: 'ADX (Average Directional Index)',
          settings: 'Period: 14, Minimum: 25',
          purpose: 'Trend strength filter (only trade when ADX > 25)'
        },
        {
          name: '5-Minute Chart (Secondary)',
          settings: 'Open a second chart window with 5m timeframe',
          purpose: 'Confirm overall trend direction'
        }
      ],
      callSignal: [
        '1m RSI < 25 (extreme oversold)',
        'Price at lower Bollinger Band (<12% of BB range)',
        'Volume spike >150% average',
        'ADX > 25 (strong trend)',
        '5m chart shows bullish trend (EMA crossover)',
        'Price bouncing upward',
        'Trade only during best hours (8am-5pm UTC)'
      ],
      putSignal: [
        '1m RSI > 75 (extreme overbought)',
        'Price at upper Bollinger Band (>88% of BB range)',
        'Volume spike >150% average',
        'ADX > 30 (strong trend)',
        '5m chart shows bearish trend',
        'Price rejected downward',
        'Trade only during best hours (8am-5pm UTC)'
      ],
      tips: [
        'STRICT ENTRY: All conditions must be met (5+ confirmations)',
        'Multi-timeframe is critical - check 5m before entering 1m trade',
        'Only 2-5 high-quality signals per day (not 15+)',
        'ADX filter removes 60-70% of false signals',
        'Best accuracy during London/NY session',
        'Risk only 1% per trade, max 5 trades/day'
      ]
    },
    'enhanced_stoch_macd_pattern': {
      name: 'Enhanced Stochastic + MACD + Pattern V2 (85-89% Target)',
      timeframe: '1 minute + 5 minute confirmation',
      chartType: 'Japanese Candlesticks',
      assets: 'EUR/USD, GBP/USD (high liquidity)',
      expiry: '60 seconds (1 minute)',
      accuracy: '85-89% (with strict filtering)',
      indicators: [
        {
          name: 'Stochastic Oscillator',
          settings: 'K: 14, D: 3, Smooth: 3, Oversold: 15, Overbought: 85 (stricter)',
          purpose: 'Extreme momentum detection'
        },
        {
          name: 'MACD',
          settings: 'Fast: 12, Slow: 26, Signal: 9',
          purpose: 'Trend and momentum confirmation'
        },
        {
          name: 'Candlestick Patterns',
          settings: 'Pattern recognition (focus on high-reliability patterns)',
          purpose: 'Price action validation'
        },
        {
          name: 'ADX',
          settings: 'Period: 14, Minimum: 30',
          purpose: 'Strong trend filter (only trade when ADX > 30)'
        },
        {
          name: '5-Minute Chart',
          settings: 'Secondary window with 5m timeframe',
          purpose: 'Overall trend confirmation'
        }
      ],
      callSignal: [
        'Stochastic < 15 (extreme oversold) and turning up',
        'MACD bullish crossover or expanding positive histogram',
        'Bullish pattern: Hammer, Bullish Engulfing, or Morning Star',
        'ADX > 30 (strong trend)',
        '5m trend is bullish',
        'Price near support/pivot level',
        'Rejection candle with long lower wick'
      ],
      putSignal: [
        'Stochastic > 85 (extreme overbought) and turning down',
        'MACD bearish crossover or expanding negative histogram',
        'Bearish pattern: Shooting Star, Bearish Engulfing, or Evening Star',
        'ADX > 30 (strong trend)',
        '5m trend is bearish',
        'Price near resistance/pivot level',
        'Rejection candle with long upper wick'
      ],
      tips: [
        'Need 4+ confirmations (not just 2)',
        'Pattern reliability matters: Three Black Crows = 84% accuracy',
        'Rejection candles add 5% to win rate',
        'Multi-timeframe alignment is mandatory',
        'Only 3-8 high-quality signals per day',
        'Test in demo with 100+ trades before live trading'
      ]
    }
  };

  const handleStrategyChange = (strategyKey) => {
    setSelectedStrategy(strategyKey);
    setCurrentStrategyConfig(strategies[strategyKey]);
    setShowSetupModal(true);
  };

  const handleConfirmSetup = () => {
    setShowSetupModal(false);
    if (onStrategySelect) {
      onStrategySelect(selectedStrategy, currentStrategyConfig);
    }
  };

  return (
    <>
      <Card className="p-6 glass-dark border-blue-500/30">
        <div className="flex items-center gap-3 mb-4">
          <TrendingUp className="w-6 h-6 text-blue-400" />
          <h3 className="text-xl font-semibold text-white">Strategy Selection</h3>
        </div>
        
        <p className="text-gray-400 text-sm mb-4">
          Select a trading strategy to generate signals. A setup guide will show you how to configure Pocket Option.
        </p>

        <Select value={selectedStrategy} onValueChange={handleStrategyChange}>
          <SelectTrigger className="w-full bg-gray-800/50 border-gray-700 text-white">
            <SelectValue placeholder="Choose a strategy..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="rsi_bb_volume">
              RSI + BB + Volume (70%+ accuracy)
            </SelectItem>
            <SelectItem value="stoch_macd_pattern">
              Stochastic + MACD + Pattern (75-80% accuracy)
            </SelectItem>
            <SelectItem value="enhanced_rsi_bb_volume">
              Enhanced RSI + BB + Volume V2 (85-89% accuracy) 🔥
            </SelectItem>
            <SelectItem value="enhanced_stoch_macd_pattern">
              Enhanced Stochastic + MACD + Pattern V2 (85-89% accuracy) 🔥
            </SelectItem>
          </SelectContent>
        </Select>

        {selectedStrategy && (
          <Button
            onClick={() => setShowSetupModal(true)}
            className="w-full mt-4 bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Settings className="w-4 h-4 mr-2" />
            View Setup Guide
          </Button>
        )}
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
                        {' '}(via timeframe selector above the chart). This matches the bot's analysis window.
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Chart Type</div>
                      <div className="text-gray-400 text-sm">
                        Use <span className="text-blue-400 font-bold">{currentStrategyConfig.chartType}</span> for best visibility of price action and patterns.
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Assets</div>
                      <div className="text-gray-400 text-sm">
                        Apply to <span className="text-blue-400 font-bold">{currentStrategyConfig.assets}</span> for optimal results.
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-500 mt-1 flex-shrink-0" />
                    <div>
                      <div className="text-white font-semibold">Expiry Time</div>
                      <div className="text-gray-400 text-sm">
                        Set trade expiry to <span className="text-blue-400 font-bold">{currentStrategyConfig.expiry}</span> to sync with signal timing.
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
                  Access indicators by clicking the "Indicators" icon in the upper left of Pocket Option (near chart type selector). 
                  Select an indicator, adjust settings, and apply. You can favorite them for quick access.
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
                <div className="mt-4 bg-yellow-900/20 rounded-lg p-3 border border-yellow-600/50">
                  <p className="text-yellow-200 text-sm">
                    ⚠️ <strong>Note:</strong> Do not overload your chart—use {currentStrategyConfig.indicators.length} indicators as shown. 
                    Remove existing ones if needed (Pocket Option limits to 30 across all charts).
                  </p>
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

                <div className="mt-4 bg-blue-900/20 rounded-lg p-3 border border-blue-600/50">
                  <p className="text-blue-200 text-sm">
                    💡 The bot uses these exact conditions based on historical data analysis. 
                    Always wait for candle close to confirm, reducing false signals.
                  </p>
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
                  Open Pocket Option, apply these settings, and monitor signals from the bot. 
                  If signals don't match, double-check settings and timeframe alignment. 
                  For best results, practice on demo account first with at least 20-50 trades!
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
