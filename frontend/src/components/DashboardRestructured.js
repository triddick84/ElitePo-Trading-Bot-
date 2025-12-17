/**
 * Restructured Dashboard - Better Organization & Navigation
 * 
 * Layout Structure:
 * 1. Header: Trading Configuration (Expirations, Assets)
 * 2. Main Left: Signal Controls & Generation
 * 3. Main Right: Recent Signals List (with Clear button)
 * 4. Bottom: Candle Sync Status & Strategy Display
 * 5. Performance Metrics
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { 
  TrendingUp, 
  Play, 
  Square, 
  Zap, 
  Clock, 
  Trash2,
  CheckCircle,
  AlertCircle,
  BarChart3,
  Settings,
  Target
} from 'lucide-react';
import { toast } from 'sonner';
import MarketAssetSelector from './MarketAssetSelector';
import ImprovedSignalPopup from './ImprovedSignalPopup';
import LatencyAdjustment from './LatencyAdjustment';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DashboardRestructured = ({ 
  botStatus, 
  liveSignals, 
  setLiveSignals, 
  notificationSettings, 
  setNotificationSettings 
}) => {
  // Configuration State
  const [config, setConfig] = useState({
    selected_assets: [],
    selected_expirations: ['1m', '2m'],
    min_probability_threshold: 85,
    selected_strategy: '',
    selected_timeframe: '1m',
    trading_mode: 'demo', // 'demo' or 'real'
    invert_signals: false, // Independent of account type
    popup_notifications: true,
    sound_alerts: true
  });
  
  // Signal Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [autoGenerateActive, setAutoGenerateActive] = useState(false);
  const [autoGenerateMode, setAutoGenerateMode] = useState('selected'); // 'selected' or 'scan'
  
  // Auto Force Generate State
  const [autoForceActive, setAutoForceActive] = useState(false);
  const [autoForceInterval, setAutoForceInterval] = useState(60); // seconds
  const [autoForceCountdown, setAutoForceCountdown] = useState(0);
  const [autoForceIntervalId, setAutoForceIntervalId] = useState(null);
  
  // Enhanced Auto-Generate Settings
  const [enhancedSettings, setEnhancedSettings] = useState({
    scanAllAssets: false,
    minPayout: 80,
    minAccuracy: 75,
    maxSignals: 5
  });
  
  // Continuous Scanning State
  const [isScanning, setIsScanning] = useState(false);
  const [scanIntervalId, setScanIntervalId] = useState(null);
  const [scanCount, setScanCount] = useState(0);
  
  // Candle Sync State
  const [candleSyncEnabled, setCandleSyncEnabled] = useState(false);
  const [candleSyncStatus, setCandleSyncStatus] = useState({ 
    enabled: false, 
    next_candle_times: {},
    bot_running: false
  });
  
  // Performance Metrics
  const [performanceData, setPerformanceData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch data on mount
  useEffect(() => {
    fetchConfiguration();
    fetchPerformance();
    fetchCandleSyncStatus();
    
    const perfInterval = setInterval(fetchPerformance, 10000);
    const syncInterval = setInterval(fetchCandleSyncStatus, 2000);
    
    return () => {
      clearInterval(perfInterval);
      clearInterval(syncInterval);
      if (autoForceIntervalId) {
        clearInterval(autoForceIntervalId);
      }
    };
  }, []);

  // Auto Force Generate Countdown
  useEffect(() => {
    if (autoForceActive && autoForceCountdown > 0) {
      const timer = setTimeout(() => {
        setAutoForceCountdown(autoForceCountdown - 1);
      }, 1000);
      return () => clearTimeout(timer);
    } else if (autoForceActive && autoForceCountdown === 0) {
      // Generate signal and reset countdown
      handleAutoForceGenerate();
    }
  }, [autoForceActive, autoForceCountdown]);

  const fetchConfiguration = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      // Convert backend 'live' mode back to frontend 'real' for display
      let tradingMode = response.data.trading_mode || 'demo';
      if (tradingMode === 'live') {
        tradingMode = 'real';
      }
      
      setConfig(prev => ({
        ...prev,
        ...response.data,
        selected_strategy: response.data.selected_strategy || '',
        selected_timeframe: response.data.selected_timeframe || '1m',
        trading_mode: tradingMode,
        invert_signals: response.data.invert_signals !== undefined ? response.data.invert_signals : false,
        popup_notifications: response.data.popup_notifications !== undefined ? response.data.popup_notifications : true,
        sound_alerts: response.data.sound_alerts_enabled !== undefined ? response.data.sound_alerts_enabled : true
      }));
    } catch (error) {
      console.error('Error fetching configuration:', error);
    }
  };

  const fetchPerformance = async () => {
    try {
      const response = await axios.get(`${API}/performance/metrics`);
      setPerformanceData(response.data);
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching performance:', error);
      setIsLoading(false);
    }
  };

  const fetchCandleSyncStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/candle-sync/status`);
      setCandleSyncStatus(response.data);
      setCandleSyncEnabled(response.data.enabled);
    } catch (error) {
      console.error('Error fetching candle sync status:', error);
    }
  };

  // Clear All Signals (Auto-clear after 10 signals)
  const handleClearAllSignals = async () => {
    try {
      const response = await axios.delete(`${API}/signals/clear-all`);
      
      if (response.data.status === 'success') {
        setLiveSignals([]);
        toast.success(`✅ Cleared ${response.data.deleted_count} signals`);
      }
    } catch (error) {
      console.error('Error clearing signals:', error);
      toast.error('Failed to clear signals');
    }
  };

  // Auto-clear when signals exceed 10 (silent - no notification)
  useEffect(() => {
    if (liveSignals.length > 10) {
      const signalsToKeep = liveSignals.slice(0, 10);
      setLiveSignals(signalsToKeep);
      // Removed toast notification to prevent frequent popups
    }
  }, [liveSignals]);

  // Single Force Generate
  const handleSingleGenerate = async () => {
    if (!config.selected_assets || config.selected_assets.length === 0) {
      toast.error('Please select at least one asset');
      return;
    }

    setIsGenerating(true);
    try {
      const asset = config.selected_assets[0];
      const [symbol, market] = asset.includes('_') ? asset.split('_') : [asset, 'regular'];
      
      const response = await axios.post(`${API}/signals/force-generate`, {
        asset_symbol: symbol,
        market_type: market,
        selected_timeframe: config.selected_timeframe || '1m',
        selected_strategy: config.selected_strategy || 'enhanced_rsi_bb_volume'
      });

      if (response.data.success && response.data.signal) {
        setLiveSignals(prev => [response.data.signal, ...prev]);
        toast.success('✅ Signal generated!');
      } else {
        toast.warning(response.data.message || 'No signal generated');
      }
    } catch (error) {
      console.error('Error generating signal:', error);
      toast.error('Failed to generate signal');
    } finally {
      setIsGenerating(false);
    }
  };

  // Enhanced Auto-Generate
  const handleEnhancedAutoGenerate = async () => {
    setIsGenerating(true);
    try {
      // Build query parameters (backend expects query params, not JSON body)
      const params = new URLSearchParams({
        scan_all_assets: enhancedSettings.scanAllAssets,
        min_payout: enhancedSettings.minPayout,
        min_accuracy: enhancedSettings.minAccuracy,
        max_signals: enhancedSettings.maxSignals
      });
      
      // Add selected assets if not scanning all
      if (!enhancedSettings.scanAllAssets && config.selected_assets) {
        config.selected_assets.forEach(asset => {
          params.append('selected_assets', asset);
        });
      }
      
      const response = await axios.post(`${API}/signals/auto-generate/enhanced?${params.toString()}`);

      if (response.data.success && response.data.signals && response.data.signals.length > 0) {
        setLiveSignals(prev => [...response.data.signals, ...prev]);
        toast.success(`✅ Generated ${response.data.signals.length} signals from ${response.data.assets_scanned} assets`);
      } else {
        toast.warning('No signals met the criteria');
      }
    } catch (error) {
      console.error('Error in enhanced auto-generate:', error);
      toast.error('Failed to generate signals');
    } finally {
      setIsGenerating(false);
    }
  };

  // Auto Force Generate
  const handleAutoForceGenerate = async () => {
    if (!config.selected_assets || config.selected_assets.length === 0) {
      toast.error('Please select at least one asset');
      setAutoForceActive(false);
      return;
    }

    try {
      const asset = config.selected_assets[Math.floor(Math.random() * config.selected_assets.length)];
      const [symbol, market] = asset.includes('_') ? asset.split('_') : [asset, 'regular'];
      
      const response = await axios.post(`${API}/signals/force-generate`, {
        asset_symbol: symbol,
        market_type: market,
        selected_timeframe: config.selected_timeframe || '1m',
        selected_strategy: config.selected_strategy || 'enhanced_rsi_bb_volume'
      });

      if (response.data.success && response.data.signal) {
        setLiveSignals(prev => [response.data.signal, ...prev]);
        toast.success(`✅ Auto-generated signal for ${symbol}`);
      }
      
      // Reset countdown
      setAutoForceCountdown(autoForceInterval);
    } catch (error) {
      console.error('Error in auto force generate:', error);
      toast.error('Auto-generate failed');
    }
  };

  // Toggle Auto Force Generate
  const handleToggleAutoForce = () => {
    if (!autoForceActive) {
      if (!config.selected_assets || config.selected_assets.length === 0) {
        toast.error('Please select at least one asset first');
        return;
      }
      // Start auto force generate
      setAutoForceActive(true);
      setAutoForceCountdown(autoForceInterval);
      toast.success(`🚀 Auto force generate started (every ${autoForceInterval}s)`);
    } else {
      // Stop auto force generate
      setAutoForceActive(false);
      setAutoForceCountdown(0);
      toast.info('⏸️ Auto force generate stopped');
    }
  };

  // Toggle Candle Sync
  const handleCandleSyncToggle = async () => {
    try {
      const endpoint = candleSyncEnabled 
        ? `${API}/bot/candle-sync/disable` 
        : `${API}/bot/candle-sync/enable`;
      
      const response = await axios.post(endpoint);
      
      if (response.data.status === 'success') {
        setCandleSyncEnabled(!candleSyncEnabled);
        toast.success(response.data.message);
        fetchCandleSyncStatus();
      }
    } catch (error) {
      console.error('Error toggling candle sync:', error);
      toast.error('Failed to toggle candle sync');
    }
  };

  // Update configuration helper
  const updateConfiguration = async (updates) => {
    try {
      // Normalize enum values to lowercase for backend
      const normalizedUpdates = { ...updates };
      
      // Convert trading_mode "real" to "live" for backend
      if (normalizedUpdates.trading_mode === 'real') {
        normalizedUpdates.trading_mode = 'live';
      }
      
      // Ensure all enum arrays are lowercase
      if (normalizedUpdates.active_strategies) {
        normalizedUpdates.active_strategies = normalizedUpdates.active_strategies.map(s => 
          typeof s === 'string' ? s.toLowerCase() : s
        );
      }
      if (normalizedUpdates.target_assets) {
        normalizedUpdates.target_assets = normalizedUpdates.target_assets.map(a => 
          typeof a === 'string' ? a.toLowerCase() : a
        );
      }
      
      // Ensure all required fields are present with defaults
      const fullConfig = {
        trading_mode: 'demo',
        selected_expirations: ['1m'],
        active_strategies: ['hybrid'],
        target_assets: ['forex'],
        risk_tolerance: 'medium',
        max_stake_per_trade: 10.0,
        max_daily_trades: 50,
        min_probability_threshold: 85.0,
        auto_trading_enabled: false,
        sound_alerts_enabled: true,
        popup_notifications: true,
        invert_signals: false,
        ...config,  // Current config
        ...normalizedUpdates  // New updates
      };
      
      await axios.put(`${API}/config`, fullConfig);
      setConfig({ ...config, ...updates }); // Use original updates for frontend state
      return true;
    } catch (error) {
      console.error('Error updating configuration:', error);
      toast.error('Failed to update configuration');
      return false;
    }
  };

  // Update expiration configuration
  const handleExpirationChange = async (newExpirations) => {
    const success = await updateConfiguration({ selected_expirations: newExpirations });
    if (success) toast.success('Expirations updated');
  };

  // Handle account type change
  const handleAccountTypeChange = async (accountType) => {
    const success = await updateConfiguration({ 
      trading_mode: accountType
      // Do NOT change invert_signals - keep it independent
    });
    if (success) {
      const mode = accountType === 'demo' ? 'DEMO' : 'REAL';
      const invertStatus = config.invert_signals ? '(Signals Inverted)' : '(Normal Signals)';
      toast.success(`Switched to ${mode} account ${invertStatus}`);
    }
  };

  // Handle toggle switches
  const handleToggleInvertSignals = async (enabled) => {
    const success = await updateConfiguration({ invert_signals: enabled });
    if (success) {
      toast.success(enabled ? 'Signals inverted' : 'Normal signals');
    }
  };

  const handleTogglePopupNotifications = async (enabled) => {
    const success = await updateConfiguration({ popup_notifications: enabled });
    if (success) {
      toast.success(enabled ? 'Popup notifications enabled' : 'Popup notifications disabled');
    }
  };

  const handleToggleSoundAlerts = async (enabled) => {
    const success = await updateConfiguration({ sound_alerts_enabled: enabled });
    if (success) {
      toast.success(enabled ? 'Sound alerts enabled' : 'Sound alerts disabled');
    }
  };

  // Format next candle time
  const formatNextCandleTime = (timeframe) => {
    const nextTime = candleSyncStatus.next_candle_times?.[timeframe];
    if (!nextTime) return 'N/A';
    
    try {
      const date = new Date(nextTime);
      return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
      });
    } catch {
      return 'N/A';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      {/* Top Bar: Account Type Selection */}
      <div className="mb-4">
        <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Label className="text-white font-semibold">Account Type:</Label>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={config.trading_mode === 'demo' ? "default" : "outline"}
                  onClick={() => handleAccountTypeChange('demo')}
                  className={config.trading_mode === 'demo'
                    ? "bg-blue-600 hover:bg-blue-700"
                    : "border-blue-500/50 text-blue-300"}
                >
                  🎮 Demo Account
                </Button>
                <Button
                  size="sm"
                  variant={config.trading_mode === 'real' ? "default" : "outline"}
                  onClick={() => handleAccountTypeChange('real')}
                  className={config.trading_mode === 'real'
                    ? "bg-green-600 hover:bg-green-700"
                    : "border-green-500/50 text-green-300"}
                >
                  💰 Real Account
                </Button>
              </div>
              {config.trading_mode === 'demo' && (
                <Badge variant="outline" className="text-blue-400 border-blue-500/50">
                  Signals Inverted by Default
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-4">
              {/* Invert Signals Toggle */}
              <div className="flex items-center gap-2">
                <Label className="text-sm text-gray-300">Invert Signals:</Label>
                <Switch
                  checked={config.invert_signals}
                  onCheckedChange={handleToggleInvertSignals}
                />
                <span className={`text-xs font-semibold ${config.invert_signals ? 'text-blue-400' : 'text-gray-400'}`}>
                  {config.invert_signals ? 'ON' : 'OFF'}
                </span>
              </div>

              {/* Popup Notifications Toggle */}
              <div className="flex items-center gap-2">
                <Label className="text-sm text-gray-300">Popup Notifications:</Label>
                <Switch
                  checked={config.popup_notifications}
                  onCheckedChange={handleTogglePopupNotifications}
                />
                <span className={`text-xs font-semibold ${config.popup_notifications ? 'text-green-400' : 'text-gray-400'}`}>
                  {config.popup_notifications ? 'ON' : 'OFF'}
                </span>
              </div>

              {/* Sound Alerts Toggle */}
              <div className="flex items-center gap-2">
                <Label className="text-sm text-gray-300">Sound Alerts:</Label>
                <Switch
                  checked={config.sound_alerts}
                  onCheckedChange={handleToggleSoundAlerts}
                />
                <span className={`text-xs font-semibold ${config.sound_alerts ? 'text-yellow-400' : 'text-gray-400'}`}>
                  {config.sound_alerts ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Header: Trading Configuration */}
      <div className="mb-6 space-y-4">
        <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Target className="w-6 h-6 text-purple-400" />
              <h2 className="text-2xl font-bold text-white">Trading Configuration</h2>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={botStatus?.is_running ? "success" : "secondary"}>
                {botStatus?.is_running ? "Bot Active" : "Bot Stopped"}
              </Badge>
              <Badge variant="outline" className={config.trading_mode === 'demo' ? 'text-blue-400' : 'text-green-400'}>
                {config.trading_mode === 'demo' ? '🎮 Demo Mode' : '💰 Real Mode'}
              </Badge>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Trading Expirations */}
            <div className="space-y-2">
              <Label className="text-purple-300">Trading Expirations / Timeframes</Label>
              <div className="flex flex-wrap gap-2">
                {['5s', '15s', '30s', '1m', '2m', '3m', '5m', '15m', '30m', '1h'].map(exp => (
                  <Button
                    key={exp}
                    size="sm"
                    variant={config.selected_expirations.includes(exp) ? "default" : "outline"}
                    onClick={() => {
                      const newExp = config.selected_expirations.includes(exp)
                        ? config.selected_expirations.filter(e => e !== exp)
                        : [...config.selected_expirations, exp];
                      handleExpirationChange(newExp);
                    }}
                    className={config.selected_expirations.includes(exp) 
                      ? "bg-purple-600 hover:bg-purple-700" 
                      : "border-purple-500/50 text-purple-300"}
                  >
                    {exp}
                  </Button>
                ))}
              </div>
              {config.selected_expirations.includes('5s') && (
                <div className="mt-2 text-xs text-blue-300 bg-blue-900/20 border border-blue-600/30 rounded px-2 py-1">
                  ⏳ Note: 5-second signals include 10-second built-in latency for stability
                </div>
              )}
            </div>

            {/* Market Assets Selection */}
            <div className="space-y-2">
              <Label className="text-purple-300">Market Assets</Label>
              <MarketAssetSelector 
                config={config}
                setConfig={setConfig}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Left: Signal Controls & Generation */}
        <Card className="lg:col-span-1 bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center gap-3 mb-6">
            <Zap className="w-6 h-6 text-yellow-400" />
            <h3 className="text-xl font-bold text-white">Signal Generation</h3>
          </div>

          <div className="space-y-4">
            {/* Manual Signal Generation */}
            <div className="space-y-3">
              <Label className="text-purple-300 font-semibold">Manual Generation</Label>
              
              <Button
                onClick={handleSingleGenerate}
                disabled={isGenerating || autoForceActive}
                className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
              >
                {isGenerating ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 mr-2" />
                    Force Generate Signal
                  </>
                )}
              </Button>
            </div>

            <div className="border-t border-purple-500/30 pt-4" />

            {/* Auto Force Generate */}
            <div className="space-y-3">
              <Label className="text-purple-300 font-semibold">Auto Force Generate</Label>
              
              <div className="space-y-2">
                <Label className="text-sm text-gray-300">Generate Every:</Label>
                <Select 
                  value={autoForceInterval.toString()} 
                  onValueChange={(val) => setAutoForceInterval(parseInt(val))}
                  disabled={autoForceActive}
                >
                  <SelectTrigger className="w-full bg-slate-700/50 border-purple-500/30 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 seconds</SelectItem>
                    <SelectItem value="60">1 minute</SelectItem>
                    <SelectItem value="120">2 minutes</SelectItem>
                    <SelectItem value="180">3 minutes</SelectItem>
                    <SelectItem value="300">5 minutes</SelectItem>
                    <SelectItem value="600">10 minutes</SelectItem>
                    <SelectItem value="900">15 minutes</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {autoForceActive && (
                <div className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-blue-300">Next signal in:</span>
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-blue-400 animate-pulse" />
                      <span className="text-lg font-bold text-blue-200 font-mono">
                        {Math.floor(autoForceCountdown / 60)}:{String(autoForceCountdown % 60).padStart(2, '0')}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <Button
                onClick={handleToggleAutoForce}
                className={`w-full ${autoForceActive 
                  ? 'bg-red-600 hover:bg-red-700' 
                  : 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700'}`}
              >
                {autoForceActive ? (
                  <>
                    <Square className="w-4 h-4 mr-2" />
                    Stop Auto Generate
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Start Auto Generate
                  </>
                )}
              </Button>
            </div>

            <div className="border-t border-purple-500/30 pt-4" />

            {/* Enhanced Auto-Generate */}
            <div className="space-y-3">
              <Label className="text-purple-300 font-semibold">Auto-Generate Settings</Label>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-gray-300">Scan All Assets</Label>
                  <Switch
                    checked={enhancedSettings.scanAllAssets}
                    onCheckedChange={(checked) => 
                      setEnhancedSettings(prev => ({ ...prev, scanAllAssets: checked }))
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-sm text-gray-300">Min Payout: {enhancedSettings.minPayout}%</Label>
                  <input
                    type="range"
                    min="70"
                    max="95"
                    value={enhancedSettings.minPayout}
                    onChange={(e) => setEnhancedSettings(prev => ({ ...prev, minPayout: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-sm text-gray-300">Min Accuracy: {enhancedSettings.minAccuracy}%</Label>
                  <input
                    type="range"
                    min="65"
                    max="95"
                    value={enhancedSettings.minAccuracy}
                    onChange={(e) => setEnhancedSettings(prev => ({ ...prev, minAccuracy: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-sm text-gray-300">Max Signals: {enhancedSettings.maxSignals}</Label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={enhancedSettings.maxSignals}
                    onChange={(e) => setEnhancedSettings(prev => ({ ...prev, maxSignals: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                </div>
              </div>

              <Button
                onClick={handleEnhancedAutoGenerate}
                disabled={isGenerating}
                className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
              >
                {isGenerating ? 'Generating...' : 'Auto-Generate Signals'}
              </Button>
            </div>
          </div>
        </Card>

        {/* Right: Recent Signals List */}
        <Card className="lg:col-span-2 bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-6 h-6 text-green-400" />
              <h3 className="text-xl font-bold text-white">Recent Signals</h3>
              <Badge variant="outline" className="text-purple-300">
                {liveSignals.length} / 10
              </Badge>
            </div>
            
            <Button
              onClick={handleClearAllSignals}
              variant="destructive"
              size="sm"
              disabled={liveSignals.length === 0}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Clear All
            </Button>
          </div>

          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {liveSignals.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No signals generated yet</p>
                <p className="text-sm">Generate signals using the controls on the left</p>
              </div>
            ) : (
              liveSignals.map((signal, index) => (
                <ImprovedSignalPopup
                  key={signal.id || index}
                  signal={signal}
                  onClose={() => {
                    setLiveSignals(prev => prev.filter((_, i) => i !== index));
                  }}
                />
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Bottom Section: Candle Sync, Strategy Display & Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Candle Synchronization */}
        <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Clock className="w-6 h-6 text-blue-400" />
              <h3 className="text-lg font-bold text-white">Pocket Option Candle Sync</h3>
            </div>
            
            <div className="flex items-center gap-3">
              <Badge variant={candleSyncEnabled ? "success" : "secondary"}>
                {candleSyncEnabled ? "SYNCED" : "DISABLED"}
              </Badge>
              <Switch
                checked={candleSyncEnabled}
                onCheckedChange={handleCandleSyncToggle}
              />
            </div>
          </div>

          {candleSyncEnabled && (
            <div className="space-y-2">
              <Label className="text-sm text-gray-300">Next Candle Times:</Label>
              <div className="grid grid-cols-2 gap-2">
                {['5s', '15s', '30s', '1m'].map(tf => (
                  <div key={tf} className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">{tf}:</span>
                    <span className="text-purple-300 font-mono">{formatNextCandleTime(tf)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Strategy Verification Display */}
        <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center gap-3 mb-4">
            <Settings className="w-6 h-6 text-purple-400" />
            <h3 className="text-lg font-bold text-white">Current Strategy</h3>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Strategy:</span>
              <span className="text-purple-300 font-semibold">
                {config.selected_strategy || 'Default'}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Timeframe:</span>
              <Badge variant="outline" className="text-purple-300">
                {config.selected_timeframe || '1m'}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Min Accuracy:</span>
              <Badge variant="outline" className="text-green-400">
                {config.min_probability_threshold || 85}%
              </Badge>
            </div>

            {performanceData && (
              <div className="flex items-center justify-between pt-2 border-t border-purple-500/30">
                <span className="text-gray-400">Today's Win Rate:</span>
                <Badge variant={performanceData.win_rate >= 70 ? "success" : "secondary"}>
                  {performanceData.win_rate?.toFixed(1) || 0}%
                </Badge>
              </div>
            )}
          </div>
        </Card>

        {/* Signal Timing/Latency Adjustment */}
        <div className="lg:col-span-1">
          <LatencyAdjustment compact={true} />
        </div>
      </div>
    </div>
  );
};

export default DashboardRestructured;
