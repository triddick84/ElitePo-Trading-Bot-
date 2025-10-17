import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Slider } from './ui/slider';
import { toast } from 'sonner';
import AssetSelector from './AssetSelector';
import AssetSelectorDropdown from './AssetSelectorDropdown';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const BotControls = ({ onStatusUpdate }) => {
  const [config, setConfig] = useState({
    trading_mode: 'demo',
    active_strategies: ['hybrid'],
    target_assets: ['forex', 'crypto'],
    selected_assets: ['EURUSD_regular', 'BTCUSD_regular'],
    selected_timeframes: ['1m', '5m'],
    chart_type: 'japanese_candles',
    risk_tolerance: 'medium',
    max_stake_per_trade: 10.0,
    max_daily_trades: 50,
    min_probability_threshold: 85,
    auto_trading_enabled: false,
    invert_signals: false,
    sound_alerts_enabled: true
  });
  
  const [botStatus, setBotStatus] = useState({ is_running: false });
  const [autoSignalStatus, setAutoSignalStatus] = useState({ auto_generation_active: false });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isAutoLoading, setIsAutoLoading] = useState(false);

  useEffect(() => {
    fetchCurrentConfig();
    fetchBotStatus();
    fetchAutoSignalStatus();
  }, []);

  const fetchCurrentConfig = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      const fetchedConfig = response.data;
      
      // Ensure new fields have default values if not present
      setConfig(prev => ({
        ...prev,
        ...fetchedConfig,
        chart_type: fetchedConfig.chart_type ?? 'japanese_candles',
        invert_signals: fetchedConfig.invert_signals ?? false,
        sound_alerts_enabled: fetchedConfig.sound_alerts_enabled ?? true
      }));
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const fetchBotStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setBotStatus(response.data);
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  const fetchAutoSignalStatus = async () => {
    try {
      const response = await axios.get(`${API}/signals/auto-generate/status`);
      setAutoSignalStatus(response.data);
    } catch (error) {
      console.error('Error fetching auto signal status:', error);
    }
  };

  const startBot = async () => {
    setIsLoading(true);
    try {
      await axios.post(`${API}/bot/start`, config);
      toast.success('Trading bot started successfully!');
      fetchBotStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error starting bot:', error);
      toast.error('Failed to start trading bot');
    } finally {
      setIsLoading(false);
    }
  };

  const stopBot = async () => {
    setIsLoading(true);
    try {
      await axios.post(`${API}/bot/stop`);
      toast.success('Trading bot stopped');
      fetchBotStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error stopping bot:', error);
      toast.error('Failed to stop trading bot');
    } finally {
      setIsLoading(false);
    }
  };

  const startAutoSignalGeneration = async () => {
    if (!botStatus.is_running) {
      toast.error('Please start the trading bot first before enabling auto signal generation');
      return;
    }

    setIsAutoLoading(true);
    try {
      await axios.post(`${API}/signals/auto-generate/start`);
      toast.success('🚀 Auto Signal Generation Started! Signals will be generated automatically.');
      fetchAutoSignalStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error starting auto signal generation:', error);
      toast.error('Failed to start auto signal generation');
    } finally {
      setIsAutoLoading(false);
    }
  };

  const stopAutoSignalGeneration = async () => {
    setIsAutoLoading(true);
    try {
      await axios.post(`${API}/signals/auto-generate/stop`);
      toast.success('Auto Signal Generation Stopped');
      fetchAutoSignalStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error stopping auto signal generation:', error);
      toast.error('Failed to stop auto signal generation');
    } finally {
      setIsAutoLoading(false);
    }
  };

  const updateConfig = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/config`, config);
      toast.success('✅ Configuration saved successfully! Settings will be used as defaults.');
      
      // Refresh the config to ensure it's loaded correctly
      await fetchCurrentConfig();
    } catch (error) {
      console.error('Error updating config:', error);
      toast.error('❌ Failed to save configuration. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleConfigChange = (key, value) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleStrategyToggle = (strategy) => {
    const current = config.active_strategies || [];
    const updated = current.includes(strategy)
      ? current.filter(s => s !== strategy)
      : [...current, strategy];
    
    handleConfigChange('active_strategies', updated);
  };

  const handleAssetToggle = (asset) => {
    const current = config.target_assets || [];
    const updated = current.includes(asset)
      ? current.filter(a => a !== asset)
      : [...current, asset];
    
    handleConfigChange('target_assets', updated);
  };

  const handleAssetSelectionChange = (selectedAssets, selectedTimeframes) => {
    setConfig(prev => ({
      ...prev,
      selected_assets: selectedAssets,
      selected_timeframes: selectedTimeframes
    }));
  };

  const strategies = [
    { id: 'hybrid', name: 'Hybrid Strategy', description: 'Combines multiple indicators for highest accuracy' },
    { id: 'cci_20', name: 'CCI 20', description: 'Commodity Channel Index overbought/oversold signals' },
    { id: 'ema_crossover', name: 'EMA Crossover', description: 'Exponential Moving Average crossover signals' },
    { id: 'rsi_5', name: 'RSI 5', description: 'Fast RSI scalping strategy' },
    { id: 'macd_momentum', name: 'MACD Momentum', description: 'Trend-following momentum signals' }
  ];

  const assetTypes = [
    { id: 'forex', name: 'Forex', icon: '💱' },
    { id: 'crypto', name: 'Cryptocurrency', icon: '₿' },
    { id: 'stocks', name: 'Stocks', icon: '📈' },
    { id: 'commodities', name: 'Commodities', icon: '🥇' },
    { id: 'otc', name: 'OTC Markets', icon: '🏛️' }
  ];

  return (
    <div className="space-y-6 animate-fade-in" data-testid="bot-controls">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Bot Controls</h2>
          <p className="text-slate-400">Configure and control your AI trading bot</p>
          <div className="flex items-center space-x-2 mt-2">
            <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
            <span className="text-emerald-400 text-sm">Settings loaded from saved configuration</span>
          </div>
        </div>
        
        {/* Quick Actions */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${
              botStatus.is_running ? 'status-online' : 'status-offline'
            }`}></div>
            <span className="text-slate-300 font-medium">
              {botStatus.is_running ? 'Running' : 'Stopped'}
            </span>
          </div>
          
          {botStatus.is_running ? (
            <Button 
              onClick={stopBot}
              disabled={isLoading}
              className="bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
              data-testid="stop-bot-btn"
            >
              {isLoading ? 'Stopping...' : '⏹️ Stop Bot'}
            </Button>
          ) : (
            <Button 
              onClick={startBot}
              disabled={isLoading}
              className="bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30"
              data-testid="start-bot-btn"
            >
              {isLoading ? 'Starting...' : '▶️ Start Bot'}
            </Button>
          )}
        </div>
      </div>

      {/* Auto Signal Generation Controls */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-semibold text-white mb-2">Auto Signal Generation</h3>
            <p className="text-slate-400 text-sm mb-4">
              Automatically generate trading signals at optimal intervals using advanced AI algorithms
            </p>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 ${autoSignalStatus.auto_generation_active ? 'bg-green-500' : 'bg-red-500'} rounded-full`}></div>
              <span className={`text-sm ${autoSignalStatus.auto_generation_active ? 'text-green-400' : 'text-red-400'}`}>
                Status: {autoSignalStatus.auto_generation_active ? 'Auto Generation Active' : 'Auto Generation Stopped'}
              </span>
            </div>
            {!botStatus.is_running && (
              <p className="text-yellow-400 text-xs mt-2">⚠️ Bot must be running to enable auto generation</p>
            )}
          </div>
          
          {autoSignalStatus.auto_generation_active ? (
            <Button 
              onClick={stopAutoSignalGeneration}
              disabled={isAutoLoading}
              className="bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
            >
              {isAutoLoading ? 'Stopping...' : '⏹️ Stop Auto Generation'}
            </Button>
          ) : (
            <Button 
              onClick={startAutoSignalGeneration}
              disabled={isAutoLoading || !botStatus.is_running}
              className="bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30 disabled:opacity-50"
            >
              {isAutoLoading ? 'Starting...' : '🚀 Start Auto Generation'}
            </Button>
          )}
        </div>
      </Card>

      {/* Configuration Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Basic Settings */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <h3 className="text-xl font-semibold text-white mb-6">Basic Settings</h3>
          
          <div className="space-y-6">
            {/* Trading Mode */}
            <div>
              <Label className="text-slate-300 font-medium mb-3 block">Trading Mode</Label>
              <Select value={config.trading_mode} onValueChange={(value) => handleConfigChange('trading_mode', value)}>
                <SelectTrigger className="bg-slate-800/50 border-slate-600 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="demo">Demo Mode (Simulated)</SelectItem>
                  <SelectItem value="live">Live Trading</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Risk Tolerance */}
            <div>
              <Label className="text-slate-300 font-medium mb-3 block">Risk Tolerance</Label>
              <Select value={config.risk_tolerance} onValueChange={(value) => handleConfigChange('risk_tolerance', value)}>
                <SelectTrigger className="bg-slate-800/50 border-slate-600 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="low">Conservative</SelectItem>
                  <SelectItem value="medium">Moderate</SelectItem>
                  <SelectItem value="high">Aggressive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Chart Type Selection */}
            <div>
              <Label className="text-slate-300 font-medium mb-3 block">Chart Type for Signal Generation</Label>
              <Select value={config.chart_type} onValueChange={(value) => handleConfigChange('chart_type', value)}>
                <SelectTrigger className="bg-slate-800/50 border-slate-600 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-600">
                  <SelectItem value="japanese_candles">🕯️ Japanese Candlesticks</SelectItem>
                  <SelectItem value="line">📈 Line Chart</SelectItem>
                  <SelectItem value="bars">📊 Bar Chart</SelectItem>
                  <SelectItem value="heikin_ashi">🎴 Heikin Ashi</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-slate-500 text-sm mt-2">
                {config.chart_type === 'japanese_candles' && 'Standard OHLC candlesticks - Best for pattern recognition'}
                {config.chart_type === 'line' && 'Clean price line - Best for trend identification'}
                {config.chart_type === 'bars' && 'OHLC bars - Best for price range analysis'}
                {config.chart_type === 'heikin_ashi' && 'Smoothed candles - Best for trend following, filters noise'}
              </p>
            </div>

            {/* Auto Trading */}
            <div className="flex items-center justify-between">
              <Label className="text-slate-300 font-medium">Auto Trading</Label>
              <Switch 
                checked={config.auto_trading_enabled}
                onCheckedChange={(checked) => handleConfigChange('auto_trading_enabled', checked)}
              />
            </div>

            {/* Invert Signals */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-slate-300 font-medium">Invert Signals</Label>
                <p className="text-slate-500 text-sm">Convert BUY signals to SELL and vice versa</p>
              </div>
              <Switch 
                checked={config.invert_signals}
                onCheckedChange={(checked) => handleConfigChange('invert_signals', checked)}
              />
            </div>

            {/* Sound Alerts */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-slate-300 font-medium">Sound Alerts</Label>
                <p className="text-slate-500 text-sm">Play audio notification for new signals</p>
              </div>
              <Switch 
                checked={config.sound_alerts_enabled}
                onCheckedChange={(checked) => handleConfigChange('sound_alerts_enabled', checked)}
              />
            </div>
          </div>
        </Card>

        {/* Trading Parameters */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <h3 className="text-xl font-semibold text-white mb-6">Trading Parameters</h3>
          
          <div className="space-y-6">
            {/* Max Stake */}
            <div>
              <Label className="text-slate-300 font-medium mb-2 block">
                Max Stake Per Trade ($)
              </Label>
              <Input
                type="number"
                value={config.max_stake_per_trade}
                onChange={(e) => handleConfigChange('max_stake_per_trade', parseFloat(e.target.value))}
                className="bg-slate-800/50 border-slate-600 text-white"
                min="1"
                max="1000"
              />
            </div>

            {/* Daily Trades Limit */}
            <div>
              <Label className="text-slate-300 font-medium mb-2 block">
                Max Daily Trades
              </Label>
              <Input
                type="number"
                value={config.max_daily_trades}
                onChange={(e) => handleConfigChange('max_daily_trades', parseInt(e.target.value))}
                className="bg-slate-800/50 border-slate-600 text-white"
                min="1"
                max="500"
              />
            </div>

            {/* Signal Probability Threshold Slider */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-slate-300 font-medium">
                  Signal Probability Threshold
                </Label>
                <div className="flex items-center space-x-2">
                  <span className={`text-lg font-bold px-3 py-1 rounded-lg ${
                    config.min_probability_threshold >= 90 ? 'text-green-400 bg-green-500/20' :
                    config.min_probability_threshold >= 75 ? 'text-yellow-400 bg-yellow-500/20' :
                    'text-red-400 bg-red-500/20'
                  }`}>
                    {config.min_probability_threshold}%
                  </span>
                </div>
              </div>
              
              <div className="space-y-3">
                <Slider
                  value={[config.min_probability_threshold]}
                  onValueChange={(value) => handleConfigChange('min_probability_threshold', value[0])}
                  min={50}
                  max={99}
                  step={1}
                  className="w-full"
                />
                
                {/* Threshold Scale */}
                <div className="flex justify-between text-xs text-slate-400">
                  <span>50%</span>
                  <span>60%</span>
                  <span>70%</span>
                  <span>80%</span>
                  <span>90%</span>
                  <span>99%</span>
                </div>
                
                {/* Threshold Description */}
                <div className="p-3 rounded-lg border border-slate-600/30 bg-slate-800/30">
                  <div className="flex items-center space-x-2 mb-2">
                    <div className={`w-2 h-2 rounded-full ${
                      config.min_probability_threshold >= 90 ? 'bg-green-500' :
                      config.min_probability_threshold >= 75 ? 'bg-yellow-500' :
                      'bg-red-500'
                    }`}></div>
                    <span className="text-slate-300 font-medium">
                      {config.min_probability_threshold >= 90 ? 'Conservative' :
                       config.min_probability_threshold >= 75 ? 'Balanced' :
                       'Aggressive'} Strategy
                    </span>
                  </div>
                  <p className="text-slate-400 text-sm">
                    {config.min_probability_threshold >= 90 ? 
                      'High accuracy signals with fewer opportunities. Recommended for consistent profits.' :
                     config.min_probability_threshold >= 75 ? 
                      'Balanced approach with good accuracy and moderate signal frequency.' :
                      'More signals with higher risk. Only use if you understand the increased risk.'}
                  </p>
                  <div className="mt-2 text-xs text-slate-500">
                    Only signals above {config.min_probability_threshold}% probability will be generated
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Trading Strategies */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Active Trading Strategies</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="strategy-selection">
          {strategies.map((strategy) => (
            <div 
              key={strategy.id}
              className={`p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                config.active_strategies?.includes(strategy.id)
                  ? 'border-emerald-500/50 bg-emerald-500/10'
                  : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
              }`}
              onClick={() => handleStrategyToggle(strategy.id)}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-white font-medium">{strategy.name}</h4>
                <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                  config.active_strategies?.includes(strategy.id)
                    ? 'border-emerald-500 bg-emerald-500'
                    : 'border-slate-400'
                }`}>
                  {config.active_strategies?.includes(strategy.id) && (
                    <span className="text-white text-xs">✓</span>
                  )}
                </div>
              </div>
              <p className="text-slate-400 text-sm">{strategy.description}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Advanced Asset & Timeframe Selection */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <AssetSelectorDropdown 
          selectedAssets={config.selected_assets}
          selectedTimeframes={config.selected_timeframes}
          onAssetsChange={(assets) => handleConfigChange('selected_assets', assets)}
          onTimeframesChange={(timeframes) => handleConfigChange('selected_timeframes', timeframes)}
        />
      </Card>

      {/* Quick Asset Categories (Legacy) */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Quick Asset Categories</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4" data-testid="asset-selection">
          {assetTypes.map((asset) => (
            <div
              key={asset.id}
              className={`p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 text-center ${
                config.target_assets?.includes(asset.id)
                  ? 'border-blue-500/50 bg-blue-500/10'
                  : 'border-slate-600/50 bg-slate-800/30 hover:border-slate-500/50'
              }`}
              onClick={() => handleAssetToggle(asset.id)}
            >
              <div className="text-2xl mb-2">{asset.icon}</div>
              <p className="text-white font-medium text-sm">{asset.name}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Save Configuration */}
      <div className="flex justify-end">
        <Button 
          onClick={updateConfig}
          disabled={isSaving}
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 btn-glow disabled:opacity-50"
          data-testid="save-config-btn"
        >
          {isSaving ? '⏳ Saving...' : '💾 Save Configuration'}
        </Button>
      </div>
    </div>
  );
};

export default BotControls;