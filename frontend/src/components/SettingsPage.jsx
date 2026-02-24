import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : '/api';

// All available timeframes
const ALL_TIMEFRAMES = [
  { value: '5s', label: '5 Seconds' },
  { value: '10s', label: '10 Seconds' },
  { value: '15s', label: '15 Seconds' },
  { value: '30s', label: '30 Seconds' },
  { value: '1m', label: '1 Minute' },
  { value: '2m', label: '2 Minutes' },
  { value: '3m', label: '3 Minutes' },
  { value: '5m', label: '5 Minutes' },
  { value: '10m', label: '10 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '30m', label: '30 Minutes' },
  { value: '1h', label: '1 Hour' },
];

// All available assets
const ALL_ASSETS = [
  // ==================== FOREX OTC ====================
  { value: 'EURUSD_otc', label: 'EUR/USD (OTC)', category: 'Forex OTC' },
  { value: 'GBPUSD_otc', label: 'GBP/USD (OTC)', category: 'Forex OTC' },
  { value: 'USDJPY_otc', label: 'USD/JPY (OTC)', category: 'Forex OTC' },
  { value: 'AUDUSD_otc', label: 'AUD/USD (OTC)', category: 'Forex OTC' },
  { value: 'USDCAD_otc', label: 'USD/CAD (OTC)', category: 'Forex OTC' },
  { value: 'USDCHF_otc', label: 'USD/CHF (OTC)', category: 'Forex OTC' },
  { value: 'NZDUSD_otc', label: 'NZD/USD (OTC)', category: 'Forex OTC' },
  { value: 'EURGBP_otc', label: 'EUR/GBP (OTC)', category: 'Forex OTC' },
  { value: 'EURJPY_otc', label: 'EUR/JPY (OTC)', category: 'Forex OTC' },
  { value: 'GBPJPY_otc', label: 'GBP/JPY (OTC)', category: 'Forex OTC' },
  { value: 'AUDCAD_otc', label: 'AUD/CAD (OTC)', category: 'Forex OTC' },
  { value: 'AUDJPY_otc', label: 'AUD/JPY (OTC)', category: 'Forex OTC' },
  { value: 'AUDNZD_otc', label: 'AUD/NZD (OTC)', category: 'Forex OTC' },
  { value: 'CADJPY_otc', label: 'CAD/JPY (OTC)', category: 'Forex OTC' },
  { value: 'CHFJPY_otc', label: 'CHF/JPY (OTC)', category: 'Forex OTC' },
  { value: 'EURAUD_otc', label: 'EUR/AUD (OTC)', category: 'Forex OTC' },
  { value: 'EURCAD_otc', label: 'EUR/CAD (OTC)', category: 'Forex OTC' },
  { value: 'EURCHF_otc', label: 'EUR/CHF (OTC)', category: 'Forex OTC' },
  { value: 'EURNZD_otc', label: 'EUR/NZD (OTC)', category: 'Forex OTC' },
  { value: 'GBPAUD_otc', label: 'GBP/AUD (OTC)', category: 'Forex OTC' },
  { value: 'GBPCAD_otc', label: 'GBP/CAD (OTC)', category: 'Forex OTC' },
  { value: 'GBPCHF_otc', label: 'GBP/CHF (OTC)', category: 'Forex OTC' },
  { value: 'GBPNZD_otc', label: 'GBP/NZD (OTC)', category: 'Forex OTC' },
  { value: 'NZDCAD_otc', label: 'NZD/CAD (OTC)', category: 'Forex OTC' },
  { value: 'NZDJPY_otc', label: 'NZD/JPY (OTC)', category: 'Forex OTC' },
  // ==================== FOREX REGULAR ====================
  { value: 'EURUSD', label: 'EUR/USD', category: 'Forex Regular' },
  { value: 'GBPUSD', label: 'GBP/USD', category: 'Forex Regular' },
  { value: 'USDJPY', label: 'USD/JPY', category: 'Forex Regular' },
  { value: 'AUDUSD', label: 'AUD/USD', category: 'Forex Regular' },
  { value: 'USDCAD', label: 'USD/CAD', category: 'Forex Regular' },
  { value: 'USDCHF', label: 'USD/CHF', category: 'Forex Regular' },
  { value: 'NZDUSD', label: 'NZD/USD', category: 'Forex Regular' },
  { value: 'EURGBP', label: 'EUR/GBP', category: 'Forex Regular' },
  { value: 'EURJPY', label: 'EUR/JPY', category: 'Forex Regular' },
  { value: 'GBPJPY', label: 'GBP/JPY', category: 'Forex Regular' },
  { value: 'AUDCAD', label: 'AUD/CAD', category: 'Forex Regular' },
  { value: 'AUDJPY', label: 'AUD/JPY', category: 'Forex Regular' },
  { value: 'CADJPY', label: 'CAD/JPY', category: 'Forex Regular' },
  { value: 'CHFJPY', label: 'CHF/JPY', category: 'Forex Regular' },
  { value: 'EURAUD', label: 'EUR/AUD', category: 'Forex Regular' },
  { value: 'EURCAD', label: 'EUR/CAD', category: 'Forex Regular' },
  { value: 'EURCHF', label: 'EUR/CHF', category: 'Forex Regular' },
  { value: 'GBPAUD', label: 'GBP/AUD', category: 'Forex Regular' },
  { value: 'GBPCAD', label: 'GBP/CAD', category: 'Forex Regular' },
  { value: 'GBPCHF', label: 'GBP/CHF', category: 'Forex Regular' },
  // ==================== CRYPTO OTC ====================
  { value: 'BTCUSD_otc', label: 'BTC/USD (OTC)', category: 'Crypto OTC' },
  { value: 'ETHUSD_otc', label: 'ETH/USD (OTC)', category: 'Crypto OTC' },
  { value: 'LTCUSD_otc', label: 'LTC/USD (OTC)', category: 'Crypto OTC' },
  { value: 'XRPUSD_otc', label: 'XRP/USD (OTC)', category: 'Crypto OTC' },
  { value: 'BNBUSD_otc', label: 'BNB/USD (OTC)', category: 'Crypto OTC' },
  { value: 'ADAUSD_otc', label: 'ADA/USD (OTC)', category: 'Crypto OTC' },
  { value: 'DOGUSD_otc', label: 'DOGE/USD (OTC)', category: 'Crypto OTC' },
  { value: 'SOLUSD_otc', label: 'SOL/USD (OTC)', category: 'Crypto OTC' },
  { value: 'DOTUSD_otc', label: 'DOT/USD (OTC)', category: 'Crypto OTC' },
  { value: 'MATUSD_otc', label: 'MATIC/USD (OTC)', category: 'Crypto OTC' },
  // ==================== CRYPTO REGULAR ====================
  { value: 'BTCUSD', label: 'BTC/USD', category: 'Crypto Regular' },
  { value: 'ETHUSD', label: 'ETH/USD', category: 'Crypto Regular' },
  { value: 'LTCUSD', label: 'LTC/USD', category: 'Crypto Regular' },
  { value: 'XRPUSD', label: 'XRP/USD', category: 'Crypto Regular' },
  { value: 'BNBUSD', label: 'BNB/USD', category: 'Crypto Regular' },
  // ==================== INDICES OTC ====================
  { value: 'US100_otc', label: 'US100/NASDAQ (OTC)', category: 'Indices OTC' },
  { value: 'US500_otc', label: 'US500/S&P500 (OTC)', category: 'Indices OTC' },
  { value: 'US30_otc', label: 'US30/Dow Jones (OTC)', category: 'Indices OTC' },
  { value: 'DE30_otc', label: 'DE30/DAX (OTC)', category: 'Indices OTC' },
  { value: 'UK100_otc', label: 'UK100/FTSE (OTC)', category: 'Indices OTC' },
  { value: 'JP225_otc', label: 'JP225/Nikkei (OTC)', category: 'Indices OTC' },
  { value: 'AU200_otc', label: 'AU200/ASX (OTC)', category: 'Indices OTC' },
  { value: 'FR40_otc', label: 'FR40/CAC (OTC)', category: 'Indices OTC' },
  // ==================== INDICES REGULAR ====================
  { value: 'US100', label: 'US100/NASDAQ', category: 'Indices Regular' },
  { value: 'US500', label: 'US500/S&P500', category: 'Indices Regular' },
  { value: 'US30', label: 'US30/Dow Jones', category: 'Indices Regular' },
  { value: 'DE30', label: 'DE30/DAX', category: 'Indices Regular' },
  { value: 'UK100', label: 'UK100/FTSE', category: 'Indices Regular' },
  // ==================== COMMODITIES OTC ====================
  { value: 'XAUUSD_otc', label: 'Gold/XAU (OTC)', category: 'Commodities OTC' },
  { value: 'XAGUSD_otc', label: 'Silver/XAG (OTC)', category: 'Commodities OTC' },
  { value: 'WTIUSD_otc', label: 'Oil/WTI (OTC)', category: 'Commodities OTC' },
  { value: 'BRNUSD_otc', label: 'Brent Oil (OTC)', category: 'Commodities OTC' },
  { value: 'NATGAS_otc', label: 'Natural Gas (OTC)', category: 'Commodities OTC' },
  // ==================== COMMODITIES REGULAR ====================
  { value: 'XAUUSD', label: 'Gold/XAU', category: 'Commodities Regular' },
  { value: 'XAGUSD', label: 'Silver/XAG', category: 'Commodities Regular' },
  { value: 'WTIUSD', label: 'Oil/WTI', category: 'Commodities Regular' },
  // ==================== STOCKS OTC ====================
  { value: 'AAPL_otc', label: 'Apple (OTC)', category: 'Stocks OTC' },
  { value: 'MSFT_otc', label: 'Microsoft (OTC)', category: 'Stocks OTC' },
  { value: 'GOOGL_otc', label: 'Google (OTC)', category: 'Stocks OTC' },
  { value: 'AMZN_otc', label: 'Amazon (OTC)', category: 'Stocks OTC' },
  { value: 'TSLA_otc', label: 'Tesla (OTC)', category: 'Stocks OTC' },
  { value: 'META_otc', label: 'Meta (OTC)', category: 'Stocks OTC' },
  { value: 'NVDA_otc', label: 'NVIDIA (OTC)', category: 'Stocks OTC' },
  { value: 'NFLX_otc', label: 'Netflix (OTC)', category: 'Stocks OTC' },
];

// Available strategies
const ALL_STRATEGIES = [
  { value: 'rsi_oversold_overbought', label: 'RSI Oversold/Overbought', description: 'Classic RSI reversal strategy' },
  { value: 'ema_crossover', label: 'EMA Crossover', description: 'Trend-following with EMA' },
  { value: 'bollinger_bands', label: 'Bollinger Bands', description: 'Volatility breakout strategy' },
  { value: 'macd_signal', label: 'MACD Signal', description: 'MACD crossover signals' },
  { value: 'stochastic', label: 'Stochastic', description: 'Stochastic oscillator reversals' },
  { value: 'supertrend', label: 'SuperTrend', description: 'Trend direction with SuperTrend' },
  { value: 'triple_confluence', label: 'Triple Confluence', description: 'Multiple indicator confirmation' },
  { value: 'vwap_momentum', label: 'VWAP Momentum', description: 'Volume-weighted momentum' },
  { value: 'williams_adx', label: 'Williams %R + ADX', description: 'Williams with trend strength' },
  { value: 'ai_ensemble', label: 'AI Ensemble', description: 'AI-powered multi-strategy' },
];

// Latency Settings Component
const LatencySettings = () => {
  const [latencyStatus, setLatencyStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [manualOffset, setManualOffset] = useState(0);

  useEffect(() => {
    fetchLatencyStatus();
  }, []);

  const fetchLatencyStatus = async () => {
    setIsLoading(true);
    try {
      const response = await axios.get(`${API}/latency/status`);
      setLatencyStatus(response.data);
      setManualOffset(response.data?.manual_offset || 0);
    } catch (error) {
      console.error('Failed to fetch latency status');
    } finally {
      setIsLoading(false);
    }
  };

  const setMode = async (mode) => {
    try {
      await axios.post(`${API}/latency/set-mode`, { mode });
      toast.success(`Latency mode set to ${mode.toUpperCase()}`);
      fetchLatencyStatus();
    } catch (error) {
      toast.error('Failed to set latency mode');
    }
  };

  const applyManualOffset = async () => {
    try {
      await axios.post(`${API}/latency/set-manual-offset`, { offset_seconds: manualOffset });
      toast.success(`Manual offset set to ${manualOffset}s`);
      fetchLatencyStatus();
    } catch (error) {
      toast.error('Failed to set manual offset');
    }
  };

  const resetLatency = async () => {
    try {
      await axios.post(`${API}/latency/reset`);
      toast.success('Latency settings reset to defaults');
      setManualOffset(0);
      fetchLatencyStatus();
    } catch (error) {
      toast.error('Failed to reset latency settings');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Mode Selection */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white text-lg">⏱️ Latency Correction Mode</CardTitle>
          <CardDescription>
            Control how signal timing is adjusted to account for network delays
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3">
            <Button
              variant="outline"
              onClick={() => setMode('auto')}
              className={latencyStatus?.mode === 'auto' 
                ? 'bg-green-600 border-green-600 text-white justify-start' 
                : 'bg-slate-800 border-slate-600 text-slate-300 justify-start'}
            >
              <span className="mr-2">🤖</span>
              AUTO (Recommended)
              {latencyStatus?.mode === 'auto' && <Badge className="ml-auto bg-green-500">Active</Badge>}
            </Button>
            <p className="text-xs text-slate-400 ml-8">
              System automatically learns from trade results and adjusts timing
            </p>

            <Button
              variant="outline"
              onClick={() => setMode('manual')}
              className={latencyStatus?.mode === 'manual' 
                ? 'bg-blue-600 border-blue-600 text-white justify-start' 
                : 'bg-slate-800 border-slate-600 text-slate-300 justify-start'}
            >
              <span className="mr-2">🎛️</span>
              MANUAL
              {latencyStatus?.mode === 'manual' && <Badge className="ml-auto bg-blue-500">Active</Badge>}
            </Button>
            <p className="text-xs text-slate-400 ml-8">
              Set a fixed timing offset for fine-tuning
            </p>

            <Button
              variant="outline"
              onClick={() => setMode('disabled')}
              className={latencyStatus?.mode === 'disabled' 
                ? 'bg-red-600 border-red-600 text-white justify-start' 
                : 'bg-slate-800 border-slate-600 text-slate-300 justify-start'}
            >
              <span className="mr-2">⛔</span>
              DISABLED
              {latencyStatus?.mode === 'disabled' && <Badge className="ml-auto bg-red-500">Active</Badge>}
            </Button>
            <p className="text-xs text-slate-400 ml-8">
              No latency correction applied
            </p>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <Button variant="outline" size="sm" onClick={resetLatency} className="text-orange-400 border-orange-400 hover:bg-orange-400/20">
              🔄 Reset to Defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Manual Offset Control */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white text-lg">🎚️ Manual Offset Control</CardTitle>
          <CardDescription>
            Fine-tune signal timing when using MANUAL mode
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Offset (seconds): {manualOffset}s</Label>
            <input 
              type="range"
              min="-5"
              max="5"
              step="0.5"
              value={manualOffset}
              onChange={(e) => setManualOffset(parseFloat(e.target.value))}
              className="w-full accent-purple-500"
            />
            <div className="flex justify-between text-xs text-slate-400">
              <span>Earlier (-5s)</span>
              <span>Neutral (0s)</span>
              <span>Later (+5s)</span>
            </div>
          </div>
          
          <div className="text-sm text-slate-300 bg-slate-800 p-3 rounded-lg">
            <p className="font-medium mb-1">Offset Guide:</p>
            <ul className="text-xs text-slate-400 space-y-1">
              <li>• <strong>Negative (-)</strong>: Signals arrive earlier (more lead time)</li>
              <li>• <strong>Positive (+)</strong>: Signals arrive later (wait longer)</li>
              <li>• If missing trades, try negative offset</li>
              <li>• If entering too early, try positive offset</li>
            </ul>
          </div>

          <Button 
            onClick={applyManualOffset} 
            className="w-full bg-purple-600 hover:bg-purple-700"
            disabled={latencyStatus?.mode !== 'manual'}
          >
            Apply Manual Offset
          </Button>
          {latencyStatus?.mode !== 'manual' && (
            <p className="text-xs text-orange-400 text-center">
              Switch to MANUAL mode to use custom offset
            </p>
          )}
        </CardContent>
      </Card>

      {/* Effective Buffers */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white text-lg">📊 Effective Timing Buffers</CardTitle>
          <CardDescription>
            How early signals arrive for each timeframe
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {latencyStatus?.effective_buffers && Object.entries(latencyStatus.effective_buffers).map(([tf, buffer]) => (
              <div key={tf} className="flex items-center justify-between bg-slate-800 p-3 rounded-lg">
                <span className="text-white font-medium">{tf}</span>
                <div className="flex items-center gap-2">
                  <span className="text-purple-400 font-mono">{buffer.toFixed(1)}s early</span>
                  <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-purple-500" 
                      style={{ width: `${Math.min(buffer / 5 * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          {latencyStatus?.mode === 'auto' && (
            <div className="mt-4 p-3 bg-green-900/20 border border-green-700 rounded-lg">
              <p className="text-green-400 text-sm">
                <span className="font-bold">🤖 Auto-correction active:</span>{' '}
                {latencyStatus?.auto_correction_offset?.toFixed(2)}s offset learned
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Accuracy Stats */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white text-lg">📈 Timing Accuracy</CardTitle>
          <CardDescription>
            Per-timeframe timing performance
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {latencyStatus?.timeframe_accuracy && Object.entries(latencyStatus.timeframe_accuracy).map(([tf, stats]) => {
              const total = stats.wins + stats.losses;
              const winRate = total > 0 ? (stats.wins / total * 100) : 0;
              return (
                <div key={tf} className="bg-slate-800 p-3 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium">{tf}</span>
                    <span className={`font-bold ${winRate >= 60 ? 'text-green-400' : winRate >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {total > 0 ? `${winRate.toFixed(0)}%` : 'N/A'}
                    </span>
                  </div>
                  <div className="flex gap-4 text-xs text-slate-400">
                    <span>✅ {stats.wins} wins</span>
                    <span>❌ {stats.losses} losses</span>
                    <span>⏰ {stats.early_errors} early</span>
                    <span>⏳ {stats.late_errors} late</span>
                  </div>
                </div>
              );
            })}
          </div>
          {Object.values(latencyStatus?.timeframe_accuracy || {}).every(s => s.wins === 0 && s.losses === 0) && (
            <p className="text-center text-slate-400 text-sm mt-4">
              No timing data yet. Trade to build accuracy stats.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const SettingsPage = () => {
  const [activeTab, setActiveTab] = useState('general');
  const [settings, setSettings] = useState({
    // General settings
    defaultTimeframe: '1m',
    defaultAsset: 'EURUSD_otc',
    selectedTimeframes: ['1m', '5m'],
    selectedAssets: ['EURUSD_otc', 'GBPUSD_otc'],
    soundEnabled: true,
    notificationsEnabled: true,
    
    // Signal settings
    minimumConfidence: 70,
    signalCooldown: 30,
    
    // Strategy settings per timeframe
    strategySettings: {
      '5s': ['triple_confluence'],
      '15s': ['triple_confluence', 'ema_crossover'],
      '30s': ['vwap_momentum', 'williams_adx'],
      '1m': ['rsi_oversold_overbought', 'macd_signal', 'bollinger_bands'],
      '5m': ['supertrend', 'ema_crossover'],
    },
    
    // Telegram
    telegramBotToken: '',
    telegramChatId: '',
  });
  
  const [integrationStatus, setIntegrationStatus] = useState({
    telegram: false,
  });
  
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  useEffect(() => {
    fetchSettings();
    checkIntegrations();
  }, []);

  const fetchSettings = async () => {
    setIsFetching(true);
    try {
      const response = await axios.get(`${API}/settings`);
      if (response.data) {
        setSettings(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.log('Using default settings');
    } finally {
      setIsFetching(false);
    }
  };

  const checkIntegrations = async () => {
    try {
      const telegramRes = await axios.get(`${API}/telegram-bot/status`);
      setIntegrationStatus(prev => ({
        ...prev,
        telegram: telegramRes.data?.status?.bot_token_configured || false
      }));
      
      // Check 3Commas status
      const tcRes = await axios.get(`${API}/3commas/status`);
      if (tcRes.data?.config) {
        setSettings(prev => ({
          ...prev,
          threeCommasEnabled: tcRes.data.config.enabled || false,
          threeCommasSecret: '', // Don't show secret
          threeCommasBotUuid: tcRes.data.config.bot_uuid || '',
          threeCommasExchange: tcRes.data.config.tv_exchange || 'BINANCE',
          threeCommasMaxLag: tcRes.data.config.max_lag || '300'
        }));
      }
    } catch (error) {
      console.log('Could not check integrations');
    }
  };

  const saveSettings = async () => {
    setIsLoading(true);
    try {
      // Save general settings
      const response = await axios.post(`${API}/settings`, settings);
      
      // Save 3Commas config separately if configured
      if (settings.threeCommasSecret || settings.threeCommasBotUuid) {
        await axios.post(`${API}/3commas/config`, {
          secret: settings.threeCommasSecret,
          bot_uuid: settings.threeCommasBotUuid,
          tv_exchange: settings.threeCommasExchange || 'BINANCE',
          max_lag: settings.threeCommasMaxLag || '300',
          enabled: settings.threeCommasEnabled || false
        });
      }
      
      if (response.data?.success) {
        toast.success('Settings saved successfully!');
      } else {
        toast.error('Failed to save settings');
      }
    } catch (error) {
      console.error('Save settings error:', error);
      toast.error('Failed to save settings: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsLoading(false);
    }
  };

  const testTelegram = async () => {
    try {
      const response = await axios.post(`${API}/telegram-bot/send`, {
        message: '🧪 Test message from GPT Signal Bot settings!'
      });
      if (response.data?.success) {
        toast.success('Test message sent to Telegram!');
      } else {
        toast.error('Failed to send test message');
      }
    } catch (error) {
      toast.error('Telegram test failed');
    }
  };

  const toggleTimeframe = (tf) => {
    setSettings(prev => ({
      ...prev,
      selectedTimeframes: prev.selectedTimeframes.includes(tf)
        ? prev.selectedTimeframes.filter(t => t !== tf)
        : [...prev.selectedTimeframes, tf]
    }));
  };

  const toggleAsset = (asset) => {
    setSettings(prev => ({
      ...prev,
      selectedAssets: prev.selectedAssets.includes(asset)
        ? prev.selectedAssets.filter(a => a !== asset)
        : [...prev.selectedAssets, asset]
    }));
  };

  const toggleStrategy = (timeframe, strategy) => {
    setSettings(prev => {
      const currentStrategies = prev.strategySettings[timeframe] || [];
      const newStrategies = currentStrategies.includes(strategy)
        ? currentStrategies.filter(s => s !== strategy)
        : [...currentStrategies, strategy];
      
      return {
        ...prev,
        strategySettings: {
          ...prev.strategySettings,
          [timeframe]: newStrategies
        }
      };
    });
  };

  if (isFetching) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
          <p className="text-slate-400">Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">⚙️ Settings</h1>
          <p className="text-slate-400">Configure your trading bot preferences</p>
        </div>
        <Button 
          onClick={saveSettings} 
          disabled={isLoading}
          className="bg-purple-600 hover:bg-purple-700"
        >
          {isLoading ? 'Saving...' : '💾 Save Settings'}
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5 bg-slate-800/50 max-w-3xl">
          <TabsTrigger value="general" className="data-[state=active]:bg-purple-600">
            ⚙️ General
          </TabsTrigger>
          <TabsTrigger value="latency" className="data-[state=active]:bg-purple-600">
            ⏱️ Latency
          </TabsTrigger>
          <TabsTrigger value="assets" className="data-[state=active]:bg-purple-600">
            📊 Assets
          </TabsTrigger>
          <TabsTrigger value="strategies" className="data-[state=active]:bg-purple-600">
            🎯 Strategies
          </TabsTrigger>
          <TabsTrigger value="integrations" className="data-[state=active]:bg-purple-600">
            🔌 Integrations
          </TabsTrigger>
        </TabsList>

        {/* General Settings */}
        <TabsContent value="general" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Default Trading Settings</CardTitle>
                <CardDescription>Configure default values for signal generation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Default Timeframe</Label>
                  <select 
                    className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
                    value={settings.defaultTimeframe}
                    onChange={(e) => setSettings({...settings, defaultTimeframe: e.target.value})}
                  >
                    {ALL_TIMEFRAMES.map(tf => (
                      <option key={tf.value} value={tf.value}>{tf.label}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Default Asset</Label>
                  <select 
                    className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
                    value={settings.defaultAsset}
                    onChange={(e) => setSettings({...settings, defaultAsset: e.target.value})}
                  >
                    {ALL_ASSETS.map(asset => (
                      <option key={asset.value} value={asset.value}>{asset.label}</option>
                    ))}
                  </select>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Signal Quality</CardTitle>
                <CardDescription>Set minimum thresholds for signals</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Minimum Confidence (%)</Label>
                  <div className="flex items-center gap-4">
                    <input 
                      type="range"
                      min="50"
                      max="95"
                      value={settings.minimumConfidence}
                      onChange={(e) => setSettings({...settings, minimumConfidence: parseInt(e.target.value)})}
                      className="flex-1 accent-purple-500"
                    />
                    <span className="text-purple-400 font-bold w-12">{settings.minimumConfidence}%</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Signal Cooldown (seconds)</Label>
                  <Input 
                    type="number"
                    min="10"
                    max="300"
                    value={settings.signalCooldown}
                    onChange={(e) => setSettings({...settings, signalCooldown: parseInt(e.target.value)})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Notifications</CardTitle>
                <CardDescription>Configure notification preferences</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Sound Alerts</Label>
                    <p className="text-xs text-slate-400">Play sound on new signals</p>
                  </div>
                  <Switch 
                    checked={settings.soundEnabled}
                    onCheckedChange={(checked) => setSettings({...settings, soundEnabled: checked})}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Browser Notifications</Label>
                    <p className="text-xs text-slate-400">Show desktop notifications</p>
                  </div>
                  <Switch 
                    checked={settings.notificationsEnabled}
                    onCheckedChange={(checked) => setSettings({...settings, notificationsEnabled: checked})}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Latency Correction Settings */}
        <TabsContent value="latency" className="mt-6">
          <LatencySettings />
        </TabsContent>

        {/* Assets & Timeframes */}
        <TabsContent value="assets" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">⏱️ Active Timeframes</CardTitle>
                <CardDescription>Select timeframes for signal generation</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-2">
                  {ALL_TIMEFRAMES.map(tf => (
                    <Button
                      key={tf.value}
                      variant="outline"
                      size="sm"
                      onClick={() => toggleTimeframe(tf.value)}
                      className={settings.selectedTimeframes?.includes(tf.value) 
                        ? 'bg-purple-600 border-purple-600 text-white' 
                        : 'bg-slate-800 border-slate-600 text-slate-300'}
                    >
                      {tf.label}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-slate-400 mt-4">
                  Selected: {settings.selectedTimeframes?.length || 0} timeframes
                </p>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">📊 Active Assets</CardTitle>
                <CardDescription>Select assets for signal generation</CardDescription>
              </CardHeader>
              <CardContent className="max-h-[400px] overflow-y-auto">
                {['Forex OTC', 'Forex Regular', 'Crypto OTC', 'Indices'].map(category => (
                  <div key={category} className="mb-4">
                    <Label className="text-purple-400 text-xs uppercase mb-2 block">{category}</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {ALL_ASSETS.filter(a => a.category === category).map(asset => (
                        <Button
                          key={asset.value}
                          variant="outline"
                          size="sm"
                          onClick={() => toggleAsset(asset.value)}
                          className={settings.selectedAssets?.includes(asset.value) 
                            ? 'bg-green-600 border-green-600 text-white text-xs' 
                            : 'bg-slate-800 border-slate-600 text-slate-300 text-xs'}
                        >
                          {asset.label.replace(` (${category.includes('OTC') ? 'OTC' : 'Regular'})`, '')}
                        </Button>
                      ))}
                    </div>
                  </div>
                ))}
                <p className="text-xs text-slate-400 mt-2">
                  Selected: {settings.selectedAssets?.length || 0} assets
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Strategy Selection */}
        <TabsContent value="strategies" className="mt-6">
          <Card className="bg-slate-900/50 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white text-lg">🎯 Strategy Selection by Timeframe</CardTitle>
              <CardDescription>Choose which strategies to use for each timeframe</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {ALL_TIMEFRAMES.filter(tf => settings.selectedTimeframes?.includes(tf.value)).map(tf => (
                  <div key={tf.value} className="p-4 bg-slate-800/50 rounded-lg">
                    <Label className="text-purple-400 font-medium mb-3 block">
                      ⏱️ {tf.label} Strategies
                    </Label>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                      {ALL_STRATEGIES.map(strategy => (
                        <Button
                          key={strategy.value}
                          variant="outline"
                          size="sm"
                          onClick={() => toggleStrategy(tf.value, strategy.value)}
                          className={settings.strategySettings?.[tf.value]?.includes(strategy.value)
                            ? 'bg-purple-600 border-purple-600 text-white text-xs'
                            : 'bg-slate-700 border-slate-600 text-slate-300 text-xs'}
                          title={strategy.description}
                        >
                          {strategy.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                ))}
                
                {(!settings.selectedTimeframes || settings.selectedTimeframes.length === 0) && (
                  <div className="text-center py-8 text-slate-400">
                    <p>No timeframes selected. Go to Assets tab to select timeframes first.</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Integrations */}
        <TabsContent value="integrations" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg flex items-center gap-2">
                  📱 Telegram Bot
                  <Badge className={integrationStatus.telegram ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                    {integrationStatus.telegram ? '✅ Connected' : '❌ Not Configured'}
                  </Badge>
                </CardTitle>
                <CardDescription>Send trading signals to Telegram</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Bot Token</Label>
                  <Input 
                    type="password"
                    placeholder="Enter Telegram bot token"
                    value={settings.telegramBotToken}
                    onChange={(e) => setSettings({...settings, telegramBotToken: e.target.value})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Chat ID</Label>
                  <Input 
                    type="text"
                    placeholder="Enter chat ID"
                    value={settings.telegramChatId}
                    onChange={(e) => setSettings({...settings, telegramChatId: e.target.value})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
                <Button onClick={testTelegram} variant="outline" className="w-full">
                  🧪 Send Test Message
                </Button>
              </CardContent>
            </Card>

            {/* 3Commas Integration */}
            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg flex items-center gap-2">
                  🤖 3Commas Signal Bot
                  <Badge className={settings.threeCommasEnabled ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}>
                    {settings.threeCommasEnabled ? '✅ Enabled' : '❌ Disabled'}
                  </Badge>
                </CardTitle>
                <CardDescription>Send signals to 3Commas trading bots</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <Label>Enable 3Commas</Label>
                    <p className="text-xs text-slate-400">Send signals to 3Commas webhook</p>
                  </div>
                  <Switch 
                    checked={settings.threeCommasEnabled || false}
                    onCheckedChange={(checked) => setSettings({...settings, threeCommasEnabled: checked})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Secret (JWT Token)</Label>
                  <Input 
                    type="password"
                    placeholder="eyJhbGciOiJIUzI1NiJ9..."
                    value={settings.threeCommasSecret || ''}
                    onChange={(e) => setSettings({...settings, threeCommasSecret: e.target.value})}
                    className="bg-slate-800 border-slate-600 font-mono text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Bot UUID</Label>
                  <Input 
                    type="text"
                    placeholder="30f00a77-616f-4013-9d36-55aa5dcbc101"
                    value={settings.threeCommasBotUuid || ''}
                    onChange={(e) => setSettings({...settings, threeCommasBotUuid: e.target.value})}
                    className="bg-slate-800 border-slate-600 font-mono text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Exchange</Label>
                  <select 
                    className="w-full p-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm"
                    value={settings.threeCommasExchange || 'BINANCE'}
                    onChange={(e) => setSettings({...settings, threeCommasExchange: e.target.value})}
                  >
                    <option value="BINANCE">Binance</option>
                    <option value="BYBIT">Bybit</option>
                    <option value="KUCOIN">KuCoin</option>
                    <option value="OKX">OKX</option>
                    <option value="BITGET">Bitget</option>
                    <option value="COINBASE">Coinbase</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Max Lag (seconds)</Label>
                  <Input 
                    type="number"
                    placeholder="300"
                    value={settings.threeCommasMaxLag || '300'}
                    onChange={(e) => setSettings({...settings, threeCommasMaxLag: e.target.value})}
                    className="bg-slate-800 border-slate-600"
                  />
                </div>
                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <p className="text-blue-400 text-xs">
                    💡 <strong>Tip:</strong> Get your Secret and Bot UUID from 3Commas Signal Bot settings.
                    Webhook URL: <code className="text-purple-400">https://api.3commas.io/signal_bots/webhooks</code>
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-900/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">📡 Data Sources</CardTitle>
                <CardDescription>Market data providers</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-green-400">✅</span>
                    <span className="text-green-400 font-medium">Real Market Data Active</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Using live data from multiple sources</p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-slate-300">Yahoo Finance</span>
                    <Badge className="bg-green-500/20 text-green-400">Active</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-slate-300">Alpha Vantage</span>
                    <Badge className="bg-yellow-500/20 text-yellow-400">Backup</Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SettingsPage;
