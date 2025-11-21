import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const StrategySelector = () => {
  const [availableStrategies, setAvailableStrategies] = useState({});
  const [selectedStrategies, setSelectedStrategies] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ text: '', type: '' });
  const [expandedTimeframe, setExpandedTimeframe] = useState('5s');

  const timeframeOrder = ['5s', '15s', '30s', '1m', '3m', '5m'];
  
  const timeframeLabels = {
    '5s': '5 Seconds',
    '15s': '15 Seconds',
    '30s': '30 Seconds',
    '1m': '1 Minute',
    '3m': '3 Minutes',
    '5m': '5 Minutes'
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      setLoading(true);
      
      // Fetch available strategies
      const availableRes = await axios.get(`${BACKEND_URL}/api/strategies/available`);
      setAvailableStrategies(availableRes.data.strategies || {});
      
      // Fetch selected strategies
      const selectedRes = await axios.get(`${BACKEND_URL}/api/strategies/selected`);
      setSelectedStrategies(selectedRes.data.selections || {});
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching strategies:', error);
      setMessage({ text: 'Failed to load strategies', type: 'error' });
      setLoading(false);
    }
  };

  const handleStrategySelect = async (timeframe, strategyId) => {
    try {
      setSaving(true);
      
      await axios.post(`${BACKEND_URL}/api/strategies/select`, {
        timeframe,
        strategy_id: strategyId
      });
      
      // Update local state
      setSelectedStrategies(prev => ({
        ...prev,
        [timeframe]: strategyId
      }));
      
      setMessage({ 
        text: `✅ Strategy updated for ${timeframeLabels[timeframe]}`, 
        type: 'success' 
      });
      
      // Clear message after 3 seconds
      setTimeout(() => setMessage({ text: '', type: '' }), 3000);
      
      setSaving(false);
    } catch (error) {
      console.error('Error selecting strategy:', error);
      setMessage({ text: '❌ Failed to update strategy', type: 'error' });
      setSaving(false);
    }
  };

  const getStrategyIcon = (strategyId) => {
    const icons = {
      'default': '🎯',
      'keltner_fractal': '📊',
      '3ema_crossover': '📈',
      'ema20_rsi14': '📉',
      'rsi_volume': '📢',
      'bollinger_ema': '🎪',
      'macd_rsi': '🔄',
      'psar_fractals': '🎲',
      'stochastic_adx': '⚡',
      'psar_stochastic': '🎯',
      'triple_confirmation': '🏆',
      'williams_macd': '⚙️',
      'smart_money': '💎',
      'ichimoku_cci': '🌊',
      'atr_sr': '📏',
      'cci_rsi': '🔋'
    };
    return icons[strategyId] || '📊';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-white text-lg">Loading strategies...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-3">
            🎯 Strategy Selection Center
          </h1>
          <p className="text-blue-200 text-lg">
            Choose your preferred trading strategy for each timeframe
          </p>
          <div className="mt-4 inline-block bg-blue-600/20 border border-blue-400/30 rounded-lg px-6 py-3">
            <p className="text-blue-300 text-sm">
              💡 Each timeframe has multiple research-backed strategies optimized for different market conditions
            </p>
          </div>
        </div>

        {/* Message Display */}
        {message.text && (
          <div className={`mb-6 p-4 rounded-lg text-center font-semibold ${
            message.type === 'success' 
              ? 'bg-green-600/20 border border-green-400 text-green-300' 
              : 'bg-red-600/20 border border-red-400 text-red-300'
          }`}>
            {message.text}
          </div>
        )}

        {/* Timeframe Cards */}
        <div className="space-y-6">
          {timeframeOrder.map((timeframe) => {
            const strategies = availableStrategies[timeframe] || [];
            const selected = selectedStrategies[timeframe] || 'default';
            const isExpanded = expandedTimeframe === timeframe;

            return (
              <div 
                key={timeframe}
                className="bg-gray-800/50 backdrop-blur-sm rounded-xl border border-blue-500/30 overflow-hidden shadow-2xl"
              >
                {/* Timeframe Header */}
                <div 
                  className="bg-gradient-to-r from-blue-600/30 to-purple-600/30 p-5 cursor-pointer hover:from-blue-600/40 hover:to-purple-600/40 transition-all"
                  onClick={() => setExpandedTimeframe(isExpanded ? null : timeframe)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <span className="text-3xl">⏱️</span>
                      <div>
                        <h2 className="text-2xl font-bold text-white">
                          {timeframeLabels[timeframe]}
                        </h2>
                        <p className="text-blue-300 text-sm">
                          {strategies.length} strategies available
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <p className="text-xs text-blue-300 mb-1">Currently Selected:</p>
                        <div className="flex items-center space-x-2 bg-green-600/20 border border-green-400/50 rounded-lg px-3 py-1">
                          <span className="text-lg">
                            {getStrategyIcon(selected)}
                          </span>
                          <span className="text-green-300 font-semibold">
                            {strategies.find(s => s.id === selected)?.name || 'Default'}
                          </span>
                        </div>
                      </div>
                      <svg 
                        className={`w-6 h-6 text-white transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Strategy Cards (Expanded) */}
                {isExpanded && (
                  <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {strategies.map((strategy) => {
                      const isSelected = selected === strategy.id;
                      
                      return (
                        <div
                          key={strategy.id}
                          className={`relative p-5 rounded-lg border-2 cursor-pointer transition-all ${
                            isSelected
                              ? 'bg-green-600/20 border-green-400 shadow-lg shadow-green-500/50'
                              : 'bg-gray-700/30 border-gray-600 hover:border-blue-400 hover:bg-gray-700/50'
                          }`}
                          onClick={() => handleStrategySelect(timeframe, strategy.id)}
                        >
                          {/* Selected Badge */}
                          {isSelected && (
                            <div className="absolute top-3 right-3">
                              <div className="bg-green-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                                ✓ ACTIVE
                              </div>
                            </div>
                          )}

                          {/* Strategy Icon and Name */}
                          <div className="flex items-start space-x-3 mb-3">
                            <span className="text-4xl">{getStrategyIcon(strategy.id)}</span>
                            <div className="flex-1">
                              <h3 className={`text-xl font-bold mb-1 ${
                                isSelected ? 'text-green-300' : 'text-white'
                              }`}>
                                {strategy.name}
                              </h3>
                              <p className="text-gray-300 text-sm leading-relaxed">
                                {strategy.description}
                              </p>
                            </div>
                          </div>

                          {/* Strategy Tags */}
                          <div className="flex flex-wrap gap-2 mt-3">
                            {strategy.id === 'default' && (
                              <span className="bg-blue-600/30 border border-blue-400 text-blue-300 text-xs px-2 py-1 rounded">
                                Default
                              </span>
                            )}
                            {strategy.id !== 'default' && (
                              <span className="bg-purple-600/30 border border-purple-400 text-purple-300 text-xs px-2 py-1 rounded">
                                Custom
                              </span>
                            )}
                            {['triple_confirmation', 'williams_macd', 'smart_money'].includes(strategy.id) && (
                              <span className="bg-yellow-600/30 border border-yellow-400 text-yellow-300 text-xs px-2 py-1 rounded">
                                90%+ Accuracy
                              </span>
                            )}
                            {['rsi_volume', 'bollinger_ema', 'macd_rsi'].includes(strategy.id) && (
                              <span className="bg-orange-600/30 border border-orange-400 text-orange-300 text-xs px-2 py-1 rounded">
                                Research 2025
                              </span>
                            )}
                          </div>

                          {/* Select Button */}
                          {!isSelected && (
                            <div className="mt-4">
                              <button
                                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 px-4 rounded-lg transition-colors disabled:opacity-50"
                                disabled={saving}
                              >
                                {saving ? 'Selecting...' : 'Select This Strategy'}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Info Footer */}
        <div className="mt-8 bg-blue-600/10 border border-blue-400/30 rounded-xl p-6">
          <h3 className="text-xl font-bold text-white mb-3">ℹ️ How to Use</h3>
          <div className="grid md:grid-cols-3 gap-4 text-blue-200">
            <div>
              <p className="font-semibold mb-2">1️⃣ Select Strategies</p>
              <p className="text-sm">Choose your preferred strategy for each timeframe based on your trading style</p>
            </div>
            <div>
              <p className="font-semibold mb-2">2️⃣ Auto-Apply</p>
              <p className="text-sm">Selected strategies automatically apply to Force Generate and Auto Generate</p>
            </div>
            <div>
              <p className="font-semibold mb-2">3️⃣ Test & Optimize</p>
              <p className="text-sm">Monitor performance and switch strategies anytime to optimize results</p>
            </div>
          </div>
        </div>

        {/* Back to Dashboard Button */}
        <div className="mt-6 text-center">
          <button
            onClick={() => window.location.href = '/'}
            className="bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-8 rounded-lg transition-colors"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default StrategySelector;
