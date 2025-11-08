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
// AssetSelector and AssetSelectorDropdown removed - using MarketAssetSelector in Dashboard instead

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
  const [candleSyncStatus, setCandleSyncStatus] = useState({ enabled: false, next_candle_times: {} });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isAutoLoading, setIsAutoLoading] = useState(false);
  const [isCandleSyncLoading, setIsCandleSyncLoading] = useState(false);

  useEffect(() => {
    fetchCurrentConfig();
    fetchBotStatus();
    fetchAutoSignalStatus();
    fetchCandleSyncStatus();
    
    // Poll candle sync status every 2 seconds for live countdown
    const interval = setInterval(() => {
      if (botStatus.is_running) {
        fetchCandleSyncStatus();
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [botStatus.is_running]);

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
      const response = await axios.get(`${API}/bot/auto-signal-status`);
      setAutoSignalStatus(response.data);
    } catch (error) {
      console.error('Error fetching auto signal status:', error);
    }
  };

  const fetchCandleSyncStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/candle-sync/status`);
      setCandleSyncStatus(response.data);
    } catch (error) {
      console.error('Error fetching candle sync status:', error);
    }
  };

  const toggleCandleSync = async () => {
    if (!botStatus.is_running) {
      toast.error('⚠️ Please start the bot first before enabling candle synchronization');
      return;
    }

    setIsCandleSyncLoading(true);
    try {
      if (candleSyncStatus.enabled) {
        // Disable candle sync
        await axios.post(`${API}/bot/candle-sync/disable`);
        toast.success('🛑 Candle synchronization disabled');
      } else {
        // Enable candle sync
        const response = await axios.post(`${API}/bot/candle-sync/enable`);
        toast.success(`✅ Candle sync enabled for ${response.data.timeframes?.join(', ')} timeframes`);
      }
      fetchCandleSyncStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error toggling candle sync:', error);
      toast.error('❌ Failed to toggle candle synchronization');
    } finally {
      setIsCandleSyncLoading(false);
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
      const response = await axios.post(`${API}/bot/stop`);
      toast.success('✅ Trading bot stopped successfully');
      console.log('Stop response:', response.data);
      fetchBotStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error stopping bot:', error);
      toast.error('❌ Failed to stop trading bot');
    } finally {
      setIsLoading(false);
    }
  };

  const clearAllSessions = async () => {
    if (!window.confirm('⚠️ This will clear all active sessions and reset the bot. Continue?')) {
      return;
    }
    
    setIsLoading(true);
    try {
      const response = await axios.post(`${API}/bot/clear-all`);
      toast.success('✅ All sessions cleared successfully');
      console.log('Clear all response:', response.data);
      fetchBotStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error clearing sessions:', error);
      toast.error('❌ Failed to clear sessions');
    } finally {
      setIsLoading(false);
    }
  };

  const restartBot = async () => {
    if (!window.confirm('🔄 This will restart the bot with current configuration. Continue?')) {
      return;
    }
    
    setIsLoading(true);
    try {
      const response = await axios.post(`${API}/bot/restart`);
      toast.success('✅ Bot restarted successfully');
      console.log('Restart response:', response.data);
      fetchBotStatus();
      if (onStatusUpdate) onStatusUpdate();
    } catch (error) {
      console.error('Error restarting bot:', error);
      toast.error('❌ Failed to restart bot');
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
          
          <div className="flex items-center space-x-2">
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
            
            {/* Clear All Sessions Button */}
            <Button 
              onClick={clearAllSessions}
              disabled={isLoading}
              className="bg-orange-500/20 text-orange-400 border border-orange-500/30 hover:bg-orange-500/30"
              title="Clear all active sessions and reset bot state"
            >
              {isLoading ? 'Clearing...' : '🗑️ Clear All'}
            </Button>
            
            {/* Restart Button */}
            <Button 
              onClick={restartBot}
              disabled={isLoading}
              className="bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30"
              title="Restart bot with current configuration"
            >
              {isLoading ? 'Restarting...' : '🔄 Restart'}
            </Button>
          </div>
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

      {/* Candle Formation Synchronization */}
      <Card className="p-6 glass-dark border-emerald-700/50 border-2">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-2">
              <h3 className="text-xl font-semibold text-white">🕐 Candle Synchronization</h3>
              <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-full border border-emerald-500/30">
                Pocket Option Sync
              </span>
            </div>
            <p className="text-slate-400 text-sm mb-4">
              Generate signals precisely when new candles form on Pocket Option platform for optimal entry timing
            </p>
            
            {/* Status Indicator */}
            <div className="flex items-center space-x-2 mb-3">
              <div className={`w-2 h-2 ${candleSyncStatus.enabled ? 'bg-emerald-500 animate-pulse' : 'bg-slate-500'} rounded-full`}></div>
              <span className={`text-sm font-medium ${candleSyncStatus.enabled ? 'text-emerald-400' : 'text-slate-400'}`}>
                {candleSyncStatus.enabled ? '✅ Candle Sync Active' : '⏸️ Candle Sync Disabled'}
              </span>
            </div>

            {/* Next Candle Times */}
            {candleSyncStatus.enabled && candleSyncStatus.next_candle_times && Object.keys(candleSyncStatus.next_candle_times).length > 0 && (
              <div className="mt-3 p-3 bg-slate-800/50 rounded-lg border border-slate-600/50">
                <div className="text-xs font-semibold text-emerald-400 mb-2">⏱️ Next Candle Formation:</div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {Object.entries(candleSyncStatus.next_candle_times).map(([timeframe, data]) => (
                    <div key={timeframe} className="p-2 bg-slate-700/50 rounded border border-slate-600/50">
                      <div className="text-xs text-slate-400">{timeframe}</div>
                      <div className="text-sm font-bold text-white">{data.seconds_until > 0 ? `${Math.floor(data.seconds_until)}s` : 'NOW'}</div>
                      <div className="text-xs text-slate-500">{data.time}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Active Timeframes */}
            {candleSyncStatus.enabled && candleSyncStatus.active_timeframes && (
              <div className="mt-2">
                <span className="text-xs text-slate-500">Monitoring: </span>
                {candleSyncStatus.active_timeframes.map((tf, idx) => (
                  <span key={tf} className="text-xs text-emerald-400 font-medium">
                    {tf}{idx < candleSyncStatus.active_timeframes.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </div>
            )}

            {!botStatus.is_running && (
              <p className="text-yellow-500 text-sm mt-2">⚠️ Start the bot first to enable candle synchronization</p>
            )}
          </div>
          
          {/* Toggle Button */}
          <div className="ml-4">
            <Button
              onClick={toggleCandleSync}
              disabled={isCandleSyncLoading || !botStatus.is_running}
              className={`${
                candleSyncStatus.enabled
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
              }`}
            >
              {isCandleSyncLoading ? (
                'Processing...'
              ) : candleSyncStatus.enabled ? (
                '⏹️ Disable Sync'
              ) : (
                '▶️ Enable Sync'
              )}
            </Button>
          </div>
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
            <div className={`rounded-lg transition-colors ${config.invert_signals ? 'bg-orange-500/10 border border-orange-500/30 p-3' : 'p-3'}`}>
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <Label className="text-slate-300 font-medium">
                    Invert Signals {config.invert_signals && <span className="text-orange-400 text-xs ml-2">(ACTIVE - All Timeframes)</span>}
                  </Label>
                  <p className="text-slate-500 text-sm">
                    Convert BUY signals to SELL and vice versa
                    {config.invert_signals && <span className="text-orange-400 block text-xs mt-1">⚠️ Applied to ALL timeframes (5s, 15s, 1m, etc.)</span>}
                  </p>
                </div>
                <Switch 
                  checked={config.invert_signals}
                  onCheckedChange={(checked) => handleConfigChange('invert_signals', checked)}
                />
              </div>
              
              {/* IMPORTANT: Demo vs Real Account Warning */}
              <div className="mt-3 p-3 rounded-lg border-2 border-blue-500/50 bg-blue-500/10">
                <div className="flex items-start space-x-2">
                  <span className="text-blue-400 text-xl">ℹ️</span>
                  <div className="flex-1">
                    <p className="text-blue-300 font-semibold text-sm mb-1">
                      📋 Account Type Guide:
                    </p>
                    <div className="space-y-1 text-xs text-blue-200">
                      <div className="flex items-center space-x-2">
                        <span className="text-green-400">✅</span>
                        <span><strong className="text-white">Demo Account:</strong> Activate Invert (Turn ON)</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-red-400">⛔</span>
                        <span><strong className="text-white">Real Account:</strong> Leave Invert OFF (Default)</span>
                      </div>
                    </div>
                    <p className="text-blue-300 text-xs mt-2 italic">
                      💡 Demo and Real accounts may have different signal behavior on Pocket Option
                    </p>
                  </div>
                </div>
              </div>
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