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
  // Forex OTC
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
  // Forex Regular
  { value: 'EURUSD_regular', label: 'EUR/USD (Regular)', category: 'Forex Regular' },
  { value: 'GBPUSD_regular', label: 'GBP/USD (Regular)', category: 'Forex Regular' },
  { value: 'USDJPY_regular', label: 'USD/JPY (Regular)', category: 'Forex Regular' },
  { value: 'AUDUSD_regular', label: 'AUD/USD (Regular)', category: 'Forex Regular' },
  // Crypto OTC
  { value: 'BTCUSD_otc', label: 'BTC/USD (OTC)', category: 'Crypto OTC' },
  { value: 'ETHUSD_otc', label: 'ETH/USD (OTC)', category: 'Crypto OTC' },
  { value: 'LTCUSD_otc', label: 'LTC/USD (OTC)', category: 'Crypto OTC' },
  // Indices
  { value: 'US100_otc', label: 'US100 (OTC)', category: 'Indices' },
  { value: 'US500_otc', label: 'US500 (OTC)', category: 'Indices' },
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
        <TabsList className="grid w-full grid-cols-4 bg-slate-800/50 max-w-2xl">
          <TabsTrigger value="general" className="data-[state=active]:bg-purple-600">
            ⚙️ General
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
