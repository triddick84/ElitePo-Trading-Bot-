import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { toast } from 'sonner';
import AssetSelector from './AssetSelector';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const BotControls = ({ onStatusUpdate }) => {
  const [config, setConfig] = useState({
    trading_mode: 'demo',
    active_strategies: ['hybrid'],
    target_assets: ['forex', 'crypto'],
    selected_assets: ['EURUSD_regular', 'BTCUSD_regular'],
    selected_timeframes: ['1m', '5m'],
    risk_tolerance: 'medium',
    max_stake_per_trade: 10.0,
    max_daily_trades: 50,
    min_probability_threshold: 95.0,
    auto_trading_enabled: false,
    invert_signals: false,
    sound_alerts_enabled: true
  });
  
  const [botStatus, setBotStatus] = useState({ is_running: false });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchCurrentConfig();
    fetchBotStatus();
  }, []);

  const fetchCurrentConfig = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      const fetchedConfig = response.data;
      
      // Ensure new fields have default values if not present
      setConfig(prev => ({
        ...prev,
        ...fetchedConfig,
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

  const updateConfig = async () => {
    try {
      await axios.put(`${API}/config`, config);
      toast.success('Configuration updated successfully!');
    } catch (error) {
      console.error('Error updating config:', error);
      toast.error('Failed to update configuration');
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

            {/* Probability Threshold */}
            <div>
              <Label className="text-slate-300 font-medium mb-2 block">
                Min Probability Threshold (%)
              </Label>
              <Input
                type="number"
                value={config.min_probability_threshold}
                onChange={(e) => handleConfigChange('min_probability_threshold', parseFloat(e.target.value))}
                className="bg-slate-800/50 border-slate-600 text-white"
                min="90"
                max="99.9"
                step="0.1"
              />
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
        <AssetSelector 
          selectedAssets={config.selected_assets}
          selectedTimeframes={config.selected_timeframes}
          onSelectionChange={handleAssetSelectionChange}
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
          className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 btn-glow"
          data-testid="save-config-btn"
        >
          💾 Save Configuration
        </Button>
      </div>
    </div>
  );
};

export default BotControls;