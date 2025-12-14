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
    selected_timeframe: '1m'
  });
  
  // Signal Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [autoGenerateActive, setAutoGenerateActive] = useState(false);
  const [autoGenerateMode, setAutoGenerateMode] = useState('selected'); // 'selected' or 'scan'
  
  // Enhanced Auto-Generate Settings
  const [enhancedSettings, setEnhancedSettings] = useState({
    scanAllAssets: false,
    minPayout: 80,
    minAccuracy: 75,
    maxSignals: 5
  });
  
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
    };
  }, []);

  const fetchConfiguration = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setConfig(prev => ({
        ...prev,
        ...response.data,
        selected_strategy: response.data.selected_strategy || '',
        selected_timeframe: response.data.selected_timeframe || '1m'
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

  // Auto-clear when signals exceed 10
  useEffect(() => {
    if (liveSignals.length > 10) {
      const signalsToKeep = liveSignals.slice(0, 10);
      setLiveSignals(signalsToKeep);
      toast.info('Auto-cleared old signals (keeping latest 10)');
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
      const response = await axios.post(`${API}/signals/auto-generate/enhanced`, {
        scan_all_assets: enhancedSettings.scanAllAssets,
        selected_assets: !enhancedSettings.scanAllAssets ? config.selected_assets : null,
        min_payout: enhancedSettings.minPayout,
        min_accuracy: enhancedSettings.minAccuracy,
        max_signals: enhancedSettings.maxSignals
      });

      if (response.data.success && response.data.signals.length > 0) {
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

  // Update expiration configuration
  const handleExpirationChange = async (newExpirations) => {
    try {
      await axios.put(`${API}/config`, {
        ...config,
        selected_expirations: newExpirations
      });
      setConfig(prev => ({ ...prev, selected_expirations: newExpirations }));
      toast.success('Expirations updated');
    } catch (error) {
      console.error('Error updating expirations:', error);
      toast.error('Failed to update expirations');
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
      {/* Header: Trading Configuration */}
      <div className="mb-6 space-y-4">
        <Card className="bg-slate-800/50 border-purple-500/30 backdrop-blur-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Target className="w-6 h-6 text-purple-400" />
              <h2 className="text-2xl font-bold text-white">Trading Configuration</h2>
            </div>
            <Badge variant={botStatus?.is_running ? "success" : "secondary"}>
              {botStatus?.is_running ? "Bot Active" : "Bot Stopped"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Trading Expirations */}
            <div className="space-y-2">
              <Label className="text-purple-300">Trading Expirations</Label>
              <div className="flex flex-wrap gap-2">
                {['30s', '1m', '2m', '3m', '5m', '15m'].map(exp => (
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
                disabled={isGenerating}
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

      {/* Bottom Section: Candle Sync & Strategy Display */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
      </div>
    </div>
  );
};

export default DashboardRestructured;
