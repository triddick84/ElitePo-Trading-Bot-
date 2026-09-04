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
  const [strategyTfFilter, setStrategyTfFilter] = useState('all');
  const [scriptVersion, setScriptVersion] = useState('—');
  const [scriptFeatures, setScriptFeatures] = useState([]);
  // Iter 94 — rich Force-Generate result modal
  const [forceGenResult, setForceGenResult] = useState(null);
  const [forceGenModalOpen, setForceGenModalOpen] = useState(false);
  // Iter 120 — Strategy backtest runner
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestResult, setBacktestResult] = useState(null);
  const [backtestAsset, setBacktestAsset] = useState('EURUSD_OTC');
  const [backtestDays, setBacktestDays] = useState(30);
  // Iter 120c — Ridicolous live-tunable config
  const [ridicolousCfg, setRidicolousCfg] = useState({
    perc: 1.0, levels: 5, min_history: 60, min_confidence: 55.0,
  });
  const [ridicolousSaving, setRidicolousSaving] = useState(false);
  const [ridicolousDirty, setRidicolousDirty] = useState(false);
  // Iter 120d — Confidence-threshold autotuner
  const [autotuneRunning, setAutotuneRunning] = useState(false);
  const [autotuneResult, setAutotuneResult] = useState(null);
  
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

  // Iter 116 — Live TM script version + feature list
  const fetchScriptVersion = useCallback(async () => {
    try {
      const response = await fetch(`${API}/tampermonkey/version`);
      const data = await response.json();
      if (data.success) {
        setScriptVersion(data.version || '—');
        setScriptFeatures(data.features || []);
      }
    } catch (error) {
      console.error('Failed to fetch TM version:', error);
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

  // Iter 120c — Fetch Ridicolous config (declared before useEffect that uses it)
  const fetchRidicolousConfig = useCallback(async () => {
    try {
      const r = await fetch(`${API}/strategies/ridicolous/config`);
      const d = await r.json();
      if (d.success && d.config) {
        setRidicolousCfg({
          perc: Number(d.config.perc),
          levels: Number(d.config.levels),
          min_history: Number(d.config.min_history),
          min_confidence: Number(d.config.min_confidence),
        });
        setRidicolousDirty(false);
      }
    } catch (e) {
      console.error('Failed to fetch Ridicolous config:', e);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    fetchStatus();
    fetchStrategies();
    fetchStats();
    fetchScriptVersion();
    fetchRidicolousConfig();

    // Iter 121 — smart poll: 8 s interval, paused when the tab is hidden.
    // Cuts API load ~40% and pauses entirely when user is on another tab.
    let interval = null;
    const start = () => {
      if (interval) return;
      interval = setInterval(() => {
        fetchSettings();
        fetchStatus();
        fetchStats();
      }, 8000);
    };
    const stop = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        // refresh immediately then resume polling
        fetchSettings();
        fetchStatus();
        fetchStats();
        start();
      } else {
        stop();
      }
    };
    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchSettings, fetchStatus, fetchStrategies, fetchStats, fetchScriptVersion, fetchRidicolousConfig]);

  // Reset stats
  const resetStats = async () => {
    try {
      await fetch(`${API}/tampermonkey/stats/reset`, { method: 'POST' });
      fetchStats();
    } catch (error) {
      console.error('Failed to reset stats:', error);
    }
  };

  // Iter 120 — Run a strategy backtest against the last N days of candles
  const runBacktest = async () => {
    if (!settings.selected_strategy || settings.selected_strategy === 'auto') {
      alert('Pick a specific strategy first — "Auto" cannot be backtested.');
      return;
    }
    try {
      setBacktestRunning(true);
      setBacktestResult(null);
      // Match candle timeframe to the strategy's declared timeframe when possible
      const strat = strategies.find(s => s.id === settings.selected_strategy);
      const tf = (strat?.timeframes || ['1m'])[0] || '1m';
      // Iter 120c — send Ridicolous tunables as per-run params
      const params = settings.selected_strategy === 'ridicolous_breakout_prediction'
        ? { ...ridicolousCfg } : undefined;
      const res = await fetch(`${API}/strategies/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: settings.selected_strategy,
          asset: backtestAsset || 'EURUSD_OTC',
          timeframe: tf,
          days: Number(backtestDays) || 30,
          max_candles: 3000,
          min_history: 60,
          payout: 0.85,
          stride: 3,
          params,
        }),
      });
      const data = await res.json();
      setBacktestResult(data);
    } catch (err) {
      setBacktestResult({ success: false, error: err.message });
    } finally {
      setBacktestRunning(false);
    }
  };

  // Iter 120c — Save Ridicolous config (fetch handler declared above the useEffect)
  const saveRidicolousConfig = async () => {
    try {
      setRidicolousSaving(true);
      const r = await fetch(`${API}/strategies/ridicolous/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ridicolousCfg),
      });
      const d = await r.json();
      if (d.success && d.config) {
        setRidicolousCfg({
          perc: Number(d.config.perc),
          levels: Number(d.config.levels),
          min_history: Number(d.config.min_history),
          min_confidence: Number(d.config.min_confidence),
        });
        setRidicolousDirty(false);
      }
    } catch (e) {
      console.error('Failed to save Ridicolous config:', e);
    } finally {
      setRidicolousSaving(false);
    }
  };

  // Iter 120d — Autotune min-confidence
  const runAutotune = async () => {
    try {
      setAutotuneRunning(true);
      setAutotuneResult(null);
      const r = await fetch(`${API}/strategies/autotune-confidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: 'ridicolous_breakout_prediction',
          asset: backtestAsset || 'EURUSD_OTC',
          timeframe: '1m',
          days: Number(backtestDays) || 30,
          max_candles: 3000,
          min_history: 60,
          payout: 0.85,
          stride: 3,
          conf_min: 50,
          conf_max: 90,
          conf_step: 5,
          min_sample_size: 15,
          params: { perc: ridicolousCfg.perc, levels: ridicolousCfg.levels },
        }),
      });
      const d = await r.json();
      setAutotuneResult(d);
    } catch (e) {
      setAutotuneResult({ success: false, error: e.message });
    } finally {
      setAutotuneRunning(false);
    }
  };

  const applyAutotuneRecommendation = async () => {
    if (!autotuneResult?.recommendation) return;
    try {
      const r = await fetch(`${API}/strategies/autotune-confidence/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: 'ridicolous_breakout_prediction',
          asset: backtestAsset || 'EURUSD_OTC',
          timeframe: '1m',
          threshold: autotuneResult.recommendation.threshold,
        }),
      });
      const d = await r.json();
      if (d.success && d.config) {
        setRidicolousCfg({
          perc: Number(d.config.perc),
          levels: Number(d.config.levels),
          min_history: Number(d.config.min_history),
          min_confidence: Number(d.config.min_confidence),
        });
        setRidicolousDirty(false);
      }
    } catch (e) {
      console.error('Failed to apply autotune:', e);
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
      <Card className="bg-slate-800/50 border-slate-700" data-testid="tm-trading-strategy-card">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between flex-wrap gap-2">
            <span>🎯 Trading Strategy</span>
            <div className="flex items-center gap-2">
              <Badge className="bg-slate-700 border-slate-600 text-slate-200 text-xs" data-testid="strategy-count-badge">
                {strategies.length} available
              </Badge>
              <Button
                size="sm"
                variant="outline"
                className="text-xs border-slate-600 h-7"
                onClick={fetchStrategies}
                data-testid="refresh-strategies-btn"
              >
                🔄 Refresh
              </Button>
            </div>
          </CardTitle>
          <CardDescription>
            Live from the same registry the Strategy Selection tool uses — filter by timeframe below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Iter 120 — Backtest runner */}
          <div className="mb-4 p-3 rounded-lg bg-slate-900/70 border border-slate-700 space-y-2" data-testid="strategy-backtest-panel">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-300 font-medium">🧪 Backtest last</span>
              <input
                type="number" min="1" max="180"
                value={backtestDays}
                onChange={(e) => setBacktestDays(e.target.value)}
                className="w-14 text-xs bg-slate-800 border border-slate-600 rounded px-1 py-0.5 text-white"
                data-testid="backtest-days-input"
              />
              <span className="text-xs text-slate-400">days on</span>
              <input
                type="text"
                value={backtestAsset}
                onChange={(e) => setBacktestAsset(e.target.value.toUpperCase())}
                className="w-32 text-xs bg-slate-800 border border-slate-600 rounded px-2 py-0.5 text-white font-mono"
                placeholder="EURUSD_OTC"
                data-testid="backtest-asset-input"
              />
              <Button
                size="sm"
                onClick={runBacktest}
                disabled={backtestRunning || !settings.selected_strategy || settings.selected_strategy === 'auto'}
                className="bg-purple-600 hover:bg-purple-700 h-7 text-xs"
                data-testid="run-backtest-btn"
              >
                {backtestRunning ? 'Running…' : 'Run backtest'}
              </Button>
              {settings.selected_strategy && settings.selected_strategy !== 'auto' && (
                <span className="text-[11px] text-slate-500 truncate">
                  Strategy: <span className="text-purple-300 font-mono">{settings.selected_strategy}</span>
                </span>
              )}
            </div>

            {/* Iter 120c — Ridicolous live-tunable sliders */}
            {settings.selected_strategy === 'ridicolous_breakout_prediction' && (
              <div
                className="mt-2 p-3 rounded-md bg-slate-950/60 border border-purple-500/30 space-y-3"
                data-testid="ridicolous-tunables-panel"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <p className="text-xs font-medium text-purple-200">
                    🎯 Ridicolous tunables · applied live + used as backtest overrides
                  </p>
                  {ridicolousDirty && (
                    <Button
                      size="sm"
                      onClick={saveRidicolousConfig}
                      disabled={ridicolousSaving}
                      className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs"
                      data-testid="save-ridicolous-cfg-btn"
                    >
                      {ridicolousSaving ? 'Saving…' : '💾 Save & apply live'}
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Step % */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Step %</span>
                      <span className="text-cyan-300 font-mono" data-testid="ridi-perc-value">
                        {ridicolousCfg.perc.toFixed(2)}%
                      </span>
                    </div>
                    <input
                      type="range" min="0.05" max="5.0" step="0.05"
                      value={ridicolousCfg.perc}
                      onChange={(e) => {
                        setRidicolousCfg(c => ({ ...c, perc: Number(e.target.value) }));
                        setRidicolousDirty(true);
                      }}
                      className="w-full accent-cyan-500"
                      data-testid="ridi-perc-slider"
                    />
                  </div>

                  {/* Levels */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Levels (probability pyramid)</span>
                      <span className="text-purple-300 font-mono" data-testid="ridi-levels-value">
                        {ridicolousCfg.levels}
                      </span>
                    </div>
                    <input
                      type="range" min="1" max="5" step="1"
                      value={ridicolousCfg.levels}
                      onChange={(e) => {
                        setRidicolousCfg(c => ({ ...c, levels: Number(e.target.value) }));
                        setRidicolousDirty(true);
                      }}
                      className="w-full accent-purple-500"
                      data-testid="ridi-levels-slider"
                    />
                  </div>

                  {/* Min confidence */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Min confidence to fire</span>
                      <span className="text-emerald-300 font-mono" data-testid="ridi-minconf-value">
                        {ridicolousCfg.min_confidence.toFixed(1)}%
                      </span>
                    </div>
                    <input
                      type="range" min="40" max="90" step="1"
                      value={ridicolousCfg.min_confidence}
                      onChange={(e) => {
                        setRidicolousCfg(c => ({ ...c, min_confidence: Number(e.target.value) }));
                        setRidicolousDirty(true);
                      }}
                      className="w-full accent-emerald-500"
                      data-testid="ridi-minconf-slider"
                    />
                  </div>

                  {/* Min history */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Min candle history</span>
                      <span className="text-amber-300 font-mono" data-testid="ridi-minhist-value">
                        {ridicolousCfg.min_history}
                      </span>
                    </div>
                    <input
                      type="range" min="30" max="300" step="10"
                      value={ridicolousCfg.min_history}
                      onChange={(e) => {
                        setRidicolousCfg(c => ({ ...c, min_history: Number(e.target.value) }));
                        setRidicolousDirty(true);
                      }}
                      className="w-full accent-amber-500"
                      data-testid="ridi-minhist-slider"
                    />
                  </div>
                </div>

                <p className="text-[10px] text-slate-500">
                  Changes are used in the next Backtest run immediately. Click <span className="text-emerald-400">Save & apply live</span> to also apply them to live signal generation.
                </p>

                {/* Iter 120d — Autotune min-confidence */}
                <div className="mt-2 pt-3 border-t border-purple-500/20" data-testid="autotune-panel">
                  <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                    <p className="text-xs font-medium text-purple-200">
                      🎯 Autotune min-confidence · sweeps 50-90% on the current asset
                    </p>
                    <Button
                      size="sm"
                      onClick={runAutotune}
                      disabled={autotuneRunning}
                      className="bg-fuchsia-600 hover:bg-fuchsia-700 h-7 text-xs"
                      data-testid="run-autotune-btn"
                    >
                      {autotuneRunning ? 'Sweeping…' : '⚡ Run autotune'}
                    </Button>
                  </div>

                  {autotuneResult && !autotuneResult.success && (
                    <div className="text-xs text-rose-300" data-testid="autotune-error">
                      ✗ {autotuneResult.error || 'autotune failed'}
                    </div>
                  )}

                  {autotuneResult && autotuneResult.success && (
                    <div className="space-y-2" data-testid="autotune-result">
                      {autotuneResult.recommendation ? (
                        <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/40 flex items-center justify-between flex-wrap gap-2">
                          <div className="text-xs">
                            <span className="text-emerald-300 font-bold" data-testid="autotune-recommendation">
                              Recommended: {autotuneResult.recommendation.threshold}%
                            </span>
                            <span className="text-slate-400 ml-2">
                              → WR {(autotuneResult.recommendation.win_rate * 100).toFixed(1)}% ·
                              Sim P&L {autotuneResult.recommendation.sim_pnl >= 0 ? '+' : ''}{autotuneResult.recommendation.sim_pnl} ·
                              n={autotuneResult.recommendation.n}
                            </span>
                          </div>
                          <Button
                            size="sm"
                            onClick={applyAutotuneRecommendation}
                            className="bg-emerald-600 hover:bg-emerald-700 h-7 text-xs"
                            data-testid="apply-autotune-btn"
                          >
                            ✓ Apply {autotuneResult.recommendation.threshold}%
                          </Button>
                        </div>
                      ) : (
                        <div className="p-2 rounded bg-slate-800/70 border border-slate-600 text-xs text-slate-400">
                          No threshold in the 50-90% band cleared break-even + min-sample gates.
                          Try widening the day range or lowering `min_sample_size`.
                        </div>
                      )}

                      <table className="w-full text-[11px] border-collapse" data-testid="autotune-sweep-table">
                        <thead>
                          <tr className="text-slate-400 border-b border-slate-700">
                            <th className="text-left py-1 pr-2">Min conf</th>
                            <th className="text-right px-2">n</th>
                            <th className="text-right px-2">WR</th>
                            <th className="text-right px-2">Sim P&L</th>
                            <th className="text-right px-2">Eligible</th>
                          </tr>
                        </thead>
                        <tbody>
                          {autotuneResult.sweep.map(row => (
                            <tr key={row.threshold}
                                className={`border-b border-slate-800 ${
                                  autotuneResult.recommendation?.threshold === row.threshold
                                    ? 'bg-emerald-900/30' : ''
                                }`}
                                data-testid={`autotune-row-${row.threshold}`}>
                              <td className="py-0.5 pr-2 text-slate-300 font-mono">{row.threshold}%</td>
                              <td className="text-right px-2 text-slate-300 font-mono">{row.n}</td>
                              <td className={`text-right px-2 font-mono ${
                                row.win_rate == null ? 'text-slate-500'
                                  : row.win_rate >= 0.556 ? 'text-emerald-300' : 'text-rose-300'
                              }`}>
                                {row.win_rate != null ? `${(row.win_rate * 100).toFixed(1)}%` : '—'}
                              </td>
                              <td className={`text-right px-2 font-mono ${
                                row.sim_pnl > 0 ? 'text-emerald-300' : row.sim_pnl < 0 ? 'text-rose-300' : 'text-slate-500'
                              }`}>
                                {row.sim_pnl > 0 ? '+' : ''}{row.sim_pnl}
                              </td>
                              <td className="text-right px-2">
                                {row.eligible ? <span className="text-emerald-400">✓</span> : <span className="text-slate-600">—</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="text-[10px] text-slate-500">
                        Eligible = sample ≥ 15 AND WR &gt; break-even ({((1 / (1 + (autotuneResult.payout || 0.85))) * 100).toFixed(1)}%).
                        Recommendation picks highest Sim P&amp;L among eligibles.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {backtestResult && !backtestResult.success && (
              <div className="text-xs text-rose-300" data-testid="backtest-error">
                ✗ {backtestResult.error || 'backtest failed'}
                {backtestResult.candles_loaded !== undefined && (
                  <span className="ml-2 text-slate-400">
                    (candles loaded: {backtestResult.candles_loaded})
                  </span>
                )}
              </div>
            )}

            {backtestResult && backtestResult.success && (
              <div className="mt-2 text-xs text-slate-200 space-y-2" data-testid="backtest-result">
                <div className="flex flex-wrap gap-3">
                  <div>
                    <span className="text-slate-400">Sample:</span>{' '}
                    <span className="text-white font-mono">{backtestResult.sample_size}</span>
                    <span className="text-slate-500 ml-1">
                      / {backtestResult.candles_used} candles
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">WR:</span>{' '}
                    <span
                      className={`font-mono font-bold ${
                        (backtestResult.win_rate || 0) >= 0.556
                          ? 'text-emerald-300'
                          : 'text-rose-300'
                      }`}
                      data-testid="backtest-winrate"
                    >
                      {backtestResult.win_rate != null
                        ? `${(backtestResult.win_rate * 100).toFixed(1)}%`
                        : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Sim P&L:</span>{' '}
                    <span
                      className={`font-mono font-bold ${
                        (backtestResult.sim_pnl || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'
                      }`}
                      data-testid="backtest-pnl"
                    >
                      {(backtestResult.sim_pnl >= 0 ? '+' : '') + backtestResult.sim_pnl}
                    </span>
                    <span className="text-slate-500 ml-1">
                      @ {(backtestResult.payout_used * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">CALL/PUT:</span>{' '}
                    <span className="text-emerald-300 font-mono">{backtestResult.signals?.calls}</span>
                    {' / '}
                    <span className="text-rose-300 font-mono">{backtestResult.signals?.puts}</span>
                    <span className="text-slate-500 ml-1">
                      ({backtestResult.signals?.neutrals} skip)
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Avg conf:</span>{' '}
                    <span className="text-cyan-300 font-mono">
                      {backtestResult.avg_confidence != null ? `${backtestResult.avg_confidence}%` : '—'}
                    </span>
                  </div>
                </div>

                {/* Confidence buckets */}
                {backtestResult.confidence_buckets?.some(b => b.n > 0) && (
                  <div>
                    <p className="text-slate-400 mt-1 mb-1">Win-rate by confidence bucket</p>
                    <div className="grid grid-cols-5 gap-1">
                      {backtestResult.confidence_buckets.map(b => (
                        <div
                          key={b.bucket}
                          className={`p-1 rounded text-center ${
                            b.n === 0 ? 'bg-slate-800/40 text-slate-500'
                              : (b.win_rate || 0) >= 0.556 ? 'bg-emerald-900/40 text-emerald-300'
                                : 'bg-rose-900/30 text-rose-300'
                          }`}
                          data-testid={`bt-bucket-${b.bucket}`}
                        >
                          <div className="text-[10px] opacity-70">{b.bucket}%</div>
                          <div className="font-mono text-xs">
                            {b.win_rate != null ? `${(b.win_rate * 100).toFixed(0)}%` : '—'}
                          </div>
                          <div className="text-[9px] opacity-60">n={b.n}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ridicolous — historical probability table */}
                {backtestResult.strategy_specific?.ridicolous_table?.probability_table && (
                  <div>
                    <p className="text-slate-400 mt-2 mb-1">
                      🎯 Ridicolous probability table · step {backtestResult.strategy_specific.ridicolous_table.step_pct}% ·
                      green {backtestResult.strategy_specific.ridicolous_table.green_total} /
                      red {backtestResult.strategy_specific.ridicolous_table.red_total}
                    </p>
                    <table className="w-full text-[11px] border-collapse" data-testid="ridicolous-table">
                      <thead>
                        <tr className="text-slate-400 border-b border-slate-700">
                          <th className="text-left py-1 pr-2">Lvl</th>
                          <th className="text-right px-2">G↑ new-high</th>
                          <th className="text-right px-2">G↓ new-low</th>
                          <th className="text-right px-2">R↑ new-high</th>
                          <th className="text-right px-2">R↓ new-low</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.strategy_specific.ridicolous_table.probability_table.map(row => (
                          <tr key={row.level} className="border-b border-slate-800">
                            <td className="py-0.5 pr-2 text-slate-400">{row.level}</td>
                            <td className="text-right px-2 text-emerald-300 font-mono">{row.green_new_high_pct}%</td>
                            <td className="text-right px-2 text-rose-300 font-mono">{row.green_new_low_pct}%</td>
                            <td className="text-right px-2 text-emerald-300 font-mono">{row.red_new_high_pct}%</td>
                            <td className="text-right px-2 text-rose-300 font-mono">{row.red_new_low_pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-[10px] text-slate-500 mt-1">
                      Compare these values against the WIN/LOSS/Profitability table in your TradingView chart.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Timeframe filter row */}
          <div className="flex flex-wrap gap-2 mb-4" data-testid="strategy-tf-filter-row">
            {['all', '5s', '15s', '30s', '1m', '2m', '3m', '5m'].map(tf => (
              <Button
                key={tf}
                size="sm"
                variant={strategyTfFilter === tf ? 'default' : 'outline'}
                className={strategyTfFilter === tf
                  ? 'bg-purple-600 hover:bg-purple-700 h-7 text-xs'
                  : 'border-slate-600 text-slate-400 h-7 text-xs'}
                onClick={() => setStrategyTfFilter(tf)}
                data-testid={`strategy-tf-filter-${tf}`}
              >
                {tf === 'all' ? '🌐 All' : tf}
              </Button>
            ))}
          </div>

          {strategies.length === 0 ? (
            <div className="text-slate-400 text-sm py-6 text-center">
              Loading strategies from the backend registry…
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 max-h-[520px] overflow-y-auto pr-1" data-testid="strategy-grid">
              {strategies
                .filter(s => strategyTfFilter === 'all' || (s.timeframes || []).includes(strategyTfFilter))
                .map(strategy => (
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
                  {strategy.description && (
                    <div className="text-xs text-slate-400 mt-1 line-clamp-2">{strategy.description}</div>
                  )}
                  <div className="flex flex-wrap items-center gap-1 mt-2">
                    {(strategy.timeframes || []).slice(0, 5).map(tf => (
                      <span key={tf} className="text-[10px] bg-slate-700 px-1.5 py-0.5 rounded">{tf}</span>
                    ))}
                    {strategy.win_rate !== undefined && strategy.win_rate !== null && (() => {
                      const raw = strategy.win_rate;
                      let display = null;
                      if (typeof raw === 'number') {
                        display = `${Math.round(raw > 1 ? raw : raw * 100)}%`;
                      } else if (typeof raw === 'string') {
                        const m = raw.match(/(\d+(?:\.\d+)?)/);
                        if (m) display = `${Math.round(parseFloat(m[1]))}%`;
                      }
                      return display ? (
                        <span className="text-[10px] bg-emerald-900/60 text-emerald-300 px-1.5 py-0.5 rounded ml-auto">
                          WR {display}
                        </span>
                      ) : null;
                    })()}
                    {strategy.beta && (
                      <span className="text-[10px] bg-amber-900/60 text-amber-300 px-1.5 py-0.5 rounded">
                        BETA
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Button Logic Guide — live version */}
      <Card className="bg-slate-800/50 border-slate-700" data-testid="tm-button-guide-card">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between flex-wrap gap-2">
            <span>📖 Tampermonkey Button Guide</span>
            <Badge className="bg-purple-600 text-white font-mono" data-testid="tm-guide-version-badge">
              v{scriptVersion}
            </Badge>
          </CardTitle>
          <CardDescription>Every button in the userscript UI, grouped exactly as they appear on the panel.</CardDescription>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-3">
          {/* Master toggle */}
          <div className="space-y-2">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Master</h4>
            <div className="bg-emerald-900/30 border border-emerald-600 rounded p-3">
              <strong className="text-emerald-400">🟢 TAP TO GO LIVE</strong> — one-tap master switch
              <p className="text-xs mt-1 text-emerald-200">Enables SCAN · AUTO · APP · CYCLE all at once. Tap again to shut every mode off.</p>
            </div>
          </div>

          {/* Primary Controls — SCAN / AUTO / GO */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Primary Controls</h4>
            <div className="bg-pink-900/30 border border-pink-600 rounded p-3">
              <strong className="text-pink-400">🔍 SCAN</strong> — Local signal generation
              <p className="text-xs mt-1 text-pink-200">Scans markets on-device using live Pocket Option prices (RSI · EMA · Stochastic · MACD · BB · ADX + ensemble). 30 s cooldown between trades.</p>
            </div>
            <div className="bg-green-900/30 border border-green-600 rounded p-3">
              <strong className="text-green-400">📡 AUTO</strong> — Automatic trade execution
              <p className="text-xs mt-1 text-green-200">When a signal arrives (from any source below), AUTO clicks CALL/PUT with the correct expiry. Turn off to review manually before firing.</p>
            </div>
            <div className="bg-yellow-900/30 border border-yellow-600 rounded p-3">
              <strong className="text-yellow-400">⚡ GO</strong> — Force-generate now
              <p className="text-xs mt-1 text-yellow-200">Tries local signal engines first for the current asset, falls back to the backend `/signals/force-generate` for a fresh AI signal.</p>
            </div>
          </div>

          {/* Secondary row — SNS / A-INV / INVERT */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Inversion Row</h4>
            <div className="bg-fuchsia-900/30 border border-fuchsia-600 rounded p-3">
              <strong className="text-fuchsia-400">🎯 SNS</strong> — Seconds-Number Strategy
              <p className="text-xs mt-1 text-fuchsia-200">Fires an opposite-direction 5 s trade at a configurable second of every 1 m candle (dip-scalp).</p>
            </div>
            <div className="bg-orange-900/30 border border-orange-600 rounded p-3">
              <strong className="text-orange-400">🔁 A-INV</strong> — Auto-Invert on N losses
              <p className="text-xs mt-1 text-orange-200">Watches the loss streak. When it hits the threshold (default 2), it flips CALL↔PUT automatically until a win. Includes momentum-check gate + built-in Diagnostic / Self-Test buttons.</p>
            </div>
            <div className="bg-red-900/30 border border-red-600 rounded p-3">
              <strong className="text-red-400">🔄 INVERT</strong> — Manual global flip
              <p className="text-xs mt-1 text-red-200">Hard-flip every signal CALL↔PUT until you toggle it off. Overrides both the app inversion switch and A-INV.</p>
            </div>
          </div>

          {/* Tertiary — CYCLE / APP */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Multi-Asset / Signal Source</h4>
            <div className="bg-cyan-900/30 border border-cyan-600 rounded p-3">
              <strong className="text-cyan-400">🔁 CYCLE</strong> — Rotate favorites, trade the best
              <p className="text-xs mt-1 text-cyan-200">Clicks through every favorite asset, dwells 30 s scanning each, trades the highest-payout signal, moves to the next.</p>
            </div>
            <div className="bg-indigo-900/30 border border-indigo-600 rounded p-3">
              <strong className="text-indigo-400">📱 APP</strong> — Follow app signals
              <p className="text-xs mt-1 text-indigo-200">Polls `/api/signals/latest` and auto-executes anything the app publishes (respects abstain gates like ADX regime, HA confluence, latency).</p>
            </div>
          </div>

          {/* Money management */}
          <div className="space-y-2 mt-4">
            <h4 className="text-white font-semibold text-xs uppercase tracking-wide">Money Management</h4>
            <div className="bg-slate-900 border border-slate-700 rounded p-3">
              <div className="text-slate-200 text-xs"><strong className="text-slate-100">MM $</strong> — base amount tracked internally (set the actual trade amount inside Pocket Option's UI).</div>
              <div className="text-slate-200 text-xs mt-1"><strong className="text-slate-100">Step</strong> — current martingale rung.</div>
              <div className="text-slate-200 text-xs mt-1"><strong className="text-emerald-300">WIN</strong> / <strong className="text-red-300">LOSS</strong> — manually record a result if auto-detection missed the balance change.</div>
            </div>
          </div>

          {/* Recommended Setups */}
          <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-600 rounded p-3 mt-4">
            <strong className="text-white">Recommended Setups:</strong>
            <ul className="text-xs mt-2 space-y-1.5">
              <li className="flex items-center gap-2">
                <span className="bg-green-600 text-white px-2 py-0.5 rounded text-xs">Elite</span>
                <span><strong>APP</strong> + <strong>A-INV</strong> + AI Gates on (dashboard) = hands-off, gated app signals with loss-streak safety</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-emerald-600 text-white px-2 py-0.5 rounded text-xs">Best</span>
                <span><strong>CYCLE</strong> + <strong>A-INV</strong> = fully automated multi-asset rotation with smart inversion</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-blue-600 text-white px-2 py-0.5 rounded text-xs">Good</span>
                <span><strong>SCAN</strong> + <strong>AUTO</strong> = single asset, local engine, auto-fire</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="bg-slate-600 text-white px-2 py-0.5 rounded text-xs">Manual</span>
                <span><strong>GO</strong> only = on-demand signal, review before every trade</span>
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

      {/* Script Info — live version */}
      <Card className="bg-slate-800/50 border-slate-700" data-testid="tm-script-info-card">
        <CardHeader>
          <CardTitle className="text-white flex items-center justify-between flex-wrap gap-2">
            <span>📄 Script Information</span>
            <Badge className="bg-purple-600 text-white font-mono" data-testid="tm-info-version-badge">
              v{scriptVersion}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-slate-300 text-sm space-y-2">
          <div className="flex justify-between">
            <span>Script Version:</span>
            <span className="text-purple-400 font-mono" data-testid="tm-info-version-value">v{scriptVersion}</span>
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
            <span className="text-purple-400">
              {strategies.find(s => s.id === settings.selected_strategy)?.name || settings.selected_strategy || 'Auto'}
            </span>
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
          
          {/* Features List — live */}
          <div className="mt-4 p-3 bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-lg border border-purple-500/30" data-testid="tm-features-list">
            <p className="text-xs text-purple-300 font-semibold mb-2">v{scriptVersion} Features:</p>
            {scriptFeatures.length === 0 ? (
              <p className="text-xs text-slate-400">Loading feature list from backend…</p>
            ) : (
              <ul className="text-xs text-slate-400 space-y-1">
                {scriptFeatures.map((f, i) => (
                  <li key={i}>✅ {f}</li>
                ))}
              </ul>
            )}
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
