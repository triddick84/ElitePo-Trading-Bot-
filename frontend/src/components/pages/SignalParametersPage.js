import React, { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Slider } from '../ui/slider';
import { Badge } from '../ui/badge';
import { toast } from 'sonner';
import { 
  Target, Zap, Volume2, RotateCcw, Clock, TrendingUp, 
  AlertTriangle, Settings2, Activity, Play, Pause 
} from 'lucide-react';

const SignalParametersPage = ({ botStatus, onBotStatusChange }) => {
  const [config, setConfig] = useState({
    selected_assets: ['EURUSD_regular', 'EURUSD_OTC'],
    selected_timeframes: ['5s'],
    min_probability_threshold: 85,
    auto_trading_enabled: false,
    invert_signals: false,
    sound_alerts_enabled: true,
    popup_notifications: true,
    max_stake_per_trade: 10.0
  });

  const [isGeneratingSignal, setIsGeneratingSignal] = useState(false);
  const [autoGenerationActive, setAutoGenerationActive] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Pocket Option compatible timeframes (ultra-short focus)
  const availableTimeframes = [
    { value: '5s', label: '5 Seconds', description: 'Ultra-fast scalping', color: 'red' },
    { value: '15s', label: '15 Seconds', description: 'Quick momentum', color: 'orange' },
    { value: '30s', label: '30 Seconds', description: 'Short-term trends', color: 'yellow' },
    { value: '1m', label: '1 Minute', description: 'Micro movements', color: 'green' },
    { value: '2m', label: '2 Minutes', description: 'Pattern confirmation', color: 'blue' },
    { value: '3m', label: '3 Minutes', description: 'Trend validation', color: 'purple' },
    { value: '5m', label: '5 Minutes', description: 'Standard analysis', color: 'pink' }
  ];

  // Popular Pocket Option assets
  const availableAssets = [
    { 
      category: 'Major Forex Pairs', 
      assets: [
        'EURUSD_regular', 'EURUSD_OTC', 'GBPUSD_regular', 'GBPUSD_OTC',
        'USDJPY_regular', 'USDJPY_OTC', 'AUDUSD_regular', 'AUDUSD_OTC'
      ]
    },
    { 
      category: 'Crypto Currencies', 
      assets: [
        'BTCUSD_regular', 'BTCUSD_OTC', 'ETHUSD_regular', 'ETHUSD_OTC',
        'ADAUSD_regular', 'ADAUSD_OTC', 'XRPUSD_regular', 'XRPUSD_OTC'
      ]
    },
    { 
      category: 'Commodities', 
      assets: [
        'GOLD_regular', 'GOLD_OTC', 'SILVER_regular', 'SILVER_OTC',
        'OIL_regular', 'OIL_OTC'
      ]
    }
  ];

  useEffect(() => {
    fetchCurrentConfig();
    fetchAutoGenerationStatus();
  }, []);

  const fetchCurrentConfig = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/config`);
      if (response.ok) {
        const fetchedConfig = await response.json();
        setConfig(prev => ({
          ...prev,
          ...fetchedConfig,
          invert_signals: fetchedConfig.invert_signals ?? false,
          sound_alerts_enabled: fetchedConfig.sound_alerts_enabled ?? true,
          popup_notifications: fetchedConfig.popup_notifications ?? true
        }));
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const fetchAutoGenerationStatus = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/auto-generate/status`);
      if (response.ok) {
        const result = await response.json();
        setAutoGenerationActive(result.auto_generation_active);
      }
    } catch (error) {
      console.error('Error fetching auto generation status:', error);
    }
  };

  const handleConfigChange = (key, value) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleAssetToggle = (asset) => {
    setConfig(prev => ({
      ...prev,
      selected_assets: prev.selected_assets.includes(asset)
        ? prev.selected_assets.filter(a => a !== asset)
        : [...prev.selected_assets, asset]
    }));
  };

  const handleTimeframeToggle = (timeframe) => {
    setConfig(prev => ({
      ...prev,
      selected_timeframes: prev.selected_timeframes.includes(timeframe)
        ? prev.selected_timeframes.filter(t => t !== timeframe)
        : [...prev.selected_timeframes, timeframe]
    }));
  };

  const saveConfiguration = async () => {
    setIsSaving(true);
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        toast.success('✅ Configuration saved! Settings synchronized with Pocket Option timing.');
        await fetchCurrentConfig();
      } else {
        toast.error('❌ Failed to save configuration');
      }
    } catch (error) {
      console.error('Error saving config:', error);
      toast.error('❌ Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const handleForceGenerateSignal = async () => {
    setIsGeneratingSignal(true);
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/force-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success && result.signals && result.signals.length > 0) {
        const regularSignal = result.regular_signal;
        const otcSignal = result.otc_signal;
        
        if (regularSignal && otcSignal) {
          toast.success(
            `🚀 ULTRA-SHORT SIGNALS GENERATED: 
            📊 Regular: ${regularSignal.direction} ${regularSignal.symbol} (${regularSignal.probability}%) - ${regularSignal.timeframe}
            📈 OTC: ${otcSignal.direction} ${otcSignal.symbol} (${otcSignal.probability}%) - ${otcSignal.timeframe}
            ⚡ Pocket Option Synchronized Timing!`,
            { duration: 12000 }
          );
        }
      } else {
        toast.warning(result.message || 'No signals generated for current market conditions');
      }
    } catch (error) {
      console.error('Error force generating signal:', error);
      toast.error('Failed to generate signal. Please try again.');
    } finally {
      setIsGeneratingSignal(false);
    }
  };

  const toggleAutoGeneration = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const endpoint = autoGenerationActive 
        ? `${BACKEND_URL}/api/signals/auto-generate/stop`
        : `${BACKEND_URL}/api/signals/auto-generate/start`;
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success) {
        setAutoGenerationActive(!autoGenerationActive);
        toast.success(result.message);
      } else {
        toast.error(result.message || 'Failed to toggle auto generation');
      }
    } catch (error) {
      console.error('Error toggling auto generation:', error);
      toast.error('Failed to toggle auto generation');
    }
  };

  const getThresholdColor = () => {
    if (config.min_probability_threshold >= 90) return 'text-green-400 bg-green-500/20 border-green-400';
    if (config.min_probability_threshold >= 75) return 'text-yellow-400 bg-yellow-500/20 border-yellow-400';
    return 'text-red-400 bg-red-500/20 border-red-400';
  };

  const getThresholdStrategy = () => {
    if (config.min_probability_threshold >= 90) return 'Conservative';
    if (config.min_probability_threshold >= 75) return 'Balanced';
    return 'Aggressive';
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Signal Parameters</h2>
          <p className="text-slate-400">Configure market selection, timeframes, and signal generation settings</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-cyan-500 rounded-full animate-pulse"></div>
            <span className="text-cyan-400 text-sm">Ultra-Short Timeframes Active</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Market & Asset Selection */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <div className="flex items-center space-x-3 mb-6">
            <Target className="w-6 h-6 text-cyan-400" />
            <h3 className="text-xl font-semibold text-white">Market & Asset Selection</h3>
          </div>

          <div className="space-y-6">
            {availableAssets.map((category) => (
              <div key={category.category}>
                <h4 className="font-semibold text-slate-300 mb-3">{category.category}</h4>
                <div className="grid grid-cols-2 gap-2">
                  {category.assets.map((asset) => {
                    const isSelected = config.selected_assets.includes(asset);
                    const isOTC = asset.includes('OTC');
                    
                    return (
                      <button
                        key={asset}
                        onClick={() => handleAssetToggle(asset)}
                        className={`
                          p-3 rounded-lg border transition-all text-left
                          ${isSelected 
                            ? isOTC 
                              ? 'bg-purple-500/20 border-purple-500/50 text-purple-300' 
                              : 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                            : 'bg-slate-800/50 border-slate-600/50 text-slate-400 hover:border-slate-500/50'
                          }
                        `}
                      >
                        <div className="font-medium text-sm">
                          {asset.replace('_regular', '').replace('_OTC', '')}
                        </div>
                        <div className="text-xs opacity-75">
                          {isOTC ? 'OTC Market' : 'Regular Market'}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Timeframe Selection */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <div className="flex items-center space-x-3 mb-6">
            <Clock className="w-6 h-6 text-cyan-400" />
            <h3 className="text-xl font-semibold text-white">Ultra-Short Timeframes</h3>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3">
              {availableTimeframes.map((tf) => {
                const isSelected = config.selected_timeframes.includes(tf.value);
                
                return (
                  <button
                    key={tf.value}
                    onClick={() => handleTimeframeToggle(tf.value)}
                    className={`
                      p-4 rounded-lg border transition-all text-left
                      ${isSelected 
                        ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300' 
                        : 'bg-slate-800/50 border-slate-600/50 text-slate-400 hover:border-slate-500/50'
                      }
                    `}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-semibold">{tf.label}</div>
                        <div className="text-sm opacity-75">{tf.description}</div>
                      </div>
                      {isSelected && (
                        <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30">
                          Active
                        </Badge>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {config.selected_timeframes.length > 0 && (
              <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
                <div className="text-cyan-400 font-medium text-sm">Selected Timeframes</div>
                <div className="text-slate-300 text-xs mt-1">
                  Signals will be synchronized with Pocket Option {config.selected_timeframes.join(', ')} candle formation timing
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signal Generation Controls */}
        <Card className="p-6 glass-dark border-emerald-500/30">
          <div className="flex items-center space-x-3 mb-6">
            <Zap className="w-6 h-6 text-emerald-400" />
            <h3 className="text-xl font-semibold text-white">Signal Generation</h3>
          </div>

          <div className="space-y-6">
            {/* Force Generate Signal */}
            <Button
              onClick={handleForceGenerateSignal}
              disabled={isGeneratingSignal || !botStatus?.is_running}
              className="w-full bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-300 border border-purple-500/30 hover:from-purple-500/30 hover:to-pink-500/30 disabled:opacity-50 font-semibold py-4"
            >
              {isGeneratingSignal ? '⚡ Generating Ultra-Short Signals...' : '🚀 FORCE GENERATE SIGNALS'}
            </Button>

            {/* Auto Generation Toggle */}
            <Button
              onClick={toggleAutoGeneration}
              disabled={!botStatus?.is_running}
              className={`w-full border font-semibold py-4 ${
                autoGenerationActive 
                  ? 'bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30' 
                  : 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30'
              } disabled:opacity-50`}
            >
              {autoGenerationActive ? (
                <>
                  <Pause className="w-4 h-4 mr-2" />
                  Stop Auto Generation
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Auto Generation
                </>
              )}
            </Button>

            {!botStatus?.is_running && (
              <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-5 h-5 text-yellow-400" />
                  <span className="text-yellow-400 font-medium">Bot Not Running</span>
                </div>
                <p className="text-slate-300 text-sm mt-1">
                  Start the trading bot first to enable signal generation.
                </p>
              </div>
            )}
          </div>
        </Card>

        {/* Threshold & Settings */}
        <Card className="p-6 glass-dark border-slate-700/50">
          <div className="flex items-center space-x-3 mb-6">
            <Settings2 className="w-6 h-6 text-cyan-400" />
            <h3 className="text-xl font-semibold text-white">Signal Settings</h3>
          </div>

          <div className="space-y-6">
            {/* Probability Threshold */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-slate-300 font-medium">Signal Probability Threshold</Label>
                <div className={`text-lg font-bold px-3 py-1 rounded-lg border ${getThresholdColor()}`}>
                  {config.min_probability_threshold}%
                </div>
              </div>
              
              <Slider
                value={[config.min_probability_threshold]}
                onValueChange={(value) => handleConfigChange('min_probability_threshold', value[0])}
                min={50}
                max={99}
                step={1}
                className="w-full"
              />
              
              <div className="flex justify-between text-xs text-slate-400">
                <span>50%</span>
                <span>70%</span>
                <span>85%</span>
                <span>99%</span>
              </div>
              
              <div className={`p-3 rounded-lg border border-slate-600/30 bg-slate-800/30`}>
                <div className="flex items-center space-x-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  <span className="text-slate-300 font-medium">{getThresholdStrategy()} Strategy</span>
                </div>
                <p className="text-slate-400 text-sm">
                  {config.min_probability_threshold >= 90 ? 
                    'Ultra-high accuracy signals with fewer opportunities. Best for consistent profits.' :
                   config.min_probability_threshold >= 75 ? 
                    'Balanced approach with good accuracy and moderate signal frequency.' :
                    'More signals with higher risk. Use only with proper risk management.'}
                </p>
              </div>
            </div>

            {/* Alert Settings */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-slate-300 font-medium">Sound Alerts</Label>
                  <p className="text-slate-500 text-sm">Audio notifications for new signals</p>
                </div>
                <Switch 
                  checked={config.sound_alerts_enabled}
                  onCheckedChange={(checked) => handleConfigChange('sound_alerts_enabled', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-slate-300 font-medium">Popup Notifications</Label>
                  <p className="text-slate-500 text-sm">Visual popup with countdown timers</p>
                </div>
                <Switch 
                  checked={config.popup_notifications}
                  onCheckedChange={(checked) => handleConfigChange('popup_notifications', checked)}
                />
              </div>

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
            </div>
          </div>
        </Card>
      </div>

      {/* Save Configuration */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Configuration Status</h3>
            <p className="text-slate-400 text-sm">
              {config.selected_assets.length} assets selected • {config.selected_timeframes.length} timeframes active
            </p>
          </div>
          
          <Button 
            onClick={saveConfiguration}
            disabled={isSaving}
            className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 btn-glow disabled:opacity-50 px-8"
          >
            {isSaving ? '⏳ Saving...' : '💾 Save Configuration'}
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default SignalParametersPage;