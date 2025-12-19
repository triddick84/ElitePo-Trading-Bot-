/**
 * Enhanced Strategy Selector
 * Includes:
 * - Strategy selection by timeframe
 * - Chart configuration (moved from Dashboard)
 * - Signal timing controls (moved from Dashboard)
 * - Flexible trading system (moved from Dashboard)
 * - Setup guides
 */

import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { 
  Settings, 
  TrendingUp, 
  Clock, 
  BarChart, 
  Sliders,
  Info,
  CheckCircle,
  Save
} from 'lucide-react';
import { toast } from 'sonner';
import SignalSetupGuideModal from './SignalSetupGuideModal';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const StrategySelectorEnhanced = ({ onStrategySelect, onConfigChange }) => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1m');
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  // Chart Configuration
  const [chartConfig, setChartConfig] = useState({
    chartType: 'japanese_candles',
    chartTimeframe: '15s',
    signalTimeframe: '5s'
  });
  
  // Flexible Trading System
  const [flexibleConfig, setFlexibleConfig] = useState({
    asset_symbol: 'EURUSD',
    market_type: 'regular',
    chart_timeframe: '30s',
    trade_duration_seconds: 82,
    force_signal: false,
    sma_fast: 6,
    sma_slow: 12,
    supertrend_atr_period: 2,
    supertrend_multiplier: 2.2,
    ao_short_period: 6,
    ao_long_period: 12
  });
  const [flexibleLoading, setFlexibleLoading] = useState(false);
  const [flexibleResult, setFlexibleResult] = useState(null);

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

  // Strategy configurations by timeframe (will be expanded with new strategies)
  const strategiesByTimeframe = {
    '5s': [
      { value: 'enhanced_breakout', name: '🚀 Enhanced Breakout Predictor', accuracy: '80%+', note: '⏳ 10s latency | S/R Levels', recommended: true },
      { value: 'proven_5s', name: '🎯 Proven RSI+Stoch+BB+EMA', accuracy: '80%+', note: '⏳ 10s latency | 4+ confirmations', recommended: true },
      { value: 'ultra_v2_5s', name: 'Ultra Precision 5s V2', accuracy: '90%+', note: '⏳ 10s latency applied' },
      { value: 'reversal_5s', name: '5s Reversal Strategy', accuracy: '85%+', note: '⏳ 10s latency applied' },
      { value: 'momentum_5s', name: '5s Momentum Breakout', accuracy: '88%+', note: '⏳ 10s latency applied' },
      { value: 'keltner_fractal', name: 'Keltner Channel + Fractal', accuracy: '85%+', note: '⏳ 10s latency applied' },
      { value: '3ema_crossover', name: '3 EMA Crossover', accuracy: '82%+', note: '⏳ 10s latency applied' },
      { value: 'ema20_rsi14', name: 'EMA20 + RSI14', accuracy: '80%+', note: '⏳ 10s latency applied' },
      { value: 'stochastic_divergence', name: 'Stochastic Divergence', accuracy: '83%+', note: '⏳ 10s latency applied' }
    ],
    '15s': [
      { value: 'fractal_15s', name: '15s Fractal Strategy', accuracy: '85%+' },
      { value: 'ema_cross_15s', name: '15s EMA Crossover', accuracy: '82%+' },
      { value: 'rsi_stoch_15s', name: '15s RSI + Stochastic', accuracy: '84%+' }
    ],
    '30s': [
      { value: 'supertrend_30s', name: '30s Supertrend Strategy', accuracy: '80%+' },
      { value: 'bollinger_rsi_30s', name: '30s Bollinger + RSI', accuracy: '83%+' },
      { value: 'macd_keltner_30s', name: '30s MACD + Keltner', accuracy: '81%+' }
    ],
    '1m': [
      { value: 'enhanced_rsi_bb_volume', name: 'Enhanced RSI + BB + Volume V2', accuracy: '85-89%', recommended: true },
      { value: 'enhanced_stoch_macd_pattern', name: 'Enhanced Stochastic + MACD + Pattern V2', accuracy: '85-89%', recommended: true },
      { value: 'smart_money_ict', name: 'Smart Money + ICT', accuracy: '80-95%' },
      { value: 'triple_confirmation', name: 'RSI + BB + MACD Triple', accuracy: '73-90%' }
    ],
    '2m': [
      { value: 'multi_layer_2m', name: '2m Multi-Layer Strategy', accuracy: '75%+' },
      { value: 'trend_follow_2m', name: '2m Trend Following', accuracy: '78%+' },
      { value: 'support_resistance_2m', name: '2m S&R Bounce', accuracy: '80%+' }
    ],
    '3m': [
      { value: 'multi_layer_3m', name: '3m Multi-Layer Strategy', accuracy: '75%+' },
      { value: 'volume_profile_3m', name: '3m Volume Profile', accuracy: '79%+' },
      { value: 'price_action_3m', name: '3m Price Action', accuracy: '82%+' }
    ],
    '5m': [
      { value: 'trend_5m', name: '5m Trend Following', accuracy: '80%+' },
      { value: 'divergence_5m', name: '5m RSI Divergence', accuracy: '83%+' },
      { value: 'breakout_5m', name: '5m Breakout Strategy', accuracy: '81%+' }
    ],
    '15m': [
      { value: 'swing_15m', name: '15m Swing Trading', accuracy: '80%+' },
      { value: 'multi_tf_15m', name: '15m Multi-Timeframe', accuracy: '85%+' },
      { value: 'fibonacci_15m', name: '15m Fibonacci Retracement', accuracy: '82%+' }
    ],
    '30m': [
      { value: 'position_30m', name: '30m Position Trading', accuracy: '82%+' },
      { value: 'elliott_30m', name: '30m Elliott Wave', accuracy: '80%+' },
      { value: 'ichimoku_30m', name: '30m Ichimoku Cloud', accuracy: '84%+' }
    ],
    '1h': [
      { value: 'daily_bias_1h', name: '1h Daily Bias', accuracy: '85%+' },
      { value: 'accumulation_1h', name: '1h Accumulation/Distribution', accuracy: '83%+' },
      { value: 'wyckoff_1h', name: '1h Wyckoff Method', accuracy: '86%+' }
    ]
  };

  // Chart types
  const chartTypes = [
    { id: 'japanese_candles', name: 'Japanese Candles', icon: '🕯️' },
    { id: 'heikin_ashi', name: 'Heikin Ashi', icon: '🎌' },
    { id: 'bar', name: 'Bar Chart', icon: '📊' },
    { id: 'line', name: 'Line Chart', icon: '📈' }
  ];

  // Load saved configuration on mount
  useEffect(() => {
    fetchSavedConfiguration();
  }, []);

  const fetchSavedConfiguration = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API}/config`);
      const data = await response.json();
      
      if (data) {
        // Load saved strategy selection
        if (data.selected_timeframe) {
          setSelectedTimeframe(data.selected_timeframe);
        }
        if (data.selected_strategy) {
          setSelectedStrategy(data.selected_strategy);
        }
        
        // Load chart configuration
        if (data.chart_config) {
          setChartConfig(data.chart_config);
        }
        
        // Load flexible configuration
        if (data.flexible_config) {
          setFlexibleConfig(data.flexible_config);
        }
        
        toast.success('✅ Loaded saved configuration');
      }
    } catch (error) {
      console.error('Error loading configuration:', error);
      toast.error('Failed to load saved configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveConfiguration = async () => {
    if (!selectedStrategy || !selectedTimeframe) {
      toast.error('Please select both timeframe and strategy before saving');
      return;
    }

    setIsSaving(true);
    try {
      const configToSave = {
        selected_timeframe: selectedTimeframe,
        selected_strategy: selectedStrategy,
        chart_config: chartConfig,
        flexible_config: flexibleConfig
      };

      const response = await fetch(`${API}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configToSave)
      });

      const data = await response.json();
      
      if (response.ok) {
        toast.success('✅ Configuration saved successfully!');
        
        // Notify parent components
        if (onConfigChange) {
          onConfigChange({
            timeframe: selectedTimeframe,
            strategy: selectedStrategy,
            chartConfig,
            flexibleConfig
          });
        }
        if (onStrategySelect) {
          onStrategySelect(selectedTimeframe, selectedStrategy);
        }
      } else {
        throw new Error(data.message || 'Failed to save configuration');
      }
    } catch (error) {
      console.error('Error saving configuration:', error);
      toast.error('Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  // Notify parent of configuration changes (but don't auto-save)
  useEffect(() => {
    if (onConfigChange && !isLoading) {
      onConfigChange({
        timeframe: selectedTimeframe,
        strategy: selectedStrategy,
        chartConfig,
        flexibleConfig
      });
    }
  }, [selectedTimeframe, selectedStrategy, chartConfig, flexibleConfig, isLoading]);

  // Notify parent of strategy selection
  useEffect(() => {
    if (onStrategySelect && selectedStrategy && !isLoading) {
      onStrategySelect(selectedTimeframe, selectedStrategy);
    }
  }, [selectedTimeframe, selectedStrategy, isLoading]);

  const handleTimeframeChange = (value) => {
    setSelectedTimeframe(value);
    setSelectedStrategy(''); // Reset strategy when timeframe changes
  };

  const handleStrategyChange = (value) => {
    setSelectedStrategy(value);
    // Show setup guide for the selected strategy
    setShowSetupModal(true);
  };

  const handleChartConfigChange = (field, value) => {
    setChartConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleFlexibleGenerate = async () => {
    setFlexibleLoading(true);
    setFlexibleResult(null);
    try {
      const response = await fetch(`${API}/signals/flexible-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flexibleConfig)
      });
      
      const data = await response.json();
      setFlexibleResult(data);
      
      if (data.success) {
        toast.success('✅ Flexible signal generated!');
      } else {
        toast.warning(data.message || 'No signal generated');
      }
    } catch (error) {
      console.error('Error generating flexible signal:', error);
      toast.error('Failed to generate signal');
    } finally {
      setFlexibleLoading(false);
    }
  };

  const availableStrategies = strategiesByTimeframe[selectedTimeframe] || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto mb-4"></div>
          <p className="text-white">Loading configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Strategy Selection Card */}
      <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <TrendingUp className="w-6 h-6 text-purple-400" />
          <h3 className="text-2xl font-bold text-white">Strategy Selection</h3>
        </div>
        
        <div className="space-y-6">
          {/* Timeframe Selection */}
          <div>
            <Label className="text-purple-300 font-semibold mb-2 block">
              1. Select Timeframe
            </Label>
            <Select value={selectedTimeframe} onValueChange={handleTimeframeChange}>
              <SelectTrigger className="w-full bg-slate-700/50 border-purple-500/30 text-white">
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
            <Label className="text-purple-300 font-semibold mb-2 block">
              2. Select Strategy for {timeframes.find(t => t.value === selectedTimeframe)?.label}
            </Label>
            
            {selectedTimeframe === '5s' && (
              <div className="mb-3 bg-blue-900/20 border border-blue-600/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-blue-300 text-sm">
                  <Clock className="w-4 h-4" />
                  <span className="font-semibold">5-Second Timeframe Notice:</span>
                </div>
                <p className="text-blue-200 text-xs mt-1">
                  Signals include 10-second processing delay for improved stability.
                </p>
              </div>
            )}
            
            <Select value={selectedStrategy} onValueChange={handleStrategyChange}>
              <SelectTrigger className="w-full bg-slate-700/50 border-purple-500/30 text-white">
                <SelectValue placeholder="Choose strategy..." />
              </SelectTrigger>
              <SelectContent>
                {availableStrategies.map(strategy => (
                  <SelectItem key={strategy.value} value={strategy.value}>
                    <div className="flex items-center gap-2">
                      <span>{strategy.name}</span>
                      <span className="text-xs text-green-400">({strategy.accuracy})</span>
                      {strategy.recommended && <span className="text-xs text-yellow-400">🔥</span>}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {selectedStrategy && (
              <div className="mt-3 bg-green-900/20 border border-green-600/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-green-300 text-sm">
                  <CheckCircle className="w-4 h-4" />
                  <span className="font-semibold">Strategy Active:</span>
                  <span>{availableStrategies.find(s => s.value === selectedStrategy)?.name}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Chart Configuration Card */}
      <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <BarChart className="w-6 h-6 text-blue-400" />
          <h3 className="text-xl font-bold text-white">Chart Configuration</h3>
        </div>
        
        <div className="space-y-4">
          {/* Chart Type */}
          <div>
            <Label className="text-purple-300 mb-2 block">Chart Type</Label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {chartTypes.map(type => (
                <Button
                  key={type.id}
                  size="sm"
                  variant={chartConfig.chartType === type.id ? "default" : "outline"}
                  onClick={() => handleChartConfigChange('chartType', type.id)}
                  className={chartConfig.chartType === type.id 
                    ? "bg-purple-600 hover:bg-purple-700" 
                    : "border-purple-500/50 text-purple-300"}
                >
                  <span className="mr-2">{type.icon}</span>
                  {type.name}
                </Button>
              ))}
            </div>
          </div>

          {/* Chart Timeframe */}
          <div>
            <Label className="text-purple-300 mb-2 block">Chart Timeframe</Label>
            <Select 
              value={chartConfig.chartTimeframe} 
              onValueChange={(val) => handleChartConfigChange('chartTimeframe', val)}
            >
              <SelectTrigger className="w-full bg-slate-700/50 border-purple-500/30 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timeframes.slice(0, 8).map(tf => (
                  <SelectItem key={tf.value} value={tf.value}>
                    {tf.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Signal Timeframe */}
          <div>
            <Label className="text-purple-300 mb-2 block">Signal Timeframe</Label>
            <Select 
              value={chartConfig.signalTimeframe} 
              onValueChange={(val) => handleChartConfigChange('signalTimeframe', val)}
            >
              <SelectTrigger className="w-full bg-slate-700/50 border-purple-500/30 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timeframes.slice(0, 6).map(tf => (
                  <SelectItem key={tf.value} value={tf.value}>
                    {tf.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {/* Flexible Trading System Card */}
      <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <Sliders className="w-6 h-6 text-green-400" />
          <h3 className="text-xl font-bold text-white">Flexible Trading System</h3>
        </div>
        
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-purple-300 mb-2 block">Asset Symbol</Label>
              <Input
                value={flexibleConfig.asset_symbol}
                onChange={(e) => setFlexibleConfig(prev => ({ ...prev, asset_symbol: e.target.value }))}
                className="bg-slate-700/50 border-purple-500/30 text-white"
              />
            </div>

            <div>
              <Label className="text-purple-300 mb-2 block">Market Type</Label>
              <Select 
                value={flexibleConfig.market_type} 
                onValueChange={(val) => setFlexibleConfig(prev => ({ ...prev, market_type: val }))}
              >
                <SelectTrigger className="bg-slate-700/50 border-purple-500/30 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="regular">Regular</SelectItem>
                  <SelectItem value="otc">OTC</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-purple-300 mb-2 block">Chart Timeframe</Label>
              <Select 
                value={flexibleConfig.chart_timeframe} 
                onValueChange={(val) => setFlexibleConfig(prev => ({ ...prev, chart_timeframe: val }))}
              >
                <SelectTrigger className="bg-slate-700/50 border-purple-500/30 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {timeframes.map(tf => (
                    <SelectItem key={tf.value} value={tf.value}>{tf.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-purple-300 mb-2 block">Trade Duration (sec)</Label>
              <Input
                type="number"
                value={flexibleConfig.trade_duration_seconds}
                onChange={(e) => setFlexibleConfig(prev => ({ ...prev, trade_duration_seconds: parseInt(e.target.value) }))}
                className="bg-slate-700/50 border-purple-500/30 text-white"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Label className="text-purple-300">Force Signal Generation</Label>
            <Switch
              checked={flexibleConfig.force_signal}
              onCheckedChange={(checked) => setFlexibleConfig(prev => ({ ...prev, force_signal: checked }))}
            />
          </div>

          <Button
            onClick={handleFlexibleGenerate}
            disabled={flexibleLoading}
            className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
          >
            {flexibleLoading ? 'Generating...' : 'Generate Flexible Signal'}
          </Button>

          {flexibleResult && (
            <div className={`mt-3 rounded-lg p-3 ${flexibleResult.success ? 'bg-green-900/20 border border-green-600/50' : 'bg-red-900/20 border border-red-600/50'}`}>
              <p className={`text-sm ${flexibleResult.success ? 'text-green-300' : 'text-red-300'}`}>
                {flexibleResult.message}
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* Save Configuration Button */}
      <Card className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 border-purple-500/50 backdrop-blur-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">Save Configuration</h3>
            <p className="text-sm text-gray-300">
              Save your strategy selection, timeframe, and settings for future use
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {/* Current Configuration Summary */}
          <div className="bg-slate-800/50 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Timeframe:</span>
              <span className="text-sm font-semibold text-purple-300">
                {selectedTimeframe ? timeframes.find(t => t.value === selectedTimeframe)?.label : 'Not selected'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Strategy:</span>
              <span className="text-sm font-semibold text-purple-300">
                {selectedStrategy ? availableStrategies.find(s => s.value === selectedStrategy)?.name : 'Not selected'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Chart Type:</span>
              <span className="text-sm font-semibold text-purple-300">
                {chartTypes.find(t => t.id === chartConfig.chartType)?.name}
              </span>
            </div>
          </div>

          {/* Save Button */}
          <Button
            onClick={handleSaveConfiguration}
            disabled={isSaving || !selectedStrategy || !selectedTimeframe}
            className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-semibold py-3"
          >
            {isSaving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Saving Configuration...
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5 mr-2" />
                Save Configuration
              </>
            )}
          </Button>

          {/* Info Notice */}
          <div className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-blue-200">
                <p className="font-semibold mb-1">Configuration will be saved for:</p>
                <ul className="list-disc list-inside space-y-1 text-blue-300">
                  <li>Strategy selection and timeframe</li>
                  <li>Chart type and configuration</li>
                  <li>Flexible trading system settings</li>
                  <li>Dashboard will use saved configuration</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Setup Guide Modal */}
      {showSetupModal && selectedStrategy && (
        <SignalSetupGuideModal
          isOpen={showSetupModal}
          onClose={() => setShowSetupModal(false)}
          strategyConfig={{
            name: availableStrategies.find(s => s.value === selectedStrategy)?.name,
            timeframe: selectedTimeframe,
            // Add more config details as needed
          }}
        />
      )}
    </div>
  );
};

export default StrategySelectorEnhanced;
