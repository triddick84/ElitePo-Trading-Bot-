import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { toast } from 'sonner';
import AssetSelector from './AssetSelector';

const LiveSignalsDisplay = ({ botStatus, onSignalExecute }) => {
  const [liveSignals, setLiveSignals] = useState([]);
  const [recentSignals, setRecentSignals] = useState([]);
  const [notificationSettings, setNotificationSettings] = useState({
    popupEnabled: true,
    soundEnabled: true,
    autoRefresh: true,
    signalInversion: false
  });
  const [selectedAssets, setSelectedAssets] = useState(['EURUSD_regular', 'BTCUSD_regular']);
  const [selectedTimeframes, setSelectedTimeframes] = useState(['1m', '5m']);
  const [previousSignalsCount, setPreviousSignalsCount] = useState(0);
  const [isGeneratingSignal, setIsGeneratingSignal] = useState(false);
  const [autoGenerationActive, setAutoGenerationActive] = useState(false);
  const [currentThreshold, setCurrentThreshold] = useState(85);

  // Sound notification function
  const playNotificationSound = () => {
    if (!notificationSettings.soundEnabled) return;
    
    // Create an audio context and play a notification sound
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      // Configure the tone (notification beep)
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime); // High pitch
      oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1); // Lower pitch
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.5);
    } catch (error) {
      console.warn('Could not play notification sound:', error);
    }
  };

  useEffect(() => {
    if (botStatus?.is_running && notificationSettings.autoRefresh) {
      const interval = setInterval(fetchLiveSignals, 3000);
      return () => clearInterval(interval);
    }
  }, [botStatus?.is_running, notificationSettings.autoRefresh]);

  useEffect(() => {
    // Fetch auto generation status and current config on component mount
    fetchAutoGenerationStatus();
    fetchCurrentConfig();
  }, []);

  const fetchLiveSignals = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/active`);
      const signals = await response.json();
      
      // Apply signal inversion if enabled
      const processedSignals = notificationSettings.signalInversion 
        ? signals.map(signal => ({
            ...signal,
            direction: signal.direction === 'BUY' ? 'SELL' : 'BUY',
            original_direction: signal.direction
          }))
        : signals;

      const highProbabilitySignals = processedSignals.filter(s => s.probability >= currentThreshold);
      setLiveSignals(highProbabilitySignals);
      
      // Check for new signals and trigger notifications
      if (highProbabilitySignals.length > previousSignalsCount) {
        const newSignalsCount = highProbabilitySignals.length - previousSignalsCount;
        
        // Play sound notification for new signals
        if (newSignalsCount > 0 && notificationSettings.soundEnabled) {
          playNotificationSound();
        }
        
        // Show popup notification if enabled
        if (newSignalsCount > 0 && notificationSettings.popupEnabled) {
          const latestSignal = highProbabilitySignals[0];
          toast.success(`🚀 New ${latestSignal.direction} signal for ${latestSignal.symbol} (${latestSignal.probability}%)`);
        }
      }
      
      setPreviousSignalsCount(highProbabilitySignals.length);
      
      // Update recent signals (last 10)
      if (processedSignals.length > 0) {
        setRecentSignals(prev => {
          const newSignals = processedSignals.filter(
            signal => !prev.some(existing => existing.id === signal.id)
          );
          return [...newSignals, ...prev].slice(0, 10);
        });
      }
    } catch (error) {
      console.error('Error fetching live signals:', error);
    }
  };

  const handleAssetSelectionChange = (assets, timeframes) => {
    setSelectedAssets(assets);
    setSelectedTimeframes(timeframes);
    
    // Send selection to backend
    updateBotConfiguration(assets, timeframes);
  };

  const updateBotConfiguration = async (assets, timeframes) => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      await fetch(`${BACKEND_URL}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_assets: assets,
          selected_timeframes: timeframes,
          trading_mode: 'demo',
          active_strategies: ['hybrid'],
          target_assets: ['forex', 'crypto'],
          risk_tolerance: 'medium',
          max_stake_per_trade: 10.0,
          max_daily_trades: 50,
          min_probability_threshold: 95.0,
          auto_trading_enabled: false
        })
      });
      
      toast.success('Asset selection updated successfully!');
    } catch (error) {
      console.error('Error updating configuration:', error);
      toast.error('Failed to update asset selection');
    }
  };

  const handleNotificationToggle = (setting, value) => {
    setNotificationSettings(prev => ({
      ...prev,
      [setting]: value
    }));

    if (setting === 'signalInversion') {
      toast.success(value ? 'Signal inversion enabled - BUY signals will show as SELL' : 'Signal inversion disabled');
    }
  };

  const handleSingleSignalGeneration = async () => {
    setIsGeneratingSignal(true);
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/generate/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success && result.signal) {
        toast.success(`🎯 Signal generated: ${result.signal.direction} ${result.signal.symbol} (${result.signal.probability}%)`);
        // Refresh signals to show the new one
        await fetchLiveSignals();
      } else {
        toast.warning(result.message || 'No high-probability signal found for current market conditions');
      }
    } catch (error) {
      console.error('Error generating single signal:', error);
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
      toast.error('Failed to toggle auto generation. Please try again.');
    }
  };

  // Fetch auto generation status on component mount
  const fetchAutoGenerationStatus = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/signals/auto-generate/status`);
      const result = await response.json();
      setAutoGenerationActive(result.auto_generation_active);
    } catch (error) {
      console.error('Error fetching auto generation status:', error);
    }
  };

  // Fetch current configuration to get threshold
  const fetchCurrentConfig = async () => {
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/api/config`);
      const config = await response.json();
      setCurrentThreshold(config.min_probability_threshold || 85);
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const getSignalColor = (direction) => {
    const isInverted = notificationSettings.signalInversion;
    const displayDirection = direction;
    
    return displayDirection === 'BUY' || displayDirection === 'CALL' 
      ? 'bg-green-500/20 text-green-400 border-green-500/30'
      : 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const SignalCard = ({ signal, isLive = false }) => (
    <Card className={`p-4 glass-dark border-slate-700/50 ${isLive ? 'border-emerald-500/30 animate-pulse' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Badge className={getSignalColor(signal.direction)}>
            {signal.direction === 'BUY' ? '📈 BUY' : '📉 SELL'}
            {notificationSettings.signalInversion && signal.original_direction && (
              <span className="ml-1 text-xs opacity-70">
                (Inverted from {signal.original_direction})
              </span>
            )}
          </Badge>
          <span className="text-white font-semibold">{signal.symbol}</span>
        </div>
        {isLive && (
          <div className="flex items-center space-x-1">
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-ping"></div>
            <span className="text-emerald-400 text-sm">LIVE</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-slate-400">Entry Price</p>
          <p className="text-white font-mono">${signal.entry_price}</p>
        </div>
        <div>
          <p className="text-slate-400">Probability</p>
          <p className="text-purple-400 font-bold">{signal.probability}%</p>
        </div>
        <div>
          <p className="text-slate-400">Expiration</p>
          <p className="text-white">{signal.expiration_minutes}m</p>
        </div>
        <div>
          <p className="text-slate-400">Time</p>
          <p className="text-slate-300">{formatTime(signal.timestamp)}</p>
        </div>
      </div>

      {isLive && (
        <div className="mt-3 pt-3 border-t border-slate-700/50">
          <Button
            onClick={() => onSignalExecute?.(signal)}
            className={`w-full ${
              signal.direction === 'BUY'
                ? 'bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30'
                : 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
            }`}
          >
            Execute {signal.direction}
          </Button>
        </div>
      )}
    </Card>
  );

  return (
    <div className="space-y-6" data-testid="live-signals-display">
      {/* Manual Signal Generation Controls */}
      <Card className="p-6 glass-dark border-emerald-500/30">
        <h3 className="text-xl font-semibold text-white mb-6">Manual Signal Generation</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <Button
            onClick={handleSingleSignalGeneration}
            disabled={!botStatus?.is_running || isGeneratingSignal}
            className="bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30 disabled:opacity-50"
          >
            {isGeneratingSignal ? '⏳ Generating...' : '🎯 Generate Single Signal'}
          </Button>
          
          <Button
            onClick={toggleAutoGeneration}
            disabled={!botStatus?.is_running}
            className={`border ${
              autoGenerationActive 
                ? 'bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30' 
                : 'bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/30'
            } disabled:opacity-50`}
          >
            {autoGenerationActive ? '⏹️ Stop Auto Generation' : '🔄 Start Auto Generation'}
          </Button>
        </div>

        {!botStatus?.is_running && (
          <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-center space-x-2">
              <span className="text-yellow-400">⚠️</span>
              <span className="text-yellow-400 font-medium">Bot Not Running</span>
            </div>
            <p className="text-slate-300 text-sm mt-1">
              Start the trading bot first to enable manual signal generation.
            </p>
          </div>
        )}

        {autoGenerationActive && (
          <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-center space-x-2">
              <span className="text-green-400">🤖</span>
              <span className="text-green-400 font-medium">Auto Generation Active</span>
            </div>
            <p className="text-slate-300 text-sm mt-1">
              The bot is continuously scanning for high-probability trading opportunities.
            </p>
          </div>
        )}
      </Card>

      {/* Notification Controls */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Signal Controls & Settings</h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="flex items-center justify-between">
            <Label className="text-slate-300">Popup Alerts</Label>
            <Switch 
              checked={notificationSettings.popupEnabled}
              onCheckedChange={(checked) => handleNotificationToggle('popupEnabled', checked)}
            />
          </div>
          
          <div className="flex items-center justify-between">
            <Label className="text-slate-300">Sound Alerts</Label>
            <Switch 
              checked={notificationSettings.soundEnabled}
              onCheckedChange={(checked) => handleNotificationToggle('soundEnabled', checked)}
            />
          </div>
          
          <div className="flex items-center justify-between">
            <Label className="text-slate-300">Auto Refresh</Label>
            <Switch 
              checked={notificationSettings.autoRefresh}
              onCheckedChange={(checked) => handleNotificationToggle('autoRefresh', checked)}
            />
          </div>
          
          <div className="flex items-center justify-between">
            <Label className="text-slate-300 flex items-center">
              <span>Invert Signals</span>
              <span className="ml-1 text-xs text-yellow-400">🔄</span>
            </Label>
            <Switch 
              checked={notificationSettings.signalInversion}
              onCheckedChange={(checked) => handleNotificationToggle('signalInversion', checked)}
            />
          </div>
        </div>

        {notificationSettings.signalInversion && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-center space-x-2">
              <span className="text-yellow-400">⚠️</span>
              <span className="text-yellow-400 font-medium">Signal Inversion Active</span>
            </div>
            <p className="text-slate-300 text-sm mt-1">
              All BUY signals will be displayed as SELL and vice versa. Use with caution!
            </p>
          </div>
        )}
      </Card>

      {/* Asset Selection */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Asset & Timeframe Selection</h3>
        <AssetSelector 
          selectedAssets={selectedAssets}
          selectedTimeframes={selectedTimeframes}
          onSelectionChange={handleAssetSelectionChange}
        />
      </Card>

      {/* Live Signals Section */}
      <Card className="p-6 glass-dark border-emerald-500/30">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
            <h3 className="text-xl font-semibold text-white">Live Trading Signals</h3>
            <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
              {liveSignals.length} Active
            </Badge>
          </div>
          <Button 
            onClick={fetchLiveSignals}
            className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
          >
            🔄 Refresh
          </Button>
        </div>

        {liveSignals.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📡</div>
            <h4 className="text-white font-semibold mb-2">
              {botStatus?.is_running ? 'Scanning for Signals...' : 'Bot Not Running'}
            </h4>
            <p className="text-slate-400">
              {botStatus?.is_running 
                ? 'High-probability trading signals will appear here when detected.'
                : 'Start the trading bot to begin generating live signals.'
              }
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {liveSignals.map((signal) => (
              <SignalCard key={signal.id} signal={signal} isLive={true} />
            ))}
          </div>
        )}
      </Card>

      {/* Recent Signals History */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-white">Recent Signals</h3>
          <Badge className="bg-slate-500/20 text-slate-400 border-slate-500/30">
            Last {recentSignals.length}
          </Badge>
        </div>

        {recentSignals.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-4xl mb-2">📜</div>
            <p className="text-slate-400">No recent signals to display</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentSignals.map((signal) => (
              <SignalCard key={`recent-${signal.id}`} signal={signal} isLive={false} />
            ))}
          </div>
        )}
      </Card>

      {/* Platform Integration Status */}
      <Card className="p-6 glass-dark border-slate-700/50">
        <h3 className="text-xl font-semibold text-white mb-6">Platform Integration Status</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-600/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-medium">Pocket Option</span>
              <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
            </div>
            <p className="text-slate-400 text-sm">SSID Authentication Ready</p>
            <p className="text-slate-300 text-xs mt-1">Account: 53953294</p>
          </div>
          
          <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-600/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-medium">Telegram Bot</span>
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            </div>
            <p className="text-slate-400 text-sm">@ElitePocket_bot</p>
            <p className="text-slate-300 text-xs mt-1">All signals forwarded</p>
          </div>
          
          <div className="p-4 bg-slate-800/30 rounded-lg border border-slate-600/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-medium">AutobotSignal.io</span>
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            </div>
            <p className="text-slate-400 text-sm">Webhook Integration</p>
            <p className="text-slate-300 text-xs mt-1">Key: RSPP</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default LiveSignalsDisplay;