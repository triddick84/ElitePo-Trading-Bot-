import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Slider } from '../components/ui/slider';
import ForceGenerateSignalModal from './ForceGenerateSignalModal';

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
  // Iter 94 — rich Force-Generate result modal
  const [forceGenResult, setForceGenResult] = useState(null);
  const [forceGenModalOpen, setForceGenModalOpen] = useState(false);
  
  // Win/Loss Stats - v6.6.0
  const [stats, setStats] = useState({
    wins: 0,
    losses: 0,
    consecutive_wins: 0,
    consecutive_losses: 0,
    session_profit: 0,
    last_result: null,
    auto_invert_active: false,
    trade_history: []
  });

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

  // Fetch win/loss stats - v6.6.0
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/stats`);
      const data = await response.json();
      if (data.success && data.stats) {
        setStats(data.stats);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
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
    fetchStats();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(() => {
      fetchSettings();
      fetchStatus();
      fetchStats();
    }, 5000);
    
    return () => clearInterval(interval);
  }, [fetchSettings, fetchStatus, fetchStrategies, fetchStats]);

  // Reset stats
  const resetStats = async () => {
    try {
      await fetch(`${API}/tampermonkey/stats/reset`, { method: 'POST' });
      fetchStats();
    } catch (error) {
      console.error('Failed to reset stats:', error);
    }
  };

  // Save settings profile to localStorage
  const saveSettingsProfile = (profileName) => {
    const profile = {
      ...settings,
      timestamp: new Date().toISOString(),
      stats: stats
    };
    localStorage.setItem(`tm_profile_${profileName}`, JSON.stringify(profile));
    alert(`Settings saved to "${profileName}" profile!`);
  };

  // Load settings profile from localStorage
  const loadSettingsProfile = async (profileName) => {
    const saved = localStorage.getItem(`tm_profile_${profileName}`);
    if (!saved) {
      alert('No saved profile found. Save your current settings first.');
      return;
    }
    try {
      const profile = JSON.parse(saved);
      // Apply loaded settings to backend
      await updateSettings(profile);
      alert(`Settings loaded from "${profileName}" profile!`);
    } catch (error) {
      console.error('Failed to load profile:', error);
      alert('Failed to load profile. It may be corrupted.');
    }
  };

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
        // Iter 94 — surface the FULL analytical breakdown (patterns,
        // votes, confluence, narrative) in a rich modal instead of the
        // legacy alert() one-liner.
        setForceGenResult(data);
        setForceGenModalOpen(true);
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
      {/* Iter 106 — Legacy Connection Status pill removed. The rich
           TampermonkeyConnectionDashboard rendered above by
           MobileAutoTraderPage now owns "am I connected?" visualization. */}

      {/* Favorites badge (moved out of the removed banner) */}
      {settings.favorites_list?.length > 0 && (
        <div className="flex justify-end">
          <Badge className="bg-purple-600">
            {settings.favorites_list.length} Favorites Detected
          </Badge>
        </div>
      )}

      {/* Win/Loss Stats - v6.6.0 */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between">
            <span>📊 Session Statistics</span>
            <Button 
              size="sm" 
              variant="outline" 
              onClick={resetStats}
              className="text-xs border-slate-600"
              data-testid="reset-stats-btn"
            >
              Reset Stats
            </Button>
          </CardTitle>
          <CardDescription>Win/Loss tracking with auto-invert system</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Wins */}
            <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 text-center">
              <div className="text-3xl font-bold text-green-400" data-testid="wins-count">{stats.wins}</div>
              <div className="text-sm text-green-300">Wins</div>
            </div>
            
            {/* Losses */}
            <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-center">
              <div className="text-3xl font-bold text-red-400" data-testid="losses-count">{stats.losses}</div>
              <div className="text-sm text-red-300">Losses</div>
            </div>
            
            {/* Streak */}
            <div className={`rounded-lg p-4 text-center ${
              stats.consecutive_wins > 0 
                ? 'bg-green-900/30 border border-green-700' 
                : stats.consecutive_losses > 0 
                  ? 'bg-red-900/30 border border-red-700'
                  : 'bg-slate-900 border border-slate-700'
            }`}>
              <div className={`text-3xl font-bold ${
                stats.consecutive_wins > 0 ? 'text-green-400' : stats.consecutive_losses > 0 ? 'text-red-400' : 'text-slate-400'
              }`} data-testid="streak-display">
                {stats.consecutive_wins > 0 
                  ? `🔥 ${stats.consecutive_wins}W` 
                  : stats.consecutive_losses > 0 
                    ? `❄️ ${stats.consecutive_losses}L`
                    : '-'}
              </div>
              <div className="text-sm text-slate-300">Streak</div>
            </div>
            
            {/* Session P/L */}
            <div className={`rounded-lg p-4 text-center ${
              stats.session_profit >= 0 
                ? 'bg-green-900/30 border border-green-700' 
                : 'bg-red-900/30 border border-red-700'
            }`}>
              <div className={`text-3xl font-bold ${stats.session_profit >= 0 ? 'text-green-400' : 'text-red-400'}`} data-testid="profit-display">
                {stats.session_profit >= 0 ? '+' : ''}${(stats.session_profit || 0).toFixed(2)}
              </div>
              <div className="text-sm text-slate-300">Session P/L</div>
            </div>
          </div>
          
          {/* Auto-Invert Status */}
          <div className={`mt-4 p-3 rounded-lg border ${
            stats.auto_invert_active 
              ? 'bg-orange-900/30 border-orange-600' 
              : 'bg-slate-900 border-slate-700'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`text-lg ${stats.auto_invert_active ? 'text-orange-400' : 'text-slate-400'}`}>
                  🔄 Auto-Invert
                </span>
                <Badge className={stats.auto_invert_active ? 'bg-orange-600' : 'bg-slate-700'}>
                  {stats.auto_invert_active ? 'ACTIVE' : 'INACTIVE'}
                </Badge>
              </div>
              <div className="text-xs text-slate-400">
                Last: {stats.last_result ? (stats.last_result === 'win' ? '✅ WIN' : '❌ LOSS') : '-'}
              </div>
            </div>
          </div>
          
          {/* Recent Trade History */}
          {stats.trade_history && stats.trade_history.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-slate-400 mb-2">Recent Trades:</div>
              <div className="flex gap-1 flex-wrap">
                {stats.trade_history.slice(-10).map((trade, idx) => (
                  <span 
                    key={idx} 
                    className={`px-2 py-1 rounded text-xs ${
                      trade.result === 'win' 
                        ? 'bg-green-900/50 text-green-400' 
                        : 'bg-red-900/50 text-red-400'
                    }`}
                    title={`${trade.direction} - $${trade.amount?.toFixed(2) || '?'}`}
                  >
                    {trade.result === 'win' ? 'W' : 'L'}
                  </span>
                ))}
              </div>
            </div>
          )}
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

      {/* Button Logic Guide v8.4 */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📖 Tampermonkey Button Guide v8.4</CardTitle>
          <CardDescription>Complete guide to bot controls on Pocket Option</CardDescription>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-3">
          {/* Main Control Buttons */}
          <div className="space-y-2">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Main Controls</h4>
            <div className="bg-green-900/30 border border-green-600 rounded p-3">
              <strong className="text-green-400">📡 AUTO</strong> - Receives APP signals only
              <p className="text-xs mt-1 text-green-200">Listens for signals from this dashboard. No local scanning.</p>
            </div>
            <div className="bg-pink-900/30 border border-pink-600 rounded p-3">
              <strong className="text-pink-400">🔍 SCAN</strong> - Local signal generation
              <p className="text-xs mt-1 text-pink-200">Generates signals using live Pocket Option prices (RSI, EMA, Stochastic). 30s cooldown.</p>
            </div>
            <div className="bg-yellow-900/30 border border-yellow-600 rounded p-3">
              <strong className="text-yellow-400">⚡ GO</strong> - Force generate signal
              <p className="text-xs mt-1 text-yellow-200">Immediately generates a signal for the current asset using backend AI analysis.</p>
            </div>
          </div>
          
          {/* Secondary Controls */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Secondary Controls</h4>
            <div className="bg-cyan-900/30 border border-cyan-600 rounded p-3">
              <strong className="text-cyan-400">🔁 CYCLE</strong> - Auto-rotate favorites
              <p className="text-xs mt-1 text-cyan-200">Automatically clicks through each favorite asset, dwells 30s scanning, trades on signal, moves to next.</p>
            </div>
            <div className="bg-slate-700 border border-slate-600 rounded p-3">
              <strong className="text-slate-300">📋 LOG</strong> - Debug console
              <p className="text-xs mt-1 text-slate-400">Opens floating console showing price scraping, signal generation, and trade execution logs.</p>
            </div>
            <div className="bg-red-900/30 border border-red-600 rounded p-3">
              <strong className="text-red-400">🗑 RESET</strong> - Clear all stats
              <p className="text-xs mt-1 text-red-200">Resets wins, losses, profit, and martingale step to zero.</p>
            </div>
          </div>
          
          {/* Invert Modes */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">3-Mode Invert Control</h4>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-slate-700 rounded p-2 text-center">
                <div className="text-slate-300 font-bold text-sm">OFF</div>
                <div className="text-xs text-slate-400">Normal signals</div>
              </div>
              <div className="bg-orange-900/50 border border-orange-500 rounded p-2 text-center">
                <div className="text-orange-400 font-bold text-sm">AUTO</div>
                <div className="text-xs text-orange-200">Momentum-aware</div>
              </div>
              <div className="bg-red-900/50 border border-red-500 rounded p-2 text-center">
                <div className="text-red-400 font-bold text-sm">ON</div>
                <div className="text-xs text-red-200">Always invert</div>
              </div>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              <strong>AUTO mode:</strong> Uses backend momentum-check API + local RSI/EMA analysis. Automatically inverts when detecting trend reversal or loss streaks.
            </p>
          </div>
          
          {/* Recommended Setups */}
          <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-600 rounded p-3 mt-4">
            <strong className="text-white">Recommended Setups:</strong>
            <ul className="text-xs mt-2 space-y-1.5">
              <li className="flex items-center gap-2">
                <span className="bg-green-600 text-white px-2 py-0.5 rounded text-xs">Best</span>
                <span><strong>CYCLE</strong> + <strong>AUTO Invert</strong> = Fully automated multi-asset trading</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white px-2 py-0.5 rounded text-xs">Good</span>
                <span><strong>SCAN</strong> + <strong>AUTO Invert</strong> = Single asset with smart inversion</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-slate-600 text-white px-2 py-0.5 rounded text-xs">Manual</span>
                <span><strong>GO</strong> button only = On-demand signal generation</span>
              </li>
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

      {/* Save/Load Settings System */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between">
            <span>💾 Settings Profiles</span>
            <Badge className="bg-blue-600">Save/Load</Badge>
          </CardTitle>
          <CardDescription>Save your configuration for quick switching between setups</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Button 
              onClick={() => saveSettingsProfile('default')}
              className="bg-green-600 hover:bg-green-700"
              data-testid="save-settings-btn"
            >
              💾 Save Current
            </Button>
            <Button 
              onClick={() => loadSettingsProfile('default')}
              variant="outline"
              className="border-slate-600 hover:bg-slate-700"
              data-testid="load-settings-btn"
            >
              📂 Load Saved
            </Button>
          </div>
          <div className="bg-slate-900 rounded-lg p-3">
            <p className="text-xs text-slate-400 mb-2">Current Configuration:</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Strategy:</span>
                <span className="text-purple-400">{settings.selected_strategy || 'Auto'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Signal Source:</span>
                <span className="text-purple-400">{signalSources.find(s => s.id === settings.signal_source)?.name || 'App AI'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Invert:</span>
                <span className={settings.invert_signals ? 'text-orange-400' : 'text-green-400'}>
                  {settings.invert_signals ? 'ON' : 'OFF'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Min Payout:</span>
                <span className="text-blue-400">{settings.min_payout}%</span>
              </div>
            </div>
          </div>
          <p className="text-xs text-slate-500">
            Settings are saved to your browser's local storage and synced with the Tampermonkey script.
          </p>
        </CardContent>
      </Card>

      {/* Script Info */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white">📄 Script Information v8.4</CardTitle>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-2">
          <div className="flex justify-between">
            <span>Script Version:</span>
            <span className="text-purple-400 font-mono">v8.4.0</span>
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
            <p className="text-xs text-slate-400 mb-2">Script URL (copy for Tampermonkey) — <span className="text-indigo-400">Modular build recommended</span>:</p>
            <div className="flex items-center gap-2">
              <code className="text-xs text-indigo-400 break-all flex-1" data-testid="tm-script-url">
                {API_BASE}/pocket-option-auto-trader-modular.user.js
              </code>
              <Button 
                size="sm" 
                variant="outline" 
                className="text-xs border-slate-600 shrink-0"
                data-testid="tm-copy-script-url-btn"
                onClick={() => {
                  navigator.clipboard.writeText(`${API_BASE}/pocket-option-auto-trader-modular.user.js`);
                  alert('Modular script URL copied!');
                }}
              >
                📋
              </Button>
            </div>
            <p className="text-[10px] text-slate-500 mt-2">
              Legacy monolithic URL (deprecated, rollback only):{' '}
              <span className="font-mono text-slate-600">{API_BASE}/pocket-option-auto-trader.user.js</span>
            </p>
          </div>
          
          {/* Features List */}
          <div className="mt-4 p-3 bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-lg border border-purple-500/30">
            <p className="text-xs text-purple-300 font-semibold mb-2">v8.8.0 Features:</p>
            <ul className="text-xs text-slate-400 space-y-1">
              <li>✅ <strong>6 Local Signal Strategies</strong> (no backend needed for OTC)</li>
              <li className="pl-3">General Multi-Indicator (RSI, MACD, Stoch, BB, EMA, ADX)</li>
              <li className="pl-3">Keltner-MACD 5s (KC EMA20 + MACD 13/24/11)</li>
              <li className="pl-3">IQ-720 Ensemble (8 weighted strategies + regime detection)</li>
              <li className="pl-3">Holly Crossover (EMA12 x WMA23 reversal)</li>
              <li className="pl-3">Golden One Moment 30s (RSI2 + Stoch mean reversion)</li>
              <li className="pl-3">Momentum Buster 15s (momentum period 3)</li>
              <li>✅ <strong>GO button</strong> tries local signals FIRST, backend API fallback</li>
              <li>✅ <strong>KC-5s button</strong> for dedicated Keltner-MACD quick trade</li>
              <li>✅ CYCLE mode with auto-invert and expiry detection</li>
              <li>✅ Session-aware trading with London/NY overlap boost</li>
              <li>✅ Balance-based WIN/LOSS detection from PO UI</li>
              <li>✅ Latency sync with backend timing config</li>
              <li>✅ Settings persistence across page refreshes</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Iter 94 — Rich Force-Generate result modal */}
      <ForceGenerateSignalModal
        open={forceGenModalOpen}
        onOpenChange={setForceGenModalOpen}
        result={forceGenResult}
      />
    </div>
  );
};

export default TampermonkeyControlPanel;
