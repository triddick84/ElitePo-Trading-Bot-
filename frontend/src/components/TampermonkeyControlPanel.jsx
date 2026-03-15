import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Slider } from '../components/ui/slider';

const API_BASE = process.env.REACT_APP_BACKEND_URL;
const API = `${API_BASE}/api`;

const TampermonkeyControlPanel = () => {
  const [settings, setSettings] = useState({
    invert_signals: true,
    scan_mode: false,
    auto_trade: true,
    switch_mode: false,
    preferred_expiry: 60,
    min_payout: 65,
    selected_timeframes: ['5s', '15s', '30s', '1m'],
    auto_generate_enabled: false,
    selected_strategy: 'auto',
    signal_source: 'app_ai',
    favorites_list: []
  });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [recentSignals, setRecentSignals] = useState([]);
  const [status, setStatus] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connectionActive, setConnectionActive] = useState(false);
  const [strategies, setStrategies] = useState([]);

  const timeframes = ['5s', '15s', '30s', '1m', '2m', '3m', '5m'];
  const expiryOptions = [5, 15, 30, 60, 120, 180, 300];
  
  const signalSources = [
    { id: 'app_ai', name: 'App AI', description: 'AI-generated signals from the app', icon: '🤖' },
    { id: 'tradingview', name: 'TradingView', description: 'Signals from TradingView webhooks', icon: '📊' },
    { id: 'mt4', name: 'MetaTrader 4', description: 'Signals from MT4 Expert Advisor', icon: '📈' },
    { id: 'mt5', name: 'MetaTrader 5', description: 'Signals from MT5 Expert Advisor', icon: '📉' },
    { id: 'tampermonkey_scan', name: 'TM Scan', description: 'Tampermonkey self-generated signals', icon: '🔍' }
  ];

  // Fetch strategies
  const fetchStrategies = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/strategies`);
      const data = await response.json();
      if (data.success && data.strategies) {
        setStrategies(data.strategies);
      }
    } catch (error) {
      console.error('Failed to fetch strategies:', error);
    }
  }, []);

  // Fetch current settings
  const fetchSettings = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/settings`);
      const data = await response.json();
      if (data.success && data.settings) {
        setSettings(data.settings);
        setLastUpdate(new Date().toLocaleTimeString());
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    }
  }, []);

  // Fetch status including recent signals and connection
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/status`);
      const data = await response.json();
      if (data.success) {
        setStatus(data);
        setRecentSignals(data.recent_signals || []);
        setConnectionActive(data.connection_active || false);
      }
    } catch (error) {
      console.error('Failed to fetch status:', error);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    fetchStatus();
    fetchStrategies();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(() => {
      fetchSettings();
      fetchStatus();
    }, 5000);
    
    return () => clearInterval(interval);
  }, [fetchSettings, fetchStatus, fetchStrategies]);

  // Update settings on server
  const updateSettings = async (newSettings) => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/tampermonkey/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings)
      });
      const data = await response.json();
      if (data.success) {
        setSettings(data.settings);
        setLastUpdate(new Date().toLocaleTimeString());
      }
    } catch (error) {
      console.error('Failed to update settings:', error);
    }
    setLoading(false);
  };

  // Toggle inversion
  const toggleInversion = async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/toggle-inversion`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setSettings(prev => ({ ...prev, invert_signals: data.invert_signals }));
      }
    } catch (error) {
      console.error('Failed to toggle inversion:', error);
    }
  };

  // Force generate signal
  const forceGenerateSignal = async (timeframe) => {
    setGenerating(true);
    try {
      const response = await fetch(`${API}/tampermonkey/force-generate?timeframe=${timeframe}`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        fetchStatus();
        alert(`Signal generated: ${data.signal.direction} ${data.signal.symbol} (${data.inverted ? 'INVERTED' : 'NORMAL'})`);
      } else {
        alert('Failed to generate signal: ' + data.message);
      }
    } catch (error) {
      console.error('Failed to generate signal:', error);
      alert('Error generating signal');
    }
    setGenerating(false);
  };

  // Handle timeframe selection
  const toggleTimeframe = (tf) => {
    const newTimeframes = settings.selected_timeframes.includes(tf)
      ? settings.selected_timeframes.filter(t => t !== tf)
      : [...settings.selected_timeframes, tf];
    updateSettings({ ...settings, selected_timeframes: newTimeframes });
  };

  return (
    <div className="space-y-6" data-testid="tampermonkey-control-panel">
      {/* Connection Status Banner */}
      <Card className={`border-2 ${connectionActive ? 'bg-green-900/20 border-green-600' : 'bg-red-900/20 border-red-600'}`}>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-4 h-4 rounded-full ${connectionActive ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
              <div>
                <h3 className={`font-bold ${connectionActive ? 'text-green-400' : 'text-red-400'}`}>
                  {connectionActive ? '🟢 Tampermonkey Connected' : '🔴 Tampermonkey Disconnected'}
                </h3>
                <p className="text-xs text-slate-400">
                  {connectionActive 
                    ? `Last heartbeat: ${settings.last_heartbeat ? new Date(settings.last_heartbeat).toLocaleTimeString() : 'Just now'}`
                    : 'Install and open Tampermonkey script on Pocket Option'}
                </p>
              </div>
            </div>
            {settings.favorites_list?.length > 0 && (
              <Badge className="bg-purple-600">
                {settings.favorites_list.length} Favorites Detected
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Signal Source Selection */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📡 Signal Source</CardTitle>
          <CardDescription>Choose where trading signals come from</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {signalSources.map(source => (
              <button
                key={source.id}
                onClick={() => updateSettings({ ...settings, signal_source: source.id })}
                className={`p-3 rounded-lg border-2 transition-all ${
                  settings.signal_source === source.id
                    ? 'border-purple-500 bg-purple-900/30'
                    : 'border-slate-600 bg-slate-800 hover:border-slate-500'
                }`}
                data-testid={`signal-source-${source.id}`}
              >
                <div className="text-2xl mb-1">{source.icon}</div>
                <div className="text-sm font-medium text-white">{source.name}</div>
                <div className="text-xs text-slate-400 mt-1">{source.description}</div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Strategy Selection */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">🎯 Trading Strategy</CardTitle>
          <CardDescription>Select which strategy Tampermonkey should use</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {strategies.map(strategy => (
              <button
                key={strategy.id}
                onClick={() => updateSettings({ ...settings, selected_strategy: strategy.id })}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  settings.selected_strategy === strategy.id
                    ? 'border-green-500 bg-green-900/30'
                    : 'border-slate-600 bg-slate-800 hover:border-slate-500'
                }`}
                data-testid={`strategy-${strategy.id}`}
              >
                <div className="text-sm font-medium text-white">{strategy.name}</div>
                <div className="text-xs text-slate-400 mt-1">{strategy.description}</div>
                {strategy.timeframes && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {strategy.timeframes.map(tf => (
                      <span key={tf} className="text-xs bg-slate-700 px-1.5 py-0.5 rounded">{tf}</span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Button Logic Guide */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📖 Button Logic Guide v6.5.0</CardTitle>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-3">
          <div className="bg-green-900/30 border border-green-600 rounded p-3">
            <strong className="text-green-400">📡 AUTO</strong> - Receives APP signals only (no generation)
            <p className="text-xs mt-1">Enable for incoming signals from app dashboard</p>
          </div>
          <div className="bg-pink-900/30 border border-pink-600 rounded p-3">
            <strong className="text-pink-400">🔍 SCAN</strong> - Tampermonkey generates & places trades
            <p className="text-xs mt-1">30 second cooldown between scan trades</p>
          </div>
          <div className="bg-purple-900/30 border border-purple-600 rounded p-3">
            <strong className="text-purple-400">🔀 SWITCH</strong> - Cycles through favorites BAR
            <p className="text-xs mt-1">v6.5.0: Now uses the visual favorites bar, not search</p>
          </div>
          <div className="bg-orange-900/30 border border-orange-600 rounded p-3">
            <strong className="text-orange-400">🔄 INVERT</strong> - Local toggle (overrides app)
            <p className="text-xs mt-1">CALL → PUT, PUT → CALL</p>
          </div>
          <div className="bg-slate-700 rounded p-3 mt-4">
            <strong className="text-white">Combinations:</strong>
            <ul className="text-xs mt-2 space-y-1">
              <li>• <span className="text-green-400">AUTO only</span>: App signals on current asset</li>
              <li>• <span className="text-pink-400">SCAN only</span>: TM scans current asset only</li>
              <li>• <span className="text-pink-400">SCAN + SWITCH</span>: TM cycles through favorites bar</li>
              <li>• <span className="text-purple-400">AUTO + SCAN</span>: BOTH sources on current asset</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Main Control Panel */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between">
            <span>🎮 Tampermonkey Remote Control</span>
            <Badge className={settings.invert_signals ? 'bg-orange-600' : 'bg-green-600'}>
              {settings.invert_signals ? '🔄 INVERSION ON' : 'NORMAL MODE'}
            </Badge>
          </CardTitle>
          <CardDescription>
            Note: Tampermonkey's local INVERT button overrides this setting
            {lastUpdate && <span className="ml-2 text-xs text-slate-500">Updated: {lastUpdate}</span>}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          {/* Critical Inversion Toggle */}
          <div className="bg-orange-900/30 border border-orange-600 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-orange-400 font-bold text-lg">🔄 Signal Inversion (App)</h3>
                <p className="text-sm text-orange-200 mt-1">
                  Tampermonkey's local INVERT toggle overrides this
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`font-bold ${settings.invert_signals ? 'text-orange-400' : 'text-slate-400'}`}>
                  {settings.invert_signals ? 'INVERTED' : 'NORMAL'}
                </span>
                <Switch
                  checked={settings.invert_signals}
                  onCheckedChange={toggleInversion}
                  className="data-[state=checked]:bg-orange-600"
                  data-testid="inversion-toggle"
                />
              </div>
            </div>
          </div>

          {/* Mode Controls */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-900 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-medium">Auto Trade</span>
                <Switch
                  checked={settings.auto_trade}
                  onCheckedChange={(checked) => updateSettings({ ...settings, auto_trade: checked })}
                  className="data-[state=checked]:bg-green-600"
                  data-testid="auto-trade-toggle"
                />
              </div>
              <p className="text-xs text-slate-400">For APP SIGNALS: Enable this, disable Scan & Switch</p>
            </div>
            
            <div className="bg-slate-900 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-medium">Scan Mode</span>
                <Switch
                  checked={settings.scan_mode}
                  onCheckedChange={(checked) => updateSettings({ ...settings, scan_mode: checked })}
                  className="data-[state=checked]:bg-pink-600"
                  data-testid="scan-mode-toggle"
                />
              </div>
              <p className="text-xs text-slate-400">Tampermonkey scans for signals (30s between trades)</p>
            </div>
          </div>

          {/* Timeframe Selection */}
          <div>
            <h3 className="text-white font-medium mb-3">📊 Active Timeframes</h3>
            <div className="flex flex-wrap gap-2">
              {timeframes.map(tf => (
                <Button
                  key={tf}
                  size="sm"
                  variant={settings.selected_timeframes?.includes(tf) ? 'default' : 'outline'}
                  className={settings.selected_timeframes?.includes(tf) 
                    ? 'bg-purple-600 hover:bg-purple-700' 
                    : 'border-slate-600 text-slate-400'}
                  onClick={() => toggleTimeframe(tf)}
                  data-testid={`timeframe-${tf}`}
                >
                  {tf}
                </Button>
              ))}
            </div>
          </div>

          {/* Preferred Expiry */}
          <div>
            <h3 className="text-white font-medium mb-3">⏱️ Preferred Expiry: {settings.preferred_expiry}s</h3>
            <div className="flex flex-wrap gap-2">
              {expiryOptions.map(exp => (
                <Button
                  key={exp}
                  size="sm"
                  variant={settings.preferred_expiry === exp ? 'default' : 'outline'}
                  className={settings.preferred_expiry === exp 
                    ? 'bg-blue-600 hover:bg-blue-700' 
                    : 'border-slate-600 text-slate-400'}
                  onClick={() => updateSettings({ ...settings, preferred_expiry: exp })}
                  data-testid={`expiry-${exp}`}
                >
                  {exp >= 60 ? `${exp/60}m` : `${exp}s`}
                </Button>
              ))}
            </div>
          </div>

          {/* Min Payout Slider */}
          <div>
            <h3 className="text-white font-medium mb-3">💰 Min Payout: {settings.min_payout}%</h3>
            <Slider
              value={[settings.min_payout]}
              onValueChange={([value]) => updateSettings({ ...settings, min_payout: value })}
              min={50}
              max={90}
              step={5}
              className="w-full"
              data-testid="min-payout-slider"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>50%</span>
              <span>90%</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Force Generate Signals */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">⚡ Force Generate Signal</CardTitle>
          <CardDescription>
            Generate a signal immediately for Tampermonkey to execute
            {settings.invert_signals && <Badge className="ml-2 bg-orange-600">Will be INVERTED</Badge>}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 md:grid-cols-7 gap-2">
            {timeframes.map(tf => (
              <Button
                key={tf}
                onClick={() => forceGenerateSignal(tf)}
                disabled={generating}
                className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                data-testid={`force-generate-${tf}`}
              >
                {generating ? '...' : tf}
              </Button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-3">
            Click a timeframe to immediately generate and send a signal to Tampermonkey
          </p>
        </CardContent>
      </Card>

      {/* Recent Signals */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📜 Recent Signals</CardTitle>
          <CardDescription>Last 5 signals generated</CardDescription>
        </CardHeader>
        <CardContent>
          {recentSignals.length === 0 ? (
            <p className="text-slate-400 text-center py-4">No recent signals</p>
          ) : (
            <div className="space-y-2">
              {recentSignals.map((signal, idx) => (
                <div 
                  key={idx}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    signal.direction === 'CALL' || signal.direction === 'BUY' || signal.direction === 'UP'
                      ? 'bg-green-900/30 border border-green-700'
                      : 'bg-red-900/30 border border-red-700'
                  }`}
                  data-testid={`recent-signal-${idx}`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`font-bold ${
                      signal.direction === 'CALL' || signal.direction === 'BUY' || signal.direction === 'UP'
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}>
                      {signal.direction === 'CALL' || signal.direction === 'BUY' || signal.direction === 'UP' ? '📈' : '📉'} {signal.direction}
                    </span>
                    <span className="text-white">{signal.symbol}</span>
                    {signal.inverted && <Badge className="bg-orange-600 text-xs">INV</Badge>}
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-slate-300">{signal.timeframe || `${signal.expiration_minutes}m`}</div>
                    <div className="text-xs text-slate-500">
                      {signal.timestamp ? new Date(signal.timestamp).toLocaleTimeString() : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Script Info */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📄 Script Information</CardTitle>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-2">
          <div className="flex justify-between">
            <span>Script Version:</span>
            <span className="text-purple-400 font-mono">v6.5.0</span>
          </div>
          <div className="flex justify-between">
            <span>Connection:</span>
            <span className={connectionActive ? 'text-green-400' : 'text-red-400'}>
              {connectionActive ? 'Active' : 'Inactive'}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Heartbeat Interval:</span>
            <span className="text-green-400">Every 10 seconds</span>
          </div>
          <div className="flex justify-between">
            <span>Signal Polling:</span>
            <span className="text-green-400">Every 3 seconds</span>
          </div>
          <div className="flex justify-between">
            <span>Current Strategy:</span>
            <span className="text-purple-400">{settings.selected_strategy || 'Auto'}</span>
          </div>
          <div className="flex justify-between">
            <span>Signal Source:</span>
            <span className="text-purple-400">
              {signalSources.find(s => s.id === settings.signal_source)?.name || settings.signal_source}
            </span>
          </div>
          <div className="mt-4 p-3 bg-slate-900 rounded-lg">
            <p className="text-xs text-slate-400 mb-2">Script URL:</p>
            <code className="text-xs text-purple-400 break-all">
              {API_BASE}/pocket-option-auto-trader.user.js
            </code>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TampermonkeyControlPanel;
